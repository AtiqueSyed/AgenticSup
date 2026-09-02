"""State shape for the onboarding LangGraph.

A plain ``TypedDict``, matching the old ``app/agents/admin_onboarding.py`` exactly --
LangGraph nodes exchange partial dicts, so the state itself carries no behaviour.
"""

from typing import Any, TypedDict


class OnboardingState(TypedDict):
    database_id: str
    database_name: str
    connection_string: str
    extracted_schema: dict[str, Any]
    semantic_descriptions: dict[str, str]
    entities: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    status: str
    errors: list[str]
