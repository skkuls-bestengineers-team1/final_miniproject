'''UC3 배송지 변경, UC4 배송일.

담당: 최민정
TODO(최민정): 하위 의도 판별과 문장 생성을 LLM으로 교체
'''

import re
from datetime import date, datetime, timedelta

from langgraph.types import interrupt

from app.db.codes import format_korean_date
from app.graph.confirm import (
    finished,
    latest_user_text,
    parse_yes_no,
    validation_retry_update,
    waiting,
)
from app.graph.state import State
from app.tools.order_tools import get_delivery_status, get_orders
from app.tools.request_tools import request_address_change

CHANGEABLE = {'PREPARING', 'SHIPPED'}


def _delivery_intent(
        text: str
) -> str:
    if any(word in text for word in ('주소', '배송지', '변경', '잘못')):
        return 'ADDRESS_CHANGE'

    return 'DELIVERY_DATE'


def _pick_changeable(
        orders: list[dict]
) -> dict | None:
    changeable = [
        order for order in orders
        if order['delivery_status'] in CHANGEABLE
    ]

    for order in changeable:
        if order['product_code'] == 'PRD-6001' and order.get('option') == '빨간색':
            return order

    if changeable:
        return changeable[0]

    return None


def _pick_tracking_order(
        orders: list[dict],
        text: str
) -> dict | None:
    active = [
        order for order in orders
        if order['delivery_status'] != 'DELIVERED' and order.get('expected_date')
    ]

    for order in active:
        if order['product_name'] in text:
            return order

    active.sort(key=lambda order: order['expected_date'])

    if active:
        return active[0]

    return None


def _deadline_line(
        text: str,
        expected_date: str | None
) -> str:
    matched = re.search(r'(\d+)\s*일', text)

    if not matched or not expected_date:
        return ''

    days = int(matched.group(1))
    expected = datetime.strptime(expected_date, '%Y-%m-%d').date()
    deadline = date.today() + timedelta(days=days)
    possible = '가능합니다' if expected <= deadline else '어렵습니다'

    return f'- {days}일 안에 배송: {possible}'


def _answer_delivery(
        user_id: str,
        text: str
) -> tuple[str, dict]:
    orders = get_orders(user_id)

    if not orders.get('ok') or not orders['orders']:
        return '조회할 주문이 없습니다.', orders

    order = _pick_tracking_order(orders['orders'], text)

    if order is None:
        return '배송 중인 주문이 없습니다.', orders

    status = get_delivery_status(order['order_id'], user_id)

    if not status.get('ok'):
        return status.get('message', '배송 상태를 확인하지 못했습니다.'), status

    lines = [
        f"예상 배송일은 {format_korean_date(status['expected_date'])}입니다.",
        f"- 배송 상태: {status['delivery_status_label']}",
        f"- 제품: {status['product_name']}",
    ]
    deadline = _deadline_line(text, status.get('expected_date'))

    if deadline:
        lines.append(deadline)

    return '\n'.join(lines), status


def worker3(
        state: State
) -> dict:
    retried = validation_retry_update(state, 'worker3')

    if retried:
        return retried

    text = latest_user_text(state)
    pending = dict(state.get('pending_data') or {})
    step = state.get('step')
    intent = pending.get('delivery_intent') or _delivery_intent(text)

    if step is None and intent == 'DELIVERY_DATE':
        draft, result = _answer_delivery(state['user_id'], text)
        return finished(state, 'worker3', draft, result)

    if step is None:
        orders = get_orders(state['user_id'])
        order = _pick_changeable(orders.get('orders') or [])

        if order is None:
            return finished(
                state,
                'worker3',
                '배송지 변경이 가능한 주문이 없습니다.',
                orders,
            )

        pending = {
            'delivery_intent': 'ADDRESS_CHANGE',
            'order_id': order['order_id'],
            'shown_address': order['ship_address'],
        }

        draft = (
            '현재 주소가 아래가 맞습니까?\n'
            '[현재]\n'
            f"{order['ship_address']}"
        )

        return waiting(state, 'worker3', 'confirm_address', draft, pending, orders)

    if step == 'confirm_address':
        answer = parse_yes_no(text)

        if answer == 'yes':
            return waiting(
                state,
                'worker3',
                'input_new_address',
                '새로운 주소를 입력해주세요.',
                pending,
            )

        if answer == 'no':
            return waiting(
                state,
                'worker3',
                'confirm_address',
                '변경할 주문의 주소를 다시 알려 주세요. 현재 확인된 주소는 '
                f"{pending.get('shown_address', '')} 입니다.",
                pending,
            )

        return waiting(
            state,
            'worker3',
            'confirm_address',
            '현재 주소가 맞으면 "네", 아니면 "아니요"라고 답해 주세요.',
            pending,
        )

    if step == 'input_new_address':
        # interrupt()는 재개 때 노드를 처음부터 다시 실행한다.
        # request_address_change는 같은 PENDING을 다시 만들지 않는다.
        created = request_address_change(
            pending['order_id'],
            state['user_id'],
            text,
        )

        if not created.get('ok'):
            return finished(
                state,
                'worker3',
                created.get('message', '배송지를 변경하지 못했습니다.'),
                created,
            )

        decision = interrupt({
            'draft': '관리자 승인 후 변경 완료 시 알림을 보내드립니다.',
            'request_id': created['request_id'],
        })
        approved = isinstance(decision, dict) and bool(decision.get('approved'))

        if approved:
            draft = '변경 완료되었습니다.'

        else:
            draft = '배송지 변경 요청이 거절되었습니다.'

        return finished(state, 'worker3', draft, {'resume': decision, **created})

    return finished(state, 'worker3', '배송 문의를 이어서 처리하지 못했습니다.', None)
