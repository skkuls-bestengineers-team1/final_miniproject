'''U001 기준 가까운 지점 3곳, 거리 오름차순.'''

import pytest

from app.db.connection import get_conn
from app.db.init_db import init_db
from app.redis_store.client import get_redis
from app.redis_store.geo import search_nearest
from tests.conftest import redis_up


def test_nearest_three_sorted(postgres_env):
    if not redis_up():
        pytest.skip('Redis가 없습니다.')

    init_db()
    conn = get_conn()

    try:
        user = conn.execute(
            'SELECT lat, lng FROM users WHERE user_id = %s',
            ('U001',)
        ).fetchone()

    finally:
        conn.close()

    rows = search_nearest(
        get_redis(),
        lng=user['lng'],
        lat=user['lat'],
        count=3,
    )

    assert len(rows) == 3
    distances = [row['distance_km'] for row in rows]
    assert distances == sorted(distances)
    assert rows[0]['store_name'] == '강남역점'
