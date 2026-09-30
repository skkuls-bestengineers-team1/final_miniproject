'''UC1 가까운 지점.

담당: 박서영
get_user_address → Redis GEOSEARCH 3개 → 검증이 지점 순서·이름을 Tool과 대조.
'''

from app.graph.confirm import finished, validation_retry_update
from app.graph.state import State
from app.tools.store_tools import find_nearest_stores
from app.tools.user_tools import get_user


def worker1(
        state: State
) -> dict:
    retried = validation_retry_update(state, 'worker1')

    if retried:
        return retried

    result = find_nearest_stores(state['user_id'], top_k=3)

    if not result.get('ok'):
        draft = result.get('message', '가까운 지점을 찾지 못했습니다.')
        return finished(state, 'worker1', draft, result)

    user = get_user(state['user_id'])
    name = user.get('name') if user.get('ok') else '고객'
    stores = result['stores']
    first = stores[0]
    lines = [
        f"{name} 님께서 계신 곳에서 가장 가까운 지점은 {first['store_name']}입니다. "
        f"(거리: 약 {float(first['distance_km']):.1f}km)"
    ]

    for index, store in enumerate(stores[1:], start=2):
        distance = float(store['distance_km'])
        lines.append(f"{index}순위 {store['store_name']} (거리: 약 {distance:.1f}km)")

    lines.append('방문 예약을 원하시면 아래에서 예약하러 가기를 눌러 주세요.')

    return finished(state, 'worker1', '\n'.join(lines), result)
