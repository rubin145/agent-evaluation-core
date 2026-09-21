# API reference

See the [runnable example](../README.md#example) for a complete judge client.

The system prompt is mandatory, nonempty and owned by the caller. No hidden template resources are loaded. The judge receives current prompt, response, scenario, history, scope and policy version as distinct JSON fields. User fields are marked as data; this does not establish resistance to prompt injection. Rubrics need task-specific evidence and human calibration. The core cannot independently verify claims in a response.

`JudgeClient.chat` receives `messages` (immutable `Message` objects with `role` and `content`), `model`, `temperature`, `max_tokens`, `json_schema` and `schema_name`. `EvalConfig` defaults to no model override, temperature 0 and 1000 output tokens; token limits must be positive integers. The client returns the judgment **dictionary directly**, matching `judge_schema()`. It owns decoding JSON and extracting SDK/envelope fields; no transport shape is required or accepted by the core. Malformed JSON, duplicate keys and nonfinite JSON constants should be rejected by the adapter before returning a dictionary. Transport/decoding exceptions become `judge_call_failed`; an invalid returned dictionary becomes `invalid_judge_result`.

Required judge fields, enums, exact booleans, finite scores in `[0,1]`, and unexpected fields are checked locally, even if the provider claims schema support. NaN and Infinity in returned values are rejected. Payloads are copied before adding derived results. `judge_schema(commercial=False)` describes the selected input contract; `evaluation_schema()` describes structural output variants and discrete constants. `validate_evaluation()` additionally recomputes **all four derived fields** for judged results using the selected policy. Derived numbers must equal the four-decimal outputs of `aggregate()` exactly (no tolerance or silent repair); serialize those outputs without recalculating them. JSON Schema alone cannot check these arithmetic relationships. Neither validator checks whether the judge's factual judgments are true. Pass the same `commercial` option to schema/validation functions as the evaluator.

## Rules and results

Rules run in this order:

| Condition | `kind` | Judge calls | Aggregate |
|---|---|---:|---:|
| `technical_error=True`, or whitespace-only response | `system_error` | 0 | 0.0 |
| Configured exact refusal, scope `True` | `refusal`, judgement `correct` | 0 | 1.0 |
| Configured exact refusal, scope `False` | `refusal`, judgement `incorrect` | 0 | 0.1 |
| Configured exact refusal, scope `None` | `refusal`, judgement `unknown` | 0 | `None` |
| All other text | `judged` (`answer` or `gen_refusal`) | 1 | Derived |

Every successful result has `eval_id`, `policy_version`, `kind`, `outcome`, `aggregate_score` and `explanation`. Judged results also contain all selected flags/scores and derived means. Technical results include a reason; refusal results include type and judgement. The output JSON Schema discriminates these variants and disallows extra fields. Unknown refusal scores are deliberately absent as a number: do not coerce `None` to zero or approval. A generated refusal from the judge has full dimensions, unlike an exact template refusal.

`out_of_scope` means suitability to the caller's task; it is **not a safety policy**. The pair API accepts only `True`, `False` or `None`; strings, integers and NaN are rejected. `conversation_context` and `scenario` accept strings or `None`. Prompt/response must be strings. `technical_error` is an exact bool and takes precedence over refusal detection.

The provider adapter must extract response text and report technical state explicitly. JSON text such as `{"body_text":""}` is ordinary text, not an envelope interpreted by this core. Quoted technical messages, AI disclosures and substrings never trigger technical failure. Refusal rules are opt-in, strip only leading/trailing whitespace and require a full, case-sensitive match. There are no implicit provider-specific phrases or incomplete-response shortcuts.

Evaluator failures raise `EvaluationError` with `code`: `invalid_input`, `judge_call_failed`, `invalid_judge_result` or `invalid_evaluation`. Provider failures retain their exception as the local cause but expose only its type in the public message. No retries, persistence, logging or request/response telemetry run inside the core. The adapter owns transport timeout/cancellation; a blocking `chat` can block evaluation.

## DataFrame evaluation

```python
results = evaluator.evaluate_dataframe(frame, max_workers=1)
```

Input needs unique columns `prompt` and `response`. Optional columns: `out_of_scope`, `conversation_context`, `scenario`, `technical_error`. The result preserves all input columns, row order, index labels, duplicate indices, MultiIndex and index names, then adds **one `evaluation` column**. Existing `evaluation` columns and duplicate column names are rejected, avoiding silent overwrites. Empty frames preserve their schema/index. The input is not modified.

Each evaluation cell is either `{"status": "ok", "result": ...}` or `{"status": "error", "error": {"code": ..., "message": ...}}`. Input/judge failures affect only that row. Original text/history remain in the output frame; callers own storage and redaction. Scope normalizes pandas/numpy bools to bool and `None`/NaN/`pd.NA` to unknown; `0/1` and strings remain errors. Optional text columns normalize the same missing values to `None`; missing prompt/response and missing technical state are errors.

Workers must be integers in `[1,64]`; default 1 runs synchronously in the calling thread, preserving client thread affinity. Values above 1 run in worker threads and require a client that permits cross-thread use and concurrent calls. Completion order never changes output order. This is an in-memory batch adapter, not a streaming scheduler, timeout manager or durable queue.
