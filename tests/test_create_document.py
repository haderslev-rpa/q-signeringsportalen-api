"""
Manuel integrationstest af et komplet oprettelsesflow med mail.

Testen:
1. Læser testmailen fra .env.
2. Læser tests/testfil.pdf som bytes.
3. Opretter et rigtigt workflow i Signeringsportalen.
4. Sender en rigtig signeringsmail til testmailen.
5. Henter workflowets status med GetDetails.
6. Gemmer ufølsomme testoplysninger i tests_local/.

Vigtigt:
- Testen opretter et rigtigt workflow.
- Testen sender en rigtig mail.
- PDF-indhold, bearer-token og credentials gemmes ikke i resultatfilen.
- Resultatfilen indeholder mailadressen på testmodtageren.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from os import getenv
from pathlib import Path

from dotenv import load_dotenv

from q_signeringsportalen_api import SigneringsportalClient


# ------------------------------------------------------------
# PROJEKTSTIER
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
PDF_PATH = PROJECT_ROOT / "tests" / "testfil.pdf"
TEST_RESULTS_DIRECTORY = PROJECT_ROOT / "tests_local"
RESULT_PATH = (
    TEST_RESULTS_DIRECTORY
    / "test_create_document_result.json"
)


# ------------------------------------------------------------
# INDLÆS .ENV
# ------------------------------------------------------------

load_dotenv(ENV_PATH)


# ------------------------------------------------------------
# TESTKONFIGURATION
# ------------------------------------------------------------

TEST_MAIL = getenv(
    "SIGNERINGSPORTAL_TEST_MAIL",
    "",
).strip()

WORKFLOW_NAME = "Automatisering - API test"

SIGNER_MESSAGE = (
    "Dette er en test fra Haderslev Kommunes "
    "automatiseringsløsning."
)

EXPIRY_DAYS = 14


# ------------------------------------------------------------
# HJÆLPEFUNKTIONER
# ------------------------------------------------------------

def get_test_mail() -> str:
    """
    Returnerer testmailen fra .env.

    Stopper testen, hvis SIGNERINGSPORTAL_TEST_MAIL
    mangler eller er tom.
    """
    if not TEST_MAIL:
        raise RuntimeError(
            "SIGNERINGSPORTAL_TEST_MAIL mangler i .env."
        )

    return TEST_MAIL


def load_pdf_bytes() -> bytes:
    """
    Læser tests/testfil.pdf og returnerer indholdet som bytes.

    Kontrollerer, at filen findes, ikke er tom og begynder
    med en PDF-header.
    """
    if not PDF_PATH.exists():
        raise FileNotFoundError(
            "Testfilen blev ikke fundet.\n"
            f"Forventet placering: {PDF_PATH}"
        )

    if not PDF_PATH.is_file():
        raise RuntimeError(
            f"PDF-stien er ikke en fil: {PDF_PATH}"
        )

    pdf_bytes = PDF_PATH.read_bytes()

    if not pdf_bytes:
        raise RuntimeError(
            f"PDF-filen er tom: {PDF_PATH}"
        )

    if not pdf_bytes.startswith(b"%PDF-"):
        raise RuntimeError(
            "Testfilen ligner ikke en gyldig PDF. "
            "PDF-filen skal begynde med %PDF-."
        )

    return pdf_bytes


def save_result(
    *,
    flow_id: str,
    sign_flow_id: str | None,
    signer_id: str | None,
    status: str,
    url: str | None,
    expires_at: datetime,
    test_mail: str,
) -> None:
    """
    Gemmer ufølsomme testoplysninger i tests_local/.

    sign_flow_id og signer_id gemmes som separate felter,
    fordi de har forskellige formål i Signeringsportalen.
    """
    result = {
        "flow_id": flow_id,
        "sign_flow_id": sign_flow_id,
        "signer_id": signer_id,
        "status": status,
        "url": url,
        "recipient_type": "Mail",
        "test_mail": test_mail,
        "source_document": PDF_PATH.name,
        "workflow_name": WORKFLOW_NAME,
        "expires_at": expires_at.isoformat(),
        "created_by_test_at": (
            datetime.now(timezone.utc).isoformat()
        ),
    }

    TEST_RESULTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    RESULT_PATH.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ------------------------------------------------------------
# TEST
# ------------------------------------------------------------

def main() -> None:
    test_mail = get_test_mail()
    pdf_bytes = load_pdf_bytes()

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(days=EXPIRY_DAYS)
    )

    print("Starter komplet test af oprettelsesflow.")
    print()
    print("PDF:", PDF_PATH)
    print("Modtager:", test_mail)
    print("Workflow-navn:", WORKFLOW_NAME)
    print("PDF-størrelse:", len(pdf_bytes), "bytes")
    print("Udløber:", expires_at.isoformat())

    print()
    print("Opretter workflow i Signeringsportalen...")

    with SigneringsportalClient.from_automation_server() as client:
        create_result = client.opret_signeringsopgave(
            navn=WORKFLOW_NAME,
            pdf_filer=[
                {
                    "titel": PDF_PATH.name,
                    "indhold": pdf_bytes,
                }
            ],
            underskrivere=[
                {
                    "identifikator": test_mail,
                    "type": "Mail",
                    "besked": SIGNER_MESSAGE,
                }
            ],
            udloeber=expires_at,
            should_creator_sign=False,
            is_structured=False,
        )

        print("Workflow blev oprettet.")
        print("Flow-id:", create_result.flow_id)

        print()
        print("Henter workflowets status...")

        workflow_status = client.hent_signeringsstatus(
            create_result.flow_id
        )

    sign_flow_id = None
    signer_id = None

    if workflow_status.underskrivere:
        first_signer = workflow_status.underskrivere[0]
        sign_flow_id = first_signer.sign_flow_id
        signer_id = first_signer.signer_id

    save_result(
        flow_id=workflow_status.flow_id,
        sign_flow_id=sign_flow_id,
        signer_id=signer_id,
        status=workflow_status.status,
        url=workflow_status.url,
        expires_at=expires_at,
        test_mail=test_mail,
    )

    print()
    print("Workflow:")
    print("  Flow-id:", workflow_status.flow_id)
    print("  Navn:", workflow_status.navn)
    print("  Status:", workflow_status.status)
    print("  URL:", workflow_status.url)
    print("  Udløber:", workflow_status.udloeber)
    print("  Er signeret:", workflow_status.er_signeret)
    print("  Afventer:", workflow_status.afventer)
    print(
        "  Afsluttet uden signatur:",
        workflow_status.er_afsluttet_uden_signatur,
    )

    print()
    print(
        "Antal underskrivere:",
        len(workflow_status.underskrivere),
    )

    for number, signer in enumerate(
        workflow_status.underskrivere,
        start=1,
    ):
        print()
        print(f"Underskriver {number}:")
        print("  SignFlow-id:", signer.sign_flow_id)
        print("  Signer-id:", signer.signer_id)
        print("  Identifikator:", signer.identifikator)
        print("  Modtagertype:", signer.modtagertype)
        print("  Status:", signer.status)
        print("  Udløber:", signer.udloeber)

    print()
    print("Testresultatet er gemt i:", RESULT_PATH)


if __name__ == "__main__":
    main()