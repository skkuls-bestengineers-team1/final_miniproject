"""배송 상담 툴. 실행 설정으로 전달받은 요청별 state를 사용한다.

config는 LLM의 입력 스키마에서 제외된다. 상태 변경은 워커가 반환값에 반영한다.
created는 한 번의 워커 실행 안에서 중복 접수를 막는 임시 정보다.
"""

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.tools.order_tools import get_delivery_status, get_order, get_orders
from app.tools.request_tools import request_address_change
from app.tools.user_tools import get_user_address



@tool('get_orders')
def orders_tool(config: RunnableConfig) -> dict:
    """본인 주문 목록을 주문일 내림차순으로 조회한다."""
    return get_orders(config['configurable']['state']['user_id'])


@tool('get_order')
def order_tool(order_id: str, config: RunnableConfig) -> dict:
    """본인 주문의 상품, 옵션, 주문일, 배송지 등 상세를 조회한다."""
    return get_order(order_id, config['configurable']['state']['user_id'])


@tool('get_delivery_status')
def delivery_tool(order_id: str, config: RunnableConfig) -> dict:
    """본인 주문의 배송 상태, 예상일, 완료일, 배송지를 조회한다."""
    return get_delivery_status(order_id, config['configurable']['state']['user_id'])


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

