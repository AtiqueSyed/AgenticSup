# Models

Reference for swapping the LLM this backend talks to. Read this before changing
`DEFAULT_LLM_MODEL`, or before assuming a new "thinking budget" knob does what its name
implies -- one of them doesn't, and it fails silently.

## Configuration

There is deliberately no provider-abstraction layer. The backend talks to one
OpenAI-compatible endpoint via `AsyncOpenAI` (`backend/src/clients/llm.py`), configured
entirely by three variables in `backend/.env`:

| Variable | Current value |
|---|---|
| `OPENAI_API_KEY` | NVIDIA NIM key |
| `OPENAI_BASE_URL` | `https://integrate.api.nvidia.com/v1` |
| `DEFAULT_LLM_MODEL` | `nvidia/nemotron-3-super-120b-a12b` |

Swapping providers (NVIDIA -> OpenAI, Together, vLLM, whatever else speaks the
OpenAI chat-completions shape) is a three-line `.env` edit, not a code change --
that's the whole point of not building an abstraction for it.

Reasoning is a separate axis from model choice, controlled by `LLM_REASONING`
(`on`/`off`, default `on`) and `LLM_REASONING_OFF_OPERATIONS` (comma-separated
operation names to force off regardless of the default) in `backend/src/core/config.py`.
See [Reasoning control](#reasoning-control-what-works-and-what-lies) for what these
map to on the wire and which of the plausible-looking alternatives don't work.

## Model entitlement

This NVIDIA NIM account's key lists 81 models at the `/v1/models` endpoint. Only 3 are
actually callable -- every other one, including every `llama-3.1-nemotron-*` id,
`nemotron-4-340b`, and `mistral-nemotron`, returns `404 ... Not found for account`.
Listed-but-not-entitled is the normal state for this key, not a misconfiguration.

| Model | Status |
|---|---|
| `nvidia/nemotron-3-super-120b-a12b` | Current default. JSON mode honored. Reasoning arrives in a separate `reasoning_content` field. |
| `nvidia/nemotron-3-ultra-550b-a55b` | Works. Untested at length. |
| `nvidia/nemotron-3.5-lightning-30b-a3b` | Works, but see [the latency trap](#the-latency-trap) below before defaulting to it for "it's smaller" reasons. |

Before trying any other model id, hit the endpoint directly and check for a 404 rather
than assuming the docs' full model list applies to this key.

## The latency trap

Smaller model is not faster here. Measured, identical prompt:

| Config | Latency | Completion tokens | `reasoning_content` chars |
|---|---|---|---|
| super-120b, default | 16.2s | 877 | 3,142 |
| lightning-30b, default | 78.1s | 2,957 | 11,872 |
| lightning-30b, second sample | 131.7s | 4,028 | 16,068 |
| super-120b + thinking off | 3.7s | 107 | 0 |
| super-120b + `reasoning_effort` low | 1.9s | 106 | 152 |
| lightning-30b + thinking off | 3.2s | 142 | 0 |
| lightning-30b + `reasoning_effort` low | 91.6s | 3,799 | 14,989 |

The 30B model is ~5x slower than the 120B by default because it emits ~4x the
reasoning tokens. Latency here is roughly `tokens emitted x per-token cost`; a smaller
model wins the second term and loses the first, and on this pair it loses badly enough
to erase the size advantage entirely.

`reasoning_effort` helps super-120b (16.2s -> 1.9s) but is ignored, or
counterproductive, on lightning (78.1s -> 91.6s, worse). Reasoning-control knobs are
per-model, not per-provider -- verify each new model individually, don't assume a knob
that worked on one model works on another from the same vendor.

## Reasoning control: what works and what lies

All four rows below were sent as `extra_body` on the same chat-completions call.

| Payload | Result |
|---|---|
| `{"chat_template_kwargs": {"thinking": "off"}}` | **Works.** This is the real switch. |
| `{"reasoning_effort": "low"}` | Works on super-120b. Ignored on lightning (see table above). |
| `{"max_thinking_tokens": 128}` | HTTP 400: `Validation: Unsupported parameter(s)`. Fails loudly -- safe. |
| `{"thinking": {"type": "enabled", "budget_tokens": 128}}` | **Accepted (HTTP 200) and silently ignored.** Full reasoning still emitted. This is the dangerous one: the request succeeds, so nothing in logs or status codes tells you the budget was never applied. |

There is no token-budget dial on this endpoint. Reasoning is a switch (on/off, plus a
per-model `reasoning_effort` enum where it's honored at all), not a slider. Do not
build a feature around `budget_tokens` or `max_thinking_tokens` against this provider --
the first is a no-op, the second is rejected outright.

## Output shape: `reasoning_content`

For all three entitled models, reasoning text arrives in a separate
`reasoning_content` message field; `content` is clean JSON (or clean prose for
`complete_text` calls). The codebase does not currently rely on this being true for
every provider: `backend/src/utils/helpers.py` (`_THINK_RE`) strips `<think>...</think>`
tags out of `content` as insurance, because some models inline reasoning into the main
content field instead of using a side channel.

If a future model inlines `<think>` tags (as `_THINK_RE` already assumes some do):

- No code change is needed for JSON parsing -- `_THINK_RE` already strips it before
  `parse_llm_json` runs.
- Check `OTEL_CAPTURE_CONTENT` spans (`gen_ai.completion`) to see raw content and
  confirm the tags are actually being stripped for that model's specific tag format.
- If the model uses a different inline delimiter than `<think>...</think>`, `_THINK_RE`
  needs a new pattern -- that's a `backend/src/utils/helpers.py` change, out of scope
  for this doc's owner.

## How to swap a model

1. Edit `DEFAULT_LLM_MODEL` in `backend/.env`.
2. Hit the endpoint directly first, outside the app, to confirm the model id isn't a
   404 for this account (see [Model entitlement](#model-entitlement)).
3. Verify JSON mode is honored -- `backend/src/clients/llm.py` already retries once
   without `response_format` on a `BadRequestError` mentioning it, but confirm the
   retry isn't silently firing every call (check for repeated "provider rejected
   response_format" warnings in logs).
4. Verify reasoning placement -- check one raw response for whether reasoning lands in
   `reasoning_content` or gets inlined into `content`. If inlined, see the `<think>`
   note above.
5. Re-run the SQL correctness check (`make smoke`, or `scripts/smoke_e2e.py
   --skip-onboard`) -- a model swap changes SQL generation quality, not just latency.
6. If the new model claims a reasoning-control knob, test it directly against the
   endpoint before wiring it in -- per this doc, one of NVIDIA's own knobs
   (`budget_tokens`) is silently ignored while looking like it works. Assume nothing
   until you've seen the token counts change.

## What we measured vs. what we assumed

- **Measured**: the entitlement table, the latency table, the reasoning-control table,
  and the `reasoning_content` field placement -- all probed live against the real
  endpoint.
- **Measured, one Jaeger trace**: a `POST /api/v1/query` on super-120b with reasoning
  on, total 52.8s, broken down as `decompose_query` 2.9s / `retrieve_context` 0.06s /
  `generate_sql` 10.3s / `execute_sql` 0.15s / `validate_results` 0.0s /
  `synthesize_answer` 13.3s / `recommend_visualizations` 26.1s. Combined Oracle + Neo4j
  + Elasticsearch + embeddings time across the whole trace: 211ms, 0.4% of total. This
  is a latency-bound LLM pipeline, not a database-bound one -- optimizing anything
  other than LLM calls (fewer/cheaper calls, reasoning off where correctness allows,
  parallelizing independent nodes) is wasted effort until that ratio changes.
- **Assumed, not measured**: that ultra-550b behaves like the other two at length, that
  the entitlement list is stable over time, that other NVIDIA NIM accounts have the
  same 3-of-81 entitlement split, and that non-NVIDIA OpenAI-compatible providers
  expose the same `chat_template_kwargs.thinking` switch. Treat all of these as
  unverified until someone measures them.

## Reasoning: measured impact per node

Chain-of-thought, not model size, dominates this app's latency. Measured with the app's
own prompts and schemas (`backend/scripts/bench_llm.py`, median of 3 repeats):

| Node | on | off | effort_low | schema-valid |
|---|---|---|---|---|
| `decompose_query` | 2.04s | 0.66s | 0.70s | 3/3 all modes |
| `generate_sql` | 5.96s | 1.71s | 1.19s | 3/3 all modes |
| `recommend_visualizations` | 2.89s | 1.16s | 1.36s | 3/3 all modes |
| `synthesize_answer` | 2.98s | 0.90s | 2.17s | free text, no schema |
| `generate_semantics` | 12.60s | 4.98s | 2.83s | 3/3 all modes |
| `identify_entities` | 43.54s | 12.32s | 14.61s | 3/3 all modes |
| `map_entity_columns` | 20.93s | 2.94s | 6.01s | 3/3 all modes |

### Why the config does not simply turn reasoning off everywhere

Schema validity is not quality. Every cell above is 3/3 valid, and two measurements
that the validity column cannot see decided the actual configuration:

**`generate_sql` keeps reasoning ON.** `backend/scripts/eval_sql_reasoning.py` ran 9
questions x 2 modes x 3 repeats against live Oracle: 27/27 parse, execute and plausible
in *both* modes, off being 4.9x faster (7.8s -> 1.6s). It looks safe. But on "how many
complaints were closed vs still open?", reasoning-off emitted a plain
`GROUP BY STATUS_CODE` where reasoning-on emitted an explicit closed/open
`SUM(CASE WHEN ...)`. Both scored correct only because all 1000 seeded rows share one
`STATUS_CODE`. On data with mixed statuses the reasoning-off query still executes, still
returns real columns, still passes every automated check -- and answers a
differently-shaped question.

**Onboarding keeps reasoning ON.** `identify_entities` on `CMS.CASES` returns 12
fine-grained entities with reasoning on (`Bank`, `Branch`, `State`, `District`, ...) and
8 coarse ones with it off (`BankBranch`, `GeographicLocation`, `CaseLifecycle`, ...) --
an overlap of 1. Both parse cleanly. Entities are what kNN retrieval matches questions
against, so a coarser set permanently degrades table retrieval for every later query.
Onboarding runs once per database and its output is durable; a query is transient. The
3.4x saving is not worth a worse knowledge graph.

Reasoning is therefore off only where the output is a transient presentation concern:
`decompose_query`, `synthesize_answer`, `recommend_visualizations`. Measured end to end
on one `POST /api/v1/query`, that took **52.8s -> 5.1s (10.3x)** with identical results
and a still-correct chart.

The lesson generalises: when evaluating a cheaper model or mode, an automated check can
only tell you the output is *well-formed*. Whether it is *right* needs a comparison
against the expensive mode's output, on data where the two can actually differ.

## Swapping to any NVIDIA 30B-120B MoE model

Model ids churn. `nvidia/nemotron-3-nano-30b-a3b` returned **HTTP 410 Gone** --
"reached its end of life on 2026-09-01" -- three days after that date, and a 410 is a
different problem from the 404 an unentitled model returns. Do not hard-code an
assumption about any one id; assume instead that the next model differs on every axis
below, and that the client must survive each difference without a code change.

### What varies, and what the code does about it

| Axis | Observed variants | Handling |
|---|---|---|
| JSON mode | honored / HTTP 400 / accepted-then-ignored (returns prose) | `_drop_rejected_kwarg` retries once without `response_format`; `parse_llm_json` digs the outermost JSON span out of surrounding prose |
| Reasoning location | separate `reasoning_content` / inlined `<think>` in `content` / absent | `_THINK_RE` strips inline tags; `_message_content` falls back to `reasoning_content` when `content` is blank |
| Reasoning switch | works / HTTP 400 / accepted-then-ignored | `_drop_rejected_kwarg` retries once without `extra_body`; an ignored switch costs latency, never correctness |
| Empty reply | `{}` -- valid JSON, validates as all-defaults | `parse_llm_json` rejects `{}`/`[]`, so the caller's one retry fires instead of silently returning zero entities |
| Schema drift | fields missing or extra | `LenientModel` ignores extras; a missing required field fails validation and feeds the error back on retry |
| Availability | 404 not entitled / 410 end-of-life / 503 rate limited | 404 and 410 propagate loudly (they are config errors, not runtime ones); 503 is retried by the SDK (`max_retries=3`) |

The design rule: **a provider quirk may cost latency, never silent wrongness.** Every
row above either degrades to a slower-but-correct path or raises. None of them return a
plausible-looking wrong answer.

### Before swapping

Run the preflight against the new endpoint and id:

```bash
uv run python scripts/check_model_compat.py --model <id> [--base-url http://on-prem:8000/v1]
```

It reports PASS/WARN/FAIL for reachability, JSON mode, reasoning placement, whether the
reasoning switch actually reduces output (it detects accepted-but-ignored), and whether
the app's real prompts still produce schema-valid `SqlPlan` and `SubQuestions`. Exit
code is non-zero on any FAIL, so it can gate a deploy.

Then re-check quality, not just validity -- the two are independent, and validity is the
one that lies:

```bash
uv run python scripts/eval_sql_reasoning.py    # SQL correctness against live Oracle
uv run python scripts/bench_llm.py             # latency + schema validity per node
uv run python scripts/smoke_e2e.py             # end to end
```

**On-prem note.** Entitlement (404) is an NVIDIA-account concept that will not exist on a
self-hosted vLLM or NIM container, so a 404 here says nothing about whether the same
weights will serve on-prem. What does carry over is the reply *shape* -- JSON mode
support, reasoning placement, and whether `chat_template_kwargs` is wired into the served
chat template at all. Self-hosted stacks frequently differ from the hosted API on exactly
those three, which is why the preflight takes a `--base-url`.
