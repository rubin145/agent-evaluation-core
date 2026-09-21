"""Offline control-flow example. Synthetic scores are not measured model quality."""

import json

from agent_evaluation_core import ResponseEvaluator


class FixtureJudge:
    def __init__(self):
        self.calls = 0

    def chat(self, **kwargs):
        self.calls += 1
        return {
            "outcome": "answer",
            "jailbreak": False,
            "pii_exposure": False,
            "hallucination": False,
            "other_flag": False,
            "safety_score": 0.8,
            "helpfulness_score": 0.8,
            "completeness_score": 0.8,
            "tone_professionalism_score": 0.8,
            "bias_score": 0.8,
            "scope_adherence_score": 0.8,
            "explanation": "Synthetic fixture; not measured model quality.",
        }


def run_demo():
    judge = FixtureJudge()
    evaluator = ResponseEvaluator(
        judge,
        system_prompt="Demonstrate control flow using fictitious museum data.",
        refusal_templates={"Session blocked.": "hard"},
    )
    cases = [
        ("empty", "", False),
        ("hard refusal", "Session blocked.", False),
        ("unknown scope refusal", "Session blocked.", None),
        ("ordinary answer", "The fictional museum opens at ten.", False),
    ]
    outputs = []
    for name, response, scope in cases:
        before = judge.calls
        result = evaluator.evaluate_pair(
            "When does the fictional museum open?", response, out_of_scope=scope
        )
        result.pop("eval_id")
        outputs.append(
            {
                "case": name,
                "synthetic_judge_calls": judge.calls - before,
                "result": result,
            }
        )
    return outputs


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2, allow_nan=False))
