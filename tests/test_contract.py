from copy import deepcopy
import json
import math
import pytest
from jsonschema import Draft202012Validator
from agent_evaluation_core import (EvaluationError, EvalConfig, ResponseEvaluator, aggregate,
                                   evaluation_schema, judge_schema, validate_evaluation)
from agent_evaluation_core.schema import dimensions


@pytest.mark.parametrize('key,value', [
    ('safety_score', 2), ('safety_score', -0.1), ('safety_score', float('nan')),
    ('safety_score', float('inf')), ('safety_score', -float('inf')),
    ('safety_score', True), ('safety_score', '0.8'), ('safety_score', None),
    ('jailbreak', 'false'), ('jailbreak', 0), ('jailbreak', None),
    ('outcome', 'system_error'), ('outcome', None), ('explanation', None),
    ('aggregate_score', 1), ('extra', 'surplus')])
def test_invalid_judge_values_rejected(key, value, valid_payload, judge_factory, evaluator_factory):
    payload = valid_payload(); payload[key] = value
    judge = judge_factory(payload)
    with pytest.raises(EvaluationError) as err:
        evaluator_factory(judge).evaluate_pair('Actual turn', 'answer')
    assert err.value.code == 'invalid_judge_result'


@pytest.mark.parametrize('commercial', [False, True])
def test_every_required_field_and_strict_schema(commercial, valid_payload, judge_factory):
    valid = valid_payload(commercial)
    Draft202012Validator.check_schema(judge_schema(commercial))
    for key in valid:
        payload = {k: v for k, v in valid.items() if k != key}
        judge = judge_factory(payload)
        evaluator = ResponseEvaluator(judge, system_prompt='Fixture', commercial=commercial)
        with pytest.raises(EvaluationError) as err:
            evaluator.evaluate_pair('turn', 'answer')
        assert err.value.code == 'invalid_judge_result'


@pytest.mark.parametrize('payload', [None, [], '{}', {}, {'choices': []},
    {'choices': [{'message': {'parsed': {}}}]},
    {'choices': [{'message': {'parsed': None, 'content': '{}'}}] * 2},
])
def test_non_judgment_returns_rejected(payload, judge_factory, evaluator_factory):
    judge = judge_factory()
    judge.payload = payload
    with pytest.raises(EvaluationError) as err:
        evaluator_factory(judge).evaluate_pair('turn', 'answer')
    assert err.value.code == 'invalid_judge_result'


def test_provider_error_is_not_agent_error(judge_factory, evaluator_factory):
    with pytest.raises(EvaluationError) as err:
        evaluator_factory(judge_factory(fail=RuntimeError('sensitive provider detail'))).evaluate_pair('turn', 'answer')
    assert err.value.code == 'judge_call_failed'
    assert 'sensitive' not in str(err.value)
    assert isinstance(err.value.__cause__, RuntimeError)


@pytest.mark.parametrize('commercial', [False, True])
def test_judged_output_validated_and_payload_not_mutated(commercial, valid_payload, judge_factory):
    payload = valid_payload(commercial); before = deepcopy(payload)
    judge = judge_factory(payload)
    evaluator = ResponseEvaluator(judge, system_prompt='Fixture', commercial=commercial)
    result = evaluator.evaluate_pair('Actual current turn?', 'answer', out_of_scope=False,
                                     scenario='Original scenario', conversation_context='Previous user and assistant turn')
    assert result['scores_avg'] == .8
    assert result['aggregate_score'] == .9
    assert payload == before
    request = json.loads(judge.calls[0]['messages'][1].content)
    assert request == {'current_prompt': 'Actual current turn?', 'response': 'answer',
                       'scenario': 'Original scenario', 'conversation_context': 'Previous user and assistant turn',
                       'out_of_scope': False, 'policy_version': 'commercial-v2' if commercial else 'core-v2'}
    Draft202012Validator(evaluation_schema(commercial)).validate(result)
    assert validate_evaluation(result, commercial=commercial) == result


@pytest.mark.parametrize('scope,judgement,score', [(True, 'correct', 1.0), (False, 'incorrect', .1), (None, 'unknown', None)])
def test_refusal_known_and_unknown(scope, judgement, score, evaluator_factory):
    evaluator = evaluator_factory()
    result = evaluator.evaluate_pair('turn', ' Session blocked. ', out_of_scope=scope)
    assert result['refusal_judgement'] == judgement
    assert result['aggregate_score'] == score
    assert evaluator.client.calls == []
    Draft202012Validator(evaluation_schema()).validate(result)


@pytest.mark.parametrize('scope', [float('nan'), 'false', 0, 1, [], {}])
def test_pair_scope_strict(scope, evaluator_factory):
    with pytest.raises(EvaluationError) as err:
        evaluator_factory().evaluate_pair('turn', 'Session blocked.', out_of_scope=scope)
    assert err.value.code == 'invalid_input'


@pytest.mark.parametrize('scope', [True, False, None])
def test_scope_is_passed_to_ordinary_judge(scope, evaluator_factory):
    evaluator = evaluator_factory()
    evaluator.evaluate_pair('turn', 'answer', out_of_scope=scope)
    assert json.loads(evaluator.client.calls[0]['messages'][1].content)['out_of_scope'] is scope


@pytest.mark.parametrize('response,technical', [('', False), (' \n\t', False), ('Session blocked.', True), ('answer', True)])
def test_technical_precedence_and_schema(response, technical, evaluator_factory):
    evaluator = evaluator_factory()
    result = evaluator.evaluate_pair('turn', response, technical_error=technical, out_of_scope=True)
    assert result['kind'] == 'system_error'
    assert result['aggregate_score'] == 0
    assert evaluator.client.calls == []
    Draft202012Validator(evaluation_schema()).validate(result)


@pytest.mark.parametrize('response', [
    '{"body_text":""}', '{"body_text": ""}',
    'Example: {"body_text":""}. Actual answer here.',
    'We explain Session blocked. here.',
    'Experimentamos un problema técnico y no pudimos procesar su solicitud. Por favor, inténtelo de nuevo más tarde.',
    'Hola, soy un asistente virtual y mis respuestas son generadas por IA.'
])
def test_text_is_not_provider_envelope(response, evaluator_factory):
    evaluator = evaluator_factory()
    assert evaluator.evaluate_pair('turn', response)['kind'] == 'judged'
    assert len(evaluator.client.calls) == 1


def test_refusal_rules_are_opt_in(judge_factory):
    judge = judge_factory()
    assert ResponseEvaluator(judge, system_prompt='Fixture').evaluate_pair('turn', 'Session blocked.')['kind'] == 'judged'


@pytest.mark.parametrize('kwargs', [{'max_tokens': 0}, {'max_tokens': True}, {'max_tokens': 2.5},
                                   {'temperature': float('nan')}, {'temperature': True},
                                   {'temperature': 3}, {'model': ''}])
def test_config_rejects_invalid_limits(kwargs):
    with pytest.raises(EvaluationError):
        EvalConfig(**kwargs)


def test_config_forwarding(judge_factory):
    judge = judge_factory()
    ResponseEvaluator(judge, system_prompt='Fixture', config=EvalConfig(model='fake', temperature=.3, max_tokens=42)).evaluate_pair('turn', 'answer')
    assert {k: judge.calls[0][k] for k in ('model', 'temperature', 'max_tokens')} == {'model': 'fake', 'temperature': .3, 'max_tokens': 42}


@pytest.mark.parametrize('commercial', [False, True])
def test_all_flags_monotonic_and_caps_combine(commercial):
    from itertools import product
    flags, scores = dimensions(commercial)
    for bits in product((False, True), repeat=len(flags)):
        data = dict(zip(flags, bits)); data.update({k: 1.0 for k in scores})
        before = deepcopy(data)
        result = aggregate(data, commercial=commercial)
        assert data == before
        assert math.isfinite(result['aggregate_score']) and 0 <= result['aggregate_score'] <= 1
        if data['empty_flag'] or data['api_error_flag']:
            assert result['aggregate_score'] <= .3
        for flag in flags:
            worse = {**data, flag: True}
            assert aggregate(worse, commercial=commercial)['aggregate_score'] <= result['aggregate_score']


def test_zero_scores_have_half_aggregate():
    flags, scores = dimensions()
    assert aggregate({**dict.fromkeys(flags, False), **dict.fromkeys(scores, 0)})['aggregate_score'] == .5


def test_general_profile_has_no_commercial_dimensions():
    assert 'competitors' not in judge_schema()['properties']
    assert 'brand_alignment_score' not in judge_schema()['properties']
    assert 'competitors' in judge_schema(True)['properties']


@pytest.mark.parametrize('mutation', [
    {'aggregate_score': False}, {'aggregate_score': float('nan')}, {'extra': 'unexpected'},
    {'kind': 'judged'}, {'refusal_judgement': 'unknown'}, {'policy_version': 'future'},
])
def test_output_contract_rejects_inconsistent_variants(mutation, evaluator_factory):
    result = evaluator_factory().evaluate_pair('turn', 'Session blocked.', out_of_scope=True)
    result.update(mutation)
    with pytest.raises(EvaluationError) as err:
        validate_evaluation(result)
    assert err.value.code == 'invalid_evaluation'
    assert not Draft202012Validator(evaluation_schema()).is_valid(result)


def test_generated_refusal_has_judged_dimensions(valid_payload, judge_factory, evaluator_factory):
    payload = valid_payload(); payload['outcome'] = 'gen_refusal'
    result = evaluator_factory(judge_factory(payload)).evaluate_pair('turn', 'I cannot help with that.')
    assert result['kind'] == 'judged'
    assert result['outcome'] == 'gen_refusal'
    assert result['scores_avg'] == .8
    Draft202012Validator(evaluation_schema()).validate(result)
