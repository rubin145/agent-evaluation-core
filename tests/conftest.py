import pytest
from agent_evaluation_core import ResponseEvaluator


@pytest.fixture
def valid_payload():
    # Literal public contract: intentionally independent of judge_schema.
    def make(commercial=False, score=0.8):
        payload = {
            'outcome': 'answer', 'jailbreak': False, 'pii_exposure': False,
            'hallucination': False, 'other_flag': False,
            'safety_score': score, 'helpfulness_score': score,
            'completeness_score': score, 'tone_professionalism_score': score,
            'bias_score': score, 'scope_adherence_score': score,
            'explanation': 'Synthetic fixture',
        }
        if commercial:
            payload.update(competitors=False, brand_alignment_score=score)
        return payload
    return make


@pytest.fixture
def judge_factory(valid_payload):
    def make(payload=None, fail=None):
        class Judge:
            def __init__(self):
                self.calls = []
                self.payload = payload if payload is not None else valid_payload()

            def chat(self, **kwargs):
                self.calls.append(kwargs)
                if fail is not None:
                    raise fail
                return self.payload
        return Judge()
    return make


@pytest.fixture
def evaluator_factory(judge_factory):
    def make(judge=None, **kwargs):
        return ResponseEvaluator(judge if judge is not None else judge_factory(), system_prompt='Synthetic test rubric',
                                 refusal_templates={'Session blocked.': 'hard'}, **kwargs)
    return make
