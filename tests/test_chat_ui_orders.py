from app.api.chat_ui import build_chat_ui


def test_build_chat_ui_orders(monkeypatch):
    monkeypatch.setattr('app.api.chat_ui.fetch_all', lambda sql: [])

    ui = build_chat_ui({
        'last_tool_results': [{
            'ok': True,
            'orders': [{
                'order_id': 'ORD-001',
                'product_name': '사성 비스포크 제트봇 AI',
                'product_code': 'PRD-6001',
                'option': '빨간색',
                'order_date': '2026-09-28',
                'delivery_status': 'PREPARING',
                'ship_address': 'AA동 BB아파트',
                'price': 1290000,
            }],
        }],
    })

    assert ui is not None
    assert ui['orders'][0]['order_id'] == 'ORD-001'
    assert ui['orders'][0]['delivery_status_label'] == '입고 전'
    assert ui['orders'][0]['price'] == 1290000


def test_build_chat_ui_prefers_delivery_detail(monkeypatch):
    monkeypatch.setattr('app.api.chat_ui.fetch_all', lambda sql: [])

    ui = build_chat_ui({
        'last_tool_results': [
            {
                'ok': True,
                'orders': [
                    {
                        'order_id': 'ORD-001',
                        'product_name': '사성 비스포크 제트봇 AI',
                        'delivery_status': 'PREPARING',
                    },
                    {
                        'order_id': 'ORD-003',
                        'product_name': '사성 워치7 블루투스 44mm',
                        'delivery_status': 'IN_TRANSIT',
                        'price': 429000,
                    },
                ],
            },
            {
                'ok': True,
                'order_id': 'ORD-003',
                'product_name': '사성 워치7 블루투스 44mm',
                'option': '블랙',
                'delivery_status': 'IN_TRANSIT',
                'delivery_status_label': '배송 중',
                'ship_address': 'AA동 BB아파트',
            },
        ],
    })

    assert ui is not None
    assert [item['order_id'] for item in ui['orders']] == ['ORD-003']
    assert ui['orders'][0]['delivery_status_label'] == '배송 중'
    assert ui['orders'][0]['price'] == 429000
