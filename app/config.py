'''환경변수 로딩.

담당: 김동규
'''

import os

from dotenv import load_dotenv

load_dotenv()


def _env(
        name: str,
        default: str = ''
) -> str:
    return os.getenv(name, default)


class Settings:
    '''호출 시점에 환경변수를 읽는다. 테스트에서 SQLITE_PATH를 바꿀 수 있다.'''

    @property
    def llm_model(self) -> str:
        return _env('LLM_MODEL', 'google_genai:gemini-3.7-flash')

    @property
    def gemini_api_key(self) -> str:
        return _env('GEMINI_API_KEY') or _env('GOOGLE_API_KEY')

    @property
    def redis_url(self) -> str:
        return _env('REDIS_URL', 'redis://localhost:6379')

    @property
    def sqlite_path(self) -> str:
        return _env('SQLITE_PATH', './data/app.db')

    @property
    def session_ttl_minutes(self) -> int:
        return int(_env('SESSION_TTL_MINUTES', '30'))

    @property
    def max_validation_retry(self) -> int:
        return int(_env('MAX_VALIDATION_RETRY', '2'))

    @property
    def default_user_id(self) -> str:
        return _env('DEFAULT_USER_ID', 'U001')


settings = Settings()
