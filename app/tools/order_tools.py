'''주문·배송 조회.

담당: 최민정
'''

from app.db.codes import DELIVERY_STATUS_LABEL
from app.db.connection import fail, fetch_all, fetch_one

_ORDER_SQL = '''
    SELECT
        o.order_id,
        o.user_id,
        o.product_code,
        p.product_name,
        p.category_code,
        p.price,
        o.option,
        o.order_date,
        o.delivery_status,
        o.expected_date,
        o.delivered_date,
        o.ship_address
    FROM orders o
    JOIN products p ON p.product_code = o.product_code
'''


def get_orders(
        user_id: str
) -> dict:
    rows = fetch_all(
        _ORDER_SQL + ' WHERE o.user_id = %s ORDER BY o.order_date DESC',
        (user_id,)
    )

    return {
        'ok': True,
        'orders': rows,
    }


def get_order(
        order_id: str,
        user_id: str
) -> dict:
    '''주문 상세. 다른 사용자 주문이면 NOT_OWNER.'''

    row = fetch_one(
        _ORDER_SQL + ' WHERE o.order_id = %s',
        (order_id,)
    )

    if row is None:
        return fail('ORDER_NOT_FOUND', '주문을 찾지 못했습니다.')

    if row['user_id'] != user_id:
        return fail('NOT_OWNER', '본인 주문만 조회할 수 있습니다.')

    return {
        'ok': True,
        **row,
    }


def get_delivery_status(
        order_id: str,
        user_id: str
) -> dict:
    order = get_order(order_id, user_id)

    if not order.get('ok'):
        return order

    status = order['delivery_status']

    return {
        'ok': True,
        'order_id': order['order_id'],
        'product_name': order['product_name'],
        'product_code': order['product_code'],
        'category_code': order['category_code'],
        'option': order['option'],
        'order_date': order['order_date'],
        'price': order['price'],
        'delivery_status': status,
        'delivery_status_label': DELIVERY_STATUS_LABEL.get(status, status),
        'expected_date': order['expected_date'],
        'delivered_date': order['delivered_date'],
        'ship_address': order['ship_address'],
    }
