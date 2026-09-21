"""Local validation for the small JSON Schema vocabulary used by this library."""

import math

from .contracts import EvaluationError

NUMBER = {"type": "number", "minimum": 0, "maximum": 1}
TEXT = {"type": "string"}
BOOL = {"type": "boolean"}


def object_schema(properties: dict) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def validate(
    value: object, schema: dict, *, code: str = "invalid_judge_result", path: str = "$"
) -> None:
    """Validate the schema vocabulary used above, without runtime dependencies.

    Numbers exclude bool and all nonfinite values (JSON-compatible contract).
    Public callers should use validate_judge_result/validate_evaluation.
    """

    def fail(reason):
        raise EvaluationError(code, f"{path}: {reason}")

    if "oneOf" in schema:
        matches = 0
        for variant in schema["oneOf"]:
            try:
                validate(value, variant, code=code, path=path)
                matches += 1
            except EvaluationError:
                pass
        if matches != 1:
            fail("result must match exactly one result variant")
        return
    if "const" in schema:
        expected = schema["const"]
        allowed_types = (
            (int, float) if type(expected) in (int, float) else (type(expected),)
        )
        if type(value) not in allowed_types or value != expected:
            fail("unexpected constant")
    if "enum" in schema and (type(value) is not str or value not in schema["enum"]):
        fail("unexpected enum value")
    kind = schema.get("type")
    if kind == "object":
        if type(value) is not dict:
            fail("expected object")
        if any(key not in value for key in schema["required"]):
            fail("missing required fields")
        if any(key not in schema["properties"] for key in value):
            fail("unexpected fields")
        for key, child in schema["properties"].items():
            validate(value[key], child, code=code, path=f"{path}.{key}")
    elif kind == "string" and type(value) is not str:
        fail("expected string")
    elif kind == "boolean" and type(value) is not bool:
        fail("expected bool")
    elif kind == "number":
        if type(value) not in (int, float):
            fail("expected number")
        if not 0 <= value <= 1 or not math.isfinite(value):
            fail("expected finite number in [0, 1]")
