'''지점 검색 기준점(search_origin).

담당: 박서영
worker1·2가 가까운 지점을 찾을 때 쓰는 기준 좌표다. 주문·배송 주소(ship_address, pickup_address)와 별개다.
형태: {lat, lng, source, label, at}
  source: 'current'(브라우저 현재 위치) / 'typed'(입력한 주소) / 'registered'(회원 등록 주소)
'''

from datetime import datetime, timedelta

from app.graph.state import State
from app.tools.geocode_tools import geocode
from app.tools.user_tools import get_user_address

ORIGIN_TTL_MINUTES = 30                 # 사용자는 이동하므로 오래된 기준점은 다시 묻는다.
TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

# 기준을 바꿔 달라는 말. 서버는 브라우저 위치를 직접 알 수 없어 'current'면 [현재 위치 사용] 버튼을 다시 띄운다.
CURRENT_ORIGIN_WORDS = (
    '현재 위치', '현재위치', '현재 주소', '현재주소', '지금 위치', '지금 있는',
    '내 위치', '내위치', '여기서', '여기 근처', '이 근처',
)
REGISTERED_ORIGIN_WORDS = (
    '등록 주소', '등록주소', '등록된 주소', '회원 주소', '우리 집', '우리집', '집 근처', '집 주변',
)
ASK_CURRENT_POSITION_MESSAGE = (
    '현재 위치로 찾으려면 아래 [현재 위치 사용]을 눌러 주세요.\n'
    '다른 곳을 기준으로 하려면 역·동 이름을 입력해 주세요.'
)


def _last_index(
        text: str,
        words: tuple[str, ...]
) -> int:
    return max((text.rfind(word) for word in words), default=-1)


def origin_request_from_text(
        text: str
) -> str | None:
    '''"현재 위치 기준으로", "등록 주소로"처럼 기준을 바꿔 달라는 말이면 'current' / 'registered'.

    "등록 주소 말고 현재 주소"처럼 둘 다 있으면 뒤에 나온 쪽을 따른다.
    '''

    current_at = _last_index(text or '', CURRENT_ORIGIN_WORDS)
    registered_at = _last_index(text or '', REGISTERED_ORIGIN_WORDS)

    if current_at < 0 and registered_at < 0:
        return None

    return 'current' if current_at > registered_at else 'registered'


def _make_origin(
        lat: float,
        lng: float,
        source: str,
        label: str
) -> dict:
    return {
        'lat': float(lat),
        'lng': float(lng),
        'source': source,
        'label': label,
        'at': datetime.now().strftime(TIME_FORMAT),
    }


def current_origin(
        lat: float,
        lng: float
) -> dict:
    '''브라우저가 보낸 현재 위치.'''

    return _make_origin(lat, lng, 'current', '현재 위치')


def registered_origin(
        user_id: str
) -> dict | None:
    '''회원 등록 주소. 사용자가 없으면 None.'''

    address = get_user_address(user_id)

    if not address.get('ok'):
        return None

    return _make_origin(address['lat'], address['lng'], 'registered', '등록 주소')


def typed_origin(
        text: str
) -> dict | None:
    '''사용자가 입력한 주소. 좌표로 바꾸지 못하면 None.'''

    found = geocode(text)

    if not found:
        return None

    return _make_origin(found['lat'], found['lng'], 'typed', found['label'])


def is_fresh(
        origin: dict | None
) -> bool:
    '''기준점이 있고 받은 지 ORIGIN_TTL_MINUTES 안인지.'''

    if not origin or origin.get('lat') is None or origin.get('lng') is None:
        return False

    try:
        received = datetime.strptime(origin['at'], TIME_FORMAT)

    except (KeyError, TypeError, ValueError):
        return False

    return datetime.now() - received <= timedelta(minutes=ORIGIN_TTL_MINUTES)


def resolve_search_origin(
        state: State
) -> tuple[dict | None, bool]:
    '''(기준점, 물어봐야 하는지).

    - 유효한 기준점이 State에 있으면 그대로 쓴다.
    - 이미 한 번 물었으면 다시 묻지 않고 등록 주소를 쓴다.
    - 아직 묻지 않았으면 물어봐야 한다.
    '''

    origin = state.get('search_origin')

    if is_fresh(origin):
        return origin, False

    if state.get('search_origin_asked'):
        return registered_origin(state['user_id']), False

    return None, True
