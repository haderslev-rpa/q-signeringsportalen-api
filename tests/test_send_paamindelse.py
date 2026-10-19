"""
Manuel integrationstest af POST /Adm/SendMail.

Udfyld kun FLOW_ID direkte i filen.

Workflowet skal:
- have status Pending
- have præcis én underskriver
- være oprettet af den aktuelle API-bruger

Testen henter selv modtagerens signerId fra GetDetails.
"""

from q_signeringsportalen_api import (
    SigneringsportalClient,
)


# ------------------------------------------------------------
# TESTINPUT - UDFYLD DENNE VÆRDI
# ------------------------------------------------------------

FLOW_ID = (
    "c57f7208-aa4d-8a29-92e4-01a1540fdeb7"
)


# ------------------------------------------------------------
# HJÆLPEFUNKTION
# ------------------------------------------------------------

def validate_test_input() -> None:
    """
    Stopper testen, hvis flow-id ikke er udfyldt.
    """
    if not FLOW_ID:
        raise RuntimeError(
            "Udfyld FLOW_ID øverst i testfilen."
        )

    if FLOW_ID == "INDSÆT_FLOW_ID_HER":
        raise RuntimeError(
            "Udfyld FLOW_ID øverst i testfilen."
        )


# ------------------------------------------------------------
# TEST
# ------------------------------------------------------------

def main() -> None:
    validate_test_input()

    print("Tester afsendelse af påmindelse.")
    print("Flow-id:", FLOW_ID)
    print()

    with SigneringsportalClient.from_automation_server() as client:
        status_before = (
            client.hent_signeringsstatus(
                FLOW_ID
            )
        )

        print(
            "Workflow-navn:",
            status_before.navn,
        )
        print(
            "Status før påmindelse:",
            status_before.status,
        )

        if not status_before.afventer:
            raise RuntimeError(
                "Påmindelsen blev ikke sendt, fordi "
                "workflowet ikke har status Pending. "
                f"Aktuel status: {status_before.status}"
            )

        if len(status_before.underskrivere) != 1:
            raise RuntimeError(
                "Denne test forventer præcis én underskriver. "
                f"Antal underskrivere: "
                f"{len(status_before.underskrivere)}."
            )

        underskriver = (
            status_before.underskrivere[0]
        )

        print()
        print("Underskriver:")
        print(
            "  SignFlow-id:",
            underskriver.sign_flow_id,
        )
        print(
            "  Signer-id:",
            underskriver.signer_id,
        )
        print(
            "  Modtagertype:",
            underskriver.modtagertype,
        )
        print(
            "  Status:",
            underskriver.status,
        )

        if underskriver.status != "Pending":
            raise RuntimeError(
                "Påmindelsen blev ikke sendt, fordi "
                "underskriveren ikke har status Pending. "
                f"Aktuel status: {underskriver.status}"
            )

        if not underskriver.signer_id:
            raise RuntimeError(
                "GetDetails returnerede ikke modtagerens "
                "signerId. SignFlow-id'et må ikke bruges "
                "som signerId i SendMail-kaldet."
            )

        if (
            underskriver.signer_id
            == underskriver.sign_flow_id
        ):
            print()
            print(
                "Bemærk: signerId og SignFlow-id "
                "har samme værdi i dette svar."
            )
        else:
            print()
            print(
                "Bekræftet: signerId og SignFlow-id "
                "er forskellige værdier."
            )

        print()
        print(
            "Sender påmindelse med signerId:",
            underskriver.signer_id,
        )

        client.send_paamindelse(
            flow_id=FLOW_ID,
            signer_id=underskriver.signer_id,
        )

    print()
    print("Påmindelseskaldet lykkedes.")
    print(
        "Signeringsportalen returnerede "
        "HTTP 204 No Content."
    )


if __name__ == "__main__":
    main()