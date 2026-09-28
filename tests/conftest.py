'''테스트 공통.'''

import redis
import pytest

from app.config import settings


@pytest.fixture
def sqlite_env(tmp_path, monkeypatch):
    path = tmp_path / 'app.db'
    monkeypatch.setenv('SQLITE_PATH', str(path))
    return path


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
