"""
Manuel integrationstest af signering med CPR-nummer via Digital Post.

Testen:
1. Læser CPR-nummer fra .env.
2. Kontrollerer om CPR-nummeret kan modtage Digital Post.
3. Læser tests/testfil.pdf som bytes.
4. Opretter et rigtigt signeringsworkflow med modtagertype DigitalPost.
5. Henter workflowets status.
6. Gemmer flow-id og ufølsomme testoplysninger i tests_local/.

Vigtigt:
- Testen opretter et rigtigt workflow.
- Testen kan sende en rigtig Digital Post/signeringsanmodning.
- Brug kun et CPR-nummer, som må anvendes til denne test.
- CPR-nummeret gemmes ikke i resultatfilen og udskrives ikke fuldt.
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

TEST_RESULTS_DIRECTORY = (
    PROJECT_ROOT
    / "tests_local"
)

RESULT_PATH = (
    TEST_RESULTS_DIRECTORY
    / "test_create_document_digital_post_result.json"
)


# ------------------------------------------------------------
# INDLÆS .ENV
# ------------------------------------------------------------

load_dotenv(ENV_PATH)


# ------------------------------------------------------------
# TESTKONFIGURATION
# ------------------------------------------------------------

TEST_CPR = (
    getenv(
        "SIGNERINGSPORTAL_TEST_CPR",
        "",
    )
    .strip()
)

WORKFLOW_NAME = (
    "Automatisering - API test med CPR"
)

SIGNER_MESSAGE = (
    "Dette er en test fra Haderslev Kommunes "
    "automatiseringsløsning."
)

EXPIRY_DAYS = 14


# ------------------------------------------------------------
# HJÆLPEFUNKTIONER
# ------------------------------------------------------------

def get_test_cpr() -> str:
    """
    Henter og validerer test-CPR fra .env.

    Bindestreg og mellemrum fjernes, før værdien sendes
    til Signeringsportalen.
    """
    normalized_cpr = (
        TEST_CPR
        .replace("-", "")
        .replace(" ", "")
    )

    if not normalized_cpr:
        raise RuntimeError(
            "SIGNERINGSPORTAL_TEST_CPR mangler i .env."
        )

    if (
        not normalized_cpr.isdigit()
        or len(normalized_cpr) != 10
    ):
        raise RuntimeError(
            "SIGNERINGSPORTAL_TEST_CPR skal bestå af "
            "10 cifre. Bindestreg og mellemrum "
            "accepteres i .env."
        )

    return normalized_cpr


def mask_cpr(
    cpr: str,
) -> str:
    """
    Returnerer CPR i maskeret form til terminaloutput.
    """
    return f"******-{cpr[-4:]}"


def load_pdf_bytes() -> bytes:
    """
    Læser test-PDF'en og returnerer indholdet som bytes.
    """
    if not PDF_PATH.exists():
        raise FileNotFoundError(
            f"Testfilen blev ikke fundet: {PDF_PATH}"
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
            f"Testfilen ligner ikke en PDF: {PDF_PATH}"
        )

    return pdf_bytes


def save_result(
    *,
    flow_id: str,
    signer_id: str | None,
    status: str,
    url: str | None,
    expires_at: datetime,
    can_receive_digital_post: bool,
) -> None:
    """
    Gemmer ufølsomme testoplysninger i tests_local/.

    CPR-nummeret gemmes bevidst ikke.
    """
    result = {
        "flow_id": flow_id,
        "signer_id": signer_id,
        "status": status,
        "url": url,
        "recipient_type": "DigitalPost",
        "can_receive_digital_post": (
            can_receive_digital_post
        ),
        "workflow_name": WORKFLOW_NAME,
        "source_document": PDF_PATH.name,
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
    test_cpr = get_test_cpr()
    pdf_bytes = load_pdf_bytes()

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(days=EXPIRY_DAYS)
    )

    print(
        "Starter signeringstest med CPR "
        "og Digital Post."
    )
    print()
    print("Modtager:", mask_cpr(test_cpr))
    print("PDF:", PDF_PATH)
    print("PDF-størrelse:", len(pdf_bytes), "bytes")
    print("Workflow-navn:", WORKFLOW_NAME)

    with SigneringsportalClient.from_automation_server() as client:
        print()
        print(
            "Kontrollerer adgang til Digital Post..."
        )

        can_receive_digital_post = (
            client.kan_modtage_digital_post_cpr(
                test_cpr
            )
        )

        print(
            "Kan modtage Digital Post:",
            can_receive_digital_post,
        )

        if not can_receive_digital_post:
            raise RuntimeError(
                "CPR-nummeret kan ikke modtage "
                "Digital Post. Workflowet blev derfor "
                "ikke oprettet."
            )

        print()
        print("Opretter signeringsworkflow...")

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
                    "identifikator": test_cpr,
                    "type": "DigitalPost",
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
        can_receive_digital_post=(
            can_receive_digital_post
        ),
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
            mask_cpr(test_cpr),
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