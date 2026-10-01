'''배송지 변경, 교환, 환불 요청.

담당: 최민정(배송지 변경), 박종석(교환·환불)
'''

from datetime import date, datetime

from app.db.connection import execute, fail, fetch_one
from app.tools.order_tools import get_order

RETURN_WINDOW_DAYS = 7
ADDRESS_CHANGE_BLOCKED = {'IN_TRANSIT', 'DELIVERED'}


def request_address_change(
        order_id: str,
        user_id: str,
        new_address: str
) -> dict:
    '''배송지 변경 요청. 배송 중·배송 완료는 거절한다. 같은 PENDING은 다시 만들지 않는다.'''

    if not new_address or not new_address.strip():
        return fail('INVALID_ADDRESS', '변경할 주소를 입력해 주세요.')

    order = get_order(order_id, user_id)

    if not order.get('ok'):
        return order

    if order['delivery_status'] in ADDRESS_CHANGE_BLOCKED:
        return fail(
            'ADDRESS_CHANGE_NOT_ALLOWED',
            '배송 중이거나 배송이 완료된 주문은 주소를 바꿀 수 없습니다.',
        )

    existing = fetch_one(
        '''
        SELECT request_id, status
        FROM requests
        WHERE order_id = %s
          AND user_id = %s
          AND request_type = 'ADDRESS_CHANGE'
          AND status = 'PENDING'
        ORDER BY request_id DESC
        LIMIT 1
        ''',
        (order_id, user_id)
    )

    if existing:
        return {
            'ok': True,
            'request_id': existing['request_id'],
            'status': 'PENDING',
        }

    request_id = execute(
        '''
        INSERT INTO requests (
            order_id, user_id, request_type, new_address, status
        )
        VALUES (%s, %s, 'ADDRESS_CHANGE', %s, 'PENDING')
        RETURNING request_id
        ''',
        (order_id, user_id, new_address.strip())
    )

    return {
        'ok': True,
        'request_id': request_id,
        'status': 'PENDING',
    }


def _days_since_delivery(
        delivered_date: str | None
) -> int | None:
    if not delivered_date:
        return None

    delivered = datetime.strptime(str(delivered_date)[:10], '%Y-%m-%d').date()

    return (date.today() - delivered).days


def _create_return_request(
        request_type: str,
        order_id: str,
        user_id: str,
        method: str,
        pickup_address: str | None = None,
        reason: str | None = None
) -> dict:
    '''교환·환불 공통 저장. 수령 후 7일이 지나면 거절한다.'''

    if method not in {'STORE_VISIT', 'PICKUP'}:
        return fail('INVALID_METHOD', '접수 방법은 지점 방문 또는 택배 수거입니다.')

    order = get_order(order_id, user_id)

    if not order.get('ok'):
        return order

    elapsed = _days_since_delivery(order.get('delivered_date'))

    if elapsed is None:
        return fail('NOT_DELIVERED', '수령 완료된 주문만 교환·환불할 수 있습니다.')

    if elapsed > RETURN_WINDOW_DAYS:
        return fail('RETURN_WINDOW_EXPIRED', '수령 후 7일이 지나 접수할 수 없습니다.')

    if method == 'PICKUP' and not pickup_address:
        return fail('INVALID_ADDRESS', '수거 주소가 필요합니다.')

    request_id = execute(
        '''
        INSERT INTO requests (
            order_id, user_id, request_type, method,
            pickup_address, reason, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, 'PENDING')
        RETURNING request_id
        ''',
        (order_id, user_id, request_type, method, pickup_address, reason)
    )

    return {
        'ok': True,
        'request_id': request_id,
        'status': 'PENDING',
        'request_type': request_type,
        'method': method,
    }


def create_exchange_request(
        order_id: str,
        user_id: str,
        method: str,
        pickup_address: str | None = None,
        reason: str | None = None
) -> dict:
    return _create_return_request(
        'EXCHANGE',
        order_id,
        user_id,
        method,
        pickup_address,
        reason,
    )


def create_refund_request(
        order_id: str,
        user_id: str,
        method: str,
        pickup_address: str | None = None,
        reason: str | None = None
) -> dict:
    return _create_return_request(
        'REFUND',
        order_id,
        user_id,
        method,
        pickup_address,
        reason,
    )


def mark_request_status(
        request_id: int,
        status: str
) -> dict:
    '''관리자 승인 API가 요청 상태를 바꾼다.'''

    row = fetch_one(
        '''
        SELECT request_id, order_id, user_id, request_type, new_address, status
        FROM requests
        WHERE request_id = %s
        ''',
        (request_id,)
    )

    if row is None:
        return fail('REQUEST_NOT_FOUND', '요청을 찾지 못했습니다.')

    execute(
        'UPDATE requests SET status = %s WHERE request_id = %s',
        (status, request_id)
    )

    if status in {'APPROVED', 'DONE'} and row['request_type'] == 'ADDRESS_CHANGE' and row['new_address']:
        execute(
            'UPDATE orders SET ship_address = %s WHERE order_id = %s',
            (row['new_address'], row['order_id'])
        )

    updated = dict(row)
    updated['status'] = status
    updated['ok'] = True

    return updated
