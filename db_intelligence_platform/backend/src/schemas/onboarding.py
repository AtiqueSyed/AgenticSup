"""Request/response models for ``/api/v1/onboard*``."""

import re

from pydantic import Field, field_validator

from src.schemas.base import ApiModel, StrictModel

#: Accepts anything shaped like ``driver://...`` (SQLAlchemy-style, e.g.
#: ``oracle+oracledb_async://user:pass@host/?service_name=x``).
_DRIVER_PREFIX_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+_.-]*://")


class OnboardRequest(StrictModel):
    database_name: str = Field(min_length=1)
    connection_string: str

    @field_validator("connection_string")
    @classmethod
    def _require_driver_prefix(cls, value: str) -> str:
        if not _DRIVER_PREFIX_RE.match(value):
            raise ValueError("connection_string must start with a 'driver://' prefix")
        return value


class OnboardAcceptedResponse(ApiModel):
    message: str
    database_id: str


class OnboardStatusResponse(ApiModel):
    database_id: str
    status: str


class DeleteDatabaseResponse(ApiModel):
    status: str
    database_id: str
