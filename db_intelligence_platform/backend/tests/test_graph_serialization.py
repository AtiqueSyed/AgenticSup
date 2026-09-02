"""`src/services/graph_read.py`'s `_to_nodes` / `_to_edges` -- the React-Flow payload
shape the frontend depends on byte-for-byte, ported from the old
`app/api/endpoints.py::get_knowledge_graph`.

Frozen shape:
    node: {"id":..., "type": "input" if label=="Database" else "default",
           "data": {"label": "[Type]\\nLabel"}, "position": {"x": 0, "y": 0}}
    edge: {"id": f"{source}-{target}-{type}", "source":..., "target":...,
           "label": type, "animated": type != "CONTAINS"}
"""

from src.services.graph_read import _to_edges, _to_nodes

# ------------------------------------------------------------------------------ nodes


def test_database_node_gets_input_type():
    raw = [{"id": "db1", "label": "MyDB", "type": "Database"}]
    assert _to_nodes(raw) == [
        {
            "id": "db1",
            "type": "input",
            "data": {"label": "[Database]\nMyDB"},
            "position": {"x": 0, "y": 0},
        }
    ]


def test_non_database_node_gets_default_type():
    for node_type in ("Table", "Column", "Entity"):
        raw = [{"id": "x1", "label": "Widget", "type": node_type}]
        assert _to_nodes(raw) == [
            {
                "id": "x1",
                "type": "default",
                "data": {"label": f"[{node_type}]\nWidget"},
                "position": {"x": 0, "y": 0},
            }
        ]


def test_multiple_nodes_preserve_order():
    raw = [
        {"id": "db1", "label": "MyDB", "type": "Database"},
        {"id": "t1", "label": "Orders", "type": "Table"},
    ]
    result = _to_nodes(raw)
    assert [n["id"] for n in result] == ["db1", "t1"]
    assert result[0]["type"] == "input"
    assert result[1]["type"] == "default"


def test_node_missing_id_is_dropped():
    raw = [
        {"label": "No Id Here", "type": "Table"},
        {"id": "t1", "label": "Has Id", "type": "Table"},
    ]
    result = _to_nodes(raw)
    assert len(result) == 1
    assert result[0]["id"] == "t1"


def test_node_with_falsy_id_is_dropped():
    raw = [
        {"id": "", "label": "Empty Id", "type": "Table"},
        {"id": None, "label": "None Id", "type": "Table"},
        {"id": "t1", "label": "Has Id", "type": "Table"},
    ]
    result = _to_nodes(raw)
    assert [n["id"] for n in result] == ["t1"]


def test_empty_node_list():
    assert _to_nodes([]) == []


# ------------------------------------------------------------------------------ edges


def test_contains_edge_is_not_animated():
    raw = [{"source": "db1", "target": "e1", "type": "CONTAINS"}]
    assert _to_edges(raw) == [
        {
            "id": "db1-e1-CONTAINS",
            "source": "db1",
            "target": "e1",
            "label": "CONTAINS",
            "animated": False,
        }
    ]


def test_non_contains_edge_is_animated():
    for edge_type in ("HAS_TABLE", "HAS_COLUMN", "MAPS_TO", "REPRESENTS", "RELATES_TO"):
        raw = [{"source": "a", "target": "b", "type": edge_type}]
        result = _to_edges(raw)
        assert result[0]["animated"] is True
        assert result[0]["id"] == f"a-b-{edge_type}"
        assert result[0]["label"] == edge_type


def test_edge_missing_source_is_dropped():
    raw = [{"target": "b", "type": "RELATES_TO"}, {"source": "a", "target": "b", "type": "X"}]
    result = _to_edges(raw)
    assert len(result) == 1
    assert result[0]["source"] == "a"


def test_edge_missing_target_is_dropped():
    raw = [{"source": "a", "type": "RELATES_TO"}, {"source": "a", "target": "b", "type": "X"}]
    result = _to_edges(raw)
    assert len(result) == 1
    assert result[0]["target"] == "b"


def test_edge_with_falsy_endpoints_is_dropped():
    raw = [
        {"source": "", "target": "b", "type": "X"},
        {"source": "a", "target": "", "type": "X"},
        {"source": "a", "target": "b", "type": "X"},
    ]
    result = _to_edges(raw)
    assert len(result) == 1
    assert result[0] == {"id": "a-b-X", "source": "a", "target": "b", "label": "X", "animated": True}


def test_empty_edge_list():
    assert _to_edges([]) == []
