'''UC1 가까운 지점.

담당: 박서영
단일 턴. TODO(박서영): 추천 문장 생성은 LLM으로 다듬기
'''

from app.graph.confirm import finished, validation_retry_update
from app.graph.state import State
from app.tools.store_tools import find_nearest_stores


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

    stores = result['stores']
    first = stores[0]
    lines = [f"가장 가까운 지점은 {first['store_name']}입니다."]

    for index, store in enumerate(stores[1:], start=2):
        distance = store['distance_km']
        lines.append(f"{index}순위: {store['store_name']} ({distance:.1f}km)")

    return finished(state, 'worker1', '\n'.join(lines), result)
