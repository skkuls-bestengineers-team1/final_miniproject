'''그래프 컴파일과 재고 문의 1회.'''

import uuid

import pytest
from langchain_core.messages import HumanMessage

from app.db.init_db import init_db
from app.graph.builder import build_graph
from app.graph.state import initial_state
from app.graph.supervisor import classify_keyword
from app.redis_store.checkpointer import get_checkpointer
from tests.conftest import redis_up


def test_keyword_routes():
    assert classify_keyword('강남역 로봇청소기 재고 알려주세요') == 'worker2'
    assert classify_keyword('로봇청소기를 사려고 합니다') == 'worker1'
    assert classify_keyword('주소를 잘못 적었습니다') == 'worker3'
    assert classify_keyword('교환 부탁드립니다') == 'worker4'
    assert classify_keyword('결제가 두 번 되었습니다') == 'fallback'


def test_stock_invoke(sqlite_env):
    if not redis_up():
        pytest.skip('Redis가 없습니다.')

    init_db()

    try:
        compiled = build_graph(get_checkpointer())

    except Exception as exc:
        pytest.skip(f'RedisSaver를 준비하지 못했습니다. {exc}')

    user_id = f'smoke-{uuid.uuid4()}'
    result = compiled.invoke(
        initial_state(
            user_id,
            HumanMessage(content='강남역 로봇청소기 재고 알려주세요'),
        ),
        {'configurable': {'thread_id': user_id}},
    )

    answer = ''

    for message in reversed(result['messages']):
        if getattr(message, 'type', None) == 'ai':
            answer = message.content
            break

    assert '재고' in answer
    assert '10개' in answer
