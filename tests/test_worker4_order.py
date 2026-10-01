'''worker4 주문 선택. 수령 전 주문을 고르지 않는다.'''

from datetime import date, timedelta
from unittest.mock import Mock

from langchain_core.messages import HumanMessage

from app.graph.state import initial_state
from app.workers import worker4_order as worker4


def _order(order_id, status, delivered=None, name='사성 비스포크 제트봇 AI', option='빨간색'):
    return {
        'order_id': order_id,
        'product_name': name,
        'option': option,
        'order_date': '2026-09-20',
        'delivery_status': status,
        'delivered_date': delivered,
        'ship_address': 'AA동 BB아파트',
    }


def test_pick_order_skips_preparing_same_product():
    preparing = _order('ORD-001', 'PREPARING')
    delivered = _order('ORD-004', 'DELIVERED', date.today().isoformat())
    picked = worker4._pick_order(
        [preparing, delivered],
        '색상이 사진과 다릅니다. 교환 부탁드립니다.',
    )

    assert picked['order_id'] == 'ORD-004'


def test_pick_order_asks_when_several_received():
    first = _order('ORD-004', 'DELIVERED', date.today().isoformat())
    second = _order(
        'ORD-007',
        'DELIVERED',
        date.today().isoformat(),
        name='사성 제트봇 70',
        option='세이지 그린',
    )

    assert worker4._pick_order([first, second], '교환하고 싶어요') is None


def test_named_expired_order_is_not_replaced_by_in_window(monkeypatch):
    today = date.today()
    expired = _order(
        'ORD-005',
        'DELIVERED',
        (today - timedelta(days=60)).isoformat(),
        name='사성 탭 S10',
        option='그레이',
    )
    recent = _order('ORD-004', 'DELIVERED', today.isoformat())
    listed = {'ok': True, 'orders': [_order('ORD-001', 'PREPARING'), recent, expired]}
    monkeypatch.setattr(worker4, 'get_orders', Mock(return_value=listed))
    monkeypatch.setattr(worker4, 'search_dispute_docs', Mock(return_value={'ok': True, 'items': []}))
    monkeypatch.setattr(worker4, 'get_llm', Mock(side_effect=RuntimeError('no llm')))

    by_id = worker4.worker4(initial_state(
        'U001',
        HumanMessage(content='ORD-005 환불하고 싶어요'),
    ))
    by_name = worker4.worker4(initial_state(
        'U001',
        HumanMessage(content='탭 S10 환불하고 싶어요'),
    ))

    assert by_id['step'] is None
    assert '탭 S10' in by_id['draft_answer']
    assert '7일이 지나' in by_id['draft_answer']
    assert 'ORD-004' not in by_id['draft_answer']
    assert by_id['tool_results'][-1]['order_id'] == 'ORD-005'
    assert by_name['tool_results'][-1]['order_id'] == 'ORD-005'


def test_pick_order_respects_order_id():
    recent = _order('ORD-004', 'DELIVERED', date.today().isoformat())
    expired = _order(
        'ORD-005',
        'DELIVERED',
        (date.today() - timedelta(days=60)).isoformat(),
        name='사성 탭 S10',
    )

    assert worker4._pick_order([recent, expired], 'ORD-005 환불하고 싶어요')['order_id'] == 'ORD-005'


def test_named_preparing_order_is_refused_not_swapped(monkeypatch):
    listed = {
        'ok': True,
        'orders': [
            _order('ORD-001', 'PREPARING'),
            _order('ORD-004', 'DELIVERED', date.today().isoformat()),
        ],
    }
    monkeypatch.setattr(worker4, 'get_orders', Mock(return_value=listed))
    monkeypatch.setattr(worker4, 'search_dispute_docs', Mock(return_value={'ok': True, 'items': []}))
    monkeypatch.setattr(worker4, 'get_llm', Mock(side_effect=RuntimeError('no llm')))

    result = worker4.worker4(initial_state(
        'U001',
        HumanMessage(content='ORD-001 교환하고 싶어요'),
    ))

    assert result['step'] is None
    assert '아직 수령 전' in result['draft_answer']
    assert '맞습니까' not in result['draft_answer']
    assert result['tool_results'][-1]['order_id'] == 'ORD-001'


def test_named_expired_refund_attaches_article(monkeypatch):
    listed = {
        'ok': True,
        'orders': [
            _order('ORD-004', 'DELIVERED', date.today().isoformat()),
            _order(
                'ORD-005',
                'DELIVERED',
                (date.today() - timedelta(days=60)).isoformat(),
                name='사성 탭 S10',
            ),
        ],
    }
    citation = {
        'ok': True,
        'items': [{
            'doc_id': 'ART-08',
            'title': '제8조 청약철회 기간',
            'content': '배송 완료일로부터 7일',
            'doc_ids': ['DOC-025'],
        }],
    }
    monkeypatch.setattr(worker4, 'get_orders', Mock(return_value=listed))
    monkeypatch.setattr(worker4, 'search_dispute_docs', Mock(return_value=citation))
    monkeypatch.setattr(worker4, 'get_llm', Mock(side_effect=RuntimeError('no llm')))

    result = worker4.worker4(initial_state(
        'U001',
        HumanMessage(content='ORD-005 환불하고 싶어요'),
    ))

    assert '7일이 지나' in result['draft_answer']
    assert 'ART-08' in result['draft_answer']
    assert '맞습니까' not in result['draft_answer']
    assert result['tool_results'][-1]['order_id'] == 'ORD-005'


def test_policy_question_keeps_confirm_step(monkeypatch):
    citation = {
        'ok': True,
        'items': [{
            'doc_id': 'ART-08',
            'title': '제8조 청약철회 기간',
            'content': '배송 완료일로부터 7일',
            'doc_ids': ['DOC-025'],
        }],
    }
    monkeypatch.setattr(worker4, 'search_dispute_docs', Mock(return_value=citation))
    monkeypatch.setattr(worker4, 'get_llm', Mock(side_effect=RuntimeError('no llm')))

    result = worker4.worker4(_pending_refund(initial_state(
        'U001',
        HumanMessage(content='관련 규정이 어떻게 되는데?'),
    )))

    assert result['step'] == 'confirm_order'
    assert result['pending_data']['order_id'] == 'ORD-004'
    assert 'ART-08' in result['draft_answer']
    assert '네' in result['draft_answer']


def test_refuse_not_received_differs_from_window():
    preparing = _order('ORD-001', 'PREPARING')

    assert '아직 수령 전' in worker4._refuse_not_received('교환', preparing)
    assert '7일' not in worker4._refuse_not_received('교환', preparing)
    assert '7일이 지나' in worker4._refuse_window('교환', preparing)


def test_exchange_starts_confirm_on_delivered_order(monkeypatch):
    today = date.today()
    listed = {
        'ok': True,
        'orders': [
            _order('ORD-001', 'PREPARING'),
            _order('ORD-004', 'DELIVERED', today.isoformat()),
            _order('ORD-005', 'DELIVERED', (today - timedelta(days=60)).isoformat(), name='사성 탭 S10', option='그레이'),
        ],
    }
    monkeypatch.setattr(worker4, 'get_orders', Mock(return_value=listed))
    monkeypatch.setattr(worker4, 'search_dispute_docs', Mock(return_value={'ok': True, 'items': []}))
    monkeypatch.setattr(worker4, 'get_llm', Mock(side_effect=RuntimeError('no llm')))

    result = worker4.worker4(initial_state(
        'U001',
        HumanMessage(content='색상이 사진과 다릅니다. 제품이 잘못 왔습니다. 교환 부탁드립니다.'),
    ))

    assert result['step'] == 'confirm_order'
    assert result['pending_data']['order_id'] == 'ORD-004'
    assert '맞습니까' in result['draft_answer']
    assert 'ORD-004' in result['draft_answer']
    assert '7일이 지나' not in result['draft_answer']


def _pending_refund(state, step='confirm_order'):
    state['step'] = step
    state['pending_data'] = {
        'order_id': 'ORD-004',
        'request_type': 'REFUND',
        'shown_address': 'AA동 BB아파트',
        'reason': '색상이 사진과 다릅니다.',
    }
    return state


def test_confirm_order_accepts_colloquial_yes(monkeypatch):
    monkeypatch.setattr(worker4, 'get_llm', Mock(side_effect=RuntimeError('no llm')))

    result = worker4.worker4(_pending_refund(initial_state(
        'U001',
        HumanMessage(content='이거 맞아'),
    )))

    assert result['step'] == 'select_method'
    assert '지점 방문' in result['draft_answer']
    assert '택배 수거' in result['draft_answer']


def test_select_method_store_visit_creates_refund(monkeypatch):
    created = {'ok': True, 'request_id': 11, 'status': 'PENDING', 'method': 'STORE_VISIT'}
    nearest = {
        'ok': True,
        'stores': [{'store_name': '강남역점', 'distance_km': 1.2}],
    }
    monkeypatch.setattr(worker4, 'get_llm', Mock(side_effect=RuntimeError('no llm')))
    monkeypatch.setattr(worker4, 'create_refund_request', Mock(return_value=created))
    monkeypatch.setattr(worker4, 'find_nearest_stores', Mock(return_value=nearest))

    result = worker4.worker4(_pending_refund(
        initial_state('U001', HumanMessage(content='지점 방문')),
        'select_method',
    ))

    assert result['step'] is None
    assert '접수를 지점 방문으로 남겼습니다' in result['draft_answer']
    assert '강남역점' in result['draft_answer']
    worker4.create_refund_request.assert_called_once()


def test_window_facts_include_refusal_evidence():
    order = _order('ORD-005', 'DELIVERED', (date.today() - timedelta(days=9)).isoformat())
    facts = worker4._window_facts(order)

    assert facts['decision'] == 'RETURN_WINDOW_EXPIRED'
    assert facts['days_since_delivery'] == 9
    assert facts['return_window_days'] == 7
    assert facts['today'] == date.today().isoformat()


def test_rewrite_keeps_refusal_and_article(monkeypatch):
    monkeypatch.setattr(worker4, 'get_llm', Mock(side_effect=RuntimeError('no llm')))
    draft = (
        '선택하신 제품(사성 비스포크 제트봇 AI)은 수령 후 7일이 지나 교환 접수가 어렵습니다.'
        '\n\n[관련 규정 ART-08 / 근거 DOC-025]\n제8조 청약철회 기간'
    )

    rewritten = worker4._rewrite_draft(
        draft,
        'Tool 결과에 오늘 날짜나 7일 경과 여부가 없으니 임의로 판단하지 마라',
        [{'decision': 'RETURN_WINDOW_EXPIRED', 'days_since_delivery': 9}],
    )

    assert rewritten == draft
    assert '가능' not in rewritten.split('[관련 규정]')[0]


def test_dispute_query_prefers_withdrawal_window():
    assert '청약철회 기간' in worker4._dispute_query('교환을 진행하고 싶어', 'RETURN_WINDOW_EXPIRED')
    items = [
        {'doc_id': 'ART-12', 'title': '제12조 재화등 교환', 'content': '준용한다'},
        {'doc_id': 'ART-08', 'title': '제8조 청약철회 기간', 'content': '배송 완료일로부터 7일'},
    ]

    assert worker4._prefer_dispute_item(items, 'RETURN_WINDOW_EXPIRED')['doc_id'] == 'ART-08'


def test_expired_order_refuses_with_evidence(monkeypatch):
    listed = {
        'ok': True,
        'orders': [
            _order('ORD-001', 'PREPARING'),
            _order('ORD-005', 'DELIVERED', (date.today() - timedelta(days=9)).isoformat(), name='사성 탭 S10'),
        ],
    }
    citation = {
        'ok': True,
        'items': [{
            'doc_id': 'ART-08',
            'title': '제8조 청약철회 기간',
            'content': '배송 완료일로부터 7일',
            'doc_ids': ['DOC-025'],
        }],
    }
    monkeypatch.setattr(worker4, 'get_orders', Mock(return_value=listed))
    monkeypatch.setattr(worker4, 'search_dispute_docs', Mock(return_value=citation))
    monkeypatch.setattr(worker4, 'get_llm', Mock(side_effect=RuntimeError('no llm')))

    result = worker4.worker4(initial_state(
        'U001',
        HumanMessage(content='교환을 진행하고 싶어'),
    ))

    assert result['step'] is None
    assert '7일이 지나' in result['draft_answer']
    assert '가능' not in result['draft_answer'].split('[관련 규정]')[0]
    assert 'ART-08' in result['draft_answer']
    assert result['tool_results'][-1]['decision'] == 'RETURN_WINDOW_EXPIRED'
    assert result['tool_results'][-1]['days_since_delivery'] == 9


def test_policy_followup_does_not_start_confirm(monkeypatch):
    citation = {
        'ok': True,
        'items': [{
            'doc_id': 'ART-08',
            'title': '제8조 청약철회 기간',
            'content': '배송 완료일로부터 7일',
            'doc_ids': ['DOC-025'],
        }],
    }
    monkeypatch.setattr(worker4, 'search_dispute_docs', Mock(return_value=citation))
    monkeypatch.setattr(worker4, 'get_orders', Mock(side_effect=AssertionError('should not list orders')))
    monkeypatch.setattr(worker4, 'get_llm', Mock(side_effect=RuntimeError('no llm')))

    state = initial_state('U001', HumanMessage(content='관련 규정이 어떻게 되는데?'))
    state['last_tool_results'] = [{
        'ok': True,
        'decision': 'RETURN_WINDOW_EXPIRED',
        'days_since_delivery': 9,
    }]
    result = worker4.worker4(state)

    assert result['step'] is None
    assert 'ART-08' in result['draft_answer']
    assert '맞습니까' not in (result['draft_answer'] or '')

