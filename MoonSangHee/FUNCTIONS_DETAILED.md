# Qook 챗봇 - 기능별 함수 상세 설명서

_팀 분업용 개발 가이드_  
_업데이트: 2025-09-02_

## 📋 목차
1. [Router & Query Enhancement (라우터 및 쿼리 향상)](#1-router--query-enhancement)
2. [Product Search & RAG (상품 검색 및 RAG)](#2-product-search--rag)
3. [Cart & Order Management (장바구니 및 주문 관리)](#3-cart--order-management)
4. [Recipe Integration (레시피 통합)](#4-recipe-integration)
5. [CS & FAQ Handling (고객응대 및 FAQ)](#5-cs--faq-handling)
6. [System Architecture (시스템 아키텍처)](#6-system-architecture)

---

## 1. Router & Query Enhancement

### 1.1 Router Functions

#### `route_user_intent(state: ChatState) -> dict`
**목적**: 사용자 입력을 분석하여 적절한 처리 경로로 라우팅

**입력 파라미터**:
- `state.user_input`: 사용자 원본 메시지
- `state.user_id`: 사용자 식별자
- `state.session_context`: 세션 컨텍스트 정보

**출력**:
```python
{
    "route_decision": "search_order" | "customer_service",
    "confidence_score": float,  # 0.0 ~ 1.0
    "reasoning": str,
    "suggested_clarification": str | None  # 신뢰도가 낮을 때
}
```

**처리 로직**:
1. LLM을 사용한 의도 분류
2. 키워드 기반 보조 분석
3. 신뢰도 점수 계산
4. 임계값 미달 시 명확화 요청

**구현 포인트**:
- 한국어 자연어 처리 최적화
- 컨텍스트 고려 (이전 대화 히스토리)
- 다의적 표현 처리

#### `clarify_user_intent(state: ChatState) -> dict`
**목적**: 모호한 사용자 입력에 대한 명확화 질문 생성

**입력 파라미터**:
- `state.ambiguous_input`: 모호한 입력
- `state.possible_intents`: 가능한 의도 목록
- `state.context_hints`: 컨텍스트 힌트

**출력**:
```python
{
    "clarification_question": str,
    "suggested_options": List[str],
    "follow_up_prompts": List[str]
}
```

### 1.2 Query Enhancement Functions

#### `enhance_search_query(state: ChatState) -> dict`
**목적**: 사용자 검색 쿼리를 검색 엔진에 최적화된 형태로 변환

**입력 파라미터**:
- `state.original_query`: 원본 검색어
- `state.user_preferences`: 사용자 선호도
- `state.search_history`: 검색 이력

**출력**:
```python
{
    "enhanced_query": str,
    "search_keywords": List[str],
    "filters": {
        "category": str | None,
        "price_range": tuple | None,
        "dietary_restrictions": List[str]
    },
    "search_type": "semantic" | "keyword" | "hybrid"
}
```

#### `extract_user_slots(state: ChatState) -> dict`
**목적**: 사용자 입력에서 구조화된 정보 추출

**출력**:
```python
{
    "product_name": str | None,
    "quantity": int | None,
    "budget_range": tuple | None,
    "delivery_time": str | None,
    "dietary_preferences": List[str],
    "location": str | None
}
```

---

## 2. Product Search & RAG

### 2.1 Product Search Functions

#### `search_products_text2sql(state: ChatState) -> dict`
**목적**: 자연어를 SQL로 변환하여 상품 검색

**입력 파라미터**:
- `state.enhanced_query`: 향상된 검색 쿼리
- `state.extracted_slots`: 추출된 슬롯 정보

**출력**:
```python
{
    "sql_query": str,
    "execution_result": List[dict],
    "product_list": List[{
        "sku": str,
        "name": str,
        "price": float,
        "stock": int,
        "category": str,
        "image_url": str,
        "relevance_score": float
    }],
    "total_count": int
}
```

**구현 포인트**:
- SQL 인젝션 방지
- 읽기 전용 쿼리 검증
- 성능 최적화 (인덱스 활용)

#### `search_products_rag(state: ChatState) -> dict`
**목적**: 벡터 유사도 검색으로 상품 찾기

**입력 파라미터**:
- `state.enhanced_query`: 향상된 검색 쿼리
- `state.search_filters`: 검색 필터

**출력**:
```python
{
    "retrieved_products": List[dict],
    "similarity_scores": List[float],
    "search_metadata": {
        "vector_store": str,
        "embedding_model": str,
        "search_params": dict
    }
}
```

### 2.2 RAG Functions

#### `retrieve_product_context(query: str, k: int = 5) -> List[dict]`
**목적**: 상품 정보 벡터 검색

**구현 요소**:
- 임베딩 모델: sentence-transformers/multi-qa-mpnet-base-dot-v1
- 벡터 스토어: FAISS/Chroma
- 하이브리드 검색 (키워드 + 시맨틱)

#### `rank_and_filter_products(products: List[dict], user_prefs: dict) -> List[dict]`
**목적**: 검색 결과 순위 조정 및 필터링

**순위 기준**:
1. 유사도 점수 (40%)
2. 재고 상태 (25%)
3. 사용자 선호도 매칭 (20%)
4. 가격 경쟁력 (15%)

---

## 3. Cart & Order Management

### 3.1 Cart Functions

#### `add_to_cart(state: ChatState) -> dict`
**목적**: 상품을 장바구니에 추가

**입력 파라미터**:
- `state.selected_products`: 선택된 상품 목록
- `state.quantities`: 수량 정보
- `state.user_id`: 사용자 ID

**출력**:
```python
{
    "cart_updated": bool,
    "cart_items": List[{
        "sku": str,
        "name": str,
        "quantity": int,
        "unit_price": float,
        "total_price": float
    }],
    "cart_summary": {
        "total_items": int,
        "subtotal": float,
        "estimated_delivery": str
    },
    "validation_errors": List[str]
}
```

**검증 로직**:
- 재고 확인
- 최소/최대 주문량 검증
- 가격 유효성 확인

#### `update_cart_item(state: ChatState) -> dict`
**목적**: 장바구니 아이템 수정/삭제

#### `calculate_cart_total(cart_items: List[dict]) -> dict`
**목적**: 장바구니 총액 계산 (할인, 배송비 포함)

### 3.2 Order Processing Functions

#### `initiate_checkout(state: ChatState) -> dict`
**목적**: 결제 프로세스 시작

**출력**:
```python
{
    "checkout_session_id": str,
    "required_info": List[str],  # ["delivery_address", "payment_method"]
    "order_summary": dict,
    "estimated_total": float
}
```

#### `process_order_confirmation(state: ChatState) -> dict`
**목적**: 주문 확정 처리

**출력**:
```python
{
    "order_id": str,
    "status": "confirmed" | "failed",
    "receipt": dict,
    "estimated_delivery": str,
    "tracking_info": str
}
```

---

## 4. Recipe Integration

### 4.1 Recipe Search Functions

#### `search_recipes_tavily(state: ChatState) -> dict`
**목적**: Tavily API를 사용한 레시피 검색

**입력 파라미터**:
- `state.recipe_query`: 레시피 검색어
- `state.dietary_filters`: 식단 필터 (채식, 글루텐프리 등)

**출력**:
```python
{
    "recipes": List[{
        "title": str,
        "url": str,
        "ingredients": List[str],
        "cooking_time": str,
        "difficulty": str,
        "description": str
    }],
    "search_metadata": {
        "query_used": str,
        "results_count": int,
        "api_response_time": float
    }
}
```

#### `match_ingredients_to_products(ingredients: List[str]) -> dict`
**목적**: 레시피 재료를 상품 카탈로그와 매칭

**출력**:
```python
{
    "matched_products": List[{
        "ingredient": str,
        "matched_sku": str,
        "product_name": str,
        "confidence": float,
        "alternatives": List[dict]
    }],
    "unmatched_ingredients": List[str],
    "shopping_list": {
        "total_items": int,
        "estimated_cost": float,
        "availability": "all_available" | "partial" | "unavailable"
    }
}
```

### 4.2 Recipe-to-Cart Functions

#### `create_recipe_cart(recipe_data: dict, servings: int = 4) -> dict`
**목적**: 레시피 기반 자동 장바구니 생성

---

## 5. CS & FAQ Handling

### 5.1 Customer Service Functions

#### `classify_cs_request(state: ChatState) -> dict`
**목적**: 고객 문의 유형 분류

**출력**:
```python
{
    "category": "refund" | "delivery" | "product_inquiry" | "complaint",
    "priority": "high" | "medium" | "low",
    "requires_human": bool,
    "auto_resolvable": bool
}
```

#### `extract_order_info(state: ChatState) -> dict`
**목적**: 주문 관련 정보 추출

### 5.2 FAQ & Policy RAG Functions

#### `search_faq_documents(query: str) -> List[dict]`
**목적**: FAQ 문서에서 관련 정보 검색

**출력**:
```python
{
    "faq_results": List[{
        "question": str,
        "answer": str,
        "category": str,
        "relevance_score": float,
        "source": str
    }],
    "policy_results": List[{
        "policy_section": str,
        "content": str,
        "last_updated": str,
        "relevance_score": float
    }]
}
```

#### `generate_cs_response(context: List[dict], query: str) -> str`
**목적**: FAQ/정책 기반 응답 생성

### 5.3 Image Processing Functions

#### `process_receipt_image(image_data: bytes) -> dict`
**목적**: 영수증 이미지 분석

#### `analyze_product_image(image_data: bytes) -> dict`
**목적**: 상품 사진 분석 (불량, 상태 등)

---

## 6. System Architecture

### 6.1 State Management

#### `ChatState` 클래스 정의:
```python
@dataclass
class ChatState:
    # User Info
    user_id: str
    session_id: str
    
    # Input Processing
    user_input: str
    enhanced_query: Optional[str] = None
    extracted_slots: Optional[dict] = None
    
    # Routing
    current_route: Optional[str] = None
    route_confidence: Optional[float] = None
    
    # Search Results
    search_results: List[dict] = field(default_factory=list)
    selected_products: List[dict] = field(default_factory=list)
    
    # Cart & Order
    cart_items: List[dict] = field(default_factory=list)
    order_info: Optional[dict] = None
    
    # Context
    message_history: List[dict] = field(default_factory=list)
    session_context: dict = field(default_factory=dict)
    
    # Response
    bot_response: str = ""
    response_artifacts: List[dict] = field(default_factory=list)
    current_step: str = "input_received"
```

### 6.2 Workflow Integration

#### `create_workflow() -> StateGraph`
**목적**: LangGraph 워크플로우 구성

**노드 연결**:
```
input → router → [search_hub | cs_hub] → response_synthesis → output
```

### 6.3 Error Handling

#### `handle_workflow_error(error: Exception, state: ChatState) -> dict`
**목적**: 워크플로우 에러 처리

---

## 📝 개발 가이드라인

### 코딩 컨벤션
- 함수명: `snake_case`
- 클래스명: `PascalCase`
- 상수: `UPPER_CASE`
- 타입 힌트 필수
- Docstring 필수 (Google style)

### 테스트 요구사항
- 각 함수별 단위 테스트 작성
- 통합 테스트 시나리오 포함
- Mock 데이터 활용

### 로깅 가이드
```python
import structlog
logger = structlog.get_logger(__name__)

logger.info("function_executed", 
           function_name="search_products",
           user_id=state.user_id,
           query=state.user_input,
           result_count=len(results))
```

### 환경 변수 설정
```env
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
VECTOR_STORE_DIR=./var/index
CHROMA_PERSIST_DIR=./var/chroma
DATABASE_URL=mysql://user:pass@localhost/qook_chatbot
```

---

## 🔄 개발 우선순위

1. **Phase 1**: Router & Query Enhancement
2. **Phase 2**: Product Search (Text2SQL 우선)
3. **Phase 3**: Cart Management
4. **Phase 4**: Recipe Integration
5. **Phase 5**: CS & FAQ
6. **Phase 6**: 통합 테스트 및 최적화

각 Phase별로 개발 완료 후 통합 테스트를 진행하고, 다음 단계로 넘어가는 것을 권장합니다.