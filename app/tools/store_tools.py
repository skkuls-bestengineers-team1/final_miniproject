'''가까운 지점.

담당: 박서영
'''

from app.redis_store.client import get_redis
from app.redis_store.geo import search_nearest
from app.tools.user_tools import get_user_address
from app.db.connection import fail

SEARCH_RADIUS_KM = (50, 200)    # 가까운 반경에 지점이 없으면 한 번 넓혀 찾는다.


def find_nearest_stores(
        user_id: str,
        top_k: int = 3,
        origin: dict | None = None
) -> dict:
    '''검색 기준점(search_origin) 근처 지점. origin이 없으면 등록 주소 기준. 결과가 없으면 EMPTY_RESULT.'''

    if origin:
        lat, lng = origin['lat'], origin['lng']
        basis = origin.get('source', 'registered')
        label = origin.get('label', '')

    else:
        address = get_user_address(user_id)

        if not address.get('ok'):
            return address

        lat, lng = address['lat'], address['lng']
        basis = 'registered'
        label = '등록 주소'

    stores = []
    radius_km = SEARCH_RADIUS_KM[0]

    try:
        client = get_redis()

        for radius_km in SEARCH_RADIUS_KM:
            stores = search_nearest(
                client,
                lng=float(lng),
                lat=float(lat),
                count=top_k,
                radius_km=radius_km,
            )

            if stores:
                break

    except Exception as exc:
        return fail('REDIS_UNAVAILABLE', f'지점 좌표를 조회하지 못했습니다. {exc}')

    if not stores:
        return fail('EMPTY_RESULT', f'{label} 기준 {SEARCH_RADIUS_KM[-1]}km 안에 지점이 없습니다.')

    return {
        'ok': True,
        'stores': stores,
        'basis': basis,
        'label': label,
        'radius_km': radius_km,
    }
