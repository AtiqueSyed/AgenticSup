"""`src/utils/helpers.py` -- prompt loading, LLM-output parsing, and the small utils.

The `load_prompt` tests are the regression guard for the f-string -> `string.Template`
migration: every real prompt file must still render with its variables substituted,
and the literal JSON braces the prompts are full of must survive untouched.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from src.agents.onboarding.schema_extractor import SchemaExtractor
from src.agents.query.schemas import SubQuestions
from src.utils.helpers import (
    LLMResponseError,
    PromptNotFoundError,
    json_dumps,
    load_prompt,
    parse_llm_json,
    strip_code_fences,
    truncate,
)

# ------------------------------------------------------------------ strip_code_fences


@pytest.mark.parametrize(
    "text, expected",
    [
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ("```sql\nSELECT 1\n```", "SELECT 1"),
        ("```\nSELECT 1\n```", "SELECT 1"),
        ("SELECT 1", "SELECT 1"),
        ("", ""),
    ],
)
def test_strip_code_fences(text, expected):
    assert strip_code_fences(text) == expected


# -------------------------------------------------------------------- parse_llm_json


def test_parse_llm_json_returns_model_on_good_input():
    model = parse_llm_json('{"sub_questions": ["q1"]}', SubQuestions)
    assert model == SubQuestions(sub_questions=["q1"])


def test_parse_llm_json_strips_fences_first():
    model = parse_llm_json('```json\n{"sub_questions": ["q1"]}\n```', SubQuestions)
    assert model.sub_questions == ["q1"]


def test_parse_llm_json_raises_on_empty_string():
    with pytest.raises(LLMResponseError):
        parse_llm_json("", SubQuestions)


def test_parse_llm_json_raises_on_none():
    with pytest.raises(LLMResponseError):
        parse_llm_json(None, SubQuestions)


def test_parse_llm_json_raises_on_non_json():
    with pytest.raises(LLMResponseError):
        parse_llm_json("this is not json at all", SubQuestions)


def test_parse_llm_json_raises_when_model_validation_fails():
    with pytest.raises(LLMResponseError):
        parse_llm_json('{"sub_questions": []}', SubQuestions)


def test_parse_llm_json_strips_think_block():
    """Some models (e.g. nemotron's smaller siblings) inline reasoning into `content`
    instead of a separate `reasoning_content` field."""
    content = "<think>let me work through this</think>\n" '{"sub_questions": ["q1"]}'
    model = parse_llm_json(content, SubQuestions)
    assert model.sub_questions == ["q1"]


def test_parse_llm_json_survives_unterminated_think_block():
    """A truncated reply: the `<think>` never closes, so nothing usable survives --
    this must still raise `LLMResponseError`, not hang or crash."""
    with pytest.raises(LLMResponseError):
        parse_llm_json("<think>still reasoning when the response got cut off", SubQuestions)


def test_parse_llm_json_survives_prose_around_json():
    content = 'Sure, here you go:\n{"sub_questions": ["q1"]}\nLet me know if you need more.'
    model = parse_llm_json(content, SubQuestions)
    assert model.sub_questions == ["q1"]


# ------------------------------------------------------------------------ load_prompt

# agent, prompt name, variables required to fully substitute it.
ONBOARDING_PROMPTS = [
    ("onboarding", "generate_semantics", {"schema_summary": "SCHEMA_SUMMARY_MARKER"}),
    (
        "onboarding",
        "identify_entities",
        {
            "existing_entities_context": "EXISTING_ENTITIES_MARKER",
            "schema_summary": "SCHEMA_SUMMARY_MARKER",
        },
    ),
    (
        "onboarding",
        "map_entity_columns",
        {"schema_summary": "SCHEMA_SUMMARY_MARKER", "entities_summary": "ENTITIES_SUMMARY_MARKER"},
    ),
]
QUERY_PROMPTS = [
    ("query", "decompose_query", {"question": "QUESTION_MARKER"}),
    ("query", "generate_sql", {"context_str": "CONTEXT_MARKER", "question": "QUESTION_MARKER"}),
    ("query", "recommend_visualizations", {"sample_data": "SAMPLE_DATA_MARKER"}),
    ("query", "synthesize_answer", {"question": "QUESTION_MARKER", "results_str": "RESULTS_MARKER"}),
]


@pytest.mark.parametrize("agent, name, variables", ONBOARDING_PROMPTS + QUERY_PROMPTS)
def test_load_prompt_renders_every_real_prompt(agent, name, variables):
    rendered = load_prompt(agent, name, **variables)

    # (a) substitution actually happened: every value shows up, and no leftover
    # `$var` remains for any variable we passed.
    for key, value in variables.items():
        assert value in rendered
        assert f"${key}" not in rendered


def test_identify_entities_prompt_keeps_literal_json_braces():
    """The regression case: `str.format` would choke on these literal braces, or
    `Template` could strip them if it were substituting too aggressively."""
    rendered = load_prompt(
        "onboarding",
        "identify_entities",
        existing_entities_context="[]",
        schema_summary="{}",
    )
    assert '"entities": [' in rendered
    assert "{" in rendered
    assert '"id": "CustomerGrievance"' in rendered


def test_generate_sql_prompt_keeps_literal_json_braces():
    rendered = load_prompt("query", "generate_sql", context_str="ctx", question="q")
    assert '"target_database_id"' in rendered
    assert "{" in rendered


def test_load_prompt_missing_prompt_raises():
    with pytest.raises(PromptNotFoundError):
        load_prompt("query", "does_not_exist")


def test_load_prompt_missing_agent_raises():
    with pytest.raises(PromptNotFoundError):
        load_prompt("no_such_agent", "decompose_query")


# ------------------------------------------------------------------------- truncate


def test_truncate_limits_to_first_n():
    assert truncate([1, 2, 3, 4, 5], 2) == [1, 2]


def test_truncate_tolerates_none():
    assert truncate(None, 5) == []


def test_truncate_shorter_than_limit_returns_all():
    assert truncate([1, 2], 5) == [1, 2]


# ------------------------------------------------------------------------ json_dumps


def test_json_dumps_plain_value():
    assert json_dumps({"a": 1}) == '{"a": 1}'


def test_json_dumps_handles_datetime_and_decimal_without_raising():
    payload = {"when": datetime(2024, 1, 1, 12, 0, 0), "amount": Decimal("19.99")}
    result = json_dumps(payload)
    assert isinstance(result, str)
    assert "2024-01-01" in result
    assert "19.99" in result


# ------------------------------------------------------------------- SchemaExtractor


class _FakeInspector:
    """Just enough of `Inspector.get_columns` for `describe_columns`."""

    def get_columns(self, table, schema=None):
        return [{"name": "ID", "type": "NUMBER"}, {"name": "NAME", "type": "VARCHAR2"}]


def test_describe_columns_populates_sample_values_from_sample_rows():
    """Regression: `_schema_summary` in `agents/onboarding/nodes.py` reads
    `column.sample_values` to show the LLM what the data looks like -- it used to be
    left at its default `[]` for every column, so the LLM was grounded on nothing."""
    samples = [{"ID": Decimal("1"), "NAME": "Alice"}, {"ID": Decimal("2"), "NAME": None}]
    columns = SchemaExtractor().describe_columns(_FakeInspector(), "CUSTOMERS", None, samples)
    assert [c.sample_values for c in columns] == [["1", "2"], ["Alice"]]


def test_empty_json_object_is_rejected_not_silently_defaulted():
    """`{}` validates cleanly against every LenientModel, yielding a model full of empty
    defaults. That is indistinguishable from a real answer at the call site, so the
    parser must reject it and let the caller retry."""
    with pytest.raises(LLMResponseError, match="empty JSON payload"):
        parse_llm_json("{}", SubQuestions)

    with pytest.raises(LLMResponseError, match="empty JSON payload"):
        parse_llm_json("[]", SubQuestions)


def test_a_populated_reply_still_parses():
    """The empty-payload guard must not reject legitimate content."""
    parsed = parse_llm_json('{"sub_questions": ["a", "b"]}', SubQuestions)
    assert parsed.sub_questions == ["a", "b"]
