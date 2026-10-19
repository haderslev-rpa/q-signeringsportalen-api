"""
Manuel integrationstest af hentning af underskrevet PDF.

Testen:
1. Læser flow-id fra .env.
2. Henter workflowets status.
3. Kontrollerer at workflowet er Signed.
4. Henter den underskrevne PAdES-PDF som bytes i memory.
5. Gemmer testresultatet i tests_local/testfil_signed.pdf.

Selve API-funktionen gemmer ikke noget på disk.
"""

from __future__ import annotations

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

TEST_RESULTS_DIRECTORY = (
    PROJECT_ROOT
    / "tests_local"
)

OUTPUT_PDF_PATH = (
    TEST_RESULTS_DIRECTORY
    / "testfil_signed.pdf"
)


# ------------------------------------------------------------
# INDLÆS .ENV
# ------------------------------------------------------------

load_dotenv(ENV_PATH)


# ------------------------------------------------------------
# TESTKONFIGURATION
# ------------------------------------------------------------

FLOW_ID = (
    getenv(
        "SIGNERINGSPORTAL_TEST_FLOW_ID",
        "",
    )
    .strip()
)


# ------------------------------------------------------------
# HJÆLPEFUNKTIONER
# ------------------------------------------------------------

def get_flow_id() -> str:
    """
    Returnerer flow-id fra .env.
    """
    if not FLOW_ID:
        raise RuntimeError(
            "SIGNERINGSPORTAL_TEST_FLOW_ID "
            "mangler i .env."
        )

    return FLOW_ID


# ------------------------------------------------------------
# TEST
# ------------------------------------------------------------

def main() -> None:
    flow_id = get_flow_id()

    print("Henter underskrevet PDF.")
    print("Flow-id:", flow_id)
    print()

    with SigneringsportalClient.from_automation_server() as client:
        print("Kontrollerer workflowets status...")

        status = client.hent_signeringsstatus(
            flow_id
        )

        print("Workflow-navn:", status.navn)
        print("Workflow-status:", status.status)

        if not status.er_signeret:
            raise RuntimeError(
                "Workflowet er ikke underskrevet endnu. "
                f"Aktuel status er: {status.status}"
            )

        print()
        print("Workflowet er underskrevet.")
        print(
            "Henter den underskrevne "
            "PAdES-PDF til memory..."
        )

        # På dette tidspunkt foretages kun API-kaldet.
        # Der gemmes ikke noget på disk i client-funktionen.
        pdf_bytes = client.hent_signeret_pdf(
            flow_id
        )

    # --------------------------------------------------------
    # KONTROLLÉR RESULTATET I MEMORY
    # --------------------------------------------------------

    if not isinstance(pdf_bytes, bytes):
        raise RuntimeError(
            "hent_signeret_pdf() returnerede ikke bytes. "
            f"Modtaget datatype: "
            f"{type(pdf_bytes).__name__}."
        )

    if not pdf_bytes:
        raise RuntimeError(
            "Den hentede PDF i memory er tom."
        )

    if not pdf_bytes.startswith(b"%PDF-"):
        raise RuntimeError(
            "Det hentede resultat i memory "
            "ligner ikke en PDF."
        )

    print()
    print("PDF'en ligger nu i memory.")
    print("Datatype:", type(pdf_bytes).__name__)
    print("Størrelse:", len(pdf_bytes), "bytes")
    print("PDF-header:", pdf_bytes[:8])

    # --------------------------------------------------------
    # GEM KUN TESTRESULTATET PÅ DISK
    # --------------------------------------------------------

    TEST_RESULTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PDF_PATH.write_bytes(
        pdf_bytes
    )

    print()
    print("Testen har gemt en kopi af PDF'en.")
    print("Fil:", OUTPUT_PDF_PATH)


if __name__ == "__main__":
    main()