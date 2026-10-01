# 사성전자 고객상담 멀티에이전트 챗봇

로그인한 사용자의 주소와 주문으로 지점, 재고, 배송, 주문 문의를 처리하는 Supervisor-Worker 상담 챗봇입니다. Gemini로 분류·검증·상담 문장을 만들고, 숫자는 Tool 결과만 사실로 봅니다.

기본 사용자는 `U001` 박종석입니다. 로그인 화면은 없고, 요청의 `user_id`로 세션을 구분합니다. `thread_id`도 같은 값입니다.

## 유스케이스

| UC | 내용 | Worker | 턴 |
|---|---|---|---|
| UC1 | 가까운 지점 추천. 기준 위치(현재 위치 / 주소 / 등록 주소) | worker1 | 한 턴. 위치가 없으면 한 번 물음 |
| UC2 | 지점 재고. 제품명이 있으면 그 제품만 | worker2 | 한 턴. 지점이 없으면 기준 위치를 물음 |
| UC3 | 배송지 변경. DB에 PENDING 접수 후 관리자 승인 | worker3 | 여러 턴 |
| UC4 | 예상 배송일, 배송 상태, 주문 내역 | worker3 | 한 턴 또는 되묻기 |
| UC5 | 교환. 지점 방문 또는 택배 수거 | worker4 | 여러 턴 |
| UC6 | 환불. 교환과 같은 흐름 | worker4 | 여러 턴 |
| 기타 | 결제, 계정, 기술, 품질 | fallback | 한 턴. `inquiries` 저장 후 상담원 연결 |

진행 중인 확인 질문의 후속 답은 다시 분류하지 않고 `current_worker`에게 넘깁니다. 새 문의면 Supervisor가 담당 Worker를 바꿉니다.

## 흐름

```
START → supervisor → worker1 | worker2 | worker3 | worker4 | fallback
worker → validator → respond(통과) | 같은 worker(재작성) | fallback(2회 실패)
respond, fallback → END
```

세션은 RedisSaver, 지점 거리는 Redis GEO(`stores:geo`)입니다. Redis Stack이 아니면 RedisSaver가 동작하지 않습니다.

worker1·2는 `search_origin`(현재 위치 / 입력 주소 / 등록 주소, 30분)을 공유합니다. 50km 안에 지점이 없으면 200km로 한 번 더 찾습니다.

worker3는 Gemini가 주문·배송 Tool을 고릅니다. 배송지 변경은 `requests`에 PENDING으로 남기고 채팅을 멈추지 않습니다. 승인은 `python scripts/admin_approve.py`가 DB 상태를 바꿉니다.

검증 에이전트는 초안의 숫자·지점·날짜·주소를 `tool_results`와 대조합니다. 통과한 답만 대화에 넣고, 카드 UI는 `last_tool_results`를 읽습니다.

## 화면

`http://localhost:5173` 채팅에서 지점 카드(예약 팝업), 재고 상품 카드, 주문 내역 카드를 붙입니다. 방문 예약 팝업의 "예약 접수"는 `POST /reservations`로 `reservations` 테이블에 저장합니다(같은 사용자의 같은 날짜·시간 중복, 지난 시간, 없는 지점은 거절). 예약 목록은 `GET /reservations/{user_id}`입니다.

## 폴더

| 경로 | 역할 |
|---|---|
| `app/graph/state.py` | 공유 State |
| `app/graph/builder.py` | 그래프 조립, RedisSaver 컴파일 |
| `app/graph/supervisor.py` | Gemini 분류·멀티턴 후속 판단 |
| `app/graph/validator.py` | Tool 결과와 초안 사실 검증 |
| `app/graph/fallback.py` | 범위 밖·검증 실패 |
| `app/graph/confirm.py` | 확인 질문, yes/no |
| `app/workers/` | UC1~UC6 |
| `app/tools/` | 사용자, 지점, 재고, 주문, 요청, 문의, 분쟁 RAG, 지오코딩 |
| `app/api/chat_ui.py` | 지점·상품·주문 카드 |
| `app/db/` | PostgreSQL 스키마, seed, 코드 한글명 |
| `app/redis_store/` | GEO, RedisSaver |
| `app/api/` | `POST /chat`, 세션 초기화, 관리자 승인, 알림 |
| `scripts/admin_approve.py` | 대기 요청 승인 CLI |
| `frontend/` | 사성 CS Bot 채팅 화면 |
| `data/seed/` | Mock JSON, 분쟁해결기준 CSV |
| `data/inquiries_testset.csv` | 분류 규칙 확인용 샘플 |
| `requirements.txt` | Python 패키지 |

## 실행

Python 3.11 이상이 필요합니다.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

docker compose up -d
python -m app.db.init_db
uvicorn app.api.main:app --reload --port 8000

cd frontend
npm install
npm run dev
```

화면은 `http://localhost:5173`, API는 `http://localhost:8000`, RedisInsight는 `http://localhost:8001` 입니다. PostgreSQL은 로컬 5432와 겹치지 않게 호스트 `5433`으로 엽니다.

```bash
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"U001","message":"강남역 로봇청소기 재고 알려주세요"}'
```

같은 사용자로 기준 위치나 승인 대기가 남아 있으면 채팅 창을 닫거나 `POST /chat/reset`으로 세션을 지웁니다.

배송지 변경을 승인할 때는 API 서버가 떠 있는 상태에서 `python scripts/admin_approve.py`를 실행합니다.

```bash
pytest
```

Redis나 PostgreSQL이 없으면 해당 테스트는 건너뜁니다.

## 환경 변수

`.env.example`을 `.env`로 복사합니다.

| 변수 | 의미 |
|---|---|
| `LLM_MODEL` | `init_chat_model` 형식. 기본 `google_genai:gemini-3.7-flash` |
| `GEMINI_API_KEY` | Gemini 키. 분쟁 기준 임베딩에도 쓴다. 없으면 문서는 들어가고 벡터는 비워 둔다 |
| `EMBEDDING_MODEL` | 기본 `gemini-embedding-2` (768차원). 분쟁 기준은 조 단위 15건으로 넣는다 |
| `REDIS_URL` | 기본 `redis://localhost:6379` |
| `DATABASE_URL` | 기본 `postgresql://postgres:postgres@localhost:5433/sasung_cs` |
| `SESSION_TTL_MINUTES` | 체크포인트 TTL. 기본 30분 |
| `MAX_VALIDATION_RETRY` | 검증 재작성 횟수. 기본 2 |
| `DEFAULT_USER_ID` | 기본 `U001` |

## 담당

| 담당 | 주로 손댈 곳 |
|---|---|
| 나송주 | Supervisor, RedisSaver, `/chat`, 그래프 테스트 |
| 박서영 | worker1·2, GEO, 재고, React |
| 최민정 | worker3, 배송지 변경, 관리자 승인, 알림 |
| 박종석 | worker4, 확인 모듈, 교환·환불 |
| 김동규 | 검증 에이전트, DB, seed, Docker, 사용자·문의 Tool |

## 데이터 메모

- 강남역점 로봇청소기 재고는 비스포크 제트봇 AI 10개, 제트봇 90 콤보 8개, 제트봇 70 5개입니다. 제품 seed는 사성 워치·버즈·탭 등 15종입니다.
- 같은 사용자 주문 내역에서는 제품명이 겹치지 않습니다. 이름 매칭 테스트가 꼬이지 않게 주문마다 다른 제품을 넣습니다.
- `ORD-001`은 입고 전인 사성 워치 Ultra(티타늄)이고 배송지는 `AA동 BB아파트`입니다. 배송지 변경 예시입니다.
- `ORD-004`는 실행일 기준 수령 후 3일(7일 안)인 사성 비스포크 제트봇 AI(빨간색)입니다. 교환·환불 예시입니다.
- `ORD-005`는 실행일 기준 수령 후 60일이 지나 교환 가능 기간이 지난 배송 완료 주문입니다.
- 주문 날짜는 `data/seed/orders.json`의 `TODAY-3` 같은 상대값이며 `init_db`가 실행일 기준으로 넣습니다.
- 문의 CSV 원본 72건은 이 저장소에 없었습니다. `data/inquiries_testset.csv`는 분류 규칙(배송·교환·환불·범위 밖, 빈 본문, 빈 유형, 중복 ID `WEB-00035`)을 담은 샘플입니다.
