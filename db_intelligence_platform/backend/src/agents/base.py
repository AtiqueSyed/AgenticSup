"""Base class for every LangGraph node.

The old nodes each repeated the same four things: an ``if status == "error": return``
guard, a try/except, a ``print`` on failure, and an append to ``state["errors"]``. All of
it lives here now, so a subclass is just its ``run`` body -- which is most of how the
cyclomatic-complexity target is met.

``__call__`` is what LangGraph invokes, so every node is automatically a span.
"""

from abc import ABC, abstractmethod
from time import perf_counter
from typing import Any

from src.clients.container import Clients
from src.core.logging import get_logger
from src.core.telemetry import get_meter, get_tracer
from src.utils.helpers import record_exception

logger = get_logger(__name__)
tracer = get_tracer(__name__)
_meter = get_meter(__name__)
_duration = _meter.create_histogram(
    "agent.node.duration", unit="ms", description="Agent node execution time"
)

ERROR_STATUS = "error"


class BaseNode(ABC):
    """One step of an agent workflow.

    Subclasses set ``name`` and implement ``run``. Returning a partial dict is the
    LangGraph convention and is preserved.
    """

    name: str = "node"
    agent: str = "agent"
    #: When true, the node is skipped if an earlier node already failed.
    skip_on_error: bool = True

    def __init__(self, clients: Clients) -> None:
        self.clients = clients
        self.settings = clients.settings
        self.log = get_logger(f"{self.agent}.{self.name}")

    @abstractmethod
    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """The node's actual work. Raise on failure -- ``__call__`` records it."""

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        if self.skip_on_error and state.get("status") == ERROR_STATUS:
            self.log.info("Skipping: an earlier node failed")
            return {}

        attributes = {
            "agent.name": self.agent,
            "agent.node": self.name,
            "db.id": str(state.get("database_id") or "-"),
        }
        with tracer.start_as_current_span(f"{self.agent}.{self.name}", attributes=attributes) as span:
            # The histogram is recorded in ``finally`` so a failed node is timed too --
            # a node that reliably blows up after 30s is exactly what you want on a chart.
            started = perf_counter()
            outcome = "error"
            try:
                result = await self.run(state)
                outcome = "ok"
            except Exception as exc:
                record_exception(span, exc)
                self.log.exception("Node failed")
                return self.failure(state, exc)
            finally:
                _duration.record(
                    (perf_counter() - started) * 1000,
                    {"agent.name": self.agent, "agent.node": self.name, "outcome": outcome},
                )
            span.set_attribute("agent.node.status", "ok")
            return result

    def failure(self, state: dict[str, Any], exc: Exception) -> dict[str, Any]:
        """Uniform error shape, so downstream nodes and the API see one convention."""
        message = f"{self.name}: {exc}"
        return {"status": ERROR_STATUS, "errors": [*state.get("errors", []), message]}
