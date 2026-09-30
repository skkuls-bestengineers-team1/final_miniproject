'''Supervisor 노드와 라우팅.

담당: 나송주
'''

from typing import Literal

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.config import settings
from app.graph.confirm import latest_user_text
from app.graph.state import State



model = init_chat_model(
    settings.llm_model,
    api_key=settings.gemini_api_key,
    temperature=0,
)



class SupervisorDecision(BaseModel):
    '''사용자 문의의 담당 Worker 분류 결과.'''

    target: Literal[
        'worker1',
        'worker2',
        'worker3',
        'worker4',
        'fallback',
    ] = Field(
        description='사용자 요청을 처리할 Worker'
    )

    reason: str = Field(
        description='해당 Worker를 선택한 이유'
    )



class ContinuationDecision(BaseModel):
    '''현재 발화가 기존 멀티턴의 후속 응답인지 판단한 결과.'''

    is_continuation: bool = Field(
        description='현재 진행 중인 Worker의 질문에 대한 후속 응답이면 True'
    )

    reason: str = Field(
        description='후속 응답인지 새로운 문의인지 판단한 이유'
    )



SUPERVISOR_SYSTEM_PROMPT = """
당신은 Sasung 전자 고객상담 멀티에이전트 시스템의 Supervisor입니다.

사용자의 요청을 아래 Worker 중 하나로 분류하세요.

worker1:
- 가까운 지점 문의
- 매장 또는 지점 추천

worker2:
- 제품 재고 문의
- 특정 지점의 제품 또는 카테고리 재고 확인

worker3:
- 배송 상태 조회
- 예상 배송일 조회
- 배송지 변경

worker4:
- 교환
- 환불

fallback:
- 위 네 가지 범주에 해당하지 않는 문의

사용자 요청의 의미를 기준으로 분류하세요.
단순 키워드 일치만으로 판단하지 마세요.

분류 시 다음 기준을 우선 적용하세요.

- 사용자가 재고 조회 목적을 명시한 경우,
  지점, 위치, 거리, 가까운 매장 등의 표현이 함께 포함되어 있어도
  재고 확인이 최종 목적이면 worker2로 분류합니다.

- worker1은 재고 조회 목적 없이
  가까운 매장, 지점 위치, 매장 추천을 요청하는 경우에만 분류합니다.

- 재고 보유 여부 또는 재고 수량이 핵심이면 worker2로 분류합니다.
- 배송 상태, 배송 예정일, 배송지 변경은 worker3로 분류합니다.
- 교환 또는 환불 요청은 worker4로 분류합니다.
- 어느 범주에도 해당하지 않으면 fallback으로 분류합니다.

예시:
- "가까운 지점 알려줘" → worker1
- "강남역 근처 매장 어디야?" → worker1
- "A 로봇청소기 재고 있어?" → worker2
- "A 로봇청소기 재고 있는 가까운 지점 알려줘" → worker2
- "재고 조회하고 싶은데 나랑 가까운 지점이 어디야" → worker2
"""


CONTINUATION_SYSTEM_PROMPT = """
당신은 고객상담 멀티턴 흐름을 판단하는 Supervisor입니다.

현재 진행 중인 Worker와 step이 주어집니다.

사용자의 새로운 발화가 현재 step에서 요구하고 있는 정보에 대한 후속 응답인지,
아니면 별도의 새로운 상담 문의인지 판단하세요.

후속 응답 예시:
- "네", "아니요", "맞아요"
- 주문 선택 단계에서 "1번", "ORD-001"
- 방법 선택 단계에서 "택배 수거", "지점 방문"
- 지점 입력 단계에서 "강남역"
- 주소 입력 단계에서 새로운 주소를 입력한 경우

새로운 문의 예시:
- 교환/환불 진행 중 "가까운 매장 알려줘"
- 재고 조회 진행 중 "배송 언제 와?"
- 배송지 변경 진행 중 "환불하고 싶어요"
- 주문 확인 단계에서 새로운 제품의 환불을 요청하는 경우

판단 기준:
현재 사용자 발화가 현재 step에서 요구하는 정보에 대한 답변이면 후속 응답입니다.
현재 step과 관계없는 새로운 상담 목적을 가진 발화이면 새로운 문의입니다.
"""


supervisor_model = model.with_structured_output(
    SupervisorDecision
)

continuation_model = model.with_structured_output(
    ContinuationDecision
)



def classify_intent(
        text: str
) -> SupervisorDecision:
    '''LLM을 사용해 사용자 요청의 담당 Worker를 분류한다.'''

    return supervisor_model.invoke(
        [
            SystemMessage(
                content=SUPERVISOR_SYSTEM_PROMPT
            ),
            HumanMessage(
                content=text
            ),
        ]
    )


def classify_continuation(
        state: State
) -> ContinuationDecision:
    '''현재 발화가 진행 중인 멀티턴의 후속 응답인지 판단한다.'''

    return continuation_model.invoke(
        [
            SystemMessage(
                content=CONTINUATION_SYSTEM_PROMPT
            ),
            HumanMessage(
                content=f"""
현재 Worker: {state.get('current_worker')}
현재 Step: {state.get('step')}
사용자 발화: {latest_user_text(state)}
"""
            ),
        ]
    )



def supervisor(
        state: State
) -> dict:
    '''새 문의 여부를 판단하고, 필요하면 기존 멀티턴 State를 초기화한다.'''

    current = state.get('current_worker')

    if not current:
        return {}

    continuation = classify_continuation(state)

    print(
        f'[Supervisor] continuation={continuation.is_continuation}, '
        f'reason={continuation.reason}'
    )

    if continuation.is_continuation:
        return {}

    return {
        'current_worker': None,
        'step': None,
        'pending_data': {},
        'draft_answer': None,
        'tool_results': [],
        'retry_count': 0,
        'validation': None,
    }




def route_from_supervisor(
        state: State
) -> str:
    '''기존 멀티턴이면 현재 Worker를 유지하고, 아니면 새 문의를 분류한다.'''

    current = state.get('current_worker')

    if current:
        return current

    decision = classify_intent(
        latest_user_text(state)
    )

    print(
        f'[Supervisor] target={decision.target}, '
        f'reason={decision.reason}'
    )

    return decision.target