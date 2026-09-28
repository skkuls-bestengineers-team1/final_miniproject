# 사성전자 고객상담 멀티에이전트 챗봇

초안. 로그인한 사용자의 주소와 주문으로 지점, 재고, 배송, 주문 문의를 처리하는 Supervisor-Worker 상담 챗봇입니다. 지금은 폴더와 실행 경로가 이어진 스켈레톤이고, LLM 분류·검증·문장 생성은 담당자 TODO로 남아 있습니다.

기본 사용자는 `U001` 박종석입니다. 로그인 화면은 없고, 요청의 `user_id`로 세션을 구분합니다. `thread_id`도 같은 값입니다.

## 유스케이스

| UC | 내용 | Worker | 턴 |
|---|---|---|---|
| UC1 | 가까운 지점 추천 | worker1 | 한 턴 |
| UC2 | 지점 재고. 제품명이 있으면 그 제품만 | worker2 | 한 턴 |
| UC3 | 배송지 변경. 관리자 승인 후 완료 | worker3 | 여러 턴 |
| UC4 | 예상 배송일과 배송 상태 | worker3 | 한 턴 |
| UC5 | 교환. 지점 방문 또는 택배 수거 | worker4 | 여러 턴 |
| UC6 | 환불. 교환과 같은 흐름 | worker4 | 여러 턴 |
| 기타 | 결제, 계정, 기술, 품질 | fallback | 한 턴. `inquiries` 저장 후 상담원 연결 |

"네 맞습니다"처럼 진행 중인 답은 다시 분류하지 않고 `current_worker`에게 넘깁니다.

## 흐름

```
START → supervisor → worker1 | worker2 | worker3 | worker4 | fallback
worker → validator → respond(통과) | 같은 worker(재작성) | fallback(2회 실패)
respond, fallback → END
```

UC3에서 새 주소를 받으면 `interrupt()`로 그래프가 멈추고, 관리자 승인 뒤 `Command(resume=...)`로 이어집니다. 세션은 RedisSaver, 지점 거리는 Redis GEO(`stores:geo`)입니다. Redis Stack이 아니면 RedisSaver가 동작하지 않습니다.

## 폴더

| 경로 | 역할 |
|---|---|
| `app/graph/state.py` | 공유 State |
| `app/graph/builder.py` | 그래프 조립, RedisSaver 컴파일 |
| `app/graph/supervisor.py` | 키워드 임시 분류 |
| `app/graph/validator.py` | 검증 stub, 통과한 답을 대화에 추가 |
| `app/graph/fallback.py` | 범위 밖·검증 실패 |
| `app/graph/confirm.py` | "아래 정보가 맞습니까?" |
| `app/workers/` | UC1~UC6 |
| `app/tools/` | 사용자, 지점, 재고, 주문, 요청, 문의 |
| `app/db/` | PostgreSQL 스키마, seed, 코드 한글명 |
| `app/redis_store/` | GEO, RedisSaver |
| `app/api/` | `POST /chat`, 관리자 승인, 알림 |
| `scripts/admin_approve.py` | 대기 요청 승인 CLI |
| `frontend/` | 채팅 화면 |
| `data/seed/` | Mock JSON |
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
| `GEMINI_API_KEY` | Gemini 키. `GOOGLE_API_KEY`가 있으면 그 값도 쓴다. 없으면 LLM 테스트는 skip |
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

미구현 지점에는 `TODO(담당자)`가 있습니다. 키워드 분류, 검증 항상 통과, 화면 스타일은 각 담당자가 LLM 또는 UI 작업으로 바꿉니다.

## 데이터 메모

- 강남역점 로봇청소기 재고는 A 10개, B 8개입니다.
- `ORD-001`은 입고 전인 빨간색 A 로봇청소기이고 배송지는 `AA동 BB아파트`입니다. 배송지 변경 예시입니다.
- `ORD-004`는 수령 후 7일 안인 같은 제품입니다. 교환·환불 예시입니다.
- `ORD-005`는 교환 가능 기간이 지난 배송 완료 주문입니다.
- 문의 CSV 원본 72건은 이 저장소에 없었습니다. `data/inquiries_testset.csv`는 분류 규칙(배송·교환·환불·범위 밖, 빈 본문, 빈 유형, 중복 ID `WEB-00035`)을 담은 샘플입니다. 원본이 생기면 이 파일을 교체하면 됩니다.
