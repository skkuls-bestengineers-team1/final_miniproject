'''UC5 교환, UC6 환불.

담당: 박종석

작업 가이드 (스켈레톤. 흐름은 유지하고 키워드 stub만 LLM으로)

냅둘 것
- step 상태머신: None → confirm_order → select_method → confirm_address
  (아니요면 select_order → 다시 confirm_order, 주소 아니면 input_address)
- Tool: get_orders, create_exchange_request, create_refund_request
- _within_return_window (수령 후 7일). 기간 계산을 모델에 맡기지 말 것
- waiting / finished / pending_data / draft_answer. 답을 messages에 직접 넣지 말 것
- 검증 fail 시 Tool 재호출 금지. validation_retry_update 훅은 유지하고 문장만 고칠 것

지우고 다시 쓸 것 (키워드 stub → LLM 추출·문장)
- _request_type: "환불" 글자면 REFUND, 아니면 EXCHANGE
- _pick_order: 제품명 포함 여부 + PRD-6001 빨간색 하드코딩
- _parse_method: "수거"/"택배"/"방문" 글자
- _confirm_fields, _closing, 안내 문구 전부 f-string 템플릿
- 기간 지난 주문도 지금은 그냥 고른다. LLM 안내 후 거절하는 분기를 넣을 것
- 지점 방문 시 worker1 GEO 안내 대신 안내 문장만 있음
- 분쟁해결기준 search_dispute_docs 미연결. 배송비·철회 기간 질문에 Tool 결과를 문장에 넣을 것

건드리지 말 것
- supervisor 라우팅, validator, schema, GEO 적재
'''

from datetime import date, datetime

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
from app.tools.order_tools import get_orders
from app.tools.request_tools import create_exchange_request, create_refund_request


def _request_type(
        text: str,
        pending: dict
) -> str:
    # 다시 쓰기: 키워드 대신 LLM이 EXCHANGE | REFUND 를 뽑게 한다.
    # 냅두기: pending에 이미 있으면 그 값을 유지 (멀티턴에서 의도 고정).
    if pending.get('request_type'):
        return pending['request_type']

    if '환불' in text:
        return 'REFUND'

    return 'EXCHANGE'


def _within_return_window(
        order: dict
) -> bool:
    # 냅두기: 수령일 기준 7일. LLM 추정 금지.
    delivered = order.get('delivered_date')

    if order.get('delivery_status') != 'DELIVERED' or not delivered:
        return False

    delivered_on = datetime.strptime(delivered, '%Y-%m-%d').date()

    return (date.today() - delivered_on).days <= 7


def _pick_order(
        orders: list[dict],
        text: str
) -> dict | None:
    '''수령 후 7일 안의 주문을 우선한다. 대표 예시는 빨간색 A 로봇청소기다.'''

    # 다시 쓰기: 발화에서 주문/제품/옵션을 추출해 get_orders 결과와 매칭.
    # 지울 것: product_name in text, PRD-6001+빨간색 우선순위 하드코딩.
    # 냅두기: 후보 목록은 get_orders. 기간은 _within_return_window로 걸러서
    # 창 밖이면 접수하지 말고 안내만.

    if not orders:
        return None

    named = [order for order in orders if order['product_name'] in text]
    pool = named or orders
    returnable = [order for order in pool if _within_return_window(order)]

    for order in returnable:
        if order['product_code'] == 'PRD-6001' and order.get('option') == '빨간색':
            return order

    if returnable:
        return returnable[0]

    for order in pool:
        if order['product_code'] == 'PRD-6001' and order.get('option') == '빨간색':
            return order

    return pool[0]


def _confirm_fields(
        order: dict,
        request_type: str
) -> dict[str, str]:
    # 냅두기: 확인 카드에 넣는 필드 값은 주문 Tool 그대로.
    # 다시 쓰기: 안내 문장(build_confirm_message 결과)은 LLM으로 다듬기.
    fields = {
        '제품명': order['product_name'],
        '옵션': order.get('option') or '-',
    }

    if request_type == 'REFUND':
        fields = {
            '주문 날짜': format_korean_date(order['order_date']),
            **fields,
        }

    return fields


def _parse_method(
        text: str
) -> str | None:
    # 다시 쓰기: LLM이 STORE_VISIT | PICKUP | None.
    # 반환 코드 두 개와 아래 step 분기는 유지.
    if '수거' in text or '택배' in text:
        return 'PICKUP'

    if '방문' in text:
        return 'STORE_VISIT'

    return None


def _closing(
        request_type: str
) -> str:
    # 다시 쓰기: 접수 완료 문장 LLM. 날짜·주문번호는 Tool 값만.
    body = '빠른 시일 내에 택배 기사님께서 회수 처리하도록 하겠습니다.'

    if request_type == 'REFUND':
        return f'{body}\n감사합니다.'

    return f'{body}\n불편을 드려 죄송합니다.'


def worker4(
        state: State
) -> dict:
    # 다시 쓰기: 아래는 reason을 초안 끝에 붙이기만 함.
    # LLM으로 문장만 재작성. get_orders / create_* 다시 치지 말 것.
    retried = validation_retry_update(state, 'worker4')

    if retried:
        return retried

    text = latest_user_text(state)
    pending = dict(state.get('pending_data') or {})
    step = state.get('step')
    request_type = _request_type(text, pending)
    label = '환불' if request_type == 'REFUND' else '교환'
    pending['request_type'] = request_type

    # 냅두기: step 분기 전체. 없는 step을 새로 만들기보다 아래 훅만 LLM으로.
    # 추가할 것: 교환/환불 사유·배송비 질문이면 search_dispute_docs로 조 전체를 가져와
    # 초안에 근거(doc_id)와 함께 넣기. RAG 적재는 김동규 쪽 완료(ART-01~15).
    if step is None:
        listed = get_orders(state['user_id'])
        order = _pick_order(listed.get('orders') or [], text)

        if order is None:
            return finished(state, 'worker4', '조회할 주문이 없습니다.', listed)

        pending['order_id'] = order['order_id']
        pending['shown_address'] = order['ship_address']
        pending['order_summary'] = f"{order['product_name']} / {order.get('option') or '-'}"

        title = '아래의 주문 정보가 맞습니까?'
        draft = build_confirm_message(title, _confirm_fields(order, request_type))

        return waiting(state, 'worker4', 'confirm_order', draft, pending, listed)

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
            for order in options:
                if order['order_id'] in text or order['product_name'] in text:
                    chosen = order
                    break

        if chosen is None:
            return waiting(
                state,
                'worker4',
                'select_order',
                '목록의 번호로 주문을 선택해 주세요.',
                pending,
            )

        pending['order_id'] = chosen['order_id']
        pending['shown_address'] = chosen['ship_address']
        draft = build_confirm_message(
            '아래의 주문 정보가 맞습니까?',
            _confirm_fields(chosen, request_type),
        )

        return waiting(state, 'worker4', 'confirm_order', draft, pending)

    if step == 'select_method':
        method = _parse_method(text)

        if method == 'STORE_VISIT':
            # 다시 쓰기: find_nearest_stores(user_id)로 가까운 지점을 받아 안내에 넣기.
            # worker1 노드로 그래프를 갈아타지 말고, 같은 Tool을 여기서 호출하면 된다.
            creator = create_exchange_request if request_type == 'EXCHANGE' else create_refund_request
            created = creator(
                pending['order_id'],
                state['user_id'],
                'STORE_VISIT',
                reason=text,
            )
            message = created.get('message')

            if not created.get('ok'):
                return finished(state, 'worker4', message or '접수하지 못했습니다.', created)

            draft = (
                f'{label} 접수를 지점 방문으로 남겼습니다. '
                '가까운 지점은 지점 문의로 다시 확인해 주세요.'
            )

            return finished(state, 'worker4', draft, created)

        if method == 'PICKUP':
            draft = (
                '현재 주소가 아래가 맞습니까?\n'
                '[현재]\n'
                f"{pending.get('shown_address', '')}"
            )

            pending['method'] = 'PICKUP'

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

            return finished(state, 'worker4', _closing(request_type), created)

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

        return finished(state, 'worker4', _closing(request_type), created)

    return finished(state, 'worker4', f'{label} 문의를 이어서 처리하지 못했습니다.', None)
