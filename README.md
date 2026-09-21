# Agent Evaluation Core

Evaluate agent responses with deterministic rules and an LLM judge. Keep the
individual judgments alongside a score computed with explicit weights and caps.

The library handles three paths: technical failures, configured refusal messages,
and responses that need a judge. You supply the judge client and evaluation rubric.

## Installation

Python 3.11 or later.

```sh
git clone https://github.com/rubin145/agent-evaluation-core.git
cd agent-evaluation-core
python -m pip install .
```

The core has no runtime dependencies. For DataFrame evaluation, install `'.[dataframe]'`.

## Example

This example runs without credentials or a model. The client returns a fixed
judgment so you can see the complete interface and resulting score.

```python
from agent_evaluation_core import ResponseEvaluator


class ExampleJudge:
    def chat(self, **kwargs):
        return {
            "outcome": "answer",
            "jailbreak": False,
            "pii_exposure": False,
            "hallucination": False,
            "other_flag": False,
            "safety_score": 1.0,
            "helpfulness_score": 1.0,
            "completeness_score": 1.0,
            "tone_professionalism_score": 1.0,
            "bias_score": 1.0,
            "scope_adherence_score": 1.0,
            "explanation": "The answer matches the supplied opening hours.",
        }


evaluator = ResponseEvaluator(
    ExampleJudge(),
    system_prompt="The museum opens at 10:00. Evaluate answers against this fact.",
)
result = evaluator.evaluate_pair(
    "When does the museum open?",
    "At 10:00.",
    out_of_scope=False,
)
print(result["kind"])             # judged
print(result["aggregate_score"])  # 1.0
print(result["explanation"])
```

To use a model, implement `JudgeClient.chat`: send the supplied messages and JSON
schema to your provider and return the decoded judgment dictionary. The library
validates it and computes the aggregate. See the [client contract](docs/api.md)
and a [complete example rubric](RUBRIC.md).

## Results

| Input | Result | Calls to the judge |
|---|---|---:|
| Empty response or reported technical failure | `system_error` | 0 |
| A configured, exact refusal message | `refusal` | 0 |
| Other responses | `judged`, with flags and scores | 1 |

A failed judge call raises `EvaluationError`; it does not become a score for the
agent. Refusal rules are optional, and their correctness depends on whether the
request is in scope. Unknown scope produces no numeric refusal score.

## Reading the score

The default policy combines a weighted flag score and a weighted quality score,
then applies caps for violations. For example, a hallucination caps the result
at 0.6. A separate commercial profile adds brand and competitor dimensions.

**The aggregate is a policy score, not a probability or a calibrated measure of
quality.** With no negative flags and all quality scores at zero, it is still
0.5. Keep the dimensions when interpreting results, and compare runs using the
same policy, rubric and judge configuration. See [weights, caps and conventions](docs/scoring.md).

## Batch evaluation

With the DataFrame extra installed:

```python
results = evaluator.evaluate_dataframe(frame, max_workers=1)
```

`frame` needs `prompt` and `response` columns. The adapter preserves rows and
indices and adds an `evaluation` column containing a result or error per row.
Multiple workers require a thread-safe judge client. See [batch options](docs/api.md#dataframe-evaluation).

## Development

Run the four-case demo with `python demo.py`. Tests, packaging checks and code
layout are described in [development](docs/development.md).
