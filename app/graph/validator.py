'''검증 에이전트와 사용자 응답 노드

담당: 김동규
검사:
  1. 초안의 숫자·날짜·주소·지점명이 tool_results와 같은가
  2. 사용자 질문에 답했는가
  3. PENDING / 승인 대기인데 완료라고 하지 않았는가
'''

import json

from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from app.config import settings
from app.graph.confirm import latest_user_text
from app.graph.state import State
from app.llm import get_llm

PROMPT = '''너는 고객상담 초안 검증기다. 말솜씨가 아니라 사실만 본다.

[사용자 질문]
{question}

[초안]
{draft}

[Tool 결과] 이 값만 사실이다.
{tools}

[추가 상태]
current_worker={worker}
step={step}

규칙:
- Tool에 없는 숫자·지점·날짜·주소를 초안이 말하면 passed=false
- Tool의 today, days_since_delivery, return_window_days, decision을 근거로 한 기간 거절은 통과
- [관련 규정] 인용은 Tool dispute.items와 맞으면 통과
- 질문에 답을 하지 않으면 passed=false
- 승인 대기나 PENDING인데 완료·변경됐다고 하면 passed=false
- 통과면 passed=true, reason은 한 줄
- 실패면 reason은 워커가 고칠 지시 한두 문장 (예: 재고를 10개로 고쳐라)
'''


class ValidationVerdict(BaseModel):
    passed: bool = Field(description='사실 검사를 통과하면 true')
    reason: str = Field(description='실패면 워커가 고칠 지시. 통과면 짧게')


def _supported_refusal(
        state: State
) -> bool:
    draft = state.get('draft_answer') or ''

    for item in state.get('tool_results') or []:
        if not isinstance(item, dict):
            continue

        decision = item.get('decision')

        if decision == 'RETURN_WINDOW_EXPIRED' and '7일이 지나' in draft:
            return True

        if decision == 'POLICY_CITATION' and '[관련 규정' in draft:
            return True

        if decision == 'NOT_DELIVERED' and (
            '수령 전' in draft or '수령 완료된 주문이 없어' in draft
        ):
            return True

    return False


def _payload(
        passed: bool,
        reason: str
) -> dict:
    return {
        'validation': {
            'pass': passed,
            'reason': reason,
        }
    }


def validator(
        state: State
) -> dict:
    draft = (state.get('draft_answer') or '').strip()

    if not draft:
        return _payload(False, '초안이 비어 있습니다. 사용자 질문에 대한 답을 작성하세요.')

    if state.get('step'):
        return _payload(True, '추가 입력을 기다리는 안내')

    if _supported_refusal(state):
        return _payload(True, '거절 근거가 Tool과 일치')

    tools = state.get('tool_results') or []
    prompt = PROMPT.format(
        question=latest_user_text(state) or '(질문 없음)',
        draft=draft,
        tools=json.dumps(tools, ensure_ascii=False, default=str),
        worker=state.get('current_worker') or '',
        step=state.get('step') or '',
    )

    try:
        llm = get_llm().with_structured_output(ValidationVerdict)
        verdict = llm.invoke(prompt)

    except Exception:
        return _payload(False, '검증을 수행하지 못했습니다. 초안의 숫자와 지점명을 Tool 결과와 맞춰 다시 작성하세요.')

    if isinstance(verdict, dict):
        passed = bool(verdict.get('passed', verdict.get('pass')))
        reason = str(verdict.get('reason') or '')

    else:
        passed = bool(verdict.passed)
        reason = verdict.reason or ''

    if passed:
        return _payload(True, reason or 'ok')

    return _payload(False, reason or '초안이 Tool 결과와 맞지 않습니다. 사실만 다시 작성하세요.')


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
        'last_tool_results': list(state.get('tool_results') or []),
        'tool_results': [],
        'retry_count': 0,
        'validation': None,
    }

    if not state.get('step'):
        update['current_worker'] = None
        update['pending_data'] = {}

    return update
