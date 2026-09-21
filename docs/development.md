# Development and distribution

```sh
uv sync --frozen --extra dataframe
uv run --frozen --extra dataframe pytest -q
uv run --frozen python demo.py
uv build
```

After dependencies are installed, these tests and the demo can run offline.
They do not call a model provider. The demo exercises four evaluation paths with
fixed synthetic judgments; the example rubric is defined in [RUBRIC.md](../RUBRIC.md).

## Verify installed packages

After building, run:

```sh
uv run --frozen python tests/check_distribution.py
```

This installs the wheel and source distribution in temporary environments outside
the checkout and checks imports and the demo. The script uses offline installs,
so uv and the required build tooling must already be cached. Add `--full` to run
the test suite against the wheel on Python 3.11, 3.12 and 3.13, with each
interpreter and its optional/development dependencies available locally.

## Code layout

- `policy.py`: dimension weights and policy versions.
- `validation.py`: the small schema vocabulary used for local value checks.
- `aggregation.py`: weighted scoring and caps; no judge or result-schema dependency.
- `schema.py`: judge/result contracts and consistency checks using the aggregator.
- `evaluator.py`: input checks, deterministic rules and judge orchestration.
- `contracts.py`: client protocol, messages and errors.
- `dataframe.py`: optional pandas batching, preserving input row order.

Both aggregation and schemas use the same policy and value checks. Result
validation calls aggregation to verify derived values; aggregation never imports
result schemas. The pandas import remains lazy so core installations do not need it.
