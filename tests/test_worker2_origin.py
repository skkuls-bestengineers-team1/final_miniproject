'''worker2 재고 문의와 검색 기준점(search_origin) 흐름.

DB·Redis·LLM·Nominatim 없이 Tool을 바꿔 끼워 흐름만 확인한다.
'''

import pytest
from langchain_core.messages import HumanMessage

import app.tools.search_origin as search_origin
import app.workers.worker2_stock as w
from app.workers.worker2_stock import StockQuery

REGISTERED = {'lat': 37.50, 'lng': 127.02, 'source': 'registered', 'label': '등록 주소'}
YONGSAN = {'lat': 37.53, 'lng': 126.96, 'source': 'typed', 'label': '용산역'}


@pytest.fixture
def tools(monkeypatch):
    '''호출 기록을 남기는 가짜 Tool.'''

    calls = {'nearest_origin': None, 'typed': []}

    def fake_get_stock(store_name, category_code=None, product_name=None):
        return {
            'ok': True,
            'store_name': store_name,
            'items': [{'product_name': '사성 비스포크 제트봇 AI', 'quantity': 10}],
            'total': 10,
            'product_name': product_name,
            'category_code': category_code,
        }

    def fake_nearest(user_id, top_k=3, origin=None):
        calls['nearest_origin'] = origin
        name = '용산점' if origin and origin['label'] == '용산역' else '강남역점'
        return {'ok': True, 'stores': [{'store_name': name, 'distance_km': 1.0}]}

    def fake_typed(text):
        calls['typed'].append(text)
        return dict(YONGSAN, at=_now()) if '용산' in text else None

    def fake_registered(user_id):
        return dict(REGISTERED, at=_now())

    monkeypatch.setattr(w, 'get_stock', fake_get_stock)
    monkeypatch.setattr(w, 'find_nearest_stores', fake_nearest)
    monkeypatch.setattr(w, 'typed_origin', fake_typed)
    monkeypatch.setattr(w, 'registered_origin', fake_registered)
    monkeypatch.setattr(search_origin, 'registered_origin', fake_registered)

    return calls


def _now() -> str:
    return search_origin.current_origin(0, 0)['at']


def _extract_returns(monkeypatch, **fields):
    monkeypatch.setattr(w, '_extract', lambda text: StockQuery(**fields))


def _state(text, **extra):
    state = {
        'messages': [HumanMessage(content=text)],
        'user_id': 'U001',
        'step': None,
        'pending_data': {},
        'tool_results': [],
        'validation': None,
        'search_origin': None,
        'search_origin_asked': False,
    }
    state.update(extra)
    return state


def test_store_given_answers_directly(monkeypatch, tools):
    _extract_returns(monkeypatch, store_name='강남역점', category_code='ROBOT_CLEANER')

    update = w.worker2(_state('강남역 로봇청소기 재고'))

    assert update['step'] is None
    assert '강남역점 재고입니다' in update['draft_answer']
    assert '사성 비스포크 제트봇 AI' in update['draft_answer']
    assert '재고 10개' in update['draft_answer']
    assert tools['nearest_origin'] is None


def test_no_store_no_origin_asks_once(monkeypatch, tools):
    _extract_returns(monkeypatch, category_code='ROBOT_CLEANER')

    update = w.worker2(_state('로봇청소기 재고'))

    assert update['step'] == 'ask_search_origin'
    assert update['search_origin_asked'] is True
    assert update['pending_data'] == {'product_name': None, 'category_code': 'ROBOT_CLEANER'}


def test_button_choice_uses_origin_from_state(monkeypatch, tools):
    current = search_origin.current_origin(37.49, 127.03)
    state = _state(
        '현재 위치 사용',
        step='ask_search_origin',
        pending_data={'product_name': None, 'category_code': 'ROBOT_CLEANER'},
        search_origin=current,
        search_origin_asked=True,
    )

    update = w.worker2(state)

    assert update['step'] is None
    assert update['draft_answer'].startswith('현재 위치 기준 가장 가까운 지점은 강남역점입니다.')
    assert tools['nearest_origin'] == current
    assert tools['typed'] == []


def test_typed_address_answer(monkeypatch, tools):
    state = _state(
        '용산역',
        step='ask_search_origin',
        pending_data={'product_name': None, 'category_code': 'ROBOT_CLEANER'},
        search_origin_asked=True,
    )

    update = w.worker2(state)

    assert update['draft_answer'].startswith('용산역 기준 가장 가까운 지점은 용산점입니다.')
    assert update['search_origin']['source'] == 'typed'


def test_unknown_address_retries_then_registered(monkeypatch, tools):
    pending = {'product_name': None, 'category_code': 'ROBOT_CLEANER'}
    first = w.worker2(_state('없는동네', step='ask_search_origin', pending_data=pending))

    assert first['step'] == 'ask_search_origin'
    assert first['pending_data']['origin_attempts'] == 1

    second = w.worker2(_state(
        '또없는동네',
        step='ask_search_origin',
        pending_data=first['pending_data'],
    ))

    assert second['step'] is None
    assert second['draft_answer'].startswith('등록 주소 기준')


def test_location_in_first_utterance(monkeypatch, tools):
    _extract_returns(monkeypatch, category_code='ROBOT_CLEANER', location_text='용산')

    update = w.worker2(_state('용산 근처 로봇청소기 재고'))

    assert update['step'] is None
    assert '용산점' in update['draft_answer']
    assert tools['typed'] == ['용산']


def test_asked_before_and_expired_uses_registered(monkeypatch, tools):
    _extract_returns(monkeypatch, category_code='ROBOT_CLEANER')
    expired = dict(YONGSAN, at='2020-01-01 00:00:00')

    update = w.worker2(_state(
        '로봇청소기 재고',
        search_origin=expired,
        search_origin_asked=True,
    ))

    assert update['step'] is None
    assert update['draft_answer'].startswith('등록 주소 기준')


def test_ask_missing_updates_product(monkeypatch, tools):
    _extract_returns(monkeypatch, store_name='용산점', product_name='사성 비스포크 제트봇 AI')

    update = w.worker2(_state(
        '용산점 사성 비스포크 제트봇 AI요',
        step='ask_missing',
        pending_data={'product_name': None, 'category_code': 'ROBOT_CLEANER'},
    ))

    assert update['step'] is None
    assert '용산점 재고입니다' in update['draft_answer']
    assert '사성 비스포크 제트봇 AI' in update['draft_answer']
    assert '재고 10개' in update['draft_answer']
