"""
Manuel integrationstest af et komplet oprettelsesflow.

Testen:
1. Læser tests/testfil.pdf som bytes.
2. Opretter et rigtigt workflow i Signeringsportalen.
3. Sender signeringsanmodningen til testmailen fra .env.
4. Gemmer flow-id og andre testoplysninger i tests/.
5. Henter workflowets status igen.

Vigtigt:
- Testen opretter et rigtigt workflow.
- Testen sender en rigtig mail.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from os import getenv
from pathlib import Path

from dotenv import load_dotenv

from q_signeringsportalen_api import (
    SigneringsportalClient,
)


# ------------------------------------------------------------
# PROJEKTSTIER
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ENV_PATH = PROJECT_ROOT / ".env"

PDF_PATH = PROJECT_ROOT / "tests" / "testfil.pdf"

RESULT_PATH = (
    PROJECT_ROOT
    / "tests_local"
    / "test_create_document_result.json"
)


# ------------------------------------------------------------
# INDLÆS .ENV
# ------------------------------------------------------------

load_dotenv(ENV_PATH)


# ------------------------------------------------------------
# TESTKONFIGURATION
# ------------------------------------------------------------

TEST_MAIL = (
    getenv("SIGNERINGSPORTAL_TEST_MAIL", "")
    .strip()
)

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

    Stopper testen, hvis miljøvariablen mangler.
    """
    if not TEST_MAIL:
        raise RuntimeError(
            "SIGNERINGSPORTAL_TEST_MAIL mangler i .env."
        )

    return TEST_MAIL


def load_pdf_bytes() -> bytes:
    """
    Læser test-PDF'en og returnerer indholdet som bytes.
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
    signer_id: str | None,
    status: str,
    url: str | None,
    expires_at: datetime,
    test_mail: str,
) -> None:
    """
    Gemmer testresultatet i tests/ som JSON.
    """
    result = {
        "flow_id": flow_id,
        "signer_id": signer_id,
        "status": status,
        "url": url,
        "test_mail": test_mail,
        "pdf_path": str(PDF_PATH),
        "workflow_name": WORKFLOW_NAME,
        "expires_at": expires_at.isoformat(),
        "created_by_test_at": (
            datetime.now(timezone.utc).isoformat()
        ),
    }

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

    print("Starter komplet test af oprettelsesflow.")
    print()
    print("PDF:", PDF_PATH)
    print("Modtager:", test_mail)
    print("Workflow-navn:", WORKFLOW_NAME)
    print("PDF-størrelse:", len(pdf_bytes), "bytes")

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(days=EXPIRY_DAYS)
    )

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

        workflow_status = (
            client.hent_signeringsstatus(
                create_result.flow_id
            )
        )

    signer_id = None

    if workflow_status.underskrivere:
        signer_id = (
            workflow_status
            .underskrivere[0]
            .signer_id
        )

    save_result(
        flow_id=workflow_status.flow_id,
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
        print("  Signer-id:", signer.signer_id)
        print(
            "  Identifikator:",
            signer.identifikator,
        )
        print(
            "  Modtagertype:",
            signer.modtagertype,
        )
        print("  Status:", signer.status)
        print("  Udløber:", signer.udloeber)

    print()
    print(
        "Testresultatet er gemt i:",
        RESULT_PATH,
    )


if __name__ == "__main__":
    main()
