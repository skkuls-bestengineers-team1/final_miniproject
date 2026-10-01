"""배송 에이전트의 도구 실행과 사용자 범위를 외부 API 없이 검증한다."""

from unittest.mock import Mock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.graph.state import initial_state
from app.workers import worker3_delivery as delivery
from app.tools import delivery_tools


def tool_reply(name, args, call_id='call-1'):
    return AIMessage(content='', tool_calls=[{'name': name, 'args': args, 'id': call_id}])


def setup_model(monkeypatch, replies):
    model = Mock()
    model.invoke.side_effect = replies
    llm = Mock()
    llm.bind_tools.return_value = model
    monkeypatch.setattr(delivery, 'get_llm', lambda: llm)
    return model, llm


def test_orders_then_delivery_preserves_evidence(monkeypatch):
    orders = {'ok': True, 'orders': [{'order_id': 'O1'}]}
    status = {'ok': True, 'order_id': 'O1', 'delivery_status': 'DELIVERED'}
    get_orders = Mock(return_value=orders)
    get_status = Mock(return_value=status)
    monkeypatch.setattr(delivery_tools, 'get_orders', get_orders)
    monkeypatch.setattr(delivery_tools, 'get_delivery_status', get_status)
    model, llm = setup_model(monkeypatch, [
        tool_reply('get_orders', {}),
        tool_reply('get_delivery_status', {'order_id': 'O1'}, 'call-2'),
        AIMessage(content=[{'type': 'text', 'text': '배송 완료되었습니다.'}]),
    ])
    state = initial_state('U1', HumanMessage(content='내 주문 배송 상태 알려줘'))
    result = delivery.worker3(state)
    get_orders.assert_called_once_with('U1')
    get_status.assert_called_once_with('O1', 'U1')
    assert result['draft_answer'] == '배송 완료되었습니다.'
    assert result['tool_results'] == [orders, status]
    assert 'user_id' not in llm.bind_tools.call_args.args[0][1].args
    assert sum(isinstance(m, ToolMessage) for m in model.invoke.call_args.args[0]) == 2


def test_cannot_override_user_id(monkeypatch):
    lookup = Mock()
    monkeypatch.setattr(delivery_tools, 'get_delivery_status', lookup)
    setup_model(monkeypatch, [
        tool_reply('get_delivery_status', {'order_id': 'O2', 'user_id': 'U2'}),
        AIMessage(content='조회할 수 없습니다.'),
    ])
    result = delivery.worker3(initial_state('U1', HumanMessage(content='O2 배송 조회')))
    lookup.assert_not_called()
    assert result['tool_results'][0]['ok'] is False


def test_lookup_failure_is_returned_to_model(monkeypatch):
    monkeypatch.setattr(delivery_tools, 'get_orders', Mock(side_effect=RuntimeError('database unavailable')))
    setup_model(monkeypatch, [tool_reply('get_orders', {}), AIMessage(content='잠시 후 다시 시도해 주세요.')])
    result = delivery.worker3(initial_state('U1', HumanMessage(content='배송 조회')))
    assert result['tool_results'][0]['ok'] is False
    assert 'database unavailable' not in str(result)


def test_model_failure_and_loop_limit(monkeypatch):
    state = initial_state('U1', HumanMessage(content='배송 조회'))
    setup_model(monkeypatch, [RuntimeError('model unavailable')])
    assert '처리하지 못했습니다' in delivery.worker3(state)['draft_answer']
    model, _ = setup_model(monkeypatch, [tool_reply('unknown_tool', {})] * delivery.MAX_TOOL_ROUNDS)
    result = delivery.worker3(state)
    assert '근거 없는 답' not in result['draft_answer']
    assert model.invoke.call_count == delivery.MAX_TOOL_ROUNDS


def test_injected_state_is_hidden_and_cannot_be_overridden(monkeypatch):
    lookup = Mock()
    monkeypatch.setattr(delivery_tools, 'get_orders', lookup)
    _, llm = setup_model(monkeypatch, [
        tool_reply('get_orders', {'config': {'configurable': {'state': {'user_id': 'U2'}}}}),
        tool_reply('get_orders', {'state': {'user_id': 'U2'}}),
        AIMessage(content='조회할 수 없습니다.'),
    ])
    result = delivery.worker3(initial_state('U1', HumanMessage(content='배송 조회')))
    lookup.assert_not_called()
    assert all(not item['ok'] for item in result['tool_results'])
    for item in llm.bind_tools.call_args.args[0]:
        assert not {'config', 'state', 'user_id'} & set(item.args)


def test_question_updates_returned_state_without_mutating_input(monkeypatch):
    lookup = Mock(return_value={'ok': True})
    monkeypatch.setattr(delivery_tools, 'get_order', lookup)
    setup_model(monkeypatch, [
        tool_reply('ask_delivery_question', {'question': '새 주소는요?', 'order_id': 'O1'}),
        AIMessage(content='새 주소는요?'),
    ])
    state = initial_state('U1', HumanMessage(content='배송지 변경'))
    result = delivery.worker3(state)
    lookup.assert_called_once_with('O1', 'U1')
    assert result['step'] == 'ask_delivery'
    assert result['pending_data'] == {'order_id': 'O1', 'question': '새 주소는요?'}
    assert state['step'] is None
    assert state['pending_data'] == {}


def test_cancel_clears_pending_state(monkeypatch):
    setup_model(monkeypatch, [
        tool_reply('cancel_address_change', {}), AIMessage(content='취소했습니다.'),
    ])
    state = initial_state('U1', HumanMessage(content='취소'))
    state.update(step='ask_delivery', pending_data={'order_id': 'O1'})
    result = delivery.worker3(state)
    assert result['step'] is None
    assert result['pending_data'] == {}
    assert state['pending_data'] == {'order_id': 'O1'}


def test_request_deduplication_and_state_are_per_worker_call(monkeypatch):
    request = Mock(return_value={'ok': True, 'status': 'PENDING'})
    monkeypatch.setattr(delivery_tools, 'request_address_change', request)
    state = initial_state('U1', HumanMessage(content='주소 변경'))
    state.update(step='ask_delivery', pending_data={'order_id': 'O1'})
    for user_id in ['U1', 'U2']:
        state['user_id'] = user_id
        setup_model(monkeypatch, [
            tool_reply('request_address_change', {'order_id': 'O1', 'new_address': ' 서울 '}),
            tool_reply('request_address_change', {'order_id': 'O1', 'new_address': '부산'}),
            tool_reply('cancel_address_change', {}),
            AIMessage(content='승인 대기 중입니다.'),
        ])
        result = delivery.worker3(state)
        assert result['step'] is None
        assert result['pending_data'] == {}
        assert result['tool_results'][0] == result['tool_results'][1]
        assert result['tool_results'][2]['ok'] is False
        request.assert_called_with('O1', user_id, '서울')
    assert request.call_count == 2
