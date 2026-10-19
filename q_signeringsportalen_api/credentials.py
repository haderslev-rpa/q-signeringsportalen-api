"""Hent OAuth-oplysninger fra Automation Server credentials."""

from dataclasses import dataclass

from automation_server_client import AutomationServer, Credential

from configuration import CREDENTIAL_NAME
from .exceptions import SigneringsportalConfigurationError


@dataclass(frozen=True, slots=True)
class OAuthCredentials:
    client_id: str
    client_secret: str


def hent_oauth_credentials(
    credential_name: str = CREDENTIAL_NAME,
) -> OAuthCredentials:
    """Returnér client-id og client-secret uden at logge værdierne."""
    AutomationServer.from_environment()
    credential = Credential.get_credential(credential_name)
    data = credential.data or {}
    client_id = data.get("client_id")
    client_secret = credential.password

    if not isinstance(client_id, str) or not client_id.strip():
        raise SigneringsportalConfigurationError(
            f"Credential {credential_name!r} mangler 'client_id' i Data JSON."
        )
    if not isinstance(client_secret, str) or not client_secret.strip():
        raise SigneringsportalConfigurationError(
            f"Credential {credential_name!r} mangler client_secret i password-feltet."
        )
    return OAuthCredentials(
        client_id=client_id.strip(),
        client_secret=client_secret.strip(),
    )
