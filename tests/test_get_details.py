"""
Manuel, skrivebeskyttet test af GetDetails.

Testen:
1. Henter bearer-token automatisk.
2. Henter detaljer for et eksisterende workflow.
3. Udskriver workflowets status.
4. Udskriver status for hver underskriver.

Testen ændrer ikke noget i Signeringsportalen.
"""

from q_signeringsportalen_api import SigneringsportalClient


FLOW_ID = "efdebe8f-28d4-85a9-985a-01a15440d8a1"


def main() -> None:
    print("Henter status fra Signeringsportalen...")
    print("Flow-id:", FLOW_ID)
    print()

    with SigneringsportalClient.from_automation_server() as client:
        status = client.hent_signeringsstatus(
            FLOW_ID
        )

    print("Workflow:")
    print("  Flow-id:", status.flow_id)
    print("  Navn:", status.navn)
    print("  Status:", status.status)
    print("  URL:", status.url)
    print("  Udløber:", status.udloeber)
    print("  Er signeret:", status.er_signeret)
    print("  Afventer:", status.afventer)
    print(
        "  Afsluttet uden signatur:",
        status.er_afsluttet_uden_signatur,
    )

    print()
    print(
        "Antal underskrivere:",
        len(status.underskrivere),
    )

    for nummer, underskriver in enumerate(
        status.underskrivere,
        start=1,
    ):
        print()
        print(f"Underskriver {nummer}:")
        print(
            "  Signer-id:",
            underskriver.signer_id,
        )
        print(
            "  Identifikator:",
            underskriver.identifikator,
        )
        print(
            "  Modtagertype:",
            underskriver.modtagertype,
        )
        print(
            "  Status:",
            underskriver.status,
        )
        print(
            "  Udløber:",
            underskriver.udloeber,
        )


if __name__ == "__main__":
    main()