'''검증 에이전트와 사용자 응답 노드.

담당: 김동규
TODO(김동규): stub을 LLM 구조화 출력으로 교체
검사 항목:
  1. 답변 속 숫자·날짜·주소·지점명이 tool_results와 일치하는가
  2. 사용자 질문에 답했는가
  3. PENDING인데 완료라고 하지 않았는가
'''

from langchain_core.messages import AIMessage

from app.config import settings
from app.graph.state import State


def validator(
        state: State
) -> dict:
    '''스켈레톤은 항상 통과시킨다.'''

    return {
        'validation': {
            'pass': True,
            'reason': 'stub',
        }
    }


def route_from_validator(
        state: State
) -> str:
    validation = state.get('validation') or {}

    if validation.get('pass'):
        return 'respond'

    retry_count = int(state.get('retry_count') or 0)

    if retry_count < settings.max_validation_retry and state.get('current_worker'):
        return state['current_worker']

    return 'fallback'


def respond(
        state: State
) -> dict:
    '''검증을 통과한 초안을 대화에 넣고, 검증용 필드를 비운다.'''

    draft = state.get('draft_answer') or ''

    update = {
        'messages': [AIMessage(content=draft)],
        'draft_answer': None,
        'tool_results': [],
        'retry_count': 0,
        'validation': None,
    }

    # 다음 사용자 답을 기다리는 단계가 아니면 worker 진행 정보도 끝낸다.
    if not state.get('step'):
        update['current_worker'] = None
        update['pending_data'] = {}

    return update
