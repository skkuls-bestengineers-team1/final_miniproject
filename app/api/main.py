'''FastAPI 앱.

담당: 나송주(채팅), 최민정(승인·알림)
로그인은 구현하지 않는다. body 또는 X-User-Id로 사용자를 받는다.
'''

from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.api.chat_ui import build_chat_ui
from app.api.schemas import (
    AdminActionResponse,
    ChatRequest,
    ChatResponse,
    NotificationItem,
    NotificationResponse,
    RequestItem,
)
from app.config import settings
from app.db.connection import fetch_all
from app.graph.builder import build_graph
from app.graph.state import initial_state
from app.redis_store.checkpointer import close_checkpointer, get_checkpointer
from app.tools.request_tools import mark_request_status
from app.tools.search_origin import current_origin, registered_origin

graph = None
graph_error = ''


@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph, graph_error

    try:
        graph = build_graph(get_checkpointer())
        graph_error = ''

    except Exception as exc:
        graph = None
        graph_error = str(exc)

    yield
    close_checkpointer()


app = FastAPI(
    title='사성전자 고객상담',
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:5173',
        'http://127.0.0.1:5173',
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


def _require_graph():
    if graph is None:
        raise HTTPException(
            status_code=503,
            detail=f'Redis 세션을 준비하지 못했습니다. {graph_error}',
        )

    return graph


def _config(user_id: str) -> dict:
    return {
        'configurable': {
            'thread_id': user_id,
        }
    }


def _interrupt_payload(snapshot) -> dict | None:
    found = list(getattr(snapshot, 'interrupts', None) or [])

    for task in getattr(snapshot, 'tasks', ()) or ():
        found.extend(getattr(task, 'interrupts', ()) or ())

    if not found:
        return None

    value = getattr(found[0], 'value', found[0])

    if isinstance(value, dict):
        return value

    return {'draft': str(value)}


def _last_ai_text(messages) -> str:
    for message in reversed(messages or []):
        if getattr(message, 'type', None) != 'ai':
            continue

        content = message.content

        if isinstance(content, str):
            return content

        return str(content)

    return ''


@app.post('/chat', response_model=ChatResponse)
def chat(
        body: ChatRequest,
        x_user_id: str | None = Header(default=None),
) -> ChatResponse:
    compiled = _require_graph()
    user_id = x_user_id or body.user_id or settings.default_user_id
    config = _config(user_id)
    snapshot = compiled.get_state(config)
    paused = _interrupt_payload(snapshot)

    if paused:
        return ChatResponse(
            answer=paused.get('draft') or '관리자 승인을 기다리고 있습니다.',
            waiting_approval=True,
        )

    if snapshot.values:
        payload = {
            'messages': [HumanMessage(content=body.message)],
        }

    else:
        payload = initial_state(
            user_id,
            HumanMessage(content=body.message),
        )

    # 기준 위치 버튼을 누른 턴에만 search_origin을 넣는다. 그 외 턴은 State에 남은 값을 쓴다.
    if body.current_position:
        payload['search_origin'] = current_origin(
            body.current_position.lat,
            body.current_position.lng,
        )

    elif body.use_registered_address:
        payload['search_origin'] = registered_origin(user_id)

    result = compiled.invoke(payload, config)
    snapshot = compiled.get_state(config)
    paused = _interrupt_payload(snapshot)

    if paused:
        return ChatResponse(
            answer=paused.get('draft') or '관리자 승인을 기다리고 있습니다.',
            waiting_approval=True,
        )

    return ChatResponse(
        answer=_last_ai_text(result.get('messages')),
        waiting_approval=False,
        ask_search_origin=(snapshot.values or {}).get('step') == 'ask_search_origin',
        ui=build_chat_ui(snapshot.values or {}),
    )


@app.get('/admin/requests', response_model=list[RequestItem])
def list_requests(
        status: str = 'PENDING'
) -> list[RequestItem]:
    rows = fetch_all(
        '''
        SELECT request_id, order_id, user_id, request_type, status,
               new_address, method, created_at
        FROM requests
        WHERE status = %s
        ORDER BY request_id
        ''',
        (status,)
    )

    return [RequestItem(**row) for row in rows]


def _resume(
        request_id: int,
        approved: bool
) -> AdminActionResponse:
    _require_graph()
    status = 'DONE' if approved else 'REJECTED'
    updated = mark_request_status(request_id, status)

    if not updated.get('ok'):
        raise HTTPException(status_code=404, detail=updated.get('message'))

    resumed = False
    detail = ''

    try:
        graph.invoke(
            Command(resume={
                'approved': approved,
                'request_id': request_id,
            }),
            _config(updated['user_id']),
        )
        resumed = True

    except Exception as exc:
        detail = str(exc)

    return AdminActionResponse(
        ok=True,
        request_id=request_id,
        status=status,
        resumed=resumed,
        detail=detail,
    )


@app.post('/admin/requests/{request_id}/approve', response_model=AdminActionResponse)
def approve_request(
        request_id: int
) -> AdminActionResponse:
    return _resume(request_id, True)


@app.post('/admin/requests/{request_id}/reject', response_model=AdminActionResponse)
def reject_request(
        request_id: int
) -> AdminActionResponse:
    return _resume(request_id, False)


@app.get('/notifications/{user_id}', response_model=NotificationResponse)
def notifications(
        user_id: str
) -> NotificationResponse:
    '''승인 완료 알림. TODO(최민정): 읽음 처리와 폴링 계약을 확정'''

    rows = fetch_all(
        '''
        SELECT request_id, request_type, status
        FROM requests
        WHERE user_id = %s AND status IN ('APPROVED', 'DONE')
        ORDER BY request_id DESC
        ''',
        (user_id,)
    )

    items = []

    for row in rows:
        if row['request_type'] == 'ADDRESS_CHANGE':
            message = '변경 완료되었습니다.'

        else:
            message = '요청이 처리되었습니다.'

        items.append(NotificationItem(
            request_id=row['request_id'],
            message=message,
        ))

    return NotificationResponse(
        user_id=user_id,
        notifications=items,
    )
