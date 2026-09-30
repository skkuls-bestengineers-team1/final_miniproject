from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.api import main as api
from app.api.schemas import ChatRequest
from app.graph.state import State, initial_state
from app.graph.validator import respond
from app.workers import worker3_delivery as delivery
from tests.test_worker3_delivery import setup_model, tool_reply


def make_graph(worker):
    builder = StateGraph(State)
    builder.add_node('worker3', worker)
    builder.add_node('respond', respond)
    builder.add_edge(START, 'worker3')
    builder.add_edge('worker3', 'respond')
    builder.add_edge('respond', END)
    return builder.compile(checkpointer=InMemorySaver())


def test_pending_request_allows_next_chat(monkeypatch):
    request = Mock(return_value={'ok': True, 'request_id': 9, 'status': 'PENDING'})
    monkeypatch.setattr(delivery, 'request_address_change', request)
    monkeypatch.setattr(delivery, 'get_orders', Mock(return_value={'ok': True, 'orders': []}))
    setup_model(monkeypatch, [
        tool_reply('request_address_change', {'new_address': '서울시 새 주소'}),
        AIMessage(content='변경 요청이 접수되었습니다. 승인 대기 중입니다.'),
        tool_reply('get_orders', {}),
        AIMessage(content='현재 조회할 주문이 없습니다.'),
    ])
    graph = make_graph(delivery.worker3)
    monkeypatch.setattr(api, 'graph', graph)
    monkeypatch.setattr(api, 'build_chat_ui', lambda state: None)
    state = initial_state('U1', HumanMessage(content='서울시 새 주소로 보내주세요'))
    state.update(step='input_new_address', current_worker='worker3', pending_data={'order_id': 'O1'})
    config = api._config('U1')
    graph.invoke(state, config)
    snapshot = graph.get_state(config)
    assert not snapshot.next
    assert not api._interrupt_payload(snapshot)
    assert snapshot.values['current_worker'] is None
    assert snapshot.values['last_tool_results'][-1]['status'] == 'PENDING'
    result = api.chat(ChatRequest(user_id='U1', message='다른 주문 배송은요?'), x_user_id=None)
    assert result.answer == '현재 조회할 주문이 없습니다.'
    assert not result.waiting_approval
    assert request.call_count == 1


@pytest.mark.parametrize('approved,status', [(True, 'DONE'), (False, 'REJECTED')])
def test_admin_action_does_not_require_or_resume_chat(monkeypatch, approved, status):
    monkeypatch.setattr(api, 'graph', None)
    update = Mock(return_value={'ok': True, 'user_id': 'U1', 'status': status})
    monkeypatch.setattr(api, 'mark_request_status', update)
    result = api._process_request(9, approved)
    update.assert_called_once_with(9, status)
    assert result.ok and not result.resumed


def test_old_interrupted_chat_is_released_without_replaying_request(monkeypatch):
    def worker(state):
        if state.get('step') == 'input_new_address':
            interrupt({'request_id': 9, 'draft': '승인 대기'})
            raise AssertionError('중단된 접수 코드를 재실행하면 안 됩니다.')
        return {'draft_answer': '새 질문 답변', 'step': None}

    graph = make_graph(worker)
    monkeypatch.setattr(api, 'graph', graph)
    monkeypatch.setattr(api, 'build_chat_ui', lambda state: None)
    state = initial_state('U1', HumanMessage(content='주소 변경'))
    state.update(step='input_new_address', current_worker='worker3')
    graph.invoke(state, api._config('U1'))
    assert api._interrupt_payload(graph.get_state(api._config('U1')))
    result = api.chat(ChatRequest(user_id='U1', message='재고 알려줘'), x_user_id=None)
    assert result.answer == '새 질문 답변'
    assert not api._interrupt_payload(graph.get_state(api._config('U1')))


def test_rejection_is_available_as_notification(monkeypatch):
    monkeypatch.setattr(api, 'fetch_all', Mock(return_value=[{
        'request_id': 9, 'request_type': 'ADDRESS_CHANGE', 'status': 'REJECTED',
    }]))
    result = api.notifications('U1')
    assert result.notifications[0].message == '배송지 변경 요청이 거절되었습니다.'
