"""Synkron klient til broker og SG.DokSigner API."""

from __future__ import annotations

import base64
import logging
import time
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import UUID

import httpx

from configuration import (
    API_BASE_URL,
    CONNECT_TIMEOUT_SECONDS,
    DEFAULT_WORKFLOW_API_TYPE,
    READ_TIMEOUT_SECONDS,
    TOKEN_EXPIRY_BUFFER_SECONDS,
    TOKEN_URL,
)
from .credentials import OAuthCredentials, hent_oauth_credentials
from .exceptions import (
    SigneringsportalApiError,
    SigneringsportalAuthenticationError,
    SigneringsportalConnectionError,
    SigneringsportalResponseError,
    SigneringsportalValidationError,
)
from .models import ApiKlient, OpretSigneringsopgaveResultat, Signeringsstatus, UnderskriverStatus
from .validation import ALLOWED_RECIPIENT_TYPES, require_aware_datetime, require_pdf_bytes, require_text, require_uuid

logger = logging.getLogger(__name__)


class SigneringsportalClient:
    """Skjuler token, endpoints, Base64 og HTTP-fejl for processen."""

    def __init__(
        self,
        credentials: OAuthCredentials,
        *,
        token_url: str = TOKEN_URL,
        api_base_url: str = API_BASE_URL,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._credentials = credentials
        self._token_url = token_url.rstrip("/")
        self._api_base_url = api_base_url.rstrip("/")
        self._owns_http_client = http_client is None
        self._http = http_client or httpx.Client(
            timeout=httpx.Timeout(
                connect=CONNECT_TIMEOUT_SECONDS,
                read=READ_TIMEOUT_SECONDS,
                write=READ_TIMEOUT_SECONDS,
                pool=CONNECT_TIMEOUT_SECONDS,
            ),
            follow_redirects=False,
        )
        self._access_token: str | None = None
        self._token_expires_monotonic = 0.0

    @classmethod
    def from_automation_server(cls) -> SigneringsportalClient:
        return cls(hent_oauth_credentials())

    def __enter__(self) -> SigneringsportalClient:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_http_client:
            self._http.close()

    def test_forbindelse(self) -> dict[str, Any]:
        """
        Tester både OAuth-tokenet og adgang til Signeringsportalens API.

        Funktionen kalder GET /Adm/GetAllPending, fordi /Client kan kræve
        administrative rettigheder.

        Returnerer Signeringsportalens svar, normalt med:
        - currentUserId: API-brugerens UUID
        - pending: API-brugerens afventende workflows
        """
        data = self._request_json(
            "GET",
            "/Adm/GetAllPending",
        )

        if not isinstance(data, dict):
            raise SigneringsportalResponseError(
                "Forbindelsestesten returnerede ikke et JSON-objekt."
            )

        current_user_id = data.get("currentUserId")

        if current_user_id is None:
            raise SigneringsportalResponseError(
                "Forbindelsestesten lykkedes, men svaret mangler "
                "'currentUserId'."
            )

        validated_user_id = require_uuid(
            current_user_id,
            "GetAllPending.currentUserId",
        )

        pending = data.get("pending")

        if pending is not None and not isinstance(pending, list):
            raise SigneringsportalResponseError(
                "GetAllPending.pending forventedes at være en liste eller null."
            )

        logger.info(
            "Forbindelsen til Signeringsportalen virker. "
            "API-bruger-id=%s",
            validated_user_id,
        )

        return {
            "api_user_id": validated_user_id,
            "pending": pending or [],
        }

    def opret_signeringsopgave(
        self,
        *,
        navn: str,
        pdf_filer: Iterable[dict[str, Any]],
        underskrivere: Iterable[dict[str, Any]],
        udloeber: datetime | None = None,
        should_creator_sign: bool = False,
        is_structured: bool = False,
    ) -> OpretSigneringsopgaveResultat:
        """
        Opretter én signeringsopgave i Signeringsportalen.

        PDF-indhold skal gives som bytes.

        Signeringsportalen har i praksis returneret både:

            {"flowId": "..."}

        og Swagger beskriver:

            [{"flowId": "..."}]

        Funktionen accepterer derfor begge svarformater.
        """
        validated_name = require_text(
            navn,
            "navn",
        )

        if not isinstance(should_creator_sign, bool):
            raise SigneringsportalValidationError(
                "should_creator_sign skal være bool."
            )

        if not isinstance(is_structured, bool):
            raise SigneringsportalValidationError(
                "is_structured skal være bool."
            )

        uploads = [
            self._build_upload(
                item,
                index,
            )
            for index, item in enumerate(pdf_filer)
        ]

        signers = [
            self._build_signer(
                item,
                index,
            )
            for index, item in enumerate(underskrivere)
        ]

        if not uploads:
            raise SigneringsportalValidationError(
                "pdf_filer skal indeholde mindst én PDF."
            )

        if not signers and not should_creator_sign:
            raise SigneringsportalValidationError(
                "Der skal være mindst én underskriver, "
                "når should_creator_sign er False."
            )

        payload: dict[str, Any] = {
            "uploads": uploads,
            "signers": signers,
            "name": validated_name,
            "shouldCreatorSign": should_creator_sign,
            "isStructured": is_structured,
            "expiryDate": None,
            "workflowApiType": DEFAULT_WORKFLOW_API_TYPE,
        }

        if udloeber is not None:
            validated_expiry = require_aware_datetime(
                udloeber,
                "udloeber",
            )

            payload["expiryDate"] = (
                validated_expiry
                .astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )

        data = self._request_json(
            "POST",
            "/Adm/CreateDocument",
            json=payload,
        )

        # Det virkelige API har returneret et enkelt objekt:
        #
        # {
        #     "flowId": "..."
        # }
        #
        # Swagger beskriver derimod en liste med objekter.
        # Vi understøtter derfor begge formater.

        if isinstance(data, dict):
            create_document_response = data

        elif isinstance(data, list):
            if len(data) != 1:
                raise SigneringsportalResponseError(
                    "CreateDocument returnerede en liste, "
                    "men listen indeholdt ikke præcis ét resultat. "
                    f"Antal resultater: {len(data)}."
                )

            if not isinstance(data[0], dict):
                raise SigneringsportalResponseError(
                    "CreateDocument returnerede en liste, "
                    "men resultatet i listen var ikke et objekt."
                )

            create_document_response = data[0]

        else:
            raise SigneringsportalResponseError(
                "CreateDocument returnerede et uventet svarformat. "
                f"Modtaget datatype: {type(data).__name__}."
            )

        flow_id_value = create_document_response.get(
            "flowId"
        )

        flow_id = require_uuid(
            flow_id_value,
            "CreateDocument.flowId",
        )

        logger.info(
            "Signeringsopgave oprettet med flowId=%s",
            flow_id,
        )

        return OpretSigneringsopgaveResultat(
            flow_id=flow_id,
        )

    def hent_signeringsstatus(self, flow_id: str) -> Signeringsstatus:
        validated_flow_id = require_uuid(flow_id, "flow_id")
        data = self._request_json("GET", "/Adm/GetDetails", params={"flowId": validated_flow_id})
        if not isinstance(data, dict):
            raise SigneringsportalResponseError("GetDetails returnerede ikke et objekt.")
        workflow = data.get("workFlow")
        if not isinstance(workflow, dict):
            raise SigneringsportalResponseError("GetDetails mangler workFlow.")
        status = require_text(workflow.get("status"), "workFlow.status")
        sign_flows = workflow.get("signFlows") or []
        if not isinstance(sign_flows, list):
            raise SigneringsportalResponseError("workFlow.signFlows er ikke en liste.")
        parsed_signers = tuple(self._parse_signer_status(item) for item in sign_flows)
        return Signeringsstatus(
            flow_id=validated_flow_id,
            status=status,
            navn=workflow.get("name"),
            url=data.get("url"),
            udloeber=workflow.get("expiryDate"),
            underskrivere=parsed_signers,
            raw=data,
        )

    def hent_signeret_pdf(
        self,
        flow_id: str,
    ) -> bytes:
        """
        Henter den underskrevne PAdES-PDF og returnerer den som bytes.

        Signeringsportalen returnerer i praksis et JSON-objekt:

            {
                "pades": "JVBERi0xLj..."
            }

        Feltet "pades" indeholder PDF-dokumentet som Base64.

        Funktionen gemmer ikke dokumentet på disk. Den kaldende proces
        eller test bestemmer selv, om og hvor dokumentet skal gemmes.

        Args:
            flow_id:
                Workflowets id i Signeringsportalen.

        Returns:
            Den underskrevne PDF som bytes i memory.

        Raises:
            SigneringsportalValidationError:
                Hvis flow_id ikke er et gyldigt UUID.

            SigneringsportalResponseError:
                Hvis API-svaret har et ukendt format, mangler feltet
                "pades", indeholder ugyldig Base64 eller ikke kan
                dekodes til en PDF.
        """
        validated_flow_id = require_uuid(
            flow_id,
            "flow_id",
        )

        data = self._request_json(
            "GET",
            "/Adm/GetPades",
            params={
                "flowId": validated_flow_id,
            },
        )

        # Det faktiske svar fra Signeringsportalen:
        #
        # {
        #     "pades": "JVBERi0xLj..."
        # }
        if isinstance(data, dict):
            if "pades" not in data:
                raise SigneringsportalResponseError(
                    "GetPades returnerede et objekt, men objektet "
                    "manglede feltet 'pades'. "
                    f"Modtagne felter: {list(data.keys())}."
                )

            base64_value = data["pades"]

        # Swagger beskriver svaret som en enkelt string.
        # Denne mulighed bevares derfor som fallback.
        elif isinstance(data, str):
            base64_value = data

        # Understøt også en liste med præcis ét dokument.
        elif isinstance(data, list):
            if not data:
                raise SigneringsportalResponseError(
                    "GetPades returnerede en tom liste."
                )

            if len(data) != 1:
                raise SigneringsportalResponseError(
                    "GetPades returnerede flere dokumenter, "
                    "men hent_signeret_pdf() forventer præcis ét. "
                    f"Antal dokumenter: {len(data)}."
                )

            document_result = data[0]

            if isinstance(document_result, dict):
                if "pades" not in document_result:
                    raise SigneringsportalResponseError(
                        "GetPades returnerede en liste med et objekt, "
                        "men objektet manglede feltet 'pades'. "
                        f"Modtagne felter: "
                        f"{list(document_result.keys())}."
                    )

                base64_value = document_result["pades"]

            elif isinstance(document_result, str):
                base64_value = document_result

            else:
                raise SigneringsportalResponseError(
                    "GetPades returnerede en liste, men elementet "
                    "var hverken tekst eller et objekt med feltet "
                    "'pades'. "
                    f"Elementets datatype: "
                    f"{type(document_result).__name__}."
                )

        else:
            raise SigneringsportalResponseError(
                "GetPades returnerede et ukendt svarformat. "
                f"Modtaget datatype: {type(data).__name__}."
            )

        if not isinstance(base64_value, str):
            raise SigneringsportalResponseError(
                "Feltet 'pades' var ikke en Base64-streng. "
                f"Modtaget datatype: "
                f"{type(base64_value).__name__}."
            )

        base64_value = base64_value.strip()

        if not base64_value:
            raise SigneringsportalResponseError(
                "Feltet 'pades' var tomt."
            )

        # Understøt også et eventuelt data-URL-format:
        #
        # data:application/pdf;base64,JVBERi0xLj...
        data_url_prefix = "data:application/pdf;base64,"

        if base64_value.lower().startswith(
            data_url_prefix
        ):
            base64_value = base64_value[
                len(data_url_prefix):
            ]

        # Base64 kan være opdelt med mellemrum eller linjeskift.
        base64_value = "".join(
            base64_value.split()
        )

        try:
            pdf_bytes = base64.b64decode(
                base64_value,
                validate=True,
            )
        except (ValueError, TypeError) as error:
            raise SigneringsportalResponseError(
                "Feltet 'pades' indeholdt ikke gyldig Base64."
            ) from error

        if not pdf_bytes:
            raise SigneringsportalResponseError(
                "Den Base64-dekodede PDF var tom."
            )

        if not pdf_bytes.startswith(b"%PDF-"):
            raise SigneringsportalResponseError(
                "Feltet 'pades' kunne Base64-dekodes, "
                "men resultatet begyndte ikke med en PDF-header."
            )

        logger.info(
            "Underskrevet PDF hentet for flowId=%s, "
            "størrelse=%s bytes",
            validated_flow_id,
            len(pdf_bytes),
        )

        return pdf_bytes

    def send_paamindelse(self, flow_id: str, signer_id: str) -> None:
        self._request_no_content(
            "POST",
            "/Adm/SendMail",
            json={
                "workFlowId": require_uuid(flow_id, "flow_id"),
                "signerId": require_uuid(signer_id, "signer_id"),
            },
        )

    def slet_signeringsopgave(self, flow_id: str) -> None:
        validated_flow_id = require_uuid(flow_id, "flow_id")
        self._request_no_content("DELETE", f"/Adm/Delete/{validated_flow_id}")

    def kan_modtage_digital_post_cpr(self, cpr: str) -> bool:
        return self._request_bool("GET", f"/DigitalPost/cpr/{require_text(cpr, 'cpr')}")

    def kan_modtage_digital_post_cvr(self, cvr: str) -> bool:
        return self._request_bool("GET", f"/DigitalPost/cvr/{require_text(cvr, 'cvr')}")

    def hent_afventende_signeringsopgaver(self) -> dict[str, Any]:
        data = self._request_json("GET", "/Adm/GetAllPending")
        if not isinstance(data, dict):
            raise SigneringsportalResponseError("GetAllPending returnerede ikke et objekt.")
        return data

    def hent_underskrevne_signeringsopgaver(self) -> dict[str, Any]:
        data = self._request_json("GET", "/Adm/GetAllSigned")
        if not isinstance(data, dict):
            raise SigneringsportalResponseError("GetAllSigned returnerede ikke et objekt.")
        return data

    def hent_api_klienter(self) -> tuple[ApiKlient, ...]:
        return tuple(self.test_forbindelse())

    def hent_api_klient(self, api_user_id: str) -> ApiKlient:
        validated_id = require_uuid(api_user_id, "api_user_id")
        data = self._request_json("GET", f"/Client/{validated_id}")
        return self._parse_api_klient(data)

    def opdater_api_klient(
        self,
        api_user_id: str,
        *,
        navn: str | None = None,
        mail: str | None = None,
    ) -> ApiKlient:
        validated_id = require_uuid(api_user_id, "api_user_id")
        payload = {
            "name": require_text(navn, "navn") if navn is not None else None,
            "mail": require_text(mail, "mail") if mail is not None else None,
        }
        data = self._request_json("PUT", f"/Client/{validated_id}", json=payload)
        return self._parse_api_klient(data)

    def _get_access_token(self, *, force_refresh: bool = False) -> str:
        now = time.monotonic()
        if not force_refresh and self._access_token and now < self._token_expires_monotonic:
            return self._access_token
        try:
            response = self._http.post(
                self._token_url,
                data={
                    "client_id": self._credentials.client_id,
                    "client_secret": self._credentials.client_secret,
                    "grant_type": "client_credentials",
                },
                headers={"Accept": "application/json"},
            )
        except httpx.RequestError as error:
            raise SigneringsportalConnectionError("Kunne ikke kontakte token-endpointet.") from error
        if response.status_code in {400, 401, 403}:
            raise SigneringsportalAuthenticationError(
                f"Token-endpointet afviste credentials med HTTP {response.status_code}."
            )
        if not response.is_success:
            raise SigneringsportalApiError(
                f"Token-endpointet returnerede HTTP {response.status_code}.",
                status_code=response.status_code,
            )
        try:
            data = response.json()
        except ValueError as error:
            raise SigneringsportalResponseError("Token-endpointet returnerede ikke JSON.") from error
        token = data.get("access_token") if isinstance(data, dict) else None
        if not isinstance(token, str) or not token.strip():
            raise SigneringsportalResponseError("Token-svaret mangler access_token.")
        expires_in = data.get("expires_in", 300)
        if isinstance(expires_in, bool) or not isinstance(expires_in, (int, float)) or expires_in <= 0:
            expires_in = 300
        usable_seconds = max(1.0, float(expires_in) - TOKEN_EXPIRY_BUFFER_SECONDS)
        self._access_token = token.strip()
        self._token_expires_monotonic = time.monotonic() + usable_seconds
        return self._access_token

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Udfører et autentificeret API-kald.

        Ved HTTP 401 hentes et nyt token, og kaldet forsøges én gang igen.

        HTTP 403 betyder, at tokenet er modtaget, men at API-klienten
        ikke har adgang til det ønskede endpoint.
        """
        response = None

        for attempt in range(2):
            token = self._get_access_token(
                force_refresh=attempt == 1
            )

            supplied_headers = kwargs.pop(
                "headers",
                {},
            )

            headers = dict(supplied_headers)

            headers.update(
                {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                }
            )

            try:
                response = self._http.request(
                    method,
                    f"{self._api_base_url}{path}",
                    headers=headers,
                    **kwargs,
                )
            except httpx.RequestError as error:
                raise SigneringsportalConnectionError(
                    "Kunne ikke kontakte Signeringsportalen "
                    f"for {method} {path}."
                ) from error

            if response.status_code != 401:
                break

            # Tokenet kan være udløbet eller tilbagekaldt.
            # Det fjernes, så næste forsøg henter et nyt.
            self._access_token = None
            self._token_expires_monotonic = 0.0

        if response is None:
            raise SigneringsportalConnectionError(
                "Signeringsportalen returnerede intet svar."
            )

        if response.status_code == 401:
            raise SigneringsportalAuthenticationError(
                "Signeringsportalen afviste bearer-tokenet "
                f"for {method} {path}."
            )

        if response.status_code == 403:
            raise SigneringsportalAuthenticationError(
                "Bearer-tokenet blev modtaget, men API-klienten "
                f"har ikke adgang til {method} {path}. "
                "Leverandøren skal kontrollere klientens roller, "
                "audience, scopes og adgang til SG.DokSigner API."
            )

        if not response.is_success:
            detail = self._safe_error_detail(
                response
            )

            raise SigneringsportalApiError(
                "Signeringsportalen returnerede "
                f"HTTP {response.status_code} "
                f"for {method} {path}{detail}.",
                status_code=response.status_code,
            )

        return response

    def _request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._request(method, path, **kwargs)
        try:
            return response.json()
        except ValueError as error:
            raise SigneringsportalResponseError(f"{method} {path} returnerede ikke JSON.") from error

    def _request_no_content(self, method: str, path: str, **kwargs: Any) -> None:
        response = self._request(method, path, **kwargs)
        if response.status_code != 204:
            raise SigneringsportalResponseError(
                f"{method} {path} forventedes at returnere HTTP 204, men returnerede {response.status_code}."
            )

    def _request_bool(self, method: str, path: str) -> bool:
        data = self._request_json(method, path)
        if not isinstance(data, bool):
            raise SigneringsportalResponseError(f"{method} {path} returnerede ikke bool.")
        return data

    @staticmethod
    def _safe_error_detail(response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return ""
        if not isinstance(data, dict):
            return ""
        detail = data.get("detail") or data.get("title")
        return f": {detail}" if isinstance(detail, str) and detail.strip() else ""

    @staticmethod
    def _build_upload(item: dict[str, Any], index: int) -> dict[str, str]:
        if not isinstance(item, dict):
            raise SigneringsportalValidationError(f"pdf_filer[{index}] skal være en dictionary.")
        title = require_text(item.get("titel"), f"pdf_filer[{index}].titel")
        pdf_bytes = require_pdf_bytes(item.get("indhold"), f"pdf_filer[{index}].indhold")
        return {"title": title, "pdfBase64": base64.b64encode(pdf_bytes).decode("ascii")}

    @staticmethod
    def _build_signer(item: dict[str, Any], index: int) -> dict[str, Any]:
        if not isinstance(item, dict):
            raise SigneringsportalValidationError(f"underskrivere[{index}] skal være en dictionary.")
        recipient_type = require_text(item.get("type"), f"underskrivere[{index}].type")
        if recipient_type not in ALLOWED_RECIPIENT_TYPES:
            raise SigneringsportalValidationError(
                f"underskrivere[{index}].type skal være Mail, DigitalPost eller DigitalPostCvr."
            )
        message = item.get("besked")
        return {
            "identifier": require_text(item.get("identifikator"), f"underskrivere[{index}].identifikator"),
            "type": recipient_type,
            "message": require_text(message, f"underskrivere[{index}].besked") if message is not None else None,
        }

    @staticmethod
    def _parse_signer_status(
        item: Any,
    ) -> UnderskriverStatus:
        """
        Fortolker ét SignFlow fra GetDetails.

        Signeringsportalen arbejder med to forskellige id'er:

        - SignFlow.id:
        Id'et på signeringsforløbet for underskriveren.

        - SignFlow.signerId:
        Id'et på selve modtageren.

        SendMailRequest.signerId forventer modtagerens signerId,
        ikke SignFlow.id.
        """
        if not isinstance(item, dict):
            raise SigneringsportalResponseError(
                "Et element i signFlows var ikke et objekt."
            )

        signer = (
            item.get("signer")
            or {}
        )

        if not isinstance(signer, dict):
            raise SigneringsportalResponseError(
                "signFlows.signer var ikke et objekt."
            )

        sign_flow_id = require_uuid(
            item.get("id"),
            "signFlows.id",
        )

        # Førstevalg er det direkte signerId på SignFlow.
        #
        # Som fallback bruges signer.id fra det indlejrede
        # Recipient-objekt.
        signer_id_value = (
            item.get("signerId")
            or signer.get("id")
        )

        signer_id = None

        if signer_id_value is not None:
            signer_id = require_uuid(
                signer_id_value,
                "signFlows.signerId",
            )

        return UnderskriverStatus(
            sign_flow_id=sign_flow_id,
            signer_id=signer_id,
            identifikator=signer.get(
                "identifier"
            ),
            modtagertype=signer.get(
                "type"
            ),
            status=require_text(
                item.get("status"),
                "signFlows.status",
            ),
            udloeber=item.get(
                "expiry"
            ),
        )

    @staticmethod
    def _parse_api_klient(data: Any) -> ApiKlient:
        if not isinstance(data, dict):
            raise SigneringsportalResponseError("API-klienten er ikke et objekt.")
        return ApiKlient(
            api_user_id=require_uuid(data.get("id"), "API-klient.id"),
            identifier=data.get("identifier"),
            navn=data.get("name"),
            mail=data.get("mail"),
        )
