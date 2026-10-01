'''확인 질문과 긍정·부정 판별.

담당: 박종석
worker3·4가 같이 쓴다. 답을 messages에 넣지 않는다.
LLM은 get_llm() (Gemini). 실패하면 키워드로 판별한다.
'''

import re
from typing import Literal

from pydantic import BaseModel, Field

from app.graph.state import State
from app.llm import content_text, get_llm

NO_WORDS = (
    '아니', '아뇨', '아니요', '아닙니다', '틀렸', '틀려', '틀림',
    '싫', '아님', '노', 'no', 'ㄴㄴ',
)
YES_WORDS = (
    '네', '예', '응', '맞', '맞아', '맞아요', '맞습니다',
    '좋아', '좋아요', '그래', 'ok', 'okay', 'yes', 'ㅇㅇ', 'ㅇㅋ',
)


class YesNoVerdict(BaseModel):
    answer: Literal['yes', 'no', 'unknown'] = Field(
        description='짧은 확인 답. yes / no / unknown'
    )


def build_confirm_message(
        title: str,
        fields: dict[str, str]
) -> str:
    lines = [title, '']

    for label, value in fields.items():
        lines.append(f'{label}: {value}')

    lines.append('')
    lines.append('위 내용이 맞는지 확인해 주세요.')

    return '\n'.join(lines)


def _normalize(
        user_text: str
) -> str:
    return re.sub(r'[^\w\s]', '', (user_text or '').strip().lower())


def _keyword_yes_no(
        text: str
) -> Literal['yes', 'no', 'unknown']:
    if not text:
        return 'unknown'

    tokens = text.split()

    if any(
        token.startswith(word) or word in tokens
        for token in tokens
        for word in NO_WORDS
    ):
        return 'no'

    if any(
        token.startswith(word) or word in tokens
        for token in tokens
        for word in YES_WORDS
    ):
        return 'yes'

    return 'unknown'


def parse_yes_no(
        user_text: str
) -> Literal['yes', 'no', 'unknown']:
    '''짧은 답을 yes / no / unknown으로 돌린다. worker3도 같은 반환값을 쓴다.'''

    text = _normalize(user_text)

    if not text:
        return 'unknown'

    keyword = _keyword_yes_no(text)

    if keyword in {'yes', 'no'}:
        return keyword

    try:
        verdict = get_llm().with_structured_output(YesNoVerdict).invoke(
            '사용자가 확인 질문에 긍정하면 yes, 부정하면 no, '
            '확인이 아니면 unknown. "이거 맞아", "맞아요"도 yes. 한 값만.\n'
            f'발화: {user_text}'
        )
        answer = getattr(verdict, 'answer', None)

        if isinstance(verdict, dict):
            answer = verdict.get('answer')

        if answer in {'yes', 'no'}:
            return answer

    except Exception:
        pass

    return 'unknown'


def looks_like_continuation(
        step: str | None,
        user_text: str
) -> bool:
    '''진행 중인 확인·선택 단계의 짧은 답이면 Supervisor LLM 없이 후속으로 본다.'''

    text = (user_text or '').strip()

    if not step or not text:
        return False

    if any(hint in text for hint in ('규정', '조항', '근거', '청약', '분쟁')):
        return True

    if step in {'confirm_order', 'confirm_address'}:
        return _keyword_yes_no(_normalize(text)) in {'yes', 'no'}

    if step == 'select_method':
        return any(word in text for word in ('방문', '수거', '택배', '지점'))

    if step == 'select_order':
        return text.isdigit() or 'ORD-' in text.upper()

    if step == 'input_address':
        return len(text) >= 4

    return False


def latest_user_text(
        state: State
) -> str:
    messages = state.get('messages') or []

    for message in reversed(messages):
        role = getattr(message, 'type', None)

        if role not in {'human', 'user'}:
            continue

        text = content_text(getattr(message, 'content', ''))

        if text:
            return text

    return ''


def validation_retry_update(
        state: State,
        worker: str
) -> dict | None:
    '''검증 실패로 돌아온 턴이면 Tool을 다시 호출하지 않고 문장만 고친다.'''

    validation = state.get('validation')

    if not validation or validation.get('pass', True):
        return None

    reason = validation.get('reason') or '답변을 다시 확인해 주세요.'
    draft = state.get('draft_answer') or ''

    return {
        'draft_answer': f'{draft}\n\n{reason}'.strip() if draft else reason,
        'current_worker': worker,
        'retry_count': int(state.get('retry_count') or 0) + 1,
        'validation': None,
    }


def finished(
        state: State,
        worker: str,
        draft: str,
        tool_result: dict | None = None
) -> dict:
    '''한 턴 답변. current_worker는 검증 재시도를 위해 남기고, 통과 후 respond가 지운다.'''

    results = list(state.get('tool_results') or [])

    if tool_result is not None:
        results.append(tool_result)

    return {
        'draft_answer': draft,
        'tool_results': results,
        'current_worker': worker,
        'step': None,
        'pending_data': {},
    }


def waiting(
        state: State,
        worker: str,
        step: str,
        draft: str,
        pending_data: dict,
        tool_result: dict | None = None
) -> dict:
    '''사용자 답을 기다리는 중간 단계.'''

    results = list(state.get('tool_results') or [])

    if tool_result is not None:
        results.append(tool_result)

    return {
        'draft_answer': draft,
        'tool_results': results,
        'current_worker': worker,
        'step': step,
        'pending_data': pending_data,
    }
