"""The one module of reusable helpers, shared by every layer of the project.

If a utility is needed in more than one place, it belongs here and nowhere else.
Covers: prompt loading, LLM-output parsing and validation, JSON serialisation,
truncation, and the tracing decorator.
"""

import json
import re
from collections.abc import Callable, Sequence
from functools import lru_cache, wraps
from inspect import iscoroutinefunction
from pathlib import Path
from string import Template
from typing import Any, TypeVar

from opentelemetry import trace
from pydantic import BaseModel, ValidationError

from src.core.logging import get_logger

logger = get_logger(__name__)

TModel = TypeVar("TModel", bound=BaseModel)

# ``agents/<agent>/prompts/<name>.txt``
_PROMPTS_ROOT = Path(__file__).resolve().parent.parent / "agents"

_FENCE_RE = re.compile(r"^\s*```(?:json|sql)?\s*|\s*```\s*$", re.IGNORECASE)
# Some models (e.g. nemotron's smaller siblings) inline their chain-of-thought into
# `content` instead of a separate `reasoning_content` field -- strip it before parsing.
_THINK_RE = re.compile(r"<think>.*?(?:</think>|$)", re.IGNORECASE | re.DOTALL)


class PromptNotFoundError(FileNotFoundError):
    """Raised when a prompt file is missing -- a deployment error, not a runtime one."""


class LLMResponseError(ValueError):
    """The model returned something that is not valid JSON, or does not match its schema."""


# --------------------------------------------------------------------------- prompts


@lru_cache(maxsize=64)
def _read_prompt(agent: str, name: str) -> str:
    path = _PROMPTS_ROOT / agent / "prompts" / f"{name}.txt"
    if not path.is_file():
        raise PromptNotFoundError(f"No prompt file at {path}")
    return path.read_text(encoding="utf-8")


def load_prompt(agent: str, name: str, **variables: Any) -> str:
    """Render ``agents/<agent>/prompts/<name>.txt`` with ``$placeholder`` substitution.

    ``string.Template`` rather than ``str.format`` on purpose: these prompts are full of
    literal JSON braces, which ``format`` would require escaping throughout.
    ``safe_substitute`` leaves an unknown ``$token`` alone instead of raising.
    """
    return Template(_read_prompt(agent, name)).safe_substitute(**variables)


# ------------------------------------------------------------------------ LLM output


def strip_code_fences(text: str) -> str:
    """Remove a leading ```json / ```sql fence and a trailing ``` fence."""
    if not text:
        return ""
    cleaned = _FENCE_RE.sub("", text.strip())
    return cleaned.strip()


def parse_llm_json(content: str | None, model: type[TModel]) -> TModel:
    """Parse an LLM reply into ``model``, raising ``LLMResponseError`` on any failure.

    This is the single boundary where untrusted model output becomes a typed object.
    """
    if not content:
        raise LLMResponseError("LLM returned an empty response")

    cleaned = strip_code_fences(_THINK_RE.sub("", content))
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        # Prose the model added around the JSON despite being told not to -- fall back
        # to the outermost balanced object/array in what's left.
        payload = _extract_json_span(cleaned)
        if payload is None:
            raise LLMResponseError(f"LLM response is not valid JSON: {exc}") from exc

    # `{}` is well-formed JSON that says nothing. Every schema here is a LenientModel
    # whose fields default to empty, so an empty payload validates cleanly and the
    # caller silently receives zero entities / zero sub-questions instead of an error.
    # Treated as a failure so the caller's one retry gets a real answer -- observed on
    # a 30B MoE under reduced reasoning, and the failure mode is invisible otherwise.
    if payload in ({}, []):
        raise LLMResponseError(f"LLM returned an empty JSON payload for {model.__name__}")

    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise LLMResponseError(f"LLM response failed {model.__name__} validation: {exc}") from exc


def _extract_json_span(text: str) -> Any | None:
    """The outermost balanced ``{...}`` or ``[...]`` in ``text``, or ``None``."""
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        if start == -1:
            continue
        depth = 0
        for i, ch in enumerate(text[start:], start):
            depth += (ch == open_ch) - (ch == close_ch)
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    break
    return None


# ------------------------------------------------------------------------------ misc


def json_dumps(value: Any) -> str:
    """``json.dumps`` that never explodes on dates, Decimals, or LOB objects."""
    return json.dumps(value, default=str)


def truncate(items: Sequence[Any] | None, limit: int) -> list[Any]:
    """First ``limit`` items, tolerating ``None``."""
    return list(items[:limit]) if items else []


def traced(name: str, **attributes: Any) -> Callable:
    """Wrap a sync or async callable in an OTel span, recording exceptions."""

    def decorator(func: Callable) -> Callable:
        tracer = trace.get_tracer(func.__module__)

        if iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with tracer.start_as_current_span(name, attributes=attributes) as span:
                    return await _run_traced_async(func, span, args, kwargs)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with tracer.start_as_current_span(name, attributes=attributes) as span:
                return _run_traced_sync(func, span, args, kwargs)

        return sync_wrapper

    return decorator


async def _run_traced_async(func: Callable, span: Any, args: tuple, kwargs: dict) -> Any:
    try:
        return await func(*args, **kwargs)
    except Exception as exc:
        record_exception(span, exc)
        raise


def _run_traced_sync(func: Callable, span: Any, args: tuple, kwargs: dict) -> Any:
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        record_exception(span, exc)
        raise


def record_exception(span: Any, exc: BaseException) -> None:
    """Mark a span as failed. Used by ``traced`` and by ``BaseNode``."""
    span.record_exception(exc)
    span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
