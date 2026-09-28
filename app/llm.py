'''LLM 인스턴스 생성.

담당: 나송주
TODO(나송주): 분류·추출에 Gemini 3.7 Flash를 연결
'''

from langchain.chat_models import init_chat_model

from app.config import settings


def get_llm():
    '''init_chat_model 형식의 모델을 만든다. 호출 전까지 API 키를 요구하지 않는다.'''

    kwargs = {
        'model': settings.llm_model,
        'temperature': 0,
    }

    if settings.gemini_api_key:
        kwargs['api_key'] = settings.gemini_api_key

    return init_chat_model(**kwargs)
