"""Validering som beskytter API'et mod tydeligt ugyldigt input."""

from datetime import datetime
from uuid import UUID

from .exceptions import SigneringsportalValidationError

ALLOWED_RECIPIENT_TYPES = {"Mail", "DigitalPost", "DigitalPostCvr"}
ALLOWED_STATUSES = {"Signed", "Pending", "Inactive", "Expired", "Deleted"}


def require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SigneringsportalValidationError(f"{field_name} skal være en ikke-tom tekst.")
    return value.strip()


def require_uuid(value: object, field_name: str) -> str:
    text = require_text(value, field_name)
    try:
        return str(UUID(text))
    except ValueError as error:
        raise SigneringsportalValidationError(f"{field_name} skal være et gyldigt UUID.") from error


def require_pdf_bytes(value: object, field_name: str = "pdf") -> bytes:
    if not isinstance(value, bytes):
        raise SigneringsportalValidationError(f"{field_name} skal være bytes.")
    if not value:
        raise SigneringsportalValidationError(f"{field_name} må ikke være tom.")
    if not value.startswith(b"%PDF-"):
        raise SigneringsportalValidationError(f"{field_name} ligner ikke en PDF-fil.")
    return value


def require_aware_datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise SigneringsportalValidationError(f"{field_name} skal være datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise SigneringsportalValidationError(f"{field_name} skal indeholde tidszone.")
    return value
