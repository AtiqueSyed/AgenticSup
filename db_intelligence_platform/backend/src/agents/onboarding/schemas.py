"""Pydantic validation for every LLM reply the onboarding agent parses.

These are the models passed to ``LLMClient.complete_model`` -- the boundary where an
LLM's JSON either becomes a typed object or raises ``LLMResponseError`` (with one
retry, handled by the LLM client itself).
"""

from pydantic import Field, RootModel

from src.schemas.base import LenientModel
from src.schemas.domain import EntityKey, Relationship

# --- generate_semantics ---


class TableSemantics(RootModel[dict[str, str]]):
    """``{table_name: description}`` -- the whole reply, no wrapper object."""


# --- identify_entities ---


class ExtractedEntity(LenientModel):
    id: str = Field(min_length=1)
    description: str = ""
    mapped_tables: list[str] = Field(default_factory=list)


class EntityExtraction(LenientModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)


# --- map_entity_columns ---


class EntityKeyAssignment(LenientModel):
    id: str = Field(min_length=1)
    entity_keys: list[EntityKey] = Field(default_factory=list)


class EntityKeyMap(LenientModel):
    entities: list[EntityKeyAssignment] = Field(default_factory=list)
