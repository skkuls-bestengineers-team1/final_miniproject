'''UC2 재고.

담당: 박서영
단일 턴. TODO(박서영): 지점명·제품명 추출을 LLM으로 교체
'''

from app.db.codes import CATEGORY_KEYWORDS
from app.db.connection import fetch_all
from app.graph.confirm import finished, latest_user_text, validation_retry_update, waiting
from app.graph.state import State
from app.tools.stock_tools import get_stock


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

    if state.get('step') == 'ask_missing':
        text = f"{pending.get('original_text', '')} {text}"

    store_name = pending.get('store_name') or _match_store(text)

    if not store_name:
        return waiting(
            state,
            'worker2',
            'ask_missing',
            '어느 지점의 재고를 확인할까요?',
            {
                'missing_field': 'store',
                'original_text': text,
            },
        )

    product_name = _match_product(text)
    category_code = None if product_name else _match_category(text)
    result = get_stock(store_name, category_code, product_name)

    return finished(state, 'worker2', _format_stock(result), result)
