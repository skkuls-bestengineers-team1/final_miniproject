'''worker1 가까운 지점과 검색 기준점(search_origin) 흐름, 반경 확장.

DB·Redis·LLM·Nominatim 없이 Tool을 바꿔 끼워 흐름만 확인한다.
'''

import pytest
from langchain_core.messages import HumanMessage

import app.tools.search_origin as search_origin
import app.tools.store_tools as store_tools
import app.workers.worker1_store as w

REGISTERED = {'lat': 37.50, 'lng': 127.02, 'source': 'registered', 'label': '등록 주소'}
YONGSAN = {'lat': 37.53, 'lng': 126.96, 'source': 'typed', 'label': '용산역'}


def _now() -> str:
    return search_origin.current_origin(0, 0)['at']


@pytest.fixture
def tools(monkeypatch):
    '''호출 기록을 남기는 가짜 Tool.'''

    calls = {'nearest_origin': None, 'typed': []}

    def fake_nearest(user_id, top_k=3, origin=None):
        calls['nearest_origin'] = origin
        first = '용산점' if origin and origin['label'] == '용산역' else '강남역점'
        return {
            'ok': True,
            'stores': [
                {'store_name': first, 'distance_km': 0.4},
                {'store_name': '잠실점', 'distance_km': 6.6},
                {'store_name': '일산점', 'distance_km': 22.0},
            ],
        }

    def fake_typed(text):
        calls['typed'].append(text)
        return dict(YONGSAN, at=_now()) if '용산' in text else None

    def fake_registered(user_id):
        return dict(REGISTERED, at=_now())

    monkeypatch.setattr(w, 'find_nearest_stores', fake_nearest)
    monkeypatch.setattr(w, 'typed_origin', fake_typed)
    monkeypatch.setattr(w, 'registered_origin', fake_registered)
    monkeypatch.setattr(w, 'get_user', lambda user_id: {'ok': True, 'name': '박종석'})
    monkeypatch.setattr(w, '_extract_location', lambda text: None)
    monkeypatch.setattr(search_origin, 'registered_origin', fake_registered)

    return calls


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


def test_no_origin_asks_once(tools):
    update = w.worker1(_state('가까운 지점 알려줘'))

    assert update['step'] == 'ask_search_origin'
    assert update['search_origin_asked'] is True
    assert tools['nearest_origin'] is None


def test_button_choice_answers_with_basis(tools):
    current = search_origin.current_origin(37.49, 127.03)

    update = w.worker1(_state(
        '현재 위치 사용',
        step='ask_search_origin',
        search_origin=current,
        search_origin_asked=True,
    ))

    lines = update['draft_answer'].split('\n')
    assert update['step'] is None
    assert lines[0].startswith('박종석 님, 현재 위치 기준 가장 가까운 지점은 강남역점입니다.')
    assert lines[1] == '2순위 잠실점 (거리: 약 6.6km)'
    assert lines[-1] == w.RESERVATION_GUIDE
    assert tools['nearest_origin'] == current
    # 지점 카드가 읽는 Tool 결과가 그대로 남는다.
    assert update['tool_results'][-1]['stores'][0]['store_name'] == '강남역점'


def test_typed_address_answer(tools):
    update = w.worker1(_state('용산역', step='ask_search_origin', search_origin_asked=True))

    assert '용산역 기준 가장 가까운 지점은 용산점' in update['draft_answer']
    assert update['search_origin']['source'] == 'typed'


def test_unknown_address_retries_then_registered(tools):
    first = w.worker1(_state('없는동네', step='ask_search_origin'))

    assert first['step'] == 'ask_search_origin'
    assert first['pending_data']['origin_attempts'] == 1

    second = w.worker1(_state('또없는동네', step='ask_search_origin', pending_data=first['pending_data']))

    assert second['step'] is None
    assert '등록 주소 기준' in second['draft_answer']


def test_location_in_utterance_skips_question(monkeypatch, tools):
    monkeypatch.setattr(w, '_extract_location', lambda text: '용산역')

    update = w.worker1(_state('용산역 근처 매장 알려줘'))

    assert update['step'] is None
    assert '용산역 기준' in update['draft_answer']
    assert tools['typed'] == ['용산역']


def test_fresh_origin_reused_without_asking(tools):
    current = search_origin.current_origin(37.49, 127.03)

    update = w.worker1(_state('가까운 지점 알려줘', search_origin=current, search_origin_asked=True))

    assert update['step'] is None
    assert '현재 위치 기준' in update['draft_answer']


def test_asked_before_and_expired_uses_registered(tools):
    expired = dict(YONGSAN, at='2020-01-01 00:00:00')

    update = w.worker1(_state('가까운 지점 알려줘', search_origin=expired, search_origin_asked=True))

    assert update['step'] is None
    assert '등록 주소 기준' in update['draft_answer']


def test_radius_expands_when_nothing_nearby(monkeypatch):
    radii = []

    def fake_search(client, lng, lat, count=3, radius_km=50):
        radii.append(radius_km)
        return [{'store_name': '수원점', 'distance_km': 120.0}] if radius_km > 50 else []

    monkeypatch.setattr(store_tools, 'get_redis', lambda: None)
    monkeypatch.setattr(store_tools, 'search_nearest', fake_search)

    result = store_tools.find_nearest_stores('U001', origin=dict(REGISTERED, at=_now()))

    assert radii == [50, 200]
    assert result['ok'] and result['radius_km'] == 200


def test_radius_gives_up_after_widest(monkeypatch):
    monkeypatch.setattr(store_tools, 'get_redis', lambda: None)
    monkeypatch.setattr(store_tools, 'search_nearest', lambda *args, **kwargs: [])

    result = store_tools.find_nearest_stores('U001', origin=dict(REGISTERED, at=_now()))

    assert not result['ok']
    assert result['error_code'] == 'EMPTY_RESULT'
    assert '200km' in result['message']
