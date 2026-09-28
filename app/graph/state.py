'''공유 State.

담당: 나송주
DB 연결이나 클라이언트 객체는 넣지 않는다.
'''

from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages

WorkerName = Literal['worker1', 'worker2', 'worker3', 'worker4']


class State(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
    current_worker: WorkerName | None
    step: str | None
    pending_data: dict
    draft_answer: str | None
    tool_results: list[dict]
    retry_count: int
    validation: dict | None


def initial_state(
        user_id: str,
        message
) -> State:
    '''첫 발화에만 모든 키를 채운다. 이후 턴은 messages만 넘긴다.'''

    return {
        'messages': [message],
        'user_id': user_id,
        'current_worker': None,
        'step': None,
        'pending_data': {},
        'draft_answer': None,
        'tool_results': [],
        'retry_count': 0,
        'validation': None,
    }
