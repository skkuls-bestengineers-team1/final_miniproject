'''Redis 클라이언트.

담당: 김동규
'''

import redis

from app.config import settings


def get_redis() -> redis.Redis:
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=2,
    )
