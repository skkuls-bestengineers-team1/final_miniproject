'''테스트 공통.'''

import psycopg
import redis
import pytest

from app.config import settings


def postgres_up() -> bool:
    try:
        with psycopg.connect(
            settings.database_url,
            connect_timeout=1,
        ) as conn:
            conn.execute('SELECT 1')
        return True

    except Exception:
        return False


def redis_up() -> bool:
    try:
        client = redis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=0.5,
            socket_timeout=1,
        )
        return bool(client.ping())

    except Exception:
        return False


@pytest.fixture
def postgres_env():
    if not postgres_up():
        pytest.skip('PostgreSQL이 없습니다.')
