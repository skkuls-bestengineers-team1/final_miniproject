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


def test_window_refusal_passes_without_llm():
    result = validator({
        'messages': [HumanMessage(content='교환을 진행하고 싶어')],
        'draft_answer': '선택하신 제품(사성 탭 S10)은 수령 후 7일이 지나 교환 접수가 어렵습니다.\n\n[관련 규정 ART-08 / 근거 DOC-025]',
        'tool_results': [{
            'ok': True,
            'decision': 'RETURN_WINDOW_EXPIRED',
            'today': '2026-10-01',
            'days_since_delivery': 9,
            'return_window_days': 7,
        }],
        'current_worker': 'worker4',
        'step': None,
        'retry_count': 0,
        'validation': None,
        'user_id': 'U001',
        'pending_data': {},
    })

    assert result['validation']['pass'] is True
