'''UC2 재고.

담당: 박서영
LLM 추출(실패 시 키워드).
지점을 말하지 않으면 검색 기준점(search_origin)에서 가장 가까운 지점의 재고로 답한다.
기준점이 없으면 한 번 묻는다: 현재 위치 / 주소 입력 / 등록 주소.
'''

from typing import Literal

from pydantic import BaseModel

from app.config import settings
from app.db.codes import CATEGORY_KEYWORDS, CATEGORY_LABEL
from app.db.connection import fetch_all
from app.graph.confirm import finished, latest_user_text, validation_retry_update, waiting
from app.graph.state import State
from app.llm import get_llm
from app.tools.search_origin import (
    ASK_CURRENT_POSITION_MESSAGE,
    is_fresh,
    origin_request_from_text,
    registered_origin,
    resolve_search_origin,
    typed_origin,
)
from app.tools.stock_tools import get_stock
from app.tools.store_tools import find_nearest_stores

ASK_ORIGIN_MESSAGE = (
    '가까운 지점을 찾으려면 기준 위치가 필요해요.\n'
    '현재 위치를 쓰거나, 역·동 이름을 입력하거나, 등록 주소로 찾을 수 있어요.'
)
RETRY_ORIGIN_MESSAGE = '입력한 위치를 찾지 못했어요. 역이나 동 이름으로 다시 입력해 주세요.'
ASK_STORE_MESSAGE = '어느 지점의 재고를 확인할까요?'
MAX_ORIGIN_ATTEMPTS = 2     # 주소를 이만큼 못 찾으면 등록 주소로 대신한다.


class StockQuery(BaseModel):
    '''발화에서 뽑은 재고 조회 조건. 목록에 없으면 None.'''

    store_name: str | None = None
    product_name: str | None = None
    category_code: str | None = None
    location_text: str | None = None    # 지점이 아닌 기준 위치 표현 (예: "용산 근처" → "용산")
    origin_request: Literal['current', 'registered'] | None = None     # "현재 위치로 / 등록 주소로"


def _match_store(
        text: str
) -> str | None:
    names = [
        row['name']
        for row in fetch_all('SELECT name FROM stores ORDER BY length(name) DESC')
    ]

    for name in names:
        stem = name[:-1] if name.endswith('점') else name

        if name in text or stem in text:
            return name

    return None


def _match_product(
        text: str
) -> str | None:
    names = [
        row['product_name']
        for row in fetch_all(
            'SELECT product_name FROM products ORDER BY length(product_name) DESC'
        )
    ]

    for name in names:
        if name in text:
            return name

    return None


def _match_category(
        text: str
) -> str | None:
    for keyword, code in CATEGORY_KEYWORDS.items():
        if keyword in text:
            return code

    return None


def _extract_with_llm(
        text: str
) -> StockQuery | None:
    '''LLM 구조화 출력으로 지점·제품·카테고리를 뽑는다. 실패하면 None.'''

    if not settings.gemini_api_key:
        return None

    # stores·products에서 지점명·제품명 목록 조회
    store_names = [
        row['name']
        for row in fetch_all('SELECT name FROM stores ORDER BY name')
    ]

    product_names = [
        row['product_name']
        for row in fetch_all('SELECT product_name FROM products ORDER BY product_name')
    ]

    # CATEGORY_LABEL로 카테고리 코드 목록 구성 (예: ROBOT_CLEANER(로봇청소기))
    category_options = [
        f'{code}({label})'
        for code, label in CATEGORY_LABEL.items()
    ]

    # 목록을 넣은 프롬프트 작성 (목록 값 그대로 고르고, 없으면 null)
    prompt = f'''당신은 사성전자 매장 재고 문의에서 조회 조건을 뽑는 역할입니다.

아래 목록에 있는 값만 그대로 고르세요. 목록에 없거나 발화에 없으면 null로 둡니다.

- store_name: 지점 목록 중 하나. "강남역", "강남"처럼 줄여 말해도 목록의 정확한 이름으로 고릅니다.
- product_name: 제품 목록 중 하나. 특정 제품을 말했을 때만 채웁니다.
- category_code: 카테고리 목록의 괄호 앞 코드만 씁니다. (예: ROBOT_CLEANER) product_name이 있으면 null로 둡니다.
- location_text: 지점 목록에 없는 기준 위치(역·동·구 이름 등)를 말했을 때만 그 지명만 씁니다. (예: "용산 근처 재고" → "용산") store_name을 채웠으면 null로 둡니다.
- origin_request: 가까운 지점의 기준을 직접 지정했을 때만 씁니다. "현재 위치", "지금 있는 곳", "여기서" → "current", "등록 주소", "우리 집" → "registered". "A 말고 B"라고 하면 B를 따릅니다. 기준을 정하지 않았으면 null로 둡니다.

지점 목록: {', '.join(store_names)}
제품 목록: {', '.join(product_names)}
카테고리 목록: {', '.join(category_options)}

발화: {text}'''

    # get_llm().with_structured_output(StockQuery)로 호출
    try:
        extractor = get_llm().with_structured_output(StockQuery)
        result = extractor.invoke(prompt)

    except Exception as exc:
        print(f'재고 조건 추출 생략: {exc}')
        return None

    if result is None:
        return None

    # 목록에 없는 값은 버린다. 잘못된 category_code는 get_stock이 걸러내지 못해 0개로 답하게 된다.
    if result.store_name not in store_names:
        result.store_name = None

    if result.product_name not in product_names:
        result.product_name = None

    if result.category_code not in CATEGORY_LABEL:
        result.category_code = None

    if result.store_name or not (result.location_text or '').strip():
        result.location_text = None

    return result


def _extract(
        text: str
) -> StockQuery:
    '''LLM 추출을 먼저 쓰고, 실패하면 키워드 매칭으로 대신한다.'''

    # 기준을 바꿔 달라는 말은 키워드가 우선이고, LLM이 다른 표현을 보완한다.
    keyword_request = origin_request_from_text(text)

    # _extract_with_llm 결과가 있으면 그대로 반환
    extracted = _extract_with_llm(text)

    if extracted is not None:
        # LLM이 지점을 놓쳤으면 지점명 키워드로 한 번 더 찾는다.
        if extracted.store_name is None:
            extracted.store_name = _match_store(text)

        if extracted.store_name:
            extracted.location_text = None

        extracted.origin_request = keyword_request or extracted.origin_request

        return extracted

    # 없으면 _match_store·_match_product·_match_category로 StockQuery 구성
    product_name = _match_product(text)

    return StockQuery(
        store_name=_match_store(text),
        product_name=product_name,
        category_code=None if product_name else _match_category(text),
        origin_request=keyword_request,
    )


def _nearest_store(
        user_id: str,
        origin: dict
) -> str | None:
    '''검색 기준점에서 가장 가까운 지점명. 찾지 못하면 None.'''

    result = find_nearest_stores(user_id, top_k=1, origin=origin)

    if not result.get('ok') or not result.get('stores'):
        return None

    return result['stores'][0]['store_name']


def _format_stock(
        result: dict
) -> str:
    if not result.get('ok'):
        return result.get('message', '재고를 확인하지 못했습니다.')

    items = result.get('items') or []
    store_name = result.get('store_name') or ''

    lines = [f"{store_name} 재고입니다. 아래에서 상품 정보를 볼 수 있습니다."]

    for item in items:
        category = CATEGORY_LABEL.get(item.get('category_code') or '', item.get('category_code') or '')
        price = item.get('price')
        price_text = f"{int(price):,}원" if price is not None else '-'
        lines.append(
            f"- {item['product_name']} ({category}): 재고 {item['quantity']}개 · {price_text}"
        )

    return '\n'.join(lines)


def _ask_store(
        state: State,
        pending: dict,
        draft: str = ASK_STORE_MESSAGE
) -> dict:
    '''지점명을 직접 묻는다. 제품·카테고리는 pending에 남겨 둔다.'''

    pending.pop('origin_attempts', None)

    return waiting(state, 'worker2', 'ask_missing', draft, pending)


def _answer(
        state: State,
        store_name: str,
        pending: dict,
        origin: dict | None = None
) -> dict:
    '''지점이 정해졌으면 재고를 조회해 답한다. 기준점으로 고른 지점이면 기준도 밝힌다.'''

    result = get_stock(
        store_name,
        pending.get('category_code'),
        pending.get('product_name'),
    )
    draft = _format_stock(result)

    if origin and result.get('ok'):
        draft = f"{origin['label']} 기준 가장 가까운 지점은 {result['store_name']}입니다.\n{draft}"

    update = finished(state, 'worker2', draft, result)

    if origin:
        # 대화가 이어질 때 다시 쓰도록 State에 남긴다.
        update['search_origin'] = origin

    return update


def _answer_nearest(
        state: State,
        pending: dict,
        origin: dict
) -> dict:
    '''기준점에서 가장 가까운 지점의 재고로 답한다.'''

    store_name = _nearest_store(state['user_id'], origin)

    if not store_name:
        update = _ask_store(
            state,
            pending,
            f"{origin['label']} 근처에서 지점을 찾지 못했어요. {ASK_STORE_MESSAGE}",
        )
        update['search_origin'] = origin
        return update

    return _answer(state, store_name, pending, origin)


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
        return _answer_nearest(state, pending, origin)

    # 버튼 대신 입력한 답: "현재 위치"·"등록 주소"라고 했거나 주소를 입력했다.
    request = origin_request_from_text(text)

    if request == 'current':
        return waiting(state, 'worker2', 'ask_search_origin', ASK_CURRENT_POSITION_MESSAGE, pending)

    if request == 'registered' or '등록' in text:
        origin = registered_origin(user_id)

    else:
        origin = typed_origin(text)

    if origin:
        return _answer_nearest(state, pending, origin)

    attempts = int(pending.get('origin_attempts') or 0) + 1

    if attempts >= MAX_ORIGIN_ATTEMPTS:
        origin = registered_origin(user_id)

        if origin:
            return _answer_nearest(state, pending, origin)

        return _ask_store(state, pending)

    pending['origin_attempts'] = attempts

    return waiting(state, 'worker2', 'ask_search_origin', RETRY_ORIGIN_MESSAGE, pending)


def worker2(
        state: State
) -> dict:
    retried = validation_retry_update(state, 'worker2')

    if retried:
        return retried

    pending = dict(state.get('pending_data') or {})
    text = latest_user_text(state)
    step = state.get('step')

    # 기준 위치를 물은 뒤의 답
    if step == 'ask_search_origin':
        return _handle_origin_answer(state, pending, text)

    # 지점명을 물은 뒤의 답: 지점을 새로 찾고, 제품·카테고리를 새로 말했으면 바꾼다.
    if step == 'ask_missing':
        query = _extract(text)

        if query.product_name or query.category_code:
            pending['product_name'] = query.product_name
            pending['category_code'] = query.category_code

        if query.store_name:
            return _answer(state, query.store_name, pending)

        return _ask_store(state, pending)

    # 첫 턴
    query = _extract(text)
    pending = {
        'product_name': query.product_name,
        'category_code': query.category_code,
    }

    if query.store_name:
        return _answer(state, query.store_name, pending)

    # "현재 위치 기준으로" / "등록 주소로"처럼 기준을 직접 지정한 경우
    if query.origin_request == 'current':
        update = waiting(state, 'worker2', 'ask_search_origin', ASK_CURRENT_POSITION_MESSAGE, pending)
        update['search_origin_asked'] = True
        # 남아 있는 기준점을 다음 턴에 버튼 선택으로 오인하지 않도록 비운다.
        update['search_origin'] = None
        return update

    if query.origin_request == 'registered':
        origin = registered_origin(state['user_id'])

        if origin:
            return _answer_nearest(state, pending, origin)

    # "용산 근처 재고"처럼 기준 위치를 직접 말한 경우
    if query.location_text:
        origin = typed_origin(query.location_text)

        if origin:
            return _answer_nearest(state, pending, origin)

    origin, need_ask = resolve_search_origin(state)

    if origin:
        return _answer_nearest(state, pending, origin)

    if need_ask:
        update = waiting(state, 'worker2', 'ask_search_origin', ASK_ORIGIN_MESSAGE, pending)
        update['search_origin_asked'] = True
        return update

    return _ask_store(state, pending)
