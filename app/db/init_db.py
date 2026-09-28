'''테이블 생성, Mock 데이터 입력, Redis GEO 적재.

담당: 김동규

실행: python -m app.db.init_db
'''

import json
from pathlib import Path

from app.db.connection import get_conn

ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = ROOT / 'data' / 'seed'
SCHEMA_PATH = Path(__file__).resolve().parent / 'schema.sql'

CLEAR_SQL = [
    'DELETE FROM inquiries',
    'DELETE FROM requests',
    'DELETE FROM orders',
    'DELETE FROM inventory',
    'DELETE FROM products',
    'DELETE FROM stores',
    'DELETE FROM users',
]


def _load_json(
        name: str
) -> list[dict]:
    path = SEED_DIR / name

    with path.open(encoding='utf-8') as file:
        return json.load(file)


def _insert_rows(
        conn,
        sql: str,
        rows: list[dict],
        columns: list[str]
) -> None:
    values = [
        tuple(row.get(column) for column in columns)
        for row in rows
    ]

    conn.executemany(sql, values)


def init_db() -> dict:
    '''스키마를 만들고 seed를 다시 넣는다. Redis가 있으면 지점 좌표를 적재한다.'''

    conn = get_conn()

    try:
        schema = SCHEMA_PATH.read_text(encoding='utf-8')
        conn.executescript(schema)
        conn.execute('PRAGMA foreign_keys = ON')

        for statement in CLEAR_SQL:
            conn.execute(statement)

        _insert_rows(
            conn,
            '''
            INSERT INTO users (user_id, name, phone, address, lat, lng)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            _load_json('users.json'),
            ['user_id', 'name', 'phone', 'address', 'lat', 'lng']
        )

        _insert_rows(
            conn,
            '''
            INSERT INTO stores (store_id, name, address, lat, lng)
            VALUES (?, ?, ?, ?, ?)
            ''',
            _load_json('stores.json'),
            ['store_id', 'name', 'address', 'lat', 'lng']
        )

        _insert_rows(
            conn,
            '''
            INSERT INTO products (product_code, product_name, category_code, price)
            VALUES (?, ?, ?, ?)
            ''',
            _load_json('products.json'),
            ['product_code', 'product_name', 'category_code', 'price']
        )

        _insert_rows(
            conn,
            '''
            INSERT INTO inventory (store_id, product_code, quantity)
            VALUES (?, ?, ?)
            ''',
            _load_json('inventory.json'),
            ['store_id', 'product_code', 'quantity']
        )

        _insert_rows(
            conn,
            '''
            INSERT INTO orders (
                order_id, user_id, product_code, option, order_date,
                delivery_status, expected_date, delivered_date, ship_address
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            _load_json('orders.json'),
            [
                'order_id', 'user_id', 'product_code', 'option', 'order_date',
                'delivery_status', 'expected_date', 'delivered_date', 'ship_address'
            ]
        )

        conn.commit()

        counts = {
            table: conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            for table in (
                'users', 'stores', 'products', 'inventory', 'orders', 'requests', 'inquiries'
            )
        }

    finally:
        conn.close()

    counts['geo'] = _load_geo()

    return counts


def _load_geo() -> int:
    '''Redis가 꺼져 있으면 0을 반환하고 SQLite 초기화는 성공으로 둔다.'''

    try:
        from app.redis_store.client import get_redis
        from app.redis_store.geo import load_store_geo

        client = get_redis()
        client.ping()
        conn = get_conn()

        try:
            return load_store_geo(conn, client)

        finally:
            conn.close()

    except Exception as exc:
        print(f'Redis GEO 적재 생략: {exc}')
        return 0


def main() -> None:
    counts = init_db()

    print('SQLite 초기화 완료')

    for name, count in counts.items():
        print(f'- {name}: {count}')


if __name__ == '__main__':
    main()
