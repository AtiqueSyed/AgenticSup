"""Request/response models for ``/api/v1/graph*``.

``CreateNodeRequest.type`` was a bare ``str`` in the old code, with a fallback to
``"Entity"`` for anything that didn't match a known label after ``.capitalize()``.
Using ``Literal`` here rejects unknown values with a 422 instead of silently
mislabeling a node -- a deliberate security fix, not a behavior regression, since the
four values the frontend actually sends still work identically.
"""

from typing import Any, Literal

from pydantic import Field

from src.schemas.base import ApiModel, StrictModel

NodeType = Literal["Database", "Table", "Column", "Entity"]


class GraphNode(ApiModel):
    id: str
    type: str
    data: dict[str, Any]
    position: dict[str, int]


class GraphEdge(ApiModel):
    id: str
    source: str
    target: str
    label: str
    animated: bool


class GraphResponse(ApiModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class CreateNodeRequest(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    type: NodeType
    description: str = ""


class CreateEdgeRequest(StrictModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    type: str = Field(pattern=r"^[A-Z_][A-Z0-9_]*$")


class MutationResponse(ApiModel):
    status: str
    node_id: str | None = None
    source: str | None = None
    target: str | None = None
