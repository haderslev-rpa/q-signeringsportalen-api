"""Indstillinger som kan ændres uden at ændre integrationslogikken."""

CREDENTIAL_NAME = "API_SIGNERINGSPORTALEN"
TOKEN_URL = "https://netseidbroker.dk/op/connect/token"
API_BASE_URL = "https://signeringsportal.haderslev.dk/doksigner"
CONNECT_TIMEOUT_SECONDS = 10.0
READ_TIMEOUT_SECONDS = 60.0
TOKEN_EXPIRY_BUFFER_SECONDS = 60
DEFAULT_WORKFLOW_API_TYPE = "SignaturgruppenBroker"
