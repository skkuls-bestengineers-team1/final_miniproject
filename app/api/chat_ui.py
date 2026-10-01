'''채팅 화면에 붙일 지점·상품·주문 카드.

검증은 Tool 결과만 본다. 카드는 last_tool_results를 읽는다.
'''

from app.db.codes import CATEGORY_LABEL, DELIVERY_STATUS_LABEL
from app.db.connection import fetch_all

STORE_PHOTOS = {
    '강남역점': 'https://images.unsplash.com/photo-1441986300917-64674bd600d8?auto=format&fit=crop&w=900&q=80',
    '용산점': 'https://images.unsplash.com/photo-1486325212027-8081e485255e?auto=format&fit=crop&w=900&q=80',
    '일산점': 'https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=900&q=80',
    '잠실점': 'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=900&q=80',
    '수원점': 'https://images.unsplash.com/photo-1464146072230-91cabc968266?auto=format&fit=crop&w=900&q=80',
}

PRODUCT_PHOTOS = {
    'ROBOT_CLEANER': 'https://images.unsplash.com/photo-1558317374-067fb5f30001?auto=format&fit=crop&w=900&q=80',
    'WEARABLE': 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=80',
    'AUDIO': 'https://images.unsplash.com/photo-1590658268037-6bf12165a8df?auto=format&fit=crop&w=900&q=80',
    'TABLET': 'https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?auto=format&fit=crop&w=900&q=80',
    'POWER': 'https://images.unsplash.com/photo-1609091839311-d5365f9ff1c4?auto=format&fit=crop&w=900&q=80',
    'SMART_HOME': 'https://images.unsplash.com/photo-1558002038-1055907df827?auto=format&fit=crop&w=900&q=80',
    'COMPUTER': 'https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=900&q=80',
}

PRODUCT_CODE_PHOTOS = {
    'PRD-6001': 'https://images.unsplash.com/photo-1558317374-067fb5f30001?auto=format&fit=crop&w=900&q=80',
    'PRD-6002': 'https://images.unsplash.com/photo-1589003077984-894e133dabab?auto=format&fit=crop&w=900&q=80',
    'PRD-6003': 'https://images.unsplash.com/photo-1518444065439-e933c06ce9cd?auto=format&fit=crop&w=900&q=80',
    'PRD-1001': 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=80',
    'PRD-1002': 'https://images.unsplash.com/photo-1590658268037-6bf12165a8df?auto=format&fit=crop&w=900&q=80',
    'PRD-1003': 'https://images.unsplash.com/photo-1434493789847-2f02dc6ce31a?auto=format&fit=crop&w=900&q=80',
    'PRD-1004': 'https://images.unsplash.com/photo-1484704849700-f032a568e944?auto=format&fit=crop&w=900&q=80',
    'PRD-2001': 'https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?auto=format&fit=crop&w=900&q=80',
    'PRD-2002': 'https://images.unsplash.com/photo-1561154464-82e9adf32764?auto=format&fit=crop&w=900&q=80',
    'PRD-3001': 'https://images.unsplash.com/photo-1583863788434-e58a36330cf0?auto=format&fit=crop&w=900&q=80',
    'PRD-3002': 'https://images.unsplash.com/photo-1609091839311-d5365f9ff1c4?auto=format&fit=crop&w=900&q=80',
    'PRD-4001': 'https://images.unsplash.com/photo-1558002038-1055907df827?auto=format&fit=crop&w=900&q=80',
    'PRD-4002': 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?auto=format&fit=crop&w=900&q=80',
    'PRD-5001': 'https://images.unsplash.com/photo-1511467687858-23d96c32e4ae?auto=format&fit=crop&w=900&q=80',
    'PRD-5002': 'https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=900&q=80',
}


def _store_rows() -> dict:
    rows = fetch_all(
        'SELECT store_id, name, address, lat, lng FROM stores'
    )
    return {row['name']: row for row in rows}


def _iso_date(value) -> str:
    if value is None:
        return ''

    if hasattr(value, 'isoformat'):
        return str(value.isoformat())[:10]

    return str(value)[:10]


def _photo_url(product_code: str, category_code: str) -> str:
    return PRODUCT_CODE_PHOTOS.get(product_code) or PRODUCT_PHOTOS.get(
        category_code, PRODUCT_PHOTOS['ROBOT_CLEANER']
    )


def _order_card(item: dict) -> dict | None:
    order_id = item.get('order_id')

    if not order_id:
        return None

    status = item.get('delivery_status') or ''
    product_code = item.get('product_code') or ''
    category = item.get('category_code') or ''
    price = item.get('price')

    return {
        'order_id': order_id,
        'product_name': item.get('product_name') or '',
        'product_code': product_code,
        'option': item.get('option') or '',
        'order_date': _iso_date(item.get('order_date')),
        'expected_date': _iso_date(item.get('expected_date')),
        'delivered_date': _iso_date(item.get('delivered_date')),
        'delivery_status': status,
        'delivery_status_label': item.get('delivery_status_label') or DELIVERY_STATUS_LABEL.get(status, status),
        'ship_address': item.get('ship_address') or '',
        'price': int(price) if price is not None else None,
        'photo_url': _photo_url(product_code, category),
    }


def build_chat_ui(
        values: dict | None
) -> dict | None:
    try:
        results = (values or {}).get('last_tool_results') or []
    except Exception:
        return None
    stores: list[dict] = []
    products: list[dict] = []
    list_orders: dict[str, dict] = {}
    detail_orders: dict[str, dict] = {}

    try:
        catalog = _store_rows() if results else {}
    except Exception:
        catalog = {}

    for payload in results:
        if not isinstance(payload, dict) or not payload.get('ok'):
            continue

        for index, item in enumerate(payload.get('stores') or []):
            name = item.get('store_name') or ''
            row = catalog.get(name) or {}
            stores.append({
                'rank': index + 1,
                'store_name': name,
                'distance_km': float(item['distance_km']) if item.get('distance_km') is not None else None,
                'address': row.get('address') or '',
                'lat': row.get('lat'),
                'lng': row.get('lng'),
                'photo_url': STORE_PHOTOS.get(name, STORE_PHOTOS['강남역점']),
            })

        store_name = payload.get('store_name') or ''

        for item in payload.get('items') or []:
            code = item.get('category_code') or ''
            product_code = item.get('product_code') or ''
            products.append({
                'store_name': store_name,
                'product_code': product_code,
                'product_name': item.get('product_name'),
                'category': CATEGORY_LABEL.get(code, code),
                'quantity': item.get('quantity'),
                'price': item.get('price'),
                'photo_url': _photo_url(product_code, code),
            })

        for item in payload.get('orders') or []:
            card = _order_card(item)

            if card:
                list_orders[card['order_id']] = card

        if payload.get('order_id') and payload.get('product_name'):
            card = _order_card(payload)

            if card:
                previous = detail_orders.get(card['order_id']) or list_orders.get(card['order_id']) or {}
                merged = {**previous, **{key: value for key, value in card.items() if value}}
                detail_orders[card['order_id']] = merged

    question_text = ' '.join(str(p.get('question', '')) for p in results if isinstance(p, dict))
    filtered_orders = {order_id: card for order_id, card in list_orders.items() if order_id in question_text}
    orders = detail_orders if detail_orders else (filtered_orders or list_orders)

    if not stores and not products and not orders:
        return None

    return {
        'stores': stores,
        'products': products,
        'orders': list(orders.values()),
    }
