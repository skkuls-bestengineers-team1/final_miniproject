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

