# 01. 기획서 (PRD)

## 1. 프로젝트 개요

- **프로젝트명:** 사성전자 고객상담 멀티에이전트 챗봇
- **개발 형태:** 3일 단기 미니프로젝트
- **목표:** 로그인 사용자의 주소·주문 정보를 활용하여 지점, 재고, 주문·배송, 교환·환불 문의를 하나의 채팅 인터페이스에서 처리하는 멀티에이전트 고객상담 PoC를 구현한다.
- **핵심 구조:** Supervisor가 사용자 문의를 분류하고, 도메인별 Worker로 라우팅한 뒤 Validator가 Tool 조회 결과와 답변을 검증한다.

## 2. 개발 배경

고객상담 문의는 지점 조회, 재고 확인, 배송 상태, 배송지 변경, 교환·환불 등 서로 다른 데이터와 처리 규칙을 요구한다.  
본 프로젝트는 하나의 LLM이 모든 업무를 처리하는 방식 대신, **Supervisor-Worker 구조로 역할을 분리**하여 문의 유형별 처리 흐름을 명확하게 구성하는 것을 목표로 한다.

또한 LLM이 생성한 숫자·날짜·주소 등 사실 정보는 Tool/DB 조회 결과와 분리하여 관리하고, 최종 답변 전에 Validator가 검증하도록 설계하였다.

## 3. 주요 사용자

- 사성전자 제품을 구매했거나 구매하려는 고객
- 지점·재고·주문·배송·교환·환불 정보를 빠르게 확인하려는 사용자
- 데모에서는 `user_id`를 기준으로 사용자를 구분하며 별도의 실제 로그인 기능은 구현하지 않는다.

## 4. 핵심 기능

| 구분 | 기능 |
|---|---|
| Supervisor | 사용자 문의 분류, 도메인 Worker 라우팅, 멀티턴 후속 발화 판단 |
| Worker1 | 현재 위치·입력 주소·등록 주소 기반 가까운 지점 조회 |
| Worker2 | 지점·제품·카테고리 기반 재고 조회 |
| Worker3 | 주문 내역·배송 상태·예상 배송일 조회, 배송지 변경 접수 |
| Worker4 | 교환·환불 가능 여부 확인 및 신청 처리 |
| Validator | 답변의 숫자·날짜·주소·지점 등 사실 정보를 Tool 결과와 대조 |
| Fallback | 지원 범위 밖 문의 저장 및 상담원 연결 안내 |
| UI | 지점·상품·주문 카드, 방문 예약, FAQ, 서비스 안내, 고객의 소리 |

## 5. 개발 범위

### 5.1 포함 범위

- React 기반 고객상담 UI
- FastAPI 기반 REST API
- LangGraph 기반 Supervisor-Worker 그래프
- Gemini 기반 문의 분류·답변 생성·검증
- PostgreSQL 기반 사용자·지점·상품·재고·주문·배송·요청 데이터 관리
- pgvector 기반 교환·환불 분쟁해결기준 검색
- Redis GEO 기반 가까운 지점 검색
- RedisSaver 기반 사용자별 멀티턴 상담 상태 저장
- 방문 예약 생성·조회·취소
- 배송지 변경 요청 생성 및 관리자 승인/거절 API
- 고객의 소리 등록
- Docker Compose 기반 PostgreSQL·Redis 실행 환경

### 5.2 제외/제한 범위

- 실제 회원 인증/인가
- 실제 물류사 API 연동
- 실제 상담원 시스템으로의 Handoff
- 운영용 관리자 UI
- 실제 사성전자 운영 데이터 연동
- 결제·계정·기술·품질 등 정의된 상담 범위 밖 업무의 자동 처리

## 6. 핵심 유스케이스

| UC | 내용 | 처리 Agent |
|---|---|---|
| UC1 | 가까운 지점 추천 | Worker1 |
| UC2 | 지점별 상품 재고 확인 | Worker2 |
| UC3 | 배송지 변경 접수 | Worker3 |
| UC4 | 주문 내역·배송 상태·예상 배송일 조회 | Worker3 |
| UC5 | 교환 접수 | Worker4 |
| UC6 | 환불 접수 | Worker4 |
| 기타 | 지원 범위 밖 문의 저장 및 안내 | Fallback |

## 7. 주요 비즈니스 규칙

- 진행 중인 확인 질문에 대한 후속 답변은 기존 `current_worker` 문맥을 우선 사용한다.
- 새 문의로 판단되면 Supervisor가 다시 담당 Worker를 결정한다.
- 지점 검색 기준은 현재 위치, 사용자가 입력한 주소, 등록 주소 중 하나를 사용한다.
- 지점은 기본 50 km 범위에서 조회하고 결과가 없으면 200 km까지 확장한다.
- 배송지 변경은 즉시 DB 내용을 변경하지 않고 `requests`에 `PENDING` 상태로 저장한다.
- 교환·환불은 주문 상태와 수령일 등 조건을 확인하여 처리한다.
- Worker 답변은 Validator 검증을 통과한 경우에만 최종 응답으로 반환한다.
- 검증 실패 시 같은 Worker가 재작성하며 최대 재시도 횟수를 초과하면 Fallback으로 이동한다.
- 사용자별 상담 State는 `thread_id = user_id`로 구분한다.

## 8. 기술 스택

| 영역 | 기술 |
|---|---|
| Frontend | React, TypeScript, Vite |
| Backend | FastAPI, Pydantic |
| Agent | LangGraph |
| LLM | Gemini |
| Database | PostgreSQL |
| Vector Search | pgvector |
| Session / GEO | Redis, RedisSaver, Redis GEO |
| Infra | Docker Compose |
| Test | pytest |

## 9. 완료 기준

- 정의된 4개 도메인 Worker가 Supervisor를 통해 정상 라우팅된다.
- 지점·재고·주문·배송·교환·환불 핵심 시나리오가 UI에서 실행 가능하다.
- Worker 답변이 Validator를 거쳐 최종 응답으로 전달된다.
- DB/Redis를 이용한 상태 및 데이터 조회 흐름이 동작한다.
- 정의된 API와 화면 기능이 연결된다.

> 작성 기준: `README.md`, `app/graph/`, `app/workers/`, `app/api/`, `app/db/`의 실제 구현 구조를 기준으로 역문서화하였다.
