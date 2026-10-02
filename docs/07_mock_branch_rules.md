# 07. Mock 데이터 및 브랜치 규칙

## 1. Mock 데이터 구성

`data/seed/`의 Seed 데이터를 기준으로 개발·시연에 필요한 고객상담 데이터를 구성하였다.

| 파일 | 데이터 수 | 용도 |
|---|---:|---|
| `users.json` | 2 | 데모 사용자 |
| `stores.json` | 5 | 서비스 지점 및 좌표 |
| `products.json` | 15 | 상품 목록 |
| `inventory.json` | 75 | 지점별 상품 재고 |
| `orders.json` | 7 | 사용자 주문 |
| `delivery.json` | 9 | 배송 이벤트/상태 |
| `dispute_resolution.csv` | 87행 | 교환·환불 분쟁해결기준 원본 |

추가로 `data/inquiries_testset.csv`는 Supervisor/Fallback 분류 규칙 확인을 위한 샘플 데이터로 사용한다.

## 2. 대표 Mock 시나리오

| 시나리오 | Mock 데이터 |
|---|---|
| 강남역점 로봇청소기 재고 | 비스포크 제트봇 AI 10개, 제트봇 90 콤보 8개, 제트봇 70 5개 |
| 배송지 변경 | `ORD-001`, 입고 전 주문, 배송지 변경 예시 |
| 교환/환불 가능 예시 | `ORD-004`, 실행일 기준 수령 후 3일 |
| 교환 기간 경과 예시 | `ORD-005`, 실행일 기준 수령 후 60일 |
| 사용자 구분 | 기본 `U001`, 추가 `U002` |
| 지점 검색 | 지점 좌표를 Redis GEO `stores:geo`에 적재 |

## 3. Mock 데이터 원칙

- 실제 고객/주문 데이터를 사용하지 않는다.
- 데모 시나리오가 겹치지 않도록 주문별 제품명을 구분한다.
- 날짜는 일부 `TODAY-n` 형태의 상대값으로 정의하고 DB 초기화 시점에 실제 날짜로 변환한다.
- 재고/배송/교환·환불 시나리오가 모두 재현될 수 있도록 데이터 상태를 의도적으로 다르게 구성한다.
- 실제 외부 물류 API 대신 Mock 배송 데이터를 사용한다.

---

## 4. Git 브랜치 운영 패턴

저장소에서 확인되는 실제 브랜치 패턴은 다음과 같다.

### 4.1 기본 브랜치

- `main`: 통합 및 최종 실행 기준 브랜치

### 4.2 기능 브랜치

```text
feature/<기능명>
```

확인된 예시:
- `feature/supervisor-integration`
- `feature/delivery`
- `feature/worker4`
- `feature/reservation`
- `feature/reservation-cancel`
- `feature/faq-tab`
- `feature/info-tabs`
- `feature/frontend-ui`

### 4.3 수정 브랜치

```text
fix/<수정내용>
```

확인된 예시:
- `fix/search-origin-switch`
- `fix/reservation-chat-link`
- `fix/worker2-origin-evidence`

### 4.4 초기 Worker 브랜치

프로젝트 초기에는 아래와 같이 Worker 이름을 직접 브랜치명으로 사용한 이력도 있다.

- `worker1`
- `worker2`

> 따라서 최종 문서에서는 브랜치 규칙을 `feature/*`, `fix/*` 중심으로 정리하고, `worker1/worker2`는 초기 개발 브랜치로 기록하는 것이 자연스럽다.

## 5. Commit 메시지 패턴

저장소에서 다음 Prefix가 확인된다.

```text
feat: 신규 기능
fix: 오류 수정
chore: 설정/환경/기타 정리
```

예시:
- `feat: supervisor multiturn routing 기존 skeleton 개선 완료`
- `fix: 배송 조회 시 해당 주문 카드만 표시하도록 수정`
- `chore: local virtual environment gitignore 추가`

영문 설명형 Commit도 일부 존재하므로, 향후 프로젝트에서는 Prefix 규칙을 통일하는 것이 좋다.

## 6. 권장 최소 협업 규칙

본 프로젝트의 실제 운영 형태를 기준으로 문서에 기재할 최소 규칙은 다음과 같다.

1. `main`에서 직접 대규모 기능 개발을 하지 않는다.
2. 기능은 `feature/<기능명>` 브랜치에서 개발한다.
3. 버그 수정은 `fix/<수정내용>` 브랜치에서 진행한다.
4. 기능 완료 후 PR로 `main`에 병합한다.
5. 병합 전 최소한 관련 pytest와 핵심 수동 시나리오를 확인한다.
6. Commit 메시지는 `feat:`, `fix:`, `chore:` 중 하나를 우선 사용한다.

> 4~6번은 저장소의 실제 PR/Commit 운영 패턴을 문서화하기 위해 간단히 정리한 협업 기준이다.
