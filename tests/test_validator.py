'''검증 노드. LLM 없이 가드와 라우팅만 본다.'''

from langchain_core.messages import HumanMessage

from app.graph.validator import route_from_validator, validator


def test_empty_draft_fails():
    result = validator({
        'messages': [HumanMessage(content='재고 알려주세요')],
        'draft_answer': '',
        'tool_results': [{'ok': True, 'total': 10}],
        'current_worker': 'worker2',
        'step': None,
        'retry_count': 0,
        'validation': None,
        'user_id': 'U001',
        'pending_data': {},
    })

    assert result['validation']['pass'] is False
    assert '초안' in result['validation']['reason']


def test_route_pass_goes_to_respond():
    assert route_from_validator({
        'validation': {'pass': True, 'reason': 'ok'},
        'retry_count': 0,
        'current_worker': 'worker1',
    }) == 'respond'


def test_route_fail_retries_same_worker():
    assert route_from_validator({
        'validation': {'pass': False, 'reason': '재고를 10개로 고쳐라'},
        'retry_count': 0,
        'current_worker': 'worker2',
    }) == 'worker2'


def test_route_fail_after_max_retry_goes_fallback():
    assert route_from_validator({
        'validation': {'pass': False, 'reason': '불일치'},
        'retry_count': 2,
        'current_worker': 'worker2',
    }) == 'fallback'
