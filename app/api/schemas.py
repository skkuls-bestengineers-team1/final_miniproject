'''API 요청·응답 모델.

담당: 나송주, 최민정
'''

from pydantic import BaseModel, Field


class Position(BaseModel):
    '''브라우저 geolocation 좌표.'''

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class ChatRequest(BaseModel):
    user_id: str = 'U001'
    message: str
    current_position: Position | None = None   # [현재 위치] 선택 시
    use_registered_address: bool = False       # [등록 주소로] 선택 또는 위치 권한 거부 시


class ChatResponse(BaseModel):
    answer: str
    waiting_approval: bool = False
    ask_search_origin: bool = False            # True면 화면에 기준 위치 선택 버튼 표시
    ui: dict | None = None


class SessionResetRequest(BaseModel):
    user_id: str = 'U001'


class RequestItem(BaseModel):
    request_id: int
    order_id: str
    user_id: str
    request_type: str
    status: str
    new_address: str | None = None
    method: str | None = None
    created_at: str | None = None


class AdminActionResponse(BaseModel):
    ok: bool
    request_id: int
    status: str
    resumed: bool = False
    detail: str = ''


class NotificationItem(BaseModel):
    request_id: int
    message: str


class NotificationResponse(BaseModel):
    user_id: str
    notifications: list[NotificationItem] = Field(default_factory=list)
