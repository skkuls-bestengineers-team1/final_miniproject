'''UC5 교환, UC6 환불.

담당: 박종석
LLM은 app.llm.get_llm() (Gemini). ChatOpenAI 쓰지 않는다.
'''

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
from app.tools.dispute_tools import search_dispute_docs
from app.tools.order_tools import get_orders
from app.tools.request_tools import create_exchange_request, create_refund_request
from app.tools.store_tools import find_nearest_stores

DISPUTE_HINTS = (
    '배송비', '철회', '청약', '규정', '분쟁',
    '색상', '하자', '변심', '누가 내', '비용 부담',
    '교환', '환불' , '결함' ,
)


class IntentVerdict(BaseModel):
    request_type: Literal['EXCHANGE', 'REFUND']


class MethodVerdict(BaseModel):
    method: Literal['STORE_VISIT', 'PICKUP', 'NONE']


class OrderPick(BaseModel):
    index: int = Field(description='주문 목록 인덱스. 모르면 0')


def _invoke_structured(
        schema,
        prompt: str,
):
    try:
        return get_llm().with_structured_output(schema).invoke(prompt)

    except Exception:
        return None


def _rewrite_draft(
        draft: str,
        reason: str
) -> str:
    prompt = (
        '교환/환불 상담 초안을 고친다. Tool 숫자·주문번호·주소·지점명은 바꾸지 마라.\n'
        f'[검증 지시]\n{reason}\n\n[초안]\n{draft}\n\n고친 문장만 출력.'
    )

    try:
        text = llm_text(get_llm().invoke(prompt))
        return text or draft

    except Exception:
        return draft


def _request_type(
        text: str,
        pending: dict
) -> str:
    if pending.get('request_type'):
        return pending['request_type']

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

    if '환불' in text or '반품' in text:
        return 'REFUND'

    return 'EXCHANGE'


def _within_return_window(
        order: dict
) -> bool:
    delivered = order.get('delivered_date')

    if order.get('delivery_status') != 'DELIVERED' or not delivered:
        return False

    delivered_on = datetime.strptime(delivered, '%Y-%m-%d').date()

    return (date.today() - delivered_on).days <= 7


def _pick_order(
        orders: list[dict],
        text: str
) -> dict | None:
    if not orders:
        return None

    if len(orders) == 1:
        return orders[0]

    summary = '\n'.join(
        f"[{index}] {order['order_id']} {order['product_name']} / {order.get('option') or '-'}"
        for index, order in enumerate(orders)
    )
    verdict = _invoke_structured(
        OrderPick,
        '목록에서 사용자 발화에 해당하는 주문의 인덱스만 고른다. '
        '특정할 수 없으면 0.\n'
        f'[목록]\n{summary}\n[발화]\n{text}',
    )

    if verdict is not None:
        index = getattr(verdict, 'index', None)

        if isinstance(verdict, dict):
            index = verdict.get('index')

        if isinstance(index, int) and 0 <= index < len(orders):
            return orders[index]

    returnable = [order for order in orders if _within_return_window(order)]

    if returnable:
        return returnable[0]

    return orders[0]


def _confirm_fields(
        order: dict,
        request_type: str
) -> dict[str, str]:
    fields = {
        '제품명': order['product_name'],
        '옵션': order.get('option') or '-',
        '주문번호': order['order_id'],
    }

    if request_type == 'REFUND':
        fields['주문 날짜'] = format_korean_date(order['order_date'])

    return fields


def _parse_method(
        text: str
) -> str | None:
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

        if method == 'NONE':
            return None

    if '수거' in text or '택배' in text:
        return 'PICKUP'

    if '방문' in text:
        return 'STORE_VISIT'

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


def _dispute_block(
        text: str
) -> tuple[str, dict | None]:
    if not any(hint in text for hint in DISPUTE_HINTS):
        return '', None

    found = search_dispute_docs(text)

    if not found.get('ok'):
        return '', found

    items = found.get('items') or []

    if not items:
        return '', found

    top = items[0]
    source_ids = top.get('doc_ids') or []
    cited = source_ids[0] if source_ids else top.get('doc_id')
    note = (
        f"\n\n[관련 규정 {top.get('doc_id')} / 근거 {cited}]\n"
        f"{top.get('title') or ''}\n"
        f"{top.get('content') or ''}"
    )

    return note, found


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
            retried.get('draft_answer') or '',
            reason,
        )
        return retried

    text = latest_user_text(state)
    pending = dict(state.get('pending_data') or {})
    step = state.get('step')
    request_type = _request_type(text, pending)
    label = '환불' if request_type == 'REFUND' else '교환'
    pending['request_type'] = request_type
    rag_note, dispute_result = _dispute_block(text)

    if step is None:
        listed = get_orders(state['user_id'])
        orders = listed.get('orders') or []
        order = _pick_order(orders, text)
        payload = listed

        if dispute_result is not None:
            payload = {**listed, 'dispute': dispute_result}

        if order is None:
            return finished(state, 'worker4', '조회할 주문이 없습니다.', payload)

        if not _within_return_window(order):
            refuse = (
                f"선택하신 제품({order['product_name']})은 수령 후 7일이 지나 "
                f'{label} 접수가 어렵습니다.'
            )
            return finished(state, 'worker4', refuse + rag_note, payload)

        pending['order_id'] = order['order_id']
        pending['shown_address'] = order['ship_address']
        pending['order_summary'] = f"{order['product_name']} / {order.get('option') or '-'}"
        draft = build_confirm_message(
            f'아래 {label} 신청 정보가 맞습니까?',
            _confirm_fields(order, request_type),
        )

        return waiting(state, 'worker4', 'confirm_order', draft + rag_note, pending, payload)

    if step == 'confirm_order':
        answer = parse_yes_no(text)

        if answer == 'yes':
            return waiting(
                state,
                'worker4',
                'select_method',
                f'{label} 방법:\n- 지점 방문\n- 택배 수거',
                pending,
            )

        if answer == 'no':
            listed = get_orders(state['user_id'])
            lines = ['어떤 주문인지 번호로 알려 주세요.']

            for index, order in enumerate(listed.get('orders') or [], start=1):
                lines.append(
                    f"{index}. {order['order_id']} {order['product_name']} / {order.get('option') or '-'}"
                )

            pending['order_options'] = listed.get('orders') or []

            return waiting(
                state,
                'worker4',
                'select_order',
                '\n'.join(lines),
                pending,
                listed,
            )

        return waiting(
            state,
            'worker4',
            'confirm_order',
            '주문 정보가 맞으면 "네", 아니면 "아니요"라고 답해 주세요.',
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
            chosen = _pick_order(options, text) if options else None

        if chosen is None:
            return waiting(
                state,
                'worker4',
                'select_order',
                '목록의 번호로 주문을 선택해 주세요.',
                pending,
            )

        if not _within_return_window(chosen):
            refuse = (
                f"선택하신 제품({chosen['product_name']})은 수령 후 7일이 지나 "
                f'{label} 접수가 어렵습니다.'
            )
            return finished(state, 'worker4', refuse)

        pending['order_id'] = chosen['order_id']
        pending['shown_address'] = chosen['ship_address']
        draft = build_confirm_message(
            f'아래 {label} 신청 정보가 맞습니까?',
            _confirm_fields(chosen, request_type),
        )

        return waiting(state, 'worker4', 'confirm_order', draft, pending)

    if step == 'select_method':
        method = _parse_method(text)

        if method == 'STORE_VISIT':
            creator = create_exchange_request if request_type == 'EXCHANGE' else create_refund_request
            created = creator(
                pending['order_id'],
                state['user_id'],
                'STORE_VISIT',
                reason=text,
            )

            if not created.get('ok'):
                return finished(state, 'worker4', created.get('message') or '접수하지 못했습니다.', created)

            guide, geo = _store_guide(state['user_id'])
            extra = f'\n{guide}' if guide else '\n가까운 지점은 지점 문의로 다시 확인해 주세요.'
            draft = f"{label} 접수를 지점 방문으로 남겼습니다.{extra}"
            payload = {'ok': True, 'request': created, 'stores': geo}

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
                reason=text,
            )

            if not created.get('ok'):
                return finished(
                    state,
                    'worker4',
                    created.get('message', '접수하지 못했습니다.'),
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
            reason=pending.get('reason'),
        )

        if not created.get('ok'):
            return finished(
                state,
                'worker4',
                created.get('message', '접수하지 못했습니다.'),
                created,
            )

        return finished(
            state,
            'worker4',
            _closing(request_type, pending.get('order_id') or ''),
            created,
        )

    return finished(state, 'worker4', f'{label} 문의를 이어서 처리하지 못했습니다.', None)
