import json
from threading import Event
import pytest
pd = pytest.importorskip('pandas')
from agent_evaluation_core import EvaluationError, ResponseEvaluator


@pytest.mark.parametrize('index', [['case_a', 'case_b'], [10, 20], [1, 0], ['same', 'same'], pd.MultiIndex.from_tuples([('a', 2), ('a', 1)])])
def test_position_and_index_preserved(index, evaluator_factory):
    frame = pd.DataFrame({'prompt': ['a', 'b'], 'response': ['Session blocked.', ''], 'out_of_scope': [False, False]}, index=index)
    original = frame.copy(deep=True)
    result = evaluator_factory().evaluate_dataframe(frame, max_workers=2)
    pd.testing.assert_frame_equal(result.drop(columns='evaluation'), original)
    pd.testing.assert_frame_equal(frame, original)
    assert [v['result']['kind'] for v in result['evaluation']] == ['refusal', 'system_error']


def test_completion_order_cannot_reorder_rows(valid_payload):
    completed = Event()
    class Judge:
        def chat(self, **kwargs):
            turn = json.loads(kwargs['messages'][1].content)['current_prompt']
            if turn == 'first':
                assert completed.wait(3)
            else:
                completed.set()
            payload = valid_payload(); payload['explanation'] = turn
            return payload
    frame = pd.DataFrame({'prompt': ['first', 'second'], 'response': ['a', 'b']}, index=[1, 0])
    result = ResponseEvaluator(Judge(), system_prompt='Fixture').evaluate_dataframe(frame, max_workers=2)
    assert [v['result']['explanation'] for v in result['evaluation']] == ['first', 'second']


@pytest.mark.parametrize('missing', [None, float('nan'), pd.NA])
def test_missing_scope_is_unknown(missing, evaluator_factory):
    frame = pd.DataFrame({'prompt': ['p'], 'response': ['Session blocked.'], 'out_of_scope': [missing]})
    result = evaluator_factory().evaluate_dataframe(frame)['evaluation'].iloc[0]
    assert result['result']['refusal_judgement'] == 'unknown'
    assert result['result']['aggregate_score'] is None


def test_nullable_bools_context_and_row_failures(evaluator_factory):
    evaluator = evaluator_factory()
    frame = pd.DataFrame({'prompt': ['actual', 'bad', 'empty', 'unknown'], 'response': ['answer', 'answer', '', 'Session blocked.'],
                          'out_of_scope': [False, 'false', False, pd.NA],
                          'conversation_context': ['history', None, None, None], 'scenario': ['scenario', None, None, None]})
    result = evaluator.evaluate_dataframe(frame)
    assert [r['status'] for r in result.evaluation] == ['ok', 'error', 'ok', 'ok']
    assert result.evaluation.iloc[1]['error']['code'] == 'invalid_input'
    request = json.loads(evaluator.client.calls[0]['messages'][1].content)
    assert request['conversation_context'] == 'history'
    assert request['scenario'] == 'scenario'
    assert request['current_prompt'] == 'actual'
    nullable = pd.DataFrame({'prompt': ['p', 'p'], 'response': ['Session blocked.'] * 2,
                             'out_of_scope': pd.Series([True, pd.NA], dtype='boolean')})
    values = evaluator.evaluate_dataframe(nullable).evaluation
    assert [v['result']['refusal_judgement'] for v in values] == ['correct', 'unknown']


def test_judge_failure_does_not_abort_other_rows(evaluator_factory, judge_factory):
    evaluator = evaluator_factory(judge_factory(fail=RuntimeError('synthetic')))
    result = evaluator.evaluate_dataframe(pd.DataFrame({'prompt': ['p', 'p'], 'response': ['answer', '']}))
    assert result.evaluation.iloc[0]['error']['code'] == 'judge_call_failed'
    assert result.evaluation.iloc[1]['result']['kind'] == 'system_error'


def test_empty_frame_preserves_schema_and_index(evaluator_factory):
    frame = pd.DataFrame(columns=['prompt', 'response']); frame.index.name = 'case'
    result = evaluator_factory().evaluate_dataframe(frame)
    assert list(result.columns) == ['prompt', 'response', 'evaluation']
    assert result.empty and result.index.name == 'case'


@pytest.mark.parametrize('workers', [0, 65, True, 1.5])
def test_worker_limits(workers, evaluator_factory):
    with pytest.raises(EvaluationError):
        evaluator_factory().evaluate_dataframe(pd.DataFrame(columns=['prompt', 'response']), max_workers=workers)


@pytest.mark.parametrize('columns', [['prompt'], ['prompt', 'response', 'response'], ['prompt', 'response', 'evaluation']])
def test_ambiguous_columns_rejected(columns, evaluator_factory):
    with pytest.raises(EvaluationError):
        evaluator_factory().evaluate_dataframe(pd.DataFrame(columns=columns))
