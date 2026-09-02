"""Shared pydantic base configurations.

Three bases, three trust levels:

- ``StrictModel``  -- inbound HTTP. Unknown fields are a 422, not a silent ignore.
- ``ApiModel``     -- outbound HTTP. Serialises exactly the frozen wire contract.
- ``LenientModel`` -- LLM and datastore output. Required fields are still enforced,
  but extra keys a model invents are dropped rather than rejected.
"""

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Request bodies. A typo in a field name surfaces as a validation error."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ApiModel(BaseModel):
    """Response bodies. ``populate_by_name`` keeps wire keys stable if a field is aliased."""

    model_config = ConfigDict(populate_by_name=True)


class LenientModel(BaseModel):
    """LLM replies and datastore records -- validate what we need, ignore the rest."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
