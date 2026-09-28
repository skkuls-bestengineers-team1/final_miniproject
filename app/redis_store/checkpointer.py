'''LangGraph RedisSaver.

담당: 나송주
thread_id = user_id, TTL 30분.
TODO(나송주): 패키지 버전별 from_conn_string 인자명이 다르면 README의 호출부를 맞춘다.
'''

from app.config import settings

_saver = None
_context = None


def get_checkpointer():
    '''프로세스 동안 하나의 RedisSaver를 유지한다. setup()은 한 번만 호출한다.'''

    global _saver, _context

    if _saver is not None:
        return _saver

    from langgraph.checkpoint.redis import RedisSaver

    ttl = {
        'default_ttl': settings.session_ttl_minutes,
        'refresh_on_read': True,
    }

    try:
        created = RedisSaver.from_conn_string(
            settings.redis_url,
            ttl=ttl,
        )

    except TypeError:
        created = RedisSaver.from_conn_string(settings.redis_url)

    if hasattr(created, '__enter__'):
        _context = created
        saver = created.__enter__()

    else:
        saver = created

    saver.setup()
    _saver = saver

    return _saver


def close_checkpointer() -> None:
    global _saver, _context

    if _context is not None:
        _context.__exit__(None, None, None)

    _context = None
    _saver = None
