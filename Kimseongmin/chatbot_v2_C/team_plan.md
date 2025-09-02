# 팀 분업 계획 (6인)

모듈 단위로 **소유권**을 명확히 하여 교차 간섭을 최소화합니다. 공용 타입은 `graph_interfaces.py`에만 정의합니다.

| 담당 | 소유 모듈 | 주요 함수 | 소비 인터페이스 | 납품물 |
|---|---|---|---|---|
| A | 라우터 & Clarify | `router_route`, `clarify` | `ChatState.query`, `metrics` | 라우팅 프롬프트, 신뢰도 게이트, Clarify 플로우 |
| B | 쿼리 보강 | `enhance_query` | A→ `query` | 재작성/슬롯/키워드 결과 |
| C | 상품 검색 | `product_search_rag_text2sql` | B→ `rewrite`,`slots` | RAG 파이프라인, Text2SQL 검증, 후보 리스트 |
| D | 카트 & 결제 | `cart_manage`, `checkout`, `order_process` | C→ `candidates` | 카트 연산, 재고/가격/쿠폰, 주문 레코드 |
| E | CS & RAG | `cs_intake`, `faq_policy_rag` | A 라우트(CS) | 티켓, 비전분류, 인용 포함 답변 |
| F | 핸드오프/오케스트레이션 | `handoff`, `end_session` | E/D → 결과 | CRM 웹훅, 요약/근거 전달, 영수증 |

**규칙**
- `ChatState`와 공개 계약은 **단일 파일**에서만 정의/변경.
- 타 모듈 상태는 변경하지 말고 **diff** 로만 반환.
- 모든 모듈은 자 모듈명으로 구조화 로그를 출력.
