'''API 요청·응답 모델.

담당: 나송주, 최민정
'''

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = 'U001'
    message: str


class ChatResponse(BaseModel):
    answer: str
    waiting_approval: bool = False


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
