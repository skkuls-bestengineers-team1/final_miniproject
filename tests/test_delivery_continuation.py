from unittest.mock import Mock

import pytest
from langchain_core.messages import HumanMessage

from app.graph import supervisor as routing
from app.graph.state import initial_state


@pytest.mark.parametrize('target,keep', [('worker3', True), ('worker4', False)])
def test_delivery_topic_change_preserves_only_delivery_context(monkeypatch, target, keep):
    monkeypatch.setattr(routing, 'classify_continuation', Mock(return_value=
        routing.ContinuationDecision(is_continuation=False, reason='질문 전환')))
    monkeypatch.setattr(routing, 'classify_intent', Mock(return_value=
        routing.SupervisorDecision(target=target, reason='새 질문의 담당자')))
    state = initial_state('U1', HumanMessage(content='다른 질문이 있어요'))
    state.update(current_worker='worker3', step='confirm_address', pending_data={'order_id': 'O1'})
    result = routing.supervisor(state)
    if keep:
        assert result == {}
    else:
        assert result['current_worker'] is None
        assert result['pending_data'] == {}
