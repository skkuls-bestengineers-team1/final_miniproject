'''범위 밖 문의, 검증 반복 실패.

담당: 김동규
'''

from langchain_core.messages import AIMessage

from app.graph.confirm import latest_user_text
from app.graph.state import State
from app.tools.inquiry_tools import save_inquiry

FALLBACK_ANSWER = '정확한 확인을 위해 상담원을 연결해 드리겠습니다.'


def fallback(
        state: State
) -> dict:
    user_id = state.get('user_id') or ''
    text = latest_user_text(state)

    save_inquiry(
        user_id=user_id,
        inquiry_text=text or '(빈 문의)',
        handled_by=None,
    )

    return {
        'messages': [AIMessage(content=FALLBACK_ANSWER)],
        'draft_answer': None,
        'tool_results': [],
        'retry_count': 0,
        'validation': None,
        'current_worker': None,
        'step': None,
        'pending_data': {},
    }
