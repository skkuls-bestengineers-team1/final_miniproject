# 08. 테스트 시나리오 및 QA 체크리스트

## 1. 테스트 목적

- Supervisor가 문의를 올바른 Worker로 라우팅하는지 확인한다.
- 각 Worker가 Tool/DB 결과를 기반으로 요구 기능을 수행하는지 확인한다.
- 멀티턴 상담 중 문맥이 유지되는지 확인한다.
- Validator가 사실 오류를 탐지하고 재작성 흐름으로 보낼 수 있는지 확인한다.
- Frontend 카드/예약/문의 기능과 Backend API가 연결되는지 확인한다.

## 2. 자동 테스트 구성

저장소에는 다음 영역의 pytest가 작성되어 있다.

| 테스트 파일 | 검증 영역 |
|---|---|
| `test_graph_smoke.py` | LangGraph 기본 연결 |
| `test_supervisor_classify.py` | Supervisor 문의 분류/라우팅 |
| `test_validator.py` | Validator 사실 검증 |
| `test_worker1_origin.py` | 지점 검색 기준 및 Worker1 |
| `test_worker2_origin.py` | 재고 검색 기준 및 Worker2 |
| `test_worker3_delivery.py` | 주문·배송 및 배송지 변경 |
| `test_delivery_continuation.py` | 배송 멀티턴/주제 전환 |
| `test_worker4_order.py` | 교환·환불 주문 흐름 |
| `test_dispute.py` | 분쟁해결기준 검색 |
| `test_dispute_chunks.py` | 분쟁 문서 Chunk |
| `test_geo.py` | Redis GEO |
| `test_reservation.py` | 방문 예약 |
| `test_request_tools.py` | 요청 생성/상태 처리 |
| `test_approval_chat.py` | 승인 처리 이후 채팅 |
| `test_chat_ui_orders.py` | 주문 카드 UI 데이터 |
| `test_db.py` | DB 연결/기초 데이터 |
| `test_init_order_dates.py` | 상대 날짜 Seed 변환 |
| `test_llm_text.py` | LLM 텍스트 처리 |

> 최종 Pass/Fail 결과는 프로젝트 의존성 및 PostgreSQL/Redis가 구성된 실행 환경에서 `pytest`로 확인한다.

---

## 3. 핵심 QA 시나리오

### QA-01 가까운 지점 조회

**입력**
```text
가까운 매장 알려줘
```

**기대 결과**
- 검색 기준이 없으면 현재 위치/등록 주소 선택을 요청한다.
- 위치 선택 후 거리순 지점이 반환된다.
- 지점 카드에 지점명, 주소, 거리 정보가 표시된다.

- [ ] 검색 기준 요청 정상
- [ ] Redis GEO 결과 정상
- [ ] 지점 카드 정상

### QA-02 지점 재고 조회

**입력**
```text
강남역점 로봇청소기 재고 있어?
```

**기대 결과**
- Supervisor → Worker2
- 해당 지점/제품의 재고 Tool 조회
- 재고 수량을 포함한 답변 및 상품 카드 표시

- [ ] Worker2 라우팅
- [ ] 재고 수량 일치
- [ ] 상품 카드 표시
- [ ] Validator 통과

### QA-03 구매 의사 → 지점 안내

**입력**
```text
로봇청소기를 구매하려고 합니다.
```

**기대 결과**
- 구매 의사 문의를 지점 안내 흐름으로 처리한다.
- 재고 질문과 구분하여 Worker1 라우팅이 가능해야 한다.

- [ ] Worker1 라우팅
- [ ] 위치 기준 확인

### QA-04 주문/배송 조회

**입력**
```text
내 주문 배송 언제 와?
```

**기대 결과**
- Supervisor → Worker3
- 사용자 주문 조회
- 배송 상태/예상일 반환
- 해당 주문 카드만 표시

- [ ] Worker3 라우팅
- [ ] 사용자 주문 필터링
- [ ] 배송 상태 일치
- [ ] 주문 카드 정상

### QA-05 배송지 변경

**입력 흐름**
```text
배송지 바꾸고 싶어
→ 대상 주문 선택
→ 새 주소 입력
```

**기대 결과**
- 대상 주문 확인
- `requests`에 `ADDRESS_CHANGE / PENDING` 생성
- 그래프가 불필요하게 멈추지 않고 응답 반환
- 관리자 승인/거절 API에서 상태 변경 가능

- [ ] PENDING 요청 생성
- [ ] 사용자/주문 ID 일치
- [ ] 관리자 승인
- [ ] 알림 조회

### QA-06 교환

**입력**
```text
ORD-004 교환하고 싶어
```

**기대 결과**
- Supervisor → Worker4
- 주문 상태/수령 기간 확인
- 분쟁해결기준 조회
- 방법(STORE_VISIT/PICKUP) 선택 후 EXCHANGE 요청 생성

- [ ] Worker4 라우팅
- [ ] 정책 검색
- [ ] 방법 선택
- [ ] 중복 요청 방지

### QA-07 환불

**입력**
```text
ORD-004 환불하고 싶어
```

**기대 결과**
- 선택한 주문 기준으로 환불 흐름 수행
- 관련 정책 근거를 사용하여 답변
- `REFUND / PENDING` 요청 생성

- [ ] 대상 주문 정확
- [ ] 정책 검색 정상
- [ ] 환불 요청 생성

### QA-08 교환 기간 경과

**입력**
```text
ORD-005 교환하고 싶어
```

**기대 결과**
- 수령 후 기간을 확인한다.
- Mock 기준으로 교환 가능 기간 경과 상황을 올바르게 안내한다.
- 허용되지 않는 요청을 임의 생성하지 않는다.

- [ ] 날짜 계산 정상
- [ ] 요청 생성 제한

### QA-09 지원 범위 밖 문의

**입력**
```text
비밀번호 변경하고 싶어
```

**기대 결과**
- Fallback으로 라우팅한다.
- `inquiries`에 문의를 저장한다.
- 지원 범위 밖임을 안내한다.

- [ ] Fallback 라우팅
- [ ] 문의 저장
- [ ] 안내 메시지 정상

### QA-10 Validator 실패/재작성

**조건**
- Worker 초안에 Tool 결과와 다른 숫자/날짜/주소를 포함한 상황을 Mock한다.

**기대 결과**
- Validator가 불일치를 탐지한다.
- 같은 Worker로 재작성한다.
- 최대 재시도 초과 시 Fallback으로 이동한다.

- [ ] 불일치 탐지
- [ ] 동일 Worker 재시도
- [ ] Retry limit 적용
- [ ] Fallback 동작

### QA-11 방문 예약

**조건**
- 지점 카드에서 미래 날짜/시간을 선택한다.

**기대 결과**
- 예약 생성
- 서비스 예약 화면에 노출
- 같은 사용자/같은 날짜/시간 중복 예약 거절
- 과거 시간 또는 존재하지 않는 지점 거절

- [ ] 예약 생성
- [ ] 예약 목록 조회
- [ ] 중복 예약 방지
- [ ] 유효성 검증

### QA-12 방문 예약 취소

**기대 결과**
- 본인 예약만 취소할 수 있다.
- 상태가 `CANCELLED`로 변경된다.
- 행은 삭제하지 않는다.

- [ ] 취소 API 성공
- [ ] 상태 변경
- [ ] 취소 시각 기록

---

## 4. 화면 QA 체크리스트

- [ ] 사용자 변경 시 해당 `user_id`로 API 요청
- [ ] FAQ 질문 선택 시 채팅 화면 이동
- [ ] 서비스 예약 → 가까운 지점 상담 연결
- [ ] 지점 카드 레이아웃 정상
- [ ] 상품 카드 재고/가격 표시 정상
- [ ] 주문 카드 배송 상태 표시 정상
- [ ] Bot Markdown 렌더링 정상
- [ ] 탭 이동 후 기존 채팅 내용 유지
- [ ] 고객의 소리 입력/접수 정상
- [ ] API 오류 시 사용자 안내 문구 표시

## 5. 실행 전 확인

```bash
docker compose up -d
python -m app.db.init_db
uvicorn app.api.main:app --reload --port 8000
cd frontend && npm run dev
```

자동 테스트:

```bash
pytest
```

README 기준으로 Redis/PostgreSQL이 없는 환경에서는 일부 테스트가 Skip될 수 있으므로, 최종 시연 전에는 실제 개발 환경에서 핵심 QA 시나리오를 수동으로 한 번 더 확인한다.
