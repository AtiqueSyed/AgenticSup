"""The single LLM entry point.

Replaces six separate ``AsyncOpenAI(...)`` constructions. Every call emits a span with
``gen_ai.*`` semantic-convention attributes and token usage, so agent cost and latency
are visible per node in the trace.
"""

from typing import TypeVar

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel

from src.core.config import Settings
from src.core.logging import get_logger
from src.core.telemetry import (
    GEN_AI_INPUT_TOKENS,
    GEN_AI_OUTPUT_TOKENS,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_SYSTEM,
    get_meter,
    get_tracer,
)
from src.utils.helpers import LLMResponseError, parse_llm_json

logger = get_logger(__name__)
tracer = get_tracer(__name__)
_meter = get_meter(__name__)
_calls = _meter.create_counter("llm.calls", description="LLM completions issued")
_failures = _meter.create_counter("llm.validation_failures", description="Replies failing schema")

TModel = TypeVar("TModel", bound=BaseModel)

JSON_MODE = {"type": "json_object"}

_RETRY_SUFFIX = (
    "\n\nYour previous reply was rejected by the schema validator with this error:\n"
    "$error\n\nReturn ONLY a valid JSON object matching the requested format."
)


class LLMClient:
    """Thin, traced wrapper over the chat-completions API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY.get_secret_value(),
            base_url=settings.OPENAI_BASE_URL,
            # The free tier 503s under load ("Worker local total request limit
            # reached"), and the SDK's 600s default timeout would otherwise turn a
            # hung request into a seemingly frozen app. 120s is a deliberate middle
            # ground: a large reasoning model legitimately needs more than the ~10s a
            # chat model takes.
            max_retries=3,
            timeout=120.0,
        )
        self._model = settings.DEFAULT_LLM_MODEL

    async def complete_text(self, prompt: str, *, operation: str = "completion") -> str:
        """Free-text completion. Returns the stripped message content."""
        message = await self._chat(prompt, operation=operation, json_mode=False)
        return (message or "").strip()

    async def complete_model(
        self,
        prompt: str,
        model: type[TModel],
        *,
        operation: str = "structured",
    ) -> TModel:
        """Structured completion validated into ``model``.

        One retry: the validation error is fed back to the model, which recovers from
        most truncation and stray-prose failures. A second failure raises
        ``LLMResponseError`` for the calling node to turn into its documented fallback.
        """
        content = await self._chat(prompt, operation=operation, json_mode=True)
        try:
            return parse_llm_json(content, model)
        except LLMResponseError as exc:
            # ``exc`` is unbound after the except block, so keep the message.
            reason = str(exc)
            logger.warning("%s: %s -- retrying once", operation, reason)
            _failures.add(1, {"operation": operation, "model": model.__name__})

        retry_prompt = prompt + _RETRY_SUFFIX.replace("$error", reason)
        content = await self._chat(retry_prompt, operation=f"{operation}.retry", json_mode=True)
        return parse_llm_json(content, model)

    async def _chat(self, prompt: str, *, operation: str, json_mode: bool) -> str | None:
        mode = _reasoning_mode(self._settings, operation)
        attributes = {
            GEN_AI_SYSTEM: "openai",
            GEN_AI_REQUEST_MODEL: self._model,
            "gen_ai.operation.name": operation,
        }
        with tracer.start_as_current_span(f"llm.{operation}", attributes=attributes) as span:
            span.set_attribute("gen_ai.reasoning", mode)
            if self._settings.OTEL_CAPTURE_CONTENT:
                span.add_event("gen_ai.prompt", {"content": prompt})

            kwargs = _build_kwargs(json_mode=json_mode, reasoning_mode=mode)
            messages = [{"role": "user", "content": prompt}]
            try:
                response = await self._client.chat.completions.create(
                    model=self._model, messages=messages, **kwargs
                )
            except openai.BadRequestError as exc:
                retry_kwargs = _drop_rejected_kwarg(kwargs, exc, operation)
                response = await self._client.chat.completions.create(
                    model=self._model, messages=messages, **retry_kwargs
                )
            _record_usage(span, response)
            _calls.add(1, {"operation": operation})

            content = _message_content(_first_choice(response).message)
            if self._settings.OTEL_CAPTURE_CONTENT:
                span.add_event("gen_ai.completion", {"content": content or ""})
            return content

    async def close(self) -> None:
        await self._client.close()


def _reasoning_mode(settings: Settings, operation: str) -> str:
    """The mode for this call: 'on' or 'off'. A retry's operation is
    ``f"{base}.retry"`` -- strip that suffix so retries inherit the same mode as
    their original call."""
    base_operation = operation.split(".", 1)[0]
    if base_operation in settings.reasoning_off_operations:
        return "off"
    return settings.LLM_REASONING


def _build_kwargs(*, json_mode: bool, reasoning_mode: str) -> dict:
    """Request payload extras. ``chat_template_kwargs`` is NVIDIA NIM's reasoning
    on/off switch for nemotron models -- there is no token-budget knob, only this."""
    kwargs: dict = {"response_format": JSON_MODE} if json_mode else {}
    if reasoning_mode == "off":
        kwargs["extra_body"] = {"chat_template_kwargs": {"thinking": "off"}}
    return kwargs


def _drop_rejected_kwarg(kwargs: dict, exc: openai.BadRequestError, operation: str) -> dict:
    """Not every OpenAI-compatible endpoint implements JSON mode or the
    thinking-toggle -- drop whichever one the provider just rejected so the caller can
    retry once instead of failing the node. Re-raises if neither applies."""
    reason = str(exc)
    if "extra_body" in kwargs and ("chat_template_kwargs" in reason or "thinking" in reason):
        dropped = "extra_body"
    elif "response_format" in kwargs and "response_format" in reason:
        dropped = "response_format"
    else:
        raise exc
    logger.warning("%s: provider rejected %s, retrying without it", operation, dropped)
    return {k: v for k, v in kwargs.items() if k != dropped}


def _message_content(message) -> str | None:
    """The reply text, preferring ``content`` but falling back to ``reasoning_content``.

    NVIDIA's nemotron MoE models differ in where they put the answer: most return clean
    JSON in ``content`` with chain-of-thought in ``reasoning_content``, but some leave
    ``content`` empty and put everything in the reasoning channel. Without this fallback
    that reply is discarded as "empty response" even though the JSON is right there --
    ``parse_llm_json`` already strips ``<think>`` blocks and digs the outermost JSON span
    out of surrounding prose, so handing it the reasoning text costs nothing when
    ``content`` was fine and recovers the answer when it was not.
    """
    content = getattr(message, "content", None)
    if content and content.strip():
        return content
    return getattr(message, "reasoning_content", None) or content


def _first_choice(response):
    """The gateway answers an auth or model error with HTTP 200 and a body carrying
    ``error`` but no ``choices``, so the SDK raises nothing and ``choices[0]`` used to
    blow up as a bare ``TypeError: 'NoneType' object is not subscriptable``. Surface
    the message the provider actually sent instead."""
    if response.choices:
        return response.choices[0]
    error = getattr(response, "error", None) or {}
    if isinstance(error, dict):
        # The gateway nests the real payload one level down: {"error": {...}, "type": ...}
        error = error.get("error", error)
        detail = error.get("message") if isinstance(error, dict) else str(error)
    else:
        detail = str(error)
    raise LLMResponseError(f"LLM provider returned no choices: {detail or response}")


def _record_usage(span, response) -> None:
    """Token counts, when the provider reports them."""
    usage = getattr(response, "usage", None)
    if not usage:
        return
    span.set_attribute(GEN_AI_INPUT_TOKENS, getattr(usage, "prompt_tokens", 0) or 0)
    span.set_attribute(GEN_AI_OUTPUT_TOKENS, getattr(usage, "completion_tokens", 0) or 0)
