'''UC5 교환, UC6 환불.

담당: 박종석
LLM은 app.llm.get_llm() (Gemini). ChatOpenAI 쓰지 않는다.
'''

import json
import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.db.codes import format_korean_date
from app.graph.confirm import (
    build_confirm_message,
    finished,
    latest_user_text,
    parse_yes_no,
    validation_retry_update,
    waiting,
)
from app.graph.state import State
from app.llm import get_llm, llm_text
from app.tools.dispute_tools import get_dispute_doc, search_dispute_docs
from app.tools.order_tools import get_orders
from app.tools.request_tools import (
    RETURN_WINDOW_DAYS,
    create_exchange_request,
    create_refund_request,
)
from app.tools.store_tools import find_nearest_stores

DISPUTE_HINTS = (
    '배송비', '철회', '청약', '규정', '분쟁',
    '색상', '하자', '변심', '누가 내', '비용 부담',
    '교환', '환불', '결함', '조항', '근거',
)
POLICY_ONLY_HINTS = ('규정', '조항', '근거', '분쟁해결', '청약철회')
REQUEST_HINTS = ('교환', '환불', '반품')
ACTION_HINTS = ('하고 싶', '해주세요', '부탁', '접수', '하는데')
SHIPPING_HINTS = ('배송비', '누가 내', '비용 부담', '반환 비용', '반환배송')
ASK_HINTS = ('어떻게', '알고 싶', '알려', '관련')
ARTICLE_NUM_RE = re.compile(r'제\s*(\d+)\s*조')
ORDER_ID_RE = re.compile(r'ORD-\d+', re.I)
ARTICLE_MARK = '[관련 규정'
LOCKED_DRAFT = (
    '아직 수령 전',
    '수령 후 7일이 지나',
    '수령 완료된 주문이 없어',
    '아래 ',
    '신청 정보가 맞습니까',
    '지점 방문',
    '택배 수거',
    '방법을 선택',
)


class IntentVerdict(BaseModel):
    request_type: Literal['EXCHANGE', 'REFUND']


class MethodVerdict(BaseModel):
    method: Literal['STORE_VISIT', 'PICKUP', 'NONE']


def _invoke_structured(
        schema,
        prompt: str,
):
    try:
        return get_llm().with_structured_output(schema).invoke(prompt)

    except Exception:
        return None


def _split_article(
        draft: str
) -> tuple[str, str]:
    text = draft or ''
    index = text.find(ARTICLE_MARK)

    if index < 0:
        return text, ''

    return text[:index].rstrip(), text[index:].strip()


def _with_citation(
        draft: str,
        note: str
) -> str:
    if not (note or '').strip() or ARTICLE_MARK in (draft or ''):
        return draft

    return f'{draft}{note}'


def _rewrite_draft(
        draft: str,
        reason: str,
        tools: list | None = None
) -> str:
    '''거절·확인 문장과 규정 인용은 유지하고, 본문만 고친다.'''

    if any(marker in (draft or '') for marker in LOCKED_DRAFT):
        return draft

    body, article = _split_article(draft)
    prompt = (
        '교환/환불 상담 초안을 고친다. Tool의 decision·날짜·일수를 사실로 쓴다.\n'
        '거절을 가능으로, 가능을 거절로 뒤집지 마라.\n'
        '관련 규정 블록은 출력하지 마라. 본문만 고친다.\n'
        '취소·재주문·상담원 연결 같은 새 안내를 덧붙이지 마라.\n'
        f'[Tool]\n{json.dumps(tools or [], ensure_ascii=False, default=str)}\n'
        f'[검증 지시]\n{reason}\n\n[초안]\n{body}\n\n고친 본문만 출력.'
    )

    try:
        text = llm_text(get_llm().invoke(prompt)) or body

        if article:
            return f'{text}\n\n{article}'

        return text

    except Exception:
        return draft


def _request_type(
        text: str,
        pending: dict
) -> str:
    if pending.get('request_type'):
        return pending['request_type']

    if '환불' in text or '반품' in text:
        return 'REFUND'

    if '교환' in text:
        return 'EXCHANGE'

    verdict = _invoke_structured(
        IntentVerdict,
        '사용자 발화가 교환이면 EXCHANGE, 환불·반품이면 REFUND.\n'
        f'발화: {text}',
    )

    if verdict is not None:
        value = getattr(verdict, 'request_type', None) or (
            verdict.get('request_type') if isinstance(verdict, dict) else None
        )

        if value in {'EXCHANGE', 'REFUND'}:
            return value

    return 'EXCHANGE'


def _iso_date(
        value
) -> str:
    if value is None:
        return ''

    if hasattr(value, 'isoformat'):
        return str(value.isoformat())[:10]

    return str(value)[:10]


def _delivered_orders(
        orders: list[dict]
) -> list[dict]:
    return [
        order for order in orders
        if order.get('delivery_status') == 'DELIVERED' and order.get('delivered_date')
    ]


def _within_return_window(
        order: dict
) -> bool:
    delivered = _iso_date(order.get('delivered_date'))

    if order.get('delivery_status') != 'DELIVERED' or not delivered:
        return False

    delivered_on = datetime.strptime(delivered, '%Y-%m-%d').date()

    return (date.today() - delivered_on).days <= RETURN_WINDOW_DAYS


def _name_in_text(
        name: str,
        text: str
) -> bool:
    if not name or not text:
        return False

    if name in text:
        return True

    stripped = name.replace('사성 ', '').strip()

    return bool(stripped) and stripped in text


def _match_named(
        orders: list[dict],
        text: str
) -> dict | None:
    '''발화에 주문번호나 제품명이 있으면 그 주문을 고른다. 기간과 무관하다.'''

    if not text or not orders:
        return None

    found_ids = {match.group(0).upper() for match in ORDER_ID_RE.finditer(text)}
    by_id = [
        order for order in orders
        if (order.get('order_id') or '').upper() in found_ids
    ]

    if len(by_id) == 1:
        return by_id[0]

    named = [
        order for order in orders
        if _name_in_text(order.get('product_name') or '', text)
    ]

    if len(named) == 1:
        return named[0]

    return None


def _pick_order(
        orders: list[dict],
        text: str
) -> dict | None:
    '''지명한 주문을 우선한다. 없으면 기간 안 수령 주문이 하나일 때만 고른다.'''

    named = _match_named(orders, text)

    if named is not None:
        print(f'[worker4] pick={named.get("order_id")} named=True')
        return named

    delivered = _delivered_orders(orders)
    window = [order for order in delivered if _within_return_window(order)]
    print(
        f'[worker4] delivered={[item.get("order_id") for item in delivered]} '
        f'window={[item.get("order_id") for item in window]}'
    )

    if len(window) == 1:
        print(f'[worker4] pick={window[0].get("order_id")} single=True')
        return window[0]

    print('[worker4] pick=None ask_select_order')
    return None


def _refuse_not_received(
        label: str,
        order: dict | None = None
) -> str:
    if order:
        return (
            f"선택하신 제품({order['product_name']})은 아직 수령 전이라 "
            f'{label}을 접수할 수 없습니다.'
        )

    return f'수령 완료된 주문이 없어 {label}을 접수할 수 없습니다.'


def _refuse_window(
        label: str,
        order: dict
) -> str:
    return (
        f"선택하신 제품({order['product_name']})은 수령 후 7일이 지나 "
        f'{label} 접수가 어렵습니다.'
    )


def _order_choice_lines(
        orders: list[dict],
        label: str
) -> str:
    lines = [f'{label}할 주문을 번호로 알려 주세요.']

    for index, order in enumerate(orders, start=1):
        lines.append(
            f"{index}. {order['order_id']} {order['product_name']} / {order.get('option') or '-'}"
        )

    return '\n'.join(lines)


def _confirm_fields(
        order: dict,
        request_type: str
) -> dict[str, str]:
    fields = {
        '주문 날짜': format_korean_date(_iso_date(order.get('order_date'))),
        '주문번호': order['order_id'],
        '제품명': order['product_name'],
        '옵션': order.get('option') or '-',
    }

    return fields


def _parse_method(
        text: str
) -> str | None:
    if '수거' in text or '택배' in text:
        return 'PICKUP'

    if '방문' in text or '지점' in text:
        return 'STORE_VISIT'

    verdict = _invoke_structured(
        MethodVerdict,
        '지점 방문이면 STORE_VISIT, 택배·수거면 PICKUP, 불명이면 NONE.\n'
        f'입력: {text}',
    )

    if verdict is not None:
        method = getattr(verdict, 'method', None) or (
            verdict.get('method') if isinstance(verdict, dict) else None
        )

        if method in {'STORE_VISIT', 'PICKUP'}:
            return method

    return None


def _closing(
        request_type: str,
        order_id: str = ''
) -> str:
    label = '환불' if request_type == 'REFUND' else '교환'
    suffix = f' (주문번호: {order_id})' if order_id else ''
    body = (
        f'{label} 접수가 완료되었습니다{suffix}.\n'
        '빠른 시일 내에 택배 기사님께서 회수 처리하도록 하겠습니다.'
    )

    if request_type == 'REFUND':
        return f'{body}\n감사합니다.'

    return f'{body}\n불편을 드려 죄송합니다.'


def _window_facts(
        order: dict | None,
        decision: str | None = None
) -> dict:
    today = date.today().isoformat()

    if not order:
        return {
            'ok': True,
            'decision': decision or 'NOT_DELIVERED',
            'today': today,
            'delivered_date': None,
            'days_since_delivery': None,
            'return_window_days': RETURN_WINDOW_DAYS,
        }

    delivered = _iso_date(order.get('delivered_date'))
    elapsed = None

    if delivered:
        elapsed = (date.today() - datetime.strptime(delivered, '%Y-%m-%d').date()).days

    if decision is None:
        if order.get('delivery_status') != 'DELIVERED' or elapsed is None:
            decision = 'NOT_DELIVERED'
        elif elapsed > RETURN_WINDOW_DAYS:
            decision = 'RETURN_WINDOW_EXPIRED'
        else:
            decision = 'WITHIN_WINDOW'

    return {
        'ok': True,
        'decision': decision,
        'today': today,
        'delivered_date': delivered or None,
        'days_since_delivery': elapsed,
        'return_window_days': RETURN_WINDOW_DAYS,
        'order_id': order.get('order_id'),
        'product_name': order.get('product_name'),
    }


def _article_code(
        text: str
) -> str | None:
    match = ARTICLE_NUM_RE.search(text or '')

    if not match:
        return None

    return f'ART-{int(match.group(1)):02d}'


def _policy_only(
        text: str
) -> bool:
    asking = _is_policy_question(text)
    acting = any(hint in text for hint in ACTION_HINTS)

    if _article_code(text) and not acting:
        return True

    return asking and not acting


def _situation_from_tools(
        results: list | None
) -> str | None:
    for item in results or []:
        if not isinstance(item, dict):
            continue

        decision = item.get('decision')

        if decision and decision != 'POLICY_CITATION':
            return decision

    return None


def _situation_for_cite(
        text: str,
        fallback: str | None = None
) -> str | None:
    blob = text or ''

    if _article_code(blob):
        return 'ARTICLE'

    if any(hint in blob for hint in SHIPPING_HINTS):
        return 'SHIPPING_COST'

    if any(hint in blob for hint in POLICY_ONLY_HINTS):
        return 'POLICY_OVERVIEW'

    if any(hint in blob for hint in REQUEST_HINTS) and any(
        hint in blob for hint in ASK_HINTS
    ):
        return 'POLICY_OVERVIEW'

    return fallback


def _wanted_articles(
        text: str,
        situation: str | None,
        article: str | None = None
) -> list[str]:
    if article:
        return [article]

    if situation == 'SHIPPING_COST':
        return ['ART-09']

    if situation in {'RETURN_WINDOW_EXPIRED', 'WITHIN_WINDOW', 'NOT_DELIVERED'}:
        return ['ART-08']

    if situation == 'POLICY_OVERVIEW':
        return ['ART-08', 'ART-09']

    return []


def _dispute_query(
        text: str,
        situation: str | None = None
) -> str:
    article = _article_code(text)

    if article:
        number = int(article.split('-')[1])
        return f'제{number}조'

    if situation == 'SHIPPING_COST':
        return '제9조 반환에 필요한 비용 부담'

    if situation in {'RETURN_WINDOW_EXPIRED', 'WITHIN_WINDOW', 'NOT_DELIVERED'}:
        return '제8조 청약철회 기간'

    if situation == 'POLICY_OVERVIEW':
        return '제8조 청약철회 기간 제9조 반환 비용'

    return ''


def _prefer_dispute_item(
        items: list,
        situation: str | None,
        article: str | None = None
) -> dict | None:
    wanted = (_wanted_articles('', situation, article) or [None])[0]

    if not items:
        return None

    if wanted:
        for item in items:
            if item.get('doc_id') == wanted:
                return item

            number = wanted.split('-')[-1].lstrip('0') or '0'

            if f'제{number}조' in str(item.get('title') or ''):
                return item

        return None

    return None


def _excerpt(
        content: str,
        needles: tuple[str, ...] = (),
        limit: int = 180
) -> str:
    sentences = [
        part.strip()
        for part in re.split(r'(?<=다\.)\s*', content or '')
        if part.strip()
    ]
    picked = [part for part in sentences if any(needle in part for needle in needles)]
    text = ' '.join((picked or sentences)[:2])

    if len(text) > limit:
        return text[:limit].rstrip() + '…'

    return text


def _format_citation(
        item: dict
) -> str:
    source_ids = item.get('doc_ids') or []
    cited = source_ids[0] if source_ids else item.get('doc_id')
    needles = {
        'ART-08': ('배송 완료일', '7일', '공급받은 날'),
        'ART-09': ('소비자가 부담', '판매자가 부담', '결함 또는 하자'),
    }.get(item.get('doc_id') or '', ())

    return (
        f"\n\n[관련 규정 {item.get('doc_id')} / 근거 {cited}]\n"
        f"{item.get('title') or ''}\n"
        f"{_excerpt(item.get('content') or '', needles)}"
    )


def _policy_lead(
        situation: str | None,
        items: list | None
) -> str:
    ids = {item.get('doc_id') for item in items or []}

    if situation == 'SHIPPING_COST' or ids == {'ART-09'}:
        return (
            '반품 배송비는 단순 변심이면 고객이 부담하고, '
            '상품 하자·오배송·파손이면 판매자가 부담합니다.'
        )

    if situation == 'RETURN_WINDOW_EXPIRED':
        return '배송 완료일로부터 7일이 지나면 청약철회(교환·환불)가 어렵습니다.'

    if situation == 'NOT_DELIVERED':
        return '배송이 시작되기 전에는 주문을 취소할 수 있습니다. 수령 전에는 교환·환불을 접수할 수 없습니다.'

    if 'ART-08' in ids and 'ART-09' in ids:
        return (
            '배송 완료일로부터 7일 이내에 청약철회(교환·환불)할 수 있습니다. '
            '반품 배송비는 단순 변심이면 고객 부담, 하자·오배송이면 판매자 부담입니다.'
        )

    if 'ART-08' in ids:
        return '배송 완료일로부터 7일 이내에 청약철회(교환·환불)할 수 있습니다.'

    return ''


def _search_dispute(
        query: str,
        situation: str | None = None,
        article: str | None = None
) -> tuple[str, dict | None]:
    wanted_ids = _wanted_articles(query, situation, article)
    items = []

    for doc_id in wanted_ids:
        direct = get_dispute_doc(doc_id)

        if direct.get('ok'):
            items.append(direct)

    if items:
        note = ''.join(_format_citation(item) for item in items)
        return note, {'ok': True, 'items': items}

    if not wanted_ids:
        return '', None

    found = search_dispute_docs(query or '청약철회')

    if not found.get('ok'):
        return '', found

    picked = []

    for doc_id in wanted_ids:
        top = _prefer_dispute_item(found.get('items') or [], situation, doc_id)

        if top and top.get('doc_id') not in {item.get('doc_id') for item in picked}:
            picked.append(top)

    if not picked:
        return '', {'ok': True, 'items': []}

    note = ''.join(_format_citation(item) for item in picked)
    return note, {'ok': True, 'items': picked}


def _cite_for(
        text: str,
        situation: str | None = None
) -> tuple[str, dict | None]:
    situation = _situation_for_cite(text, situation)
    article = _article_code(text)
    query = _dispute_query(text, situation)
    wanted = _wanted_articles(text, situation, article)

    if not wanted:
        return '', None

    return _search_dispute(query, situation, article)


def _saved_reason(
        pending: dict,
        text: str
) -> str:
    stored = (pending.get('reason') or '').strip()

    if stored:
        return stored

    return (text or '').strip()


def _finish_refuse(
        state: State,
        draft: str,
        payload: dict,
        text: str,
        facts: dict
) -> dict:
    note, found = _cite_for(text, facts.get('decision'))
    merged = {**payload, **facts}

    if found is not None:
        merged['dispute'] = found

    return finished(state, 'worker4', _with_citation(draft, note), merged)


def _is_ui_complaint(
        text: str
) -> bool:
    blob = text or ''

    return any(word in blob for word in ('상품정보', '재고 개', '카드')) and any(
        word in blob for word in ('왜', '나와', '뜨')
    )


def _is_policy_question(
        text: str
) -> bool:
    if _is_ui_complaint(text):
        return False

    return bool(_article_code(text)) or any(
        hint in (text or '') for hint in POLICY_ONLY_HINTS + SHIPPING_HINTS + ASK_HINTS
    )


def _policy_follow_prompt(
        step: str | None,
        label: str
) -> str:
    if step == 'select_method':
        return f'{label} 방법을 선택해 주세요.\n- 지점 방문\n- 택배 수거'

    if step == 'confirm_address':
        return '주소가 맞으면 "네", 아니면 "아니요"라고 답해 주세요.'

    if step == 'input_address':
        return '수거할 주소를 입력해 주세요.'

    if step == 'select_order':
        return '목록의 번호로 주문을 선택해 주세요.'

    return f'위 {label} 신청을 이어서 진행할까요? "네" 또는 "아니요"로 답해 주세요.'


def _store_guide(
        user_id: str
) -> tuple[str, dict]:
    result = find_nearest_stores(user_id)

    if not result.get('ok'):
        return '', result

    lines = []

    for store in result.get('stores') or []:
        name = store.get('store_name') or ''
        distance = store.get('distance_km')

        if distance is None:
            lines.append(name)
            continue

        lines.append(f'{name} ({float(distance):.1f}km)')

    if not lines:
        return '', result

    return '가까운 지점: ' + ', '.join(lines), result


def worker4(
        state: State
) -> dict:
    retried = validation_retry_update(state, 'worker4')

    if retried:
        reason = (state.get('validation') or {}).get('reason') or ''
        retried['draft_answer'] = _rewrite_draft(
            state.get('draft_answer') or '',
            reason,
            state.get('tool_results'),
        )
        return retried

    text = latest_user_text(state)
    pending = dict(state.get('pending_data') or {})
    step = state.get('step')

    if _is_policy_question(text) and (step or _policy_only(text)):
        situation = _situation_for_cite(
            text,
            _situation_from_tools(
                state.get('tool_results') or state.get('last_tool_results')
            ),
        )
        note, found = _cite_for(text, situation)
        items = (found or {}).get('items') or []
        payload = {
            'ok': bool(found and found.get('ok')),
            'decision': 'POLICY_CITATION',
            'dispute': found,
        }
        lead = _policy_lead(situation, items)
        extra = note or '\n관련 규정을 찾지 못했습니다.'
        body = f'{lead}{extra}' if lead else f'관련 규정은 아래와 같습니다.{extra}'
        label = '환불' if (pending.get('request_type') or _request_type(text, pending)) == 'REFUND' else '교환'

        if step:
            return waiting(
                state,
                'worker4',
                step,
                f'{body}\n\n{_policy_follow_prompt(step, label)}',
                pending,
                payload,
            )

        return finished(state, 'worker4', body, payload)

    request_type = _request_type(text, pending)
    label = '환불' if request_type == 'REFUND' else '교환'
    pending['request_type'] = request_type

    if step is None:
        listed = get_orders(state['user_id'])
        orders = listed.get('orders') or []
        delivered = _delivered_orders(orders)
        window = [order for order in delivered if _within_return_window(order)]
        payload = listed

        print(
            f'[worker4] step=None delivered={[item.get("order_id") for item in delivered]} '
            f'window={[item.get("order_id") for item in window]}'
        )

        if not orders:
            return finished(state, 'worker4', '조회할 주문이 없습니다.', payload)

        if not delivered:
            return _finish_refuse(
                state,
                _refuse_not_received(label),
                payload,
                text,
                _window_facts(None, 'NOT_DELIVERED'),
            )

        order = _pick_order(orders, text)

        if order is not None:
            if order.get('delivery_status') != 'DELIVERED' or not order.get('delivered_date'):
                return _finish_refuse(
                    state,
                    _refuse_not_received(label, order),
                    {**payload, 'orders': [order]},
                    text,
                    _window_facts(order, 'NOT_DELIVERED'),
                )

            if not _within_return_window(order):
                return _finish_refuse(
                    state,
                    _refuse_window(label, order),
                    {**payload, 'orders': [order]},
                    text,
                    _window_facts(order),
                )

            payload = {**payload, 'orders': [order]}
            pending['order_id'] = order['order_id']
            pending['shown_address'] = order['ship_address']
            pending['order_summary'] = f"{order['product_name']} / {order.get('option') or '-'}"
            pending['reason'] = pending.get('reason') or text
            draft = build_confirm_message(
                f'아래 {label} 신청 정보가 맞습니까?',
                _confirm_fields(order, request_type),
            )

            return waiting(state, 'worker4', 'confirm_order', draft, pending, payload)

        if not window:
            latest = delivered[0]
            return _finish_refuse(
                state,
                _refuse_window(label, latest),
                {**payload, 'orders': [latest]},
                text,
                _window_facts(latest),
            )

        pending['order_options'] = window
        pending['reason'] = pending.get('reason') or text
        listed_window = {**payload, 'orders': window}
        return waiting(
            state,
            'worker4',
            'select_order',
            _order_choice_lines(window, label),
            pending,
            listed_window,
        )

    if step == 'confirm_order':
        answer = parse_yes_no(text)

        if answer == 'yes':
            return waiting(
                state,
                'worker4',
                'select_method',
                f'{label} 방법을 선택해 주세요.\n- 지점 방문\n- 택배 수거',
                pending,
                {'ok': True, 'methods': ['STORE_VISIT', 'PICKUP']},
            )

        if answer == 'no':
            listed = get_orders(state['user_id'])
            window = [
                order for order in _delivered_orders(listed.get('orders') or [])
                if _within_return_window(order)
            ]
            options = window or _delivered_orders(listed.get('orders') or [])
            pending['order_options'] = options

            return waiting(
                state,
                'worker4',
                'select_order',
                _order_choice_lines(options, label),
                pending,
                {**listed, 'orders': options},
            )

        hint = ''

        if any(word in text for word in ('상품정보', '재고', '카드', '왜')):
            hint = '규정 안내와 상품 카드는 별개입니다. 지금은 환불·교환 신청 내용을 확인하고 있습니다.\n\n'

        return waiting(
            state,
            'worker4',
            'confirm_order',
            f'{hint}주문 정보가 맞으면 "네", 아니면 "아니요"라고 답해 주세요.',
            pending,
        )

    if step == 'select_order':
        options = pending.get('order_options') or []
        chosen = None
        stripped = text.strip()

        if stripped.isdigit():
            index = int(stripped) - 1

            if 0 <= index < len(options):
                chosen = options[index]

        if chosen is None:
            chosen = _match_named(options, text)

        if chosen is None:
            listed = get_orders(state['user_id'])
            chosen = _match_named(listed.get('orders') or [], text)

        if chosen is None:
            return waiting(
                state,
                'worker4',
                'select_order',
                '목록의 번호로 주문을 선택해 주세요.',
                pending,
            )

        if not _within_return_window(chosen):
            listed = {'ok': True, 'orders': [chosen]}

            if chosen.get('delivery_status') != 'DELIVERED':
                return _finish_refuse(
                    state,
                    _refuse_not_received(label, chosen),
                    listed,
                    text,
                    _window_facts(chosen, 'NOT_DELIVERED'),
                )

            return _finish_refuse(
                state,
                _refuse_window(label, chosen),
                listed,
                text,
                _window_facts(chosen),
            )

        pending['order_id'] = chosen['order_id']
        pending['shown_address'] = chosen['ship_address']
        pending['reason'] = pending.get('reason') or text
        draft = build_confirm_message(
            f'아래 {label} 신청 정보가 맞습니까?',
            _confirm_fields(chosen, request_type),
        )

        return waiting(
            state,
            'worker4',
            'confirm_order',
            draft,
            pending,
            {'ok': True, 'orders': [chosen]},
        )

    if step == 'select_method':
        method = _parse_method(text)

        if method == 'STORE_VISIT':
            creator = create_exchange_request if request_type == 'EXCHANGE' else create_refund_request
            created = creator(
                pending['order_id'],
                state['user_id'],
                'STORE_VISIT',
                reason=_saved_reason(pending, text),
            )

            if not created.get('ok'):
                return finished(state, 'worker4', created.get('message') or '접수하지 못했습니다.', created)

            if created.get('already_pending'):
                return finished(
                    state,
                    'worker4',
                    created.get('message') or f'이미 같은 주문의 {label} 요청이 승인 대기 중입니다.',
                    created,
                )

            guide, geo = _store_guide(state['user_id'])
            extra = f'\n{guide}' if guide else '\n가까운 지점은 지점 문의로 다시 확인해 주세요.'
            draft = f"{label} 접수를 지점 방문으로 남겼습니다.{extra}"
            stores = geo.get('stores') if isinstance(geo, dict) else None
            payload = {
                'ok': True,
                'request': created,
                'stores': stores or [],
            }

            return finished(state, 'worker4', draft, payload)

        if method == 'PICKUP':
            pending['method'] = 'PICKUP'
            draft = (
                '현재 주소가 아래가 맞습니까?\n'
                '[현재]\n'
                f"{pending.get('shown_address', '')}"
            )

            return waiting(state, 'worker4', 'confirm_address', draft, pending)

        return waiting(
            state,
            'worker4',
            'select_method',
            '지점 방문과 택배 수거 중에서 선택해 주세요.',
            pending,
            {'ok': True, 'methods': ['STORE_VISIT', 'PICKUP']},
        )

    if step == 'confirm_address':
        answer = parse_yes_no(text)
        creator = create_exchange_request if request_type == 'EXCHANGE' else create_refund_request

        if answer == 'yes':
            created = creator(
                pending['order_id'],
                state['user_id'],
                'PICKUP',
                pickup_address=pending.get('shown_address'),
                reason=_saved_reason(pending, text),
            )

            if not created.get('ok'):
                return finished(
                    state,
                    'worker4',
                    created.get('message', '접수하지 못했습니다.'),
                    created,
                )

            if created.get('already_pending'):
                return finished(
                    state,
                    'worker4',
                    created.get('message') or f'이미 같은 주문의 {label} 요청이 승인 대기 중입니다.',
                    created,
                )

            return finished(
                state,
                'worker4',
                _closing(request_type, pending.get('order_id') or ''),
                created,
            )

        if answer == 'no':
            return waiting(
                state,
                'worker4',
                'input_address',
                '수거할 주소를 입력해 주세요.',
                pending,
            )

        return waiting(
            state,
            'worker4',
            'confirm_address',
            '주소가 맞으면 "네", 아니면 "아니요"라고 답해 주세요.',
            pending,
        )

    if step == 'input_address':
        creator = create_exchange_request if request_type == 'EXCHANGE' else create_refund_request
        created = creator(
            pending['order_id'],
            state['user_id'],
            'PICKUP',
            pickup_address=text.strip(),
            reason=_saved_reason(pending, text),
        )

        if not created.get('ok'):
            return finished(
                state,
                'worker4',
                created.get('message', '접수하지 못했습니다.'),
                created,
            )

        if created.get('already_pending'):
            return finished(
                state,
                'worker4',
                created.get('message') or f'이미 같은 주문의 {label} 요청이 승인 대기 중입니다.',
                created,
            )

        return finished(
            state,
            'worker4',
            _closing(request_type, pending.get('order_id') or ''),
            created,
        )

    return finished(state, 'worker4', f'{label} 문의를 이어서 처리하지 못했습니다.', None)
