'''확인 질문과 긍정·부정 판별.

담당: 박종석

냅둘 것: finished, waiting, latest_user_text, validation_retry_update 시그니처.
         worker3·4가 같이 씀. 답을 messages에 넣지 말 것.
다시 쓸 것: parse_yes_no (네/아니 키워드), 확인 문장 톤.
         validation_retry_update 안의 "[검증 반영]" 붙이기는 임시.
'''

from typing import Literal

from app.graph.state import State


def build_confirm_message(
        title: str,
        fields: dict[str, str]
) -> str:
    lines = [title, '']

    for label, value in fields.items():
        lines.append(f'{label}: {value}')

    lines.append('')
    lines.append('아래 정보가 맞습니까?')

    return '\n'.join(lines)


def parse_yes_no(
        user_text: str
) -> Literal['yes', 'no', 'unknown']:
    '''짧은 답의 임시 판별.'''

    # 다시 쓰기: LLM이 yes | no | unknown. 반환 세 값은 유지 (worker3도 사용).

    text = user_text.strip()

    if not text:
        return 'unknown'

    no_words = ('아니', '아뇨', '아니요', '싫', '틀렸')
    yes_words = ('네', '예', '응', '맞', '좋아', '그래')

    if text.startswith(no_words):
        return 'no'

    if text.startswith(yes_words):
        return 'yes'

    return 'unknown'


def latest_user_text(
        state: State
) -> str:
    messages = state.get('messages') or []

    for message in reversed(messages):
        role = getattr(message, 'type', None)

        if role not in {'human', 'user'}:
            continue

        content = getattr(message, 'content', '')

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = []

            for part in content:
                if isinstance(part, dict):
                    parts.append(str(part.get('text', '')))

                else:
                    parts.append(str(part))

            return ' '.join(parts)

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
        'draft_answer': f'{draft}\n\n[검증 반영] {reason}'.strip(),
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
