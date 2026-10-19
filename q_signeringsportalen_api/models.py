"""Små returmodeller til processerne."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(
    frozen=True,
    slots=True,
)
class OpretSigneringsopgaveResultat:
    """
    Resultat fra oprettelse af en signeringsopgave.
    """

    flow_id: str


@dataclass(
    frozen=True,
    slots=True,
)
class UnderskriverStatus:
    """
    Status for én underskriver.

    sign_flow_id:
        Id'et på underskriverens SignFlow.

    signer_id:
        Id'et på selve modtageren.

        Dette id skal bruges som signerId ved SendMail.
        Feltet kan være None, hvis API-svaret ikke indeholder
        signerId eller signer.id.

    identifikator:
        Mailadresse, CPR eller CVR afhængigt af typen.

    modtagertype:
        Mail, DigitalPost eller DigitalPostCvr.
    """

    sign_flow_id: str
    signer_id: str | None
    identifikator: str | None
    modtagertype: str | None
    status: str
    udloeber: str | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class Signeringsstatus:
    """
    Samlet status for ét signeringsworkflow.
    """

    flow_id: str
    status: str
    navn: str | None
    url: str | None
    udloeber: str | None

    underskrivere: tuple[
        UnderskriverStatus,
        ...
    ] = field(
        default_factory=tuple,
    )

    raw: dict[
        str,
        Any,
    ] = field(
        default_factory=dict,
        repr=False,
    )

    @property
    def er_signeret(self) -> bool:
        """
        True når hele workflowet har status Signed.
        """
        return self.status == "Signed"

    @property
    def afventer(self) -> bool:
        """
        True når workflowet har status Pending.
        """
        return self.status == "Pending"

    @property
    def er_afsluttet_uden_signatur(self) -> bool:
        """
        True ved en afsluttet status uden underskrift.
        """
        return self.status in {
            "Inactive",
            "Expired",
            "Deleted",
        }


@dataclass(
    frozen=True,
    slots=True,
)
class ApiKlient:
    """
    Brugeroplysninger for en API-bruger.
    """

    api_user_id: str
    identifier: str | None
    navn: str | None
    mail: str | None