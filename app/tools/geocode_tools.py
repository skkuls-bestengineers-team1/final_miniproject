'''주소 문자열 → 좌표 변환.

담당: 박서영
OpenStreetMap Nominatim을 쓴다. 사용 정책(https://operations.osmfoundation.org/policies/nominatim/):
  - 초당 1회 이하, 앱을 식별하는 User-Agent 필수
  - 결과 캐싱 필수 → Redis geocode:{주소}
  - 자동완성 금지 → 사용자가 입력을 보낸 뒤에만 호출
  - 화면에 "© OpenStreetMap contributors" 표시
'''

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import settings

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
CACHE_PREFIX = 'geocode:'
CACHE_TTL_SECONDS = 30 * 24 * 3600      # 역·동 좌표는 거의 바뀌지 않는다.
MISS_TTL_SECONDS = 3600                 # 못 찾은 주소도 반복 호출하지 않도록 짧게 저장
TIMEOUT_SECONDS = 5


def normalize_address(
        address: str
) -> str:
    '''캐시 키용. 앞뒤·중복 공백을 없애고 소문자로 맞춘다.'''

    return ' '.join((address or '').split()).lower()


def _cache_get(
        key: str
) -> tuple[bool, dict | None]:
    '''(캐시에 있었는지, 값). Redis가 꺼져 있으면 캐시 없이 진행한다.'''

    try:
        from app.redis_store.client import get_redis

        raw = get_redis().get(key)

    except Exception:
        return False, None

    if raw is None:
        return False, None

    value = json.loads(raw)

    return True, value or None


def _cache_set(
        key: str,
        value: dict | None
) -> None:
    try:
        from app.redis_store.client import get_redis

        ttl = CACHE_TTL_SECONDS if value else MISS_TTL_SECONDS
        get_redis().set(key, json.dumps(value or {}, ensure_ascii=False), ex=ttl)

    except Exception:
        pass


def _call_nominatim(
        address: str
) -> dict | None:
    '''국내 결과 1건. 네트워크 오류는 호출한 쪽에서 처리한다.'''

    query = urlencode({
        'q': address,
        'format': 'json',
        'countrycodes': 'kr',
        'limit': 1,
        'accept-language': 'ko',
    })
    request = Request(
        f'{NOMINATIM_URL}?{query}',
        headers={'User-Agent': settings.nominatim_user_agent},
    )

    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        rows = json.loads(response.read().decode('utf-8'))

    if not rows:
        return None

    return {
        'lat': float(rows[0]['lat']),
        'lng': float(rows[0]['lon']),      # Nominatim은 경도 키가 lon이다.
    }


def geocode(
        address: str
) -> dict | None:
    '''주소를 {lat, lng, label}로 바꾼다. 못 찾거나 호출에 실패하면 None.'''

    normalized = normalize_address(address)

    if not normalized:
        return None

    key = f'{CACHE_PREFIX}{normalized}'
    hit, cached = _cache_get(key)

    if hit:
        return cached

    try:
        found = _call_nominatim(normalized)

    except Exception as exc:
        # 일시적인 실패는 캐시하지 않는다.
        print(f'주소 변환 생략: {exc}')
        return None

    result = None

    if found:
        result = {
            **found,
            'label': ' '.join(address.split()),
        }

    _cache_set(key, result)

    return result
