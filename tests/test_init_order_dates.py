'''주문 seed 날짜는 실행일 기준 상대값이다.'''

import json
from datetime import date

import pytest

from app.db.init_db import (
    SEED_DIR,
    _dated_orders,
    assert_unique_order_products,
    resolve_seed_date,
)


def test_resolve_seed_date_offsets():
    today = date(2026, 10, 1)

    assert resolve_seed_date('TODAY', today) == '2026-10-01'
    assert resolve_seed_date('TODAY-3', today) == '2026-09-28'
    assert resolve_seed_date('TODAY+2', today) == '2026-10-03'
    assert resolve_seed_date(None, today) is None
    assert resolve_seed_date('2026-09-22', today) == '2026-09-22'


def test_dated_orders_keeps_demo_windows():
    today = date(2026, 10, 1)
    rows = _dated_orders(
        [
            {'order_id': 'ORD-004', 'delivered_date': 'TODAY-3'},
            {'order_id': 'ORD-005', 'delivered_date': 'TODAY-60'},
        ],
        today,
    )

    assert rows[0]['delivered_date'] == '2026-09-28'
    assert rows[1]['delivered_date'] == '2026-08-02'


def test_seed_orders_unique_product_names_per_user():
    orders = json.loads((SEED_DIR / 'orders.json').read_text(encoding='utf-8'))
    products = json.loads((SEED_DIR / 'products.json').read_text(encoding='utf-8'))

    assert_unique_order_products(orders, products)

    names = {item['product_code']: item['product_name'] for item in products}
    u001 = [
        names[order['product_code']]
        for order in orders
        if order['user_id'] == 'U001'
    ]

    assert '사성 비스포크 제트봇 AI' in u001
    assert '사성 워치 Ultra' in u001
    assert u001.count('사성 비스포크 제트봇 AI') == 1


def test_assert_unique_order_products_rejects_overlap():
    orders = [
        {'user_id': 'U001', 'product_code': 'A'},
        {'user_id': 'U001', 'product_code': 'B'},
    ]
    products = [
        {'product_code': 'A', 'product_name': '같은 이름'},
        {'product_code': 'B', 'product_name': '같은 이름'},
    ]

    with pytest.raises(ValueError, match='제품명이 겹칩니다'):
        assert_unique_order_products(orders, products)
