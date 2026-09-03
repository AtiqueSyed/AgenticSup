"""`src/clients/llm.py` -- per-operation reasoning control and the BadRequestError
fallback path. No network: `AsyncOpenAI.chat.completions.create` is replaced with an
`AsyncMock` on the already-constructed client.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import openai
import pytest

from src.agents.query.schemas import SubQuestions
from src.clients.llm import LLMClient

OFF_OPERATIONS = "recommend_visualizations,decompose_query,synthesize_answer"


def _fake_response(content: str = '{"ok": true}') -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=None,
    )


def _bad_request(message: str) -> openai.BadRequestError:
    request = httpx.Request("POST", "http://test/chat/completions")
    response = httpx.Response(400, request=request, json={"error": {"message": message}})
    return openai.BadRequestError(message, response=response, body=None)


def _client_for(settings_for_test, **overrides) -> LLMClient:
    settings = settings_for_test.model_copy(update=overrides)
    client = LLMClient(settings)
    client._client.chat.completions.create = AsyncMock(return_value=_fake_response())
    return client


# --------------------------------------------------------------- per-operation mode


async def test_off_list_operation_sends_thinking_off(settings_for_test):
    client = _client_for(settings_for_test, LLM_REASONING_OFF_OPERATIONS=OFF_OPERATIONS)

    await client.complete_text("prompt", operation="recommend_visualizations")

    kwargs = client._client.chat.completions.create.call_args.kwargs
    assert kwargs["extra_body"] == {"chat_template_kwargs": {"thinking": "off"}}


async def test_operation_not_in_off_list_keeps_default_reasoning(settings_for_test):
    client = _client_for(settings_for_test, LLM_REASONING_OFF_OPERATIONS=OFF_OPERATIONS)

    await client.complete_text("prompt", operation="generate_sql")

    kwargs = client._client.chat.completions.create.call_args.kwargs
    assert "extra_body" not in kwargs


async def test_llm_reasoning_off_flips_the_default_for_every_operation(settings_for_test):
    client = _client_for(settings_for_test, LLM_REASONING="off", LLM_REASONING_OFF_OPERATIONS="")

    await client.complete_text("prompt", operation="generate_sql")

    kwargs = client._client.chat.completions.create.call_args.kwargs
    assert kwargs["extra_body"] == {"chat_template_kwargs": {"thinking": "off"}}


async def test_retry_suffixed_operation_resolves_to_its_base_mode(settings_for_test):
    client = _client_for(settings_for_test, LLM_REASONING_OFF_OPERATIONS=OFF_OPERATIONS)

    await client.complete_text("prompt", operation="decompose_query.retry")

    kwargs = client._client.chat.completions.create.call_args.kwargs
    assert kwargs["extra_body"] == {"chat_template_kwargs": {"thinking": "off"}}


def test_llm_reasoning_rejects_invalid_mode(settings_for_test):
    # `model_copy` skips validation by design, so exercise the real validator via the
    # constructor instead.
    from src.core.config import Settings

    with pytest.raises(ValueError):
        Settings(**{**settings_for_test.model_dump(), "OPENAI_API_KEY": "k", "LLM_REASONING": "verbose"})


# ---------------------------------------------------------------- BadRequestError fallback


async def test_bad_request_for_thinking_toggle_retries_without_extra_body(settings_for_test):
    client = _client_for(settings_for_test, LLM_REASONING="off")
    client._client.chat.completions.create = AsyncMock(
        side_effect=[_bad_request("Unsupported parameter: chat_template_kwargs"), _fake_response()]
    )

    content = await client.complete_text("prompt", operation="anything")

    assert content == '{"ok": true}'
    second_call_kwargs = client._client.chat.completions.create.call_args_list[1].kwargs
    assert "extra_body" not in second_call_kwargs


async def test_bad_request_for_response_format_retries_without_it(settings_for_test):
    client = _client_for(settings_for_test)
    client._client.chat.completions.create = AsyncMock(
        side_effect=[_bad_request("Unsupported parameter: response_format"), _fake_response()]
    )

    result = await client._chat("prompt", operation="structured", json_mode=True)

    assert result == '{"ok": true}'
    second_call_kwargs = client._client.chat.completions.create.call_args_list[1].kwargs
    assert "response_format" not in second_call_kwargs


async def test_bad_request_for_unrelated_reason_still_raises(settings_for_test):
    client = _client_for(settings_for_test)
    client._client.chat.completions.create = AsyncMock(side_effect=_bad_request("model not found"))

    with pytest.raises(openai.BadRequestError):
        await client.complete_text("prompt", operation="anything")


# ------------------------------------------------- reply-shape tolerance across models


def _fake_reasoning_response(content, reasoning_content):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, reasoning_content=reasoning_content)
            )
        ],
        usage=None,
    )


async def test_answer_recovered_from_reasoning_content_when_content_is_empty(settings_for_test):
    """Some nemotron MoE variants leave ``content`` empty and put the whole reply in
    ``reasoning_content``. Discarding that as an empty response loses a usable answer."""
    client = _client_for(settings_for_test)
    client._client.chat.completions.create = AsyncMock(
        return_value=_fake_reasoning_response("", '{"sub_questions": ["x"]}')
    )

    parsed = await client.complete_model("p", SubQuestions, operation="decompose_query")

    assert parsed.sub_questions == ["x"]


async def test_content_wins_when_both_are_present(settings_for_test):
    """The fallback must not shadow a good ``content`` with chain-of-thought text."""
    client = _client_for(settings_for_test)
    client._client.chat.completions.create = AsyncMock(
        return_value=_fake_reasoning_response(
            '{"sub_questions": ["real"]}', '{"sub_questions": ["thinking out loud"]}'
        )
    )

    parsed = await client.complete_model("p", SubQuestions, operation="decompose_query")

    assert parsed.sub_questions == ["real"]


async def test_empty_json_object_is_retried_not_returned_as_defaults(settings_for_test):
    """``{}`` validates against every LenientModel as "all defaults", which at the call
    site is indistinguishable from a real answer. It must trigger the retry instead."""
    client = _client_for(settings_for_test)
    client._client.chat.completions.create = AsyncMock(
        side_effect=[_fake_response("{}"), _fake_response('{"sub_questions": ["recovered"]}')]
    )

    parsed = await client.complete_model("p", SubQuestions, operation="decompose_query")

    assert parsed.sub_questions == ["recovered"]
    assert client._client.chat.completions.create.await_count == 2
