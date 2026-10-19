"""Manuel integrationstest af DELETE /Adm/Delete/{flowId}.

Udfyld FLOW_ID direkte i filen.
Brug kun et særskilt test-workflow, som må slettes.
"""

from q_signeringsportalen_api import SigneringsportalClient


# ------------------------------------------------------------
# TESTINPUT - UDFYLD DENNE VÆRDI
# ------------------------------------------------------------

FLOW_ID = "c57f7208-aa4d-8a29-92e4-01a1540fdeb7"

# Sikkerhedsflag. Skift kun til True, når FLOW_ID er kontrolleret.
BEKRAEFT_SLETNING = True


# ------------------------------------------------------------
# HJÆLPEFUNKTION
# ------------------------------------------------------------

def validate_test_input() -> None:
    """Stopper testen, medmindre flow-id og sikkerhedsflag er udfyldt."""
    if FLOW_ID == "INDSÆT_FLOW_ID_HER":
        raise RuntimeError("Udfyld FLOW_ID øverst i testfilen.")

    if BEKRAEFT_SLETNING is not True:
        raise RuntimeError(
            "Sletning er ikke bekræftet. Kontrollér FLOW_ID og sæt "
            "BEKRAEFT_SLETNING = True."
        )


# ------------------------------------------------------------
# TEST
# ------------------------------------------------------------

def main() -> None:
    validate_test_input()

    print("Tester sletning af signeringsopgave.")
    print("Flow-id:", FLOW_ID)
    print()

    with SigneringsportalClient.from_automation_server() as client:
        status_before = client.hent_signeringsstatus(FLOW_ID)

        print("Workflow-navn:", status_before.navn)
        print("Status før sletning:", status_before.status)
        print("Sletter workflowet...")

        client.slet_signeringsopgave(FLOW_ID)

    print()
    print("Sletningskaldet lykkedes.")
    print("API'et returnerede HTTP 204 No Content.")


if __name__ == "__main__":
    main()
