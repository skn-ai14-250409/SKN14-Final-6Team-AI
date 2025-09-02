# FUNCTIONS.md — 노드별 계약 및 상세 설명

본 문서는 LangGraph 상의 각 노드 함수에 대한 **책임, 입·출력, 부작용, 실패 시 동작**을 정의합니다.  
모든 구현은 이 계약을 지켜 팀 간 간섭을 최소화합니다.

> 모든 함수는 `ChatState`(입력)를 기반으로 **부분 상태 갱신(dict)** 을 반환합니다.  
> 공용 타입과 스텁은 `graph_interfaces.py` 에 정의되어 있습니다.

---

## 1) router_route(state) → Search/Order HUB | CS HUB | Clarify
**목적**: 하드코딩 없는 LLM 라우팅.  
**입력**: `state.query`, `state.attachments?`, `state.session?`  
**출력**: `state.route = {"target": "search_order" | "cs" | "clarify", "confidence": float}`  
**오류**: LLM 실패 시 `clarify`로 폴백 + 사과 메시지 유도.  
**비고**: `state.metrics.routing_confidence` 기록 필수.

---

## 2) enhance_query(state)
**목적**: 사용자 입력 재작성 + 슬롯/키워드 추출.  
**입력**: `state.query`  
**출력**: 
- `state.rewrite.text`
- `state.rewrite.keywords[]`
- `state.slots = {quantity, category, diet, price_cap, delivery_slot?...}`
**오류**: 치명적 오류 없음(원문 유지로 폴백).

---

## 3) product_search_rag_text2sql(state)
**목적**: 카탈로그 **RAG** 또는 **Text2SQL** 로 후보 생성.  
**입력**: `state.rewrite`, `state.slots`  
**출력**: 
- `state.search.candidates = [{sku, name, price, stock, score}]`
- `state.search.method = "text2sql" | "rag"`
- `state.search.sql` (선택)
**오류**: SQL 검증 실패 → RAG 폴백. 결과 없음 → Clarify 유도.

---

## 4) clarify(state)
**목적**: 모호/무결과 상황에서 표적 질문 생성 및 슬롯 보강.  
**입력**: `state.search` 또는 라우터 저신뢰  
**출력**: `state.clarify.questions[]`, 업데이트된 `state.slots`  
**엣지**: `enhance_query` 또는 `product_search_rag_text2sql` 로 루프백.  
**루프 한도**: 기본 2–3회.

---

## 5) cart_manage(state)
**목적**: 장바구니 멱등 연산 및 합계 계산.  
**입력**: `state.search.candidates` 또는 명시적 아이템 조작  
**출력**: `state.cart = {items[], subtotal, discounts[], total}`  
**오류**: 재고/제한 위반 시 사용자 교정 메시지.

---

## 6) checkout(state)
**목적**: 배송지/배송창/결제수단 수집(과금 없음).  
**입력**: `state.cart`, `state.profile`  
**출력**: `state.checkout = {address, slot, payment_method, confirmed:false}`

---

## 7) order_process(state)
**목적**: 확정/취소 처리 및 주문 레코드 생성.  
**입력**: `state.checkout`(+ 사용자 확인)  
**출력**: `state.order = {order_id, status: 'confirmed'|'cancelled'}`

---

## 8) recipe_search(state)
**목적**: 외부 레시피 검색 및 재료→SKU 매핑 제안.  
**입력**: `state.rewrite`, `state.slots`  
**출력**: `state.recipe.results[]`, `state.recipe.sku_suggestions[]?`

---

## 9) cs_intake(state)
**목적**: CS 접수(반품/교환/배송 등) + 이미지 분류.  
**입력**: `state.query`, `state.attachments`  
**출력**: `state.cs.ticket = {ticket_id, category, summary}`

---

## 10) faq_policy_rag(state)
**목적**: 통합 FAQ & Policy 말뭉치 기반 근거 있는 답변.  
**입력**: 자연어 질문 또는 `state.cs.ticket`  
**출력**: `state.cs.answer = {text, citations[], confidence}`  
**엣지**: 저신뢰 → `handoff`.

---

## 11) handoff(state)
**목적**: 인간 상담사/CRM으로 이관(요약/근거 포함).  
**입력**: `state.cs.answer` 신뢰도, 대화 이력  
**출력**: `state.handoff = {ticket_id, crm_id, status}`

---

## 12) end_session(state)
**목적**: 영수증/링크/요약 등 최종 아티팩트 반환.  
**입력**: `state.order` 또는 `state.cs`  
**출력**: `state.end = {reason, artifacts[]}`
