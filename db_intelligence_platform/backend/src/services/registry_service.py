"""File-backed registry of onboarded databases and their onboarding status.

Replaces the old module-level ``tasks_status`` / ``mock_db_connections`` globals plus
the module-level ``read_registry`` / ``write_registry`` functions in
``app/api/endpoints.py``. Status now lives in the same JSON file as the connection
info, so (bug fix) it survives a process reload -- the old in-memory ``tasks_status``
dict did not.
"""

import json
from pathlib import Path
from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


class DatabaseRegistry:
    """CRUD over the JSON registry file at ``settings.REGISTRY_PATH``.

    Every method re-reads the file before mutating it -- this is a small, low-write
    hackathon-scale registry, not a database, so there is no in-memory cache to keep in
    sync across the multiple worker processes uvicorn may spawn.
    """

    def __init__(self, path: str) -> None:
        self._path = Path(path)

    def _read(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("Failed to read registry at %s; treating as empty", self._path)
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        try:
            self._path.write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            logger.exception("Failed to write registry at %s", self._path)

    def all(self) -> dict[str, Any]:
        """Every registered ``{database_id: {name, connection_string, status}}`` entry."""
        return self._read()

    def get(self, db_id: str) -> dict[str, Any] | None:
        return self._read().get(db_id)

    def add(self, db_id: str, name: str, connection_string: str) -> None:
        data = self._read()
        data[db_id] = {"name": name, "connection_string": connection_string}
        self._write(data)

    def remove(self, db_id: str) -> None:
        data = self._read()
        if data.pop(db_id, None) is not None:
            self._write(data)

    def clear(self) -> None:
        self._write({})

    def connection_string_for(self, db_id: str) -> str | None:
        entry = self.get(db_id)
        return entry.get("connection_string") if entry else None

    def set_status(self, db_id: str, status: str) -> None:
        data = self._read()
        data.setdefault(db_id, {})["status"] = status
        self._write(data)

    def get_status(self, db_id: str) -> str | None:
        entry = self.get(db_id)
        return entry.get("status") if entry else None

    def statuses(self) -> dict[str, str]:
        return {db_id: info.get("status", "") for db_id, info in self._read().items()}
