"""배송 상담 툴. 실행 설정으로 전달받은 요청별 state를 사용한다.

config는 LLM의 입력 스키마에서 제외된다. 상태 변경은 워커가 반환값에 반영한다.
created는 한 번의 워커 실행 안에서 중복 접수를 막는 임시 정보다.
"""

from typing import Literal

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.db.codes import DELIVERY_STATUS_LABEL
from app.db.connection import get_conn, fetch_one, fail
from app.tools.order_tools import get_order, get_orders
from app.tools.request_tools import request_address_change
from app.tools.user_tools import get_user_address


CARRIERS = {'CJ_LOGISTICS': 'CJ대한통운'}


def _latest_delivery_event(order_id: str, product_code: str):
    """저장한 요청사항을 포함한 최신 DB 배송 이력을 조회한다."""
    return fetch_one(
        '''SELECT * FROM delivery WHERE order_id = %s AND product_code = %s
           ORDER BY occurred_at DESC, event_seq DESC LIMIT 1''',
        (order_id, product_code),
    )


@tool('update_delivery_request')
def update_delivery_request_tool(
    order_id: str, delivery_request: str, mode: Literal['replace', 'append'],
    config: RunnableConfig,
) -> dict:
    """본인 주문의 최신 배송 요청사항을 저장한다. replace는 교체, append는 기존 내용에 추가한다. 택배사 전송은 하지 않는다."""
    text = delivery_request.strip()
    if not text or len(text) > 1000:
        return fail('INVALID_REQUEST', '배송 요청사항은 1~1000자로 입력해 주세요.')
    user_id = config['configurable']['state']['user_id']
    with get_conn() as conn:
        order = conn.execute(
            'SELECT product_code FROM orders WHERE order_id = %s AND user_id = %s FOR UPDATE',
            (order_id, user_id),
        ).fetchone()
        if not order:
            return fail('ORDER_NOT_ACCESSIBLE', '본인 주문을 확인할 수 없습니다.')
        event = conn.execute(
            '''SELECT * FROM delivery WHERE order_id = %s AND product_code = %s
               ORDER BY occurred_at DESC, event_seq DESC LIMIT 1 FOR UPDATE''',
            (order_id, order['product_code']),
        ).fetchone()
        if not event:
            return fail('DELIVERY_NOT_FOUND', '배송 정보가 없어 요청사항을 저장하지 못했습니다.')
        previous = event['delivery_request'] or ''
        # 같은 추가 요청의 재호출로 동일 문장이 중복 저장되지 않도록 한다.
        saved = previous if mode == 'append' and text in previous.split('\n') else (
            f'{previous}\n{text}' if mode == 'append' and previous else text
        )
        if len(saved) > 1000:
            return fail('INVALID_REQUEST', '기존 내용을 포함한 배송 요청사항은 1000자 이하여야 합니다.')
        conn.execute(
            '''UPDATE delivery SET delivery_request = %s
               WHERE order_id = %s AND product_code = %s AND event_seq = %s''',
            (saved, order_id, order['product_code'], event['event_seq']),
        )
    return {
        'ok': True, 'order_id': order_id, 'delivery_request': saved,
        'event_seq': event['event_seq'], 'carrier_notified': False,
        'message': '배송 요청사항을 저장했습니다. 택배사나 기사님에게 전달된 것은 아닙니다.',
    }



@tool('get_orders')
def orders_tool(config: RunnableConfig) -> dict:
    """본인 주문 목록을 주문일 내림차순으로 조회한다."""
    return get_orders(config['configurable']['state']['user_id'])


@tool('get_order')
def order_tool(order_id: str, config: RunnableConfig) -> dict:
    """본인 주문의 상품, 옵션, 주문일, 배송지 등 상세를 조회한다."""
    return get_order(order_id, config['configurable']['state']['user_id'])


@tool('get_delivery_info')
def delivery_tool(
    order_id: str, 
    config: RunnableConfig
) -> dict:
    """본인 주문의 배송 상태, 운송장, 배송 업무용 연락처, 인도 주소, 지연 사유를 조회한다."""
    order = get_order(
        order_id, 
        config['configurable']['state']['user_id']
    )
    
    if not order.get('ok'):
        return order

    event = _latest_delivery_event(
        order_id, 
        order['product_code']
    )
    
    
    # 주문 상태와 배송 이력의 상태가 다르면 상세 정보를 안내하지 않는다.
    if (
        event 
        and event['delivery_status'] != order['delivery_status']
    ):
        event = None
        
        
    status = order['delivery_status']
    
    result = {
        'ok': True, 
        'order_id': order_id, 
        'product_name': order['product_name'],
        'option': order.get('option'), 
        'delivery_status': status,
        'delivery_status_label': DELIVERY_STATUS_LABEL.get(status, status),
        'expected_date': order.get('expected_date'),
        'delivered_date': order.get('delivered_date'),
        'ship_address': order['ship_address'],
        'source': event.get('source', 'ORDER') if event else 'ORDER',
        'carrier_name': None, 
        'tracking_number': None, 
        'driver_contact_phone': None,
        'delivery_request': event.get('delivery_request') if event else None,
        'actual_delivery_address': None,
        'delay_reason': None, 
        'delay_reason_status': 'UNKNOWN',
        'guidance': [],
        
    }
    
    guidance = result['guidance']
    if status == 'PREPARING':
        guidance.append('아직 배송 전으로, 안내 가능한 운송장 번호가 없습니다.')
        return result
    if status == 'DELIVERED':
        guidance.append('배송이 완료되었습니다.')
    if not event:
        guidance.append('현재 운송장 번호와 기사님 연락처를 확인할 수 없습니다.')
        return result

    carrier = CARRIERS.get(event.get('carrier_code'))
    if not carrier:
        guidance.append('택배사 정보를 확인할 수 없어 상세 배송 정보를 안내하기 어렵습니다.')
        return result

    # 외부 응답 전체를 전달하지 않고 고객 안내에 허용한 필드만 선택한다.
    result.update(
        carrier_name=carrier,
        tracking_number=event.get('tracking_number'),
        driver_contact_phone=event.get('driver_contact_phone'),
        delivery_request=event.get('delivery_request'),
        actual_delivery_address=(event.get('actual_delivery_address')
                                 if status == 'DELIVERED' else None),
        expected_date=event.get('expected_delivery_at') or result['expected_date'],
        delivered_date=(event.get('delivered_at') or result['delivered_date']
                        if status == 'DELIVERED' else None),
        delay_reason=event.get('delay_reason'),
        delay_reason_status=event.get('delay_reason_status', 'UNKNOWN'),
    )
    if not result['tracking_number']:
        guidance.append('운송장 정보가 아직 전달되지 않았습니다.')
    if not result['driver_contact_phone']:
        guidance.append('기사님 연락처가 아직 전달되지 않았습니다.')
    if not result['delay_reason']:
        if result['delay_reason_status'] == 'NOT_RECEIVED':
            guidance.append('지연 사유를 묻는 경우: 택배사에서 상세 지연 사유가 아직 전달되지 않았습니다.')
        else:
            result['delay_reason_status'] = 'UNKNOWN'
            guidance.append('지연 사유를 묻는 경우: 정확한 지연 사유를 확인할 수 없습니다.')
    return result

@tool('get_delivery_status')
def get_delivery_status(
    order_id: str, 
    config: RunnableConfig
) -> dict:
    
    """본인 주문의 배송 상태, 운송장, 배송 업무용 연락처, 인도 주소, 지연 사유를 조회한다."""
    order = get_order(
        order_id, 
        config['configurable']['state']['user_id']
    )
    
    if not order.get('ok'):
        return order

    event = _latest_delivery_event(
        order_id, 
        order['product_code']
    )
    
    
    # 주문 상태와 배송 이력의 상태가 다르면 상세 정보를 안내하지 않는다.
    if (
        event 
        and event['delivery_status'] != order['delivery_status']
    ):
        event = None
        
        
    status = order['delivery_status']
    
    result = {
        'delivery_status': status,
        **order,
    }
    
    return result


@tool('get_user_address')
def user_address_tool(config: RunnableConfig) -> dict:
    """본인의 회원 등록 주소를 조회한다. 주문 배송지와 다를 수 있다."""
    return get_user_address(config['configurable']['state']['user_id'])


@tool('ask_delivery_question')
def question_tool(question: str, config: RunnableConfig, order_id: str = '') -> dict:
    """부족한 주문·주소 정보를 질문하고 배송 상담을 유지한다."""
    state = config['configurable']['state']
    pending = state['pending_data']
    created = config['configurable']['created']
    if created:
        return {'ok': False, 'message': '이미 접수되었습니다. 승인 대기 상태를 안내하세요.'}
    if order_id:
        order = get_order(order_id, config['configurable']['state']['user_id'])
        if not order.get('ok'):
            return order
        pending['order_id'] = order_id
    pending['question'] = question
    state['step'] = 'ask_delivery'
    return {'ok': True, 'question': question}


@tool('cancel_address_change')
def cancel_tool(config: RunnableConfig) -> dict:
    """접수 전 변경 대화를 종료한다. 이미 저장된 요청은 취소하지 않는다."""
    state = config['configurable']['state']
    pending = state['pending_data']
    created = config['configurable']['created']
    if created:
        return {'ok': False, 'message': '이미 접수된 요청은 이 도구로 취소할 수 없습니다.'}
    pending.clear()
    state['step'] = None
    return {'ok': True, 'message': '접수 전 절차를 종료했습니다. DB 요청은 변경하지 않았습니다.'}


@tool('request_address_change')
def request_tool(order_id: str, new_address: str, config: RunnableConfig) -> dict:
    """명확히 요청한 주문과 새 주소로 변경을 접수한다. 본인 여부·배송 상태를 검사하고 PENDING을 반환한다."""
    state = config['configurable']['state']
    pending = state['pending_data']
    created = config['configurable']['created']
    if created:
        return created
    if not new_address.strip():
        return {'ok': False, 'message': '변경할 주소를 입력해 주세요.'}
    result = request_address_change(order_id, state['user_id'], new_address.strip())
    if not result.get('ok'):
        return result
    created.update(result)
    pending.clear()
    state['step'] = None
    return result

