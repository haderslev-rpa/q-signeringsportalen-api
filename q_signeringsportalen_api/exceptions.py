"""Fejltyper som den kaldende proces kan håndtere særskilt."""

class SigneringsportalError(Exception):
    """Grundfejl for integrationen."""


class SigneringsportalConfigurationError(SigneringsportalError):
    """Credential eller konfiguration mangler eller er ugyldig."""


class SigneringsportalValidationError(SigneringsportalError, ValueError):
    """Input fra den kaldende proces er ugyldigt."""


class SigneringsportalAuthenticationError(SigneringsportalError):
    """Broker eller API afviste autentifikationen."""


class SigneringsportalConnectionError(SigneringsportalError):
    """API'et kunne ikke kontaktes inden for de valgte timeouts."""


class SigneringsportalApiError(SigneringsportalError):
    """API'et returnerede en fejlstatus."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class SigneringsportalResponseError(SigneringsportalError):
    """API-svaret havde et uventet format."""
