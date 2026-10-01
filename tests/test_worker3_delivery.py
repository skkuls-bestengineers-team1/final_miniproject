'''배송 에이전트의 도구 실행. DB·Gemini 없이 흐름만 확인한다.'''

from unittest.mock import Mock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.graph.state import initial_state
from app.workers import worker3_delivery as delivery


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
    monkeypatch.setattr(delivery, 'get_orders', get_orders)
    monkeypatch.setattr(delivery, 'get_delivery_status', get_status)
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
    assert sum(isinstance(message, ToolMessage) for message in model.invoke.call_args.args[0]) == 2


def test_cannot_override_user_id(monkeypatch):
    lookup = Mock()
    monkeypatch.setattr(delivery, 'get_delivery_status', lookup)
    setup_model(monkeypatch, [
        tool_reply('get_delivery_status', {'order_id': 'O2', 'user_id': 'U2'}),
        AIMessage(content='조회할 수 없습니다.'),
    ])
    result = delivery.worker3(initial_state('U1', HumanMessage(content='O2 배송 조회')))

    lookup.assert_not_called()
    assert result['tool_results'][0]['ok'] is False


def test_lookup_failure_is_returned_to_model(monkeypatch):
    monkeypatch.setattr(
        delivery,
        'get_orders',
        Mock(side_effect=RuntimeError('database unavailable')),
    )
    setup_model(monkeypatch, [
        tool_reply('get_orders', {}),
        AIMessage(content='잠시 후 다시 시도해 주세요.'),
    ])
    result = delivery.worker3(initial_state('U1', HumanMessage(content='배송 조회')))

    assert result['tool_results'][0]['ok'] is False
    assert 'database unavailable' not in str(result)


def test_model_failure_and_loop_limit(monkeypatch):
    state = initial_state('U1', HumanMessage(content='배송 조회'))
    setup_model(monkeypatch, [RuntimeError('model unavailable')])
    assert '처리하지 못했습니다' in delivery.worker3(state)['draft_answer']

    looping = tool_reply('get_orders', {})
    model, _ = setup_model(monkeypatch, [looping] * delivery.MAX_TOOL_ROUNDS)
    monkeypatch.setattr(delivery, 'get_orders', Mock(return_value={'ok': True, 'orders': []}))
    result = delivery.worker3(state)

    assert '처리하지 못했습니다' in result['draft_answer']
    assert model.invoke.call_count == delivery.MAX_TOOL_ROUNDS


def test_address_change_request_does_not_pause_graph(monkeypatch):
    created = {'ok': True, 'request_id': 9, 'status': 'PENDING'}
    monkeypatch.setattr(delivery, 'request_address_change', Mock(return_value=created))
    setup_model(monkeypatch, [
        tool_reply('request_address_change', {
            'order_id': 'ORD-001',
            'new_address': '서울시 새 주소',
        }),
        AIMessage(content='변경 요청이 접수되었습니다. 승인 대기 중입니다.'),
    ])
    result = delivery.worker3(initial_state('U1', HumanMessage(content='서울시 새 주소로 보내주세요')))

    assert result['step'] is None
    assert result['tool_results'][-1] == created
    assert '승인 대기' in result['draft_answer']
