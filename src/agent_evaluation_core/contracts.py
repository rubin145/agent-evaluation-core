"""Small, provider-independent boundary; adapters own transport and extraction."""

from dataclasses import dataclass
from typing import Protocol


class EvaluationError(Exception):
    """An evaluator failure, never an agent score. `code` is machine-readable."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

    def as_dict(self) -> dict:
        return {"code": self.code, "message": str(self)}


@dataclass(frozen=True)
class Message:
    role: str
    content: str


class JudgeClient(Protocol):
    def chat(
        self,
        *,
        messages: list[Message],
        model: str | None,
        temperature: float,
        max_tokens: int,
        json_schema: dict,
        schema_name: str,
    ) -> dict:
        """Return the judgment dictionary described by json_schema directly.

        Adapters own JSON parsing and SDK/envelope extraction. Raise an Exception
        on transport or decoding failures. The core does not retry,
        persist, log request bodies, or instantiate provider clients.
        """
