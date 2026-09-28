'''가까운 지점.

담당: 박서영
'''

from app.redis_store.client import get_redis
from app.redis_store.geo import search_nearest
from app.tools.user_tools import get_user_address
from app.db.connection import fail


def find_nearest_stores(
        user_id: str,
        top_k: int = 3
) -> dict:
    '''사용자 좌표 기준 가까운 지점. 결과가 없으면 EMPTY_RESULT.'''

    address = get_user_address(user_id)

    if not address.get('ok'):
        return address

    try:
        client = get_redis()
        stores = search_nearest(
            client,
            lng=float(address['lng']),
            lat=float(address['lat']),
            count=top_k,
        )

    except Exception as exc:
        return fail('REDIS_UNAVAILABLE', f'지점 좌표를 조회하지 못했습니다. {exc}')

    if not stores:
        return fail('EMPTY_RESULT', '반경 안에 지점이 없습니다.')

    return {
        'ok': True,
        'stores': stores,
    }
