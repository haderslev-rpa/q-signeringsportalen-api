"""
Diagnosetest af autentifikation til Signeringsportalen.

Testen:
1. Henter client_id og client_secret fra Automation Server.
2. Henter et JWT access-token fra brokeren.
3. Læser kun ufølsomme claims fra tokenet.
4. Kalder GET /Adm/GetAllPending.
5. Udskriver HTTP-status, WWW-Authenticate og et eventuelt fejlsvar.

Vigtigt:
- Selve access-tokenet udskrives aldrig.
- Client secret udskrives aldrig.
- JWT-signaturen valideres ikke her.
  Tokenet afkodes kun lokalt for fejlsøgning.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any

from q_signeringsportalen_api import SigneringsportalClient


SAFE_CLAIMS = (
    "iss",
    "aud",
    "scope",
    "client_id",
    "azp",
    "sub",
    "exp",
    "nbf",
    "iat",
)


def decode_jwt_payload_without_validation(
    token: str,
) -> dict[str, Any]:
    """
    Læser JWT-payloaden uden at validere signaturen.

    Funktionen bruges kun til lokal fejlsøgning.
    Den må ikke bruges til sikkerhedsbeslutninger.
    """
    token_parts = token.split(".")

    if len(token_parts) != 3:
        raise ValueError(
            "Access-tokenet ligner ikke et JWT med tre dele."
        )

    payload_base64 = token_parts[1]

    # Base64 URL-data kan mangle afsluttende =-tegn.
    padding_length = (-len(payload_base64)) % 4
    payload_base64 += "=" * padding_length

    try:
        payload_bytes = base64.urlsafe_b64decode(
            payload_base64.encode("ascii")
        )
        payload = json.loads(
            payload_bytes.decode("utf-8")
        )
    except (
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise ValueError(
            "JWT-payloaden kunne ikke afkodes."
        ) from error

    if not isinstance(payload, dict):
        raise ValueError(
            "JWT-payloaden er ikke et JSON-objekt."
        )

    return payload


def format_timestamp(
    value: Any,
) -> str | None:
    """
    Omsætter et Unix-timestamp til en læsbar UTC-dato.
    """
    if isinstance(value, bool):
        return None

    if not isinstance(value, (int, float)):
        return None

    return datetime.fromtimestamp(
        value,
        tz=timezone.utc,
    ).isoformat()


def get_safe_claims(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Returnerer kun claims, som er relevante for fejlsøgningen.
    """
    result = {
        claim_name: payload[claim_name]
        for claim_name in SAFE_CLAIMS
        if claim_name in payload
    }

    for timestamp_claim in ("exp", "nbf", "iat"):
        if timestamp_claim not in payload:
            continue

        formatted_value = format_timestamp(
            payload[timestamp_claim]
        )

        if formatted_value is not None:
            result[f"{timestamp_claim}_utc"] = (
                formatted_value
            )

    return result


def get_safe_response_body(
    response,
) -> Any:
    """
    Returnerer et begrænset fejlsvar uden headers eller token.
    """
    try:
        response_data = response.json()
    except ValueError:
        response_text = response.text.strip()

        if not response_text:
            return None

        # Undgå meget store HTML-fejlsider i terminalen.
        return response_text[:2000]

    return response_data


def main() -> None:
    print(
        "Henter token og undersøger adgang "
        "til Signeringsportalen..."
    )

    with SigneringsportalClient.from_automation_server() as client:
        # Privat funktion anvendes kun i denne lokale diagnosetest.
        access_token = client._get_access_token()

        jwt_payload = decode_jwt_payload_without_validation(
            access_token
        )
        safe_claims = get_safe_claims(
            jwt_payload
        )

        print()
        print("JWT-oplysninger:")
        print(
            json.dumps(
                safe_claims,
                indent=2,
                ensure_ascii=False,
            )
        )

        response = client._http.get(
            (
                f"{client._api_base_url}"
                "/Adm/GetAllPending"
            ),
            headers={
                "Authorization": (
                    f"Bearer {access_token}"
                ),
                "Accept": "application/json",
            },
        )

        print()
        print("Svar fra Signeringsportalen:")
        print(
            "HTTP-status:",
            response.status_code,
        )
        print(
            "Content-Type:",
            response.headers.get(
                "content-type"
            ),
        )
        print(
            "WWW-Authenticate:",
            response.headers.get(
                "www-authenticate"
            ),
        )
        print(
            "Server:",
            response.headers.get(
                "server"
            ),
        )

        response_body = get_safe_response_body(
            response
        )

        print("Svarindhold:")
        print(
            json.dumps(
                response_body,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )

        if response.status_code == 200:
            print()
            print(
                "Forbindelsen til "
                "Signeringsportalen virker."
            )
            return

        if response.status_code == 401:
            print()
            print(
                "Tokenet blev ikke accepteret. "
                "Kontrollér issuer, audience og udløbstid."
            )
            return

        if response.status_code == 403:
            print()
            print(
                "Tokenet blev modtaget, men adgangen "
                "til endpointet blev afvist."
            )
            print(
                "Kontrollér især JWT-claims: "
                "aud, scope, client_id og azp."
            )
            return

        print()
        print(
            "Signeringsportalen returnerede en "
            "anden fejlstatus end forventet."
        )


if __name__ == "__main__":
    main()