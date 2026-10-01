from datetime import date
from unittest.mock import Mock

from app.tools import request_tools as rt


def test_duplicate_pending_exchange_is_not_inserted(monkeypatch):
    monkeypatch.setattr(rt, 'get_order', Mock(return_value={
        'ok': True,
        'delivered_date': date.today().isoformat(),
        'delivery_status': 'DELIVERED',
    }))
    monkeypatch.setattr(rt, 'fetch_one', Mock(return_value={
        'request_id': 3,
        'status': 'PENDING',
        'method': 'STORE_VISIT',
    }))
    monkeypatch.setattr(rt, 'execute', Mock(side_effect=AssertionError('should not insert')))

    result = rt.create_exchange_request('ORD-004', 'U001', 'STORE_VISIT', reason='제품에 하자가 있어서')

    assert result['ok']
    assert result['already_pending'] is True
    assert result['request_id'] == 3
    assert '이미' in result['message']


def test_new_exchange_uses_provided_reason(monkeypatch):
    monkeypatch.setattr(rt, 'get_order', Mock(return_value={
        'ok': True,
        'delivered_date': date.today().isoformat(),
        'delivery_status': 'DELIVERED',
    }))
    monkeypatch.setattr(rt, 'fetch_one', Mock(return_value=None))
    monkeypatch.setattr(rt, 'execute', Mock(return_value=12))

    result = rt.create_exchange_request('ORD-004', 'U001', 'STORE_VISIT', reason='제품에 하자가 있어서')

    assert result == {
        'ok': True,
        'request_id': 12,
        'status': 'PENDING',
        'request_type': 'EXCHANGE',
        'method': 'STORE_VISIT',
    }
    assert rt.execute.call_args.args[1][-1] == '제품에 하자가 있어서'
