"""
Manuel integrationstest med to PDF-dokumenter.

Testen:
1. Læser tests/testfil.pdf som bytes.
2. Læser tests/testfil2.pdf som bytes.
3. Opretter ét workflow med begge PDF-filer.
4. Sender workflowet til testmailen fra .env.
5. Henter status på det oprettede workflow.
6. Gemmer flow-id og testoplysninger i tests_local/.

Vigtigt:
- Testen opretter et rigtigt workflow.
- Testen sender en rigtig signeringsmail.
- Selve PDF-indholdet sendes til API'et som bytes.
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

PDF_PATH_1 = (
    PROJECT_ROOT
    / "tests"
    / "testfil.pdf"
)

PDF_PATH_2 = (
    PROJECT_ROOT
    / "tests"
    / "testfil2.pdf"
)

TEST_RESULTS_DIRECTORY = (
    PROJECT_ROOT
    / "tests_local"
)

RESULT_PATH = (
    TEST_RESULTS_DIRECTORY
    / "test_create_documents_result.json"
)


# ------------------------------------------------------------
# INDLÆS .ENV
# ------------------------------------------------------------

load_dotenv(ENV_PATH)


# ------------------------------------------------------------
# TESTKONFIGURATION
# ------------------------------------------------------------

TEST_MAIL = (
    getenv(
        "SIGNERINGSPORTAL_TEST_MAIL",
        "",
    )
    .strip()
)

WORKFLOW_NAME = (
    "Automatisering - API test med to dokumenter"
)

SIGNER_MESSAGE = (
    "Dette er en integrationstest med to dokumenter "
    "fra Haderslev Kommunes automatiseringsløsning."
)

EXPIRY_DAYS = 14


# ------------------------------------------------------------
# HJÆLPEFUNKTIONER
# ------------------------------------------------------------

def get_test_mail() -> str:
    """
    Returnerer testmailen fra .env.
    """
    if not TEST_MAIL:
        raise RuntimeError(
            "SIGNERINGSPORTAL_TEST_MAIL mangler i .env."
        )

    return TEST_MAIL


def load_pdf_bytes(
    pdf_path: Path,
) -> bytes:
    """
    Læser én PDF-fil og returnerer indholdet som bytes.

    Funktionen kontrollerer:
    - at filen findes
    - at stien er en fil
    - at filen ikke er tom
    - at filen begynder med en PDF-header
    """
    if not pdf_path.exists():
        raise FileNotFoundError(
            "Testfilen blev ikke fundet.\n"
            f"Forventet placering: {pdf_path}"
        )

    if not pdf_path.is_file():
        raise RuntimeError(
            f"PDF-stien er ikke en fil: {pdf_path}"
        )

    pdf_bytes = pdf_path.read_bytes()

    if not pdf_bytes:
        raise RuntimeError(
            f"PDF-filen er tom: {pdf_path}"
        )

    if not pdf_bytes.startswith(b"%PDF-"):
        raise RuntimeError(
            "Testfilen ligner ikke en gyldig PDF. "
            f"Fil: {pdf_path}"
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
    Gemmer testoplysninger i tests_local/.

    Der gemmes ikke PDF-indhold eller credentials.
    """
    result = {
        "flow_id": flow_id,
        "signer_id": signer_id,
        "status": status,
        "url": url,
        "test_mail": test_mail,
        "workflow_name": WORKFLOW_NAME,
        "source_documents": [
            PDF_PATH_1.name,
            PDF_PATH_2.name,
        ],
        "document_count": 2,
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

    pdf_bytes_1 = load_pdf_bytes(
        PDF_PATH_1
    )

    pdf_bytes_2 = load_pdf_bytes(
        PDF_PATH_2
    )

    print(
        "Starter oprettelsestest "
        "med to PDF-dokumenter."
    )
    print()
    print("Workflow-navn:", WORKFLOW_NAME)
    print("Modtager:", test_mail)

    print()
    print("Dokument 1:")
    print("  Fil:", PDF_PATH_1)
    print("  Størrelse:", len(pdf_bytes_1), "bytes")
    print("  Header:", pdf_bytes_1[:8])

    print()
    print("Dokument 2:")
    print("  Fil:", PDF_PATH_2)
    print("  Størrelse:", len(pdf_bytes_2), "bytes")
    print("  Header:", pdf_bytes_2[:8])

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(days=EXPIRY_DAYS)
    )

    print()
    print(
        "Opretter workflow med to dokumenter "
        "i Signeringsportalen..."
    )

    with SigneringsportalClient.from_automation_server() as client:
        create_result = client.opret_signeringsopgave(
            navn=WORKFLOW_NAME,
            pdf_filer=[
                {
                    "titel": PDF_PATH_1.name,
                    "indhold": pdf_bytes_1,
                },
                {
                    "titel": PDF_PATH_2.name,
                    "indhold": pdf_bytes_2,
                },
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

    print()
    print("Næste trin:")
    print(
        "1. Kontrollér at begge dokumenter vises "
        "i signeringsforløbet."
    )
    print(
        "2. Underskriv workflowet."
    )
    print(
        "3. Sæt SIGNERINGSPORTAL_TEST_FLOW_ID "
        "til det nye flow-id i .env."
    )
    print(
        "4. Undersøg derefter det faktiske svar "
        "fra GetPades."
    )


if __name__ == "__main__":
    main()