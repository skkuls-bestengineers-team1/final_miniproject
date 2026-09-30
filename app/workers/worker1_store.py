'''UC1 가까운 지점.

담당: 박서영
검색 기준점(search_origin)에서 가까운 지점 3곳을 안내한다. 검증은 지점 순서·이름을 Tool과 대조.
발화에 위치가 있으면("용산역 근처 매장") 묻지 않고 그 위치로 찾는다.
기준점이 없으면 한 번 묻는다: 현재 위치 / 주소 입력 / 등록 주소.
'''

from pydantic import BaseModel

from app.config import settings
from app.graph.confirm import finished, latest_user_text, validation_retry_update, waiting
from app.graph.state import State
from app.llm import get_llm
from app.tools.search_origin import is_fresh, registered_origin, resolve_search_origin, typed_origin
from app.tools.store_tools import find_nearest_stores
from app.tools.user_tools import get_user

TOP_K = 3
ASK_ORIGIN_MESSAGE = (
    '가까운 지점을 찾으려면 기준 위치가 필요해요.\n'
    '현재 위치를 쓰거나, 역·동 이름을 입력하거나, 등록 주소로 찾을 수 있어요.'
)
RETRY_ORIGIN_MESSAGE = '입력한 위치를 찾지 못했어요. 역이나 동 이름으로 다시 입력해 주세요.'
NO_ORIGIN_MESSAGE = '기준 위치를 확인하지 못해 가까운 지점을 안내할 수 없습니다. 역이나 동 이름으로 다시 물어봐 주세요.'
RESERVATION_GUIDE = '방문 예약을 원하시면 아래에서 예약하러 가기를 눌러 주세요.'
MAX_ORIGIN_ATTEMPTS = 2     # 주소를 이만큼 못 찾으면 등록 주소로 대신한다.


class LocationQuery(BaseModel):
    '''발화 속 기준 위치 표현.'''

    location_text: str | None = None


def _extract_location(
        text: str
) -> str | None:
    '''"용산역 근처 매장"처럼 기준이 되는 지명을 말했으면 그 지명. 없거나 LLM을 못 쓰면 None.'''

    if not settings.gemini_api_key:
        return None

    prompt = f'''당신은 가까운 매장 문의에서 기준 위치를 뽑는 역할입니다.

- 기준이 되는 지명(역·동·구·랜드마크 이름)을 말했으면 그 지명만 location_text에 씁니다. (예: "용산역 근처 매장 알려줘" → "용산역")
- "나랑 가까운", "여기서", "우리 집 근처"처럼 지명이 없으면 null로 둡니다.

발화: {text}'''

    try:
        result = get_llm().with_structured_output(LocationQuery).invoke(prompt)

    except Exception as exc:
        print(f'기준 위치 추출 생략: {exc}')
        return None

    if result is None:
        return None

    return (result.location_text or '').strip() or None


def _answer(
        state: State,
        origin: dict
) -> dict:
    '''기준점에서 가까운 지점을 순위대로 안내한다. 기준점은 다음 대화에서 다시 쓰도록 State에 남긴다.'''

    result = find_nearest_stores(state['user_id'], top_k=TOP_K, origin=origin)

    if not result.get('ok'):
        update = finished(state, 'worker1', result.get('message', '가까운 지점을 찾지 못했습니다.'), result)
        update['search_origin'] = origin
        return update

    user = get_user(state['user_id'])
    name = user.get('name') if user.get('ok') else '고객'
    stores = result['stores']
    first = stores[0]
    lines = [
        f"{name} 님, {origin['label']} 기준 가장 가까운 지점은 {first['store_name']}입니다. "
        f"(거리: 약 {float(first['distance_km']):.1f}km)"
    ]

    for index, store in enumerate(stores[1:], start=2):
        distance = float(store['distance_km'])
        lines.append(f"{index}순위 {store['store_name']} (거리: 약 {distance:.1f}km)")

    lines.append(RESERVATION_GUIDE)

    update = finished(state, 'worker1', '\n'.join(lines), result)
    update['search_origin'] = origin

    return update


def _handle_origin_answer(
        state: State,
        pending: dict,
        text: str
) -> dict:
    '''기준 위치를 물은 뒤의 답. 버튼 선택은 main.py가 search_origin에 이미 넣어 두었다.'''

    user_id = state['user_id']
    origin = state.get('search_origin')

    # 물을 때는 유효한 기준점이 없었으므로, 지금 유효하면 이번 턴에 버튼으로 받은 값이다.
    if is_fresh(origin):
        return _answer(state, origin)

    # 버튼 대신 입력한 답: "등록 주소"라고 했거나 주소를 입력했다.
    if '등록' in text:
        origin = registered_origin(user_id)

    else:
        origin = typed_origin(text)

    if origin:
        return _answer(state, origin)

    attempts = int(pending.get('origin_attempts') or 0) + 1

    if attempts >= MAX_ORIGIN_ATTEMPTS:
        origin = registered_origin(user_id)

        if origin:
            return _answer(state, origin)

        return finished(state, 'worker1', NO_ORIGIN_MESSAGE)

    pending['origin_attempts'] = attempts

    return waiting(state, 'worker1', 'ask_search_origin', RETRY_ORIGIN_MESSAGE, pending)


def worker1(
        state: State
) -> dict:
    retried = validation_retry_update(state, 'worker1')

    if retried:
        return retried

    pending = dict(state.get('pending_data') or {})
    text = latest_user_text(state)

    # 기준 위치를 물은 뒤의 답
    if state.get('step') == 'ask_search_origin':
        return _handle_origin_answer(state, pending, text)

    # "용산역 근처 매장"처럼 기준 위치를 직접 말한 경우
    location_text = _extract_location(text)

    if location_text:
        origin = typed_origin(location_text)

        if origin:
            return _answer(state, origin)

    origin, need_ask = resolve_search_origin(state)

    if origin:
        return _answer(state, origin)

    if need_ask:
        update = waiting(state, 'worker1', 'ask_search_origin', ASK_ORIGIN_MESSAGE, {})
        update['search_origin_asked'] = True
        return update

    return finished(state, 'worker1', NO_ORIGIN_MESSAGE)
