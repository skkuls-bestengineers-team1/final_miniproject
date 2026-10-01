'''관리자 승인은 DB만 바꾸고, 새 worker3는 채팅을 멈추지 않는다.'''

from unittest.mock import Mock

from app.api import main as api


def test_admin_skips_resume_when_chat_is_not_paused(monkeypatch):
    compiled = Mock()
    monkeypatch.setattr(api, 'graph', compiled)
    monkeypatch.setattr(api, '_require_graph', lambda: compiled)
    monkeypatch.setattr(
        api,
        'mark_request_status',
        Mock(return_value={'ok': True, 'user_id': 'U1', 'status': 'DONE'}),
    )
    monkeypatch.setattr(api, '_graph_snapshot', Mock(return_value=None))

    result = api._resume(9, True)

    compiled.invoke.assert_not_called()
    assert result.ok
    assert result.status == 'DONE'
    assert result.resumed is False


def test_rejection_is_available_as_notification(monkeypatch):
    monkeypatch.setattr(api, 'fetch_all', Mock(return_value=[{
        'request_id': 9,
        'request_type': 'ADDRESS_CHANGE',
        'status': 'REJECTED',
    }]))

    result = api.notifications('U1')

    assert result.notifications[0].message == '배송지 변경 요청이 거절되었습니다.'
