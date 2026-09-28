'''Supervisor 노드와 라우팅.

담당: 나송주
TODO(나송주): 키워드 분류를 LLM 구조화 출력({"target", "reason"})으로 교체
'''

from app.graph.confirm import latest_user_text
from app.graph.state import State


def classify_keyword(
        text: str
) -> str:
    '''임시 분류. 먼저 맞는 키워드를 고른다.'''

    if '재고' in text:
        return 'worker2'

    if '지점' in text or '사려고' in text or '가까운' in text:
        return 'worker1'

    if '주소' in text or '배송' in text:
        return 'worker3'

    if '교환' in text or '환불' in text:
        return 'worker4'

    return 'fallback'


def supervisor(
        state: State
) -> dict:
    '''분류 자체는 route_from_supervisor가 한다.'''

    return {}


def route_from_supervisor(
        state: State
) -> str:
    '''진행 중인 worker가 있으면 재분류하지 않는다.'''

    current = state.get('current_worker')

    if current:
        return current

    return classify_keyword(latest_user_text(state))
