"""Compiled onboarding workflow.

The factory signature is fixed here because ``services/onboarding_service.py`` imports
it.
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.onboarding.nodes import (
    ConstructKnowledgeGraphNode,
    ExtractSchemaNode,
    GenerateEmbeddingsNode,
    GenerateSemanticsNode,
    IdentifyEntitiesNode,
    MapEntityColumnsNode,
    RegisterMetadataNode,
)
from src.agents.onboarding.state import OnboardingState
from src.clients.container import Clients


def build_onboarding_graph(clients: Clients) -> CompiledStateGraph:
    """Compile the admin onboarding LangGraph.

    Node order is unchanged from the original implementation:
    extract_schema -> generate_semantics -> identify_entities -> map_entity_columns
    -> construct_knowledge_graph -> generate_embeddings -> register_metadata
    """
    workflow = StateGraph(OnboardingState)

    workflow.add_node("extract_schema", ExtractSchemaNode(clients))
    workflow.add_node("generate_semantics", GenerateSemanticsNode(clients))
    workflow.add_node("identify_entities", IdentifyEntitiesNode(clients))
    workflow.add_node("map_entity_columns", MapEntityColumnsNode(clients))
    workflow.add_node("construct_knowledge_graph", ConstructKnowledgeGraphNode(clients))
    workflow.add_node("generate_embeddings", GenerateEmbeddingsNode(clients))
    workflow.add_node("register_metadata", RegisterMetadataNode(clients))

    workflow.add_edge(START, "extract_schema")
    workflow.add_edge("extract_schema", "generate_semantics")
    workflow.add_edge("generate_semantics", "identify_entities")
    workflow.add_edge("identify_entities", "map_entity_columns")
    workflow.add_edge("map_entity_columns", "construct_knowledge_graph")
    workflow.add_edge("construct_knowledge_graph", "generate_embeddings")
    workflow.add_edge("generate_embeddings", "register_metadata")
    workflow.add_edge("register_metadata", END)

    return workflow.compile()
