"""Independent evaluation core; no provider, persistence or Workbench imports."""

from .aggregation import aggregate
from .contracts import EvaluationError, JudgeClient, Message
from .evaluator import EvalConfig, ResponseEvaluator
from .schema import (
    evaluation_schema,
    judge_schema,
    validate_evaluation,
    validate_judge_result,
)

__all__ = [
    "aggregate",
    "EvaluationError",
    "JudgeClient",
    "Message",
    "EvalConfig",
    "ResponseEvaluator",
    "evaluation_schema",
    "judge_schema",
    "validate_evaluation",
    "validate_judge_result",
]
