"""Manuel integrationstest af GET /Adm/GetAllSigned.

Testen kræver ingen input og ændrer ingen workflows.
"""

from typing import Any

from q_signeringsportalen_api import SigneringsportalClient


def mask_identifier(
    identifier: Any,
    recipient_type: Any,
) -> str:
    """Maskerer CPR/CVR i terminaloutput og viser mail uændret."""
    if not isinstance(identifier, str) or not identifier:
        return ""

    normalized = identifier.replace("-", "").replace(" ", "")

    if recipient_type == "DigitalPost":
        return f"******-{normalized[-4:]}" if len(normalized) >= 4 else "**********"

    if recipient_type == "DigitalPostCvr":
        return f"****{normalized[-4:]}" if len(normalized) >= 4 else "********"

    return identifier


def main() -> None:
    print("Henter alle underskrevne signeringsopgaver...")
    print()

    with SigneringsportalClient.from_automation_server() as client:
        result = client.hent_underskrevne_signeringsopgaver()

    current_user_id = result.get("currentUserId")
    workflows = result.get("signed") or []

    if not isinstance(workflows, list):
        raise RuntimeError("Feltet 'signed' var ikke en liste eller null.")

    print("Aktuel API-bruger-id:", current_user_id)
    print("Antal underskrevne workflows:", len(workflows))

    for number, workflow in enumerate(workflows, start=1):
        if not isinstance(workflow, dict):
            raise RuntimeError(
                f"Workflow {number} var ikke et JSON-objekt."
            )

        print()
        print(f"Workflow {number}:")
        print("  Flow-id:", workflow.get("id"))
        print("  Navn:", workflow.get("name"))
        print("  Status:", workflow.get("status"))
        print("  Oprettet:", workflow.get("created"))
        print("  Opdateret:", workflow.get("updated"))

        signers = workflow.get("signFlows") or []
        print("  Antal underskrivere:", len(signers))

        for signer_number, sign_flow in enumerate(signers, start=1):
            signer = sign_flow.get("signer") or {}
            recipient_type = signer.get("type")

            print(f"    Underskriver {signer_number}:")
            print("      Signer-id:", sign_flow.get("id"))
            print(
                "      Identifikator:",
                mask_identifier(
                    signer.get("identifier"),
                    recipient_type,
                ),
            )
            print("      Modtagertype:", recipient_type)
            print("      Status:", sign_flow.get("status"))
            print("      Udløber:", sign_flow.get("expiry"))


if __name__ == "__main__":
    main()
