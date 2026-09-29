'''UC2 재고.

담당: 박서영
LLM 추출(실패 시 키워드), 지점이 없으면 가까운 지점 제안 후 되묻기.
'''

from pydantic import BaseModel

from app.config import settings
from app.db.codes import CATEGORY_KEYWORDS, CATEGORY_LABEL
from app.db.connection import fetch_all
from app.graph.confirm import finished, latest_user_text, parse_yes_no, validation_retry_update, waiting
from app.graph.state import State
from app.llm import get_llm
from app.tools.stock_tools import get_stock
from app.tools.store_tools import find_nearest_stores


class StockQuery(BaseModel):
    '''발화에서 뽑은 재고 조회 조건. 목록에 없으면 None.'''

    store_name: str | None = None
    product_name: str | None = None
    category_code: str | None = None


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

    return result


def _extract(
        text: str
) -> StockQuery:
    '''LLM 추출을 먼저 쓰고, 실패하면 키워드 매칭으로 대신한다.'''

    # _extract_with_llm 결과가 있으면 그대로 반환
    extracted = _extract_with_llm(text)

    if extracted is not None:
        # LLM이 지점을 놓쳤으면 지점명 키워드로 한 번 더 찾는다.
        if extracted.store_name is None:
            extracted.store_name = _match_store(text)

        return extracted

    # 없으면 _match_store·_match_product·_match_category로 StockQuery 구성
    product_name = _match_product(text)

    return StockQuery(
        store_name=_match_store(text),
        product_name=product_name,
        category_code=None if product_name else _match_category(text),
    )


def _suggest_nearest_store(
        user_id: str
) -> str | None:
    '''사용자 기준 가장 가까운 지점명. 찾지 못하면 None.'''

    # find_nearest_stores(user_id, top_k=1) 호출
    result = find_nearest_stores(user_id, top_k=1)

    # ok가 아니거나 결과가 없으면 None, 있으면 1순위 store_name 반환
    if not result.get('ok') or not result.get('stores'):
        return None

    return result['stores'][0]['store_name']


def _is_yes(
        text: str
) -> bool:
    '''제안한 지점으로 조회해도 되는지에 대한 긍정 답변인지.'''

    return parse_yes_no(text) == 'yes'


def _format_stock(
        result: dict
) -> str:
    if not result.get('ok'):
        return result.get('message', '재고를 확인하지 못했습니다.')

    items = result.get('items') or []
    store_name = result.get('store_name') or ''

    if result.get('product_name') and len(items) == 1:
        item = items[0]
        return f"{store_name} {item['product_name']} 재고는 {item['quantity']}개입니다."

    lines = [f"{store_name} 재고는 {result.get('total', 0)}개입니다."]

    for item in items:
        lines.append(f"- {item['product_name']}: {item['quantity']}개")

    return '\n'.join(lines)


def worker2(
        state: State
) -> dict:
    retried = validation_retry_update(state, 'worker2')

    if retried:
        return retried

    pending = dict(state.get('pending_data') or {})
    text = latest_user_text(state)
    step = state.get('step')
    store_name = None

    if step == 'confirm_nearest' and _is_yes(text):
        # 제안한 가까운 지점으로 조회
        store_name = pending.get('suggested_store')

    elif step in {'confirm_nearest', 'ask_missing'}:
        # 되물은 뒤의 답: 지점명만 새로 찾는다. 제품·카테고리는 pending에 있다.
        store_name = _extract(text).store_name

    else:
        # 첫 턴
        query = _extract(text)
        store_name = query.store_name
        pending = {
            'product_name': query.product_name,
            'category_code': query.category_code,
        }

        if not store_name:
            suggested = _suggest_nearest_store(state['user_id'])

            if suggested:
                pending['suggested_store'] = suggested

                return waiting(
                    state,
                    'worker2',
                    'confirm_nearest',
                    f'가장 가까운 {suggested} 기준으로 확인할까요?',
                    pending,
                )

    if not store_name:
        return waiting(
            state,
            'worker2',
            'ask_missing',
            '어느 지점의 재고를 확인할까요?',
            pending,
        )

    result = get_stock(
        store_name,
        pending.get('category_code'),
        pending.get('product_name'),
    )

    return finished(state, 'worker2', _format_stock(result), result)
