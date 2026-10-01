'''LLM 인스턴스 생성.

담당: 나송주
TODO(나송주): 분류·추출에 Gemini 3.7 Flash를 연결
'''

from langchain.chat_models import init_chat_model

from app.config import settings


def content_text(content) -> str:
    '''Gemini 블록 목록에서 본문만 꺼낸다. extras.signature는 버린다.'''

    if content is None:
        return ''

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = [_part_text(part) for part in content]
        return '\n'.join(part for part in parts if part).strip()

    return _part_text(content)


def llm_text(result) -> str:
    '''Chat 모델 응답에서 화면용 문자열만 꺼낸다.'''

    if result is None:
        return ''

    if isinstance(result, str):
        return result.strip()

    return content_text(getattr(result, 'content', result)).strip()


def _part_text(part) -> str:
    if part is None:
        return ''

    if isinstance(part, str):
        return part.strip()

    if isinstance(part, dict):
        return str(part.get('text') or part.get('content') or '').strip()

    text = getattr(part, 'text', None)

    if text:
        return str(text).strip()

    return ''


def get_llm():
    '''init_chat_model 형식의 모델을 만든다. 호출 전까지 API 키를 요구하지 않는다.'''

    kwargs = {
        'model': settings.llm_model,
        'temperature': 0,
    }

    if settings.gemini_api_key:
        kwargs['api_key'] = settings.gemini_api_key

    return init_chat_model(**kwargs)
