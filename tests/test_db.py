'''init_db 이후 테이블과 seed 건수.'''

from app.db.connection import get_conn
from app.db.init_db import init_db

TABLES = (
    'users',
    'stores',
    'products',
    'inventory',
    'orders',
    'requests',
    'inquiries',
)

EXPECTED = {
    'users': 2,
    'stores': 5,
    'products': 8,
    'inventory': 10,
    'orders': 5,
    'requests': 0,
    'inquiries': 0,
}


def test_seed_counts(postgres_env):
    counts = init_db()
    conn = get_conn()

    try:
        names = {
            row['table_name']
            for row in conn.execute(
                '''
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                '''
            )
        }

        for table in TABLES:
            assert table in names
            assert counts[table] == EXPECTED[table]

        assert counts['dispute_docs'] >= 80

        quantity = conn.execute(
            '''
            SELECT i.quantity
            FROM inventory i
            JOIN stores s ON s.store_id = i.store_id
            JOIN products p ON p.product_code = i.product_code
            WHERE s.name = '강남역점' AND p.product_code = 'PRD-6001'
            '''
        ).fetchone()['quantity']

        assert quantity == 10

    finally:
        conn.close()
