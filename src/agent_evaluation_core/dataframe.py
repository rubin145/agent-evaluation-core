"""Optional pandas adapter with positional identity and isolated row failures."""

from concurrent.futures import ThreadPoolExecutor

from .contracts import EvaluationError


def evaluate_dataframe(evaluator, dataframe, *, max_workers=1):
    import numpy as np
    import pandas as pd

    if not isinstance(dataframe, pd.DataFrame):
        raise EvaluationError("invalid_input", "expected a DataFrame")
    if type(max_workers) is not int or not 1 <= max_workers <= 64:
        raise EvaluationError(
            "invalid_input", "max_workers must be an integer in [1, 64]"
        )
    if not dataframe.columns.is_unique or not {"prompt", "response"}.issubset(
        dataframe.columns
    ):
        raise EvaluationError(
            "invalid_input", "unique columns including prompt and response required"
        )
    if "evaluation" in dataframe.columns:
        raise EvaluationError("invalid_input", "evaluation is a reserved output column")
    snapshot = dataframe.copy(deep=True)

    def missing(value):
        return (
            value is None
            or value is pd.NA
            or (isinstance(value, (float, np.floating)) and np.isnan(value))
        )

    def optional_text(value):
        return None if missing(value) else value

    def scope(value):
        if missing(value):
            return None
        if isinstance(value, (bool, np.bool_)):
            return bool(value)
        raise EvaluationError(
            "invalid_input",
            "out_of_scope must be bool or missing; 0/1 and strings are not accepted",
        )

    def run(row):
        try:
            technical = row.get("technical_error", False)
            if isinstance(technical, np.bool_):
                technical = bool(technical)
            result = evaluator.evaluate_pair(
                row["prompt"],
                row["response"],
                out_of_scope=scope(row.get("out_of_scope")),
                conversation_context=optional_text(row.get("conversation_context")),
                scenario=optional_text(row.get("scenario")),
                technical_error=technical,
            )
            return {"status": "ok", "result": result}
        except EvaluationError as exc:
            return {"status": "error", "error": exc.as_dict()}

    # map preserves input position even when completion order differs. Labels are
    # never interpreted as offsets; assignment uses a list, not index alignment.
    rows = snapshot.to_dict(orient="records")
    if max_workers == 1:
        records = [run(row) for row in rows]
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            records = list(executor.map(run, rows))
    snapshot["evaluation"] = records
    return snapshot
