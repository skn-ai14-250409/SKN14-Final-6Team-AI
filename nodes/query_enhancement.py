import logging
import os
import json
from typing import Dict, Any, Optional
import sys
from graph_interfaces import ChatState
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.chat_history import analyze_search_intent_with_history
from config import Config

logger = logging.getLogger("B_QUERY_ENHANCEMENT")

try:
    import openai
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        openai_client = openai.OpenAI(api_key=openai_api_key)
    else:
        openai_client = None
        logger.warning("OpenAI API key not found. Using fallback processing.")
except ImportError:
    openai_client = None
    logger.warning("OpenAI package not available.")

def enhance_query(state: ChatState) -> Dict[str, Any]:
    """
    쿼리 보강(재작성/키워드/슬롯 추출)
    - 원문(query)은 폐기하지 말고 `rewrite.text`와 함께 보존하세요.
    """
    logger.info("쿼리 보강 프로세스 시작", extra={
        "user_id": state.user_id,
        "original_query": state.query
    })

    recent_history_text = ""
    if state.conversation_history:
        history_slice = state.conversation_history[-6:]
        formatted_history = []
        for message in history_slice:
            role_label = "사용자" if message.get("role") == "user" else "봇"
            content = message.get("content", "")
            formatted_history.append(f"{role_label}: {content}")
        recent_history_text = "\n".join(formatted_history)

    search_intent = None
    try:

        search_intent = analyze_search_intent_with_history(state, state.query)
    except Exception as analyze_error:
        logger.warning(f"히스토리 기반 검색 의도 분석 실패: {analyze_error}")
        search_intent = None

    setattr(enhance_query, "_current_state", state)  
    setattr(enhance_query, "_history_text", recent_history_text)  
    setattr(enhance_query, "_search_intent", search_intent or {}) 

    try:
        result = _llm_enhance_all(state.query)
        if result is None:
            raise ValueError("LLM query enhancement returned no result") 
        logger.info(f"LLM 전체 호출 결과: {result}")

        if search_intent and search_intent.get("is_alternative_search"):
            try:
                slots = result.setdefault("slots", {})
                slots.setdefault("search_context", {})
                slots["search_context"].update({  
                    "type": "alternative",
                    "previous_dish": search_intent.get("previous_dish"),
                    "intent_scope": search_intent.get("intent_scope"),
                    "similarity_level": search_intent.get("similarity_level"),
                    "search_strategy": search_intent.get("search_strategy")
                })
            except Exception as context_error:
                logger.warning(f"검색 맥락 정보 추가 실패: {context_error}")

        filters = result.get("filters") or result.get("search_filters")
        if filters:
            meta = result.setdefault("meta", {})
            meta.update({"search_filters": filters, "enhance_path": "one_call"})  

        if recent_history_text:
            meta = result.setdefault("meta", {})
            meta.setdefault("conversation_history_used", True)  

        logger.info("쿼리 보강(통합 LLM 호출) 완료", extra={
            "has_filters": bool(filters),
            "slots_extracted": len(result.get("slots", {})),
            "keywords_generated": len(result.get("rewrite", {}).get("keywords", [])),
            "used_history": bool(recent_history_text)
        })
        return result

    except Exception as e:
        logger.error(f"쿼리 보강 실패: {e}", extra={
            "user_id": state.user_id,
            "error": str(e)
        })

        return {
            "rewrite": {
                "text": state.query,
                "keywords": [state.query],
                "confidence": 0.1
            },
            "slots": {"quantity": 1}
        }
    finally:

        setattr(enhance_query, "_current_state", None)
        setattr(enhance_query, "_history_text", "")
        setattr(enhance_query, "_search_intent", {})

def _enhance_query(state: ChatState) -> Dict[str, Any]:
    """
    히스토리 기반 쿼리 보강 (레시피 재검색 개선 버전)
    - 레시피 검색 히스토리를 참조하여 재검색 의도 분석
    - 동일 음식 vs 다른 메뉴 구분
    - 검색 맥락 정보를 slots에 추가
    - 실패 시 기존 방식으로 완벽 폴백 보장
    """
    logger.info("히스토리 기반 쿼리 보강 프로세스 시작", extra={
        "user_id": state.user_id,
        "original_query": state.query
    })

    try:
        search_intent = None
        try:
            search_intent = analyze_search_intent_with_history(state, state.query)
            logger.info(f"검색 의도 분석 결과: {search_intent}")
        except Exception as e:
            logger.warning(f"검색 의도 분석 실패, 기존 방식 사용: {e}")
            search_intent = {"is_alternative_search": False}

        if search_intent and search_intent.get("is_alternative_search"):
            try:
                result = _llm_enhance_with_history(state.query, search_intent)
                logger.info("히스토리 기반 LLM 보강 성공")
            except Exception as e:
                logger.warning(f"히스토리 기반 보강 실패, 기존 방식 사용: {e}")
                result = _llm_enhance_all(state.query)
        else:
            result = _llm_enhance_all(state.query)

        logger.info(f"LLM 보강 결과: {result}")

        if search_intent and search_intent.get("is_alternative_search"):
            try:
                if "slots" not in result:
                    result["slots"] = {}

                result["slots"]["search_context"] = {
                    "type": "alternative",
                    "previous_dish": search_intent.get("previous_dish"),
                    "intent_scope": search_intent.get("intent_scope"),
                    "similarity_level": search_intent.get("similarity_level"),
                    "search_strategy": search_intent.get("search_strategy")
                }
                logger.info("검색 맥락 정보 추가 완료")
            except Exception as e:
                logger.warning(f"검색 맥락 정보 추가 실패 (무시하고 계속): {e}")

        filters = result.get("filters") or result.get("search_filters")
        if filters:
            result["meta"] = {"search_filters": filters, "enhance_path": "history_enhanced"}

        logger.info("히스토리 기반 쿼리 보강 완료", extra={
            "is_alternative_search": search_intent.get("is_alternative_search") if search_intent else False,
            "intent_scope": search_intent.get("intent_scope") if search_intent else "unknown",
            "has_filters": bool(filters),
            "slots_extracted": len(result.get("slots", {}))
        })
        return result

    except Exception as e:
        logger.error(f"히스토리 기반 쿼리 보강 완전 실패, 기존 방식으로 폴백: {e}", extra={
            "user_id": state.user_id,
            "error": str(e)
        })

        try:
            result = _llm_enhance_all(state.query)
            logger.info("기존 방식 폴백 성공")
            return result
        except Exception as fallback_e:
            logger.error(f"기존 방식 폴백도 실패, 최소 응답 반환: {fallback_e}")

            return {
                "rewrite": {
                    "text": state.query,
                    "keywords": [state.query],
                    "confidence": 0.1
                },
                "slots": {"quantity": 1}
            }

def _llm_enhance_with_history(query: str, search_intent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """히스토리 맥락을 포함한 쿼리 보강 (재검색용)"""
    if not openai_client:
        logger.warning("OpenAI 클라이언트 없음, 기존 방식 사용")
        return _llm_enhance_all(query)

    previous_dish = search_intent.get("previous_dish", "")
    intent_scope = search_intent.get("intent_scope", "same_dish")
    search_strategy = search_intent.get("search_strategy", "SAME_DISH_ALTERNATIVE")

    system_prompt = """당신은 신선식품 쇼핑몰의 전문 쿼리 분석가입니다.
사용자의 입력을 분석하여, 이어지는 다양한 작업(상품 검색, 레시피 검색, 장바구니 관리 등)에 필요한 정보를 구조화된 JSON 형식으로 추출해야 합니다.

# === 🆕 재검색 맥락 분석 ===
현재 사용자는 이전 검색과 관련된 재검색을 요청하고 있습니다.

재검색 유형:
- same_dish: 같은 음식의 다른 레시피 검색 (예: "다른 김치찌개 레시피")
- different_menu: 완전히 다른 메뉴 검색 (예: "다른 요리 추천")

재검색 처리 규칙:
1. same_dish인 경우: 이전 음식명을 기반으로 slots 생성, 검색 다양화 키워드 추가
2. different_menu인 경우: 완전히 새로운 음식 카테고리 제안

# --- 기존 규칙들 (변경 없음) ---
최종 목표: 사용자 쿼리 하나를 분석하여, 아래 후속 작업들 중 하나를 수행하는 데 필요한 모든 정보를 완벽하게 추출해야 합니다.
1. **상품 검색**: 특정 조건(가격, 카테고리, 유기농 여부 등)에 맞는 상품을 찾습니다.
2. **레시피 검색**: 특정 요리명이나 재료로 만들 수 있는 레시피를 찾습니다.
3. **장바구니 관리**: 장바구니에 상품을 담거나, 특정 상품을 빼거나, 전체 목록을 보거나, 결제를 진행합니다.
4. **체크아웃**: 장바구니에 담긴 상품을 결제합니다.

## 상품 검색 (Product Search) 필수 규칙
- **`item` 또는 `category` 슬롯 중 하나 이상은 반드시 추출되어야 합니다.** 사용자가 무엇을 찾는지 명확하지 않으면 검색을 수행할 수 없습니다.
- product_search일 경우, slots에 product, category는 필수적으로 들어가야 합니다(중요).

## 레시피 검색 (Recipe Search) 필수 규칙
- **`dish_name` 또는 `ingredients` 슬롯 중 하나 이상은 반드시 추출되어야 합니다.** 어떤 요리에 대한 레시피인지 명확해야 합니다.
- `ingredients` 리스트에는 최소 하나 이상의 재료가 포함되어야 합니다.

# --- 출력 JSON 구조 및 슬롯 정의 ---
- **rewrite**: 사용자 의도를 명확하게 재작성한 객체.
- `text`: 표준화된 쿼리 문자열.
- `keywords`: 검색 및 분석에 사용될 키워드 목록 (재검색시 다양화 키워드 포함).
- `confidence`: 분석 신뢰도 (0.0 ~ 1.0).
- `changes`: 수행한 변경 내역.
- **slots**: 추출된 정형 데이터 객체.
- `product` (String): 상품명 (예: "사과", "교자").
- `category` (String): [과일, 채소, 곡물/견과류, 육류/수산, 유제품, 냉동식품, 조미료/소스, 음료, 베이커리, 기타] 중 하나.
- `item` (String): 구체적인 상품 품목명 (예: "사과", "한우 등심").
- `quantity` (Integer): 구매 또는 제거하려는 상품의 개수.
- `price_cap` (Integer): 최대 가격 상한선.
- `organic` (Boolean): 유기농 여부.
- `origin` (String): 원산지 (예: "국내산", "미국산", "국산"->"국내산"으로 변경).
- `ingredients` (List[String]): 레시피 검색에 사용할 재료 목록 (예: ["돼지고기", "김치"]).

# --- 핵심 규칙 ---
1. **카테고리 분류**: 제시된 10개 카테리 중 하나로 반드시 분류합니다.
2. **수량(quantity) 추출**: "개", "팩", "봉지" 등 명시적 단위만 인정하며, 기본값은 1입니다.
3. **가격(price_cap) 추출**: "만원 이하" -> 10000, "2-3만원" -> 30000 (최대값) 처럼 숫자만 추출합니다.
4. **원산지(origin) 인식**: 'XX산', '국내산', '수입산' 키워드가 있을 때만 추출하며 국가명만 있을 시 뒤에 '산'을 붙입니다. ('국산' -> '국내산'으로 대신 표기)
5. **키워드(keywords) 생성**: 상품명, 카테고리, 속성(유기농, 맛있는), 의도(구매, 검색, 레시피), 브랜드, 원산지 등을 모두 포함합니다.
6. **재작성(rewrite.text) 규칙**: 불필요한 조사, 불용어("좀")를 제거하고, 의도를 표준화합니다.
7. **물품명(product) 추출**: 기본적인 키워드이며 product_search일 경우, slots에 product는 필수적으로 들어가야 합니다.

# --- 재검색 전용 예시 ---

## 예시 1: 동일 음식 재검색 (same_dish)
- 이전 검색: "김치찌개"
- 현재 입력: "다른 김치찌개 레시피 없어?"
- 출력: {{"rewrite": {{"text": "김치찌개 레시피 검색", "keywords": ["김치찌개", "레시피", "매운", "간단한", "전통", "특별한"], "confidence": 0.9, "changes": ["재검색 의도 반영", "다양화 키워드 추가"]}}, "slots": {{"dish_name": "김치찌개", "ingredients": ["김치", "돼지고기"]}}}}

## 예시 2: 다른 메뉴 재검색 (different_menu)
- 이전 검색: "김치찌개"
- 현재 입력: "다른 요리 추천해줘"
- 출력: {{"rewrite": {{"text": "다른 요리 추천", "keywords": ["요리", "추천", "메뉴", "레시피"], "confidence": 0.8, "changes": ["완전 다른 메뉴 요청으로 분석"]}}, "slots": {{"dish_name": "추천 요리"}}}}

위 규칙과 예시를 정확히 따라 JSON 형식으로만 응답하세요."""

    try:
        context_info = f"""
재검색 맥락:
- 이전 검색: "{previous_dish}"
- 재검색 유형: {intent_scope}
- 검색 전략: {search_strategy}

현재 입력: {query}
"""

        response = openai_client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context_info}
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
            max_tokens=500
        )

        result = json.loads(response.choices[0].message.content.strip())

        if "rewrite" in result:
            rewrite = result["rewrite"]
            if "keywords" not in rewrite:
                rewrite["keywords"] = [query]
            if "confidence" not in rewrite:
                rewrite["confidence"] = 0.7

        if "slots" not in result or not result["slots"]:
            result["slots"] = {"quantity": 1}
        if "slots" in result:
            result["slots"] = {k: v for k, v in result["slots"].items() if v is not None}
            if not result["slots"]:
                result["slots"] = {"quantity": 1}

        logger.info("히스토리 기반 LLM 쿼리 보강 성공")
        return result

    except Exception as e:
        logger.error(f"히스토리 기반 LLM 호출 실패: {e}")
        return None

def _llm_enhance_all(query: str) -> Optional[Dict[str, Any]]:
    """전체 쿼리 보강 (재작성 + 슬롯 + 키워드)"""
    state_ctx = getattr(enhance_query, "_current_state", None) 
    history_text = getattr(enhance_query, "_history_text", "")  
    intent_ctx = getattr(enhance_query, "_search_intent", {}) 

    system_prompt = """당신은 신선식품 쇼핑몰의 전문 쿼리 분석가입니다.
사용자의 입력을 분석하여, 이어지는 다양한 작업(상품 검색, 레시피 검색, 장바구니 관리 등)에 필요한 정보를 구조화된 JSON 형식으로 추출해야 합니다.

# --- 최종 목표 ---
사용자 쿼리 하나를 분석하여, 아래 후속 작업들 중 하나를 수행하는 데 필요한 모든 정보를 완벽하게 추출해야 합니다.
1.  **상품 검색**: 특정 조건(가격, 카테고리, 유기농 여부 등)에 맞는 상품을 찾습니다.
2.  **레시피 검색**: 특정 요리명이나 재료로 만들 수 있는 레시피를 찾습니다.
3.  **장바구니 관리**: 장바구니에 상품을 담거나, 특정 상품을 빼거나, 전체 목록을 보거나, 결제를 진행합니다.
4.  **체크아웃**: 장바구니에 담긴 상품을 결제합니다.

## 상품 검색 (Product Search) 필수 규칙
- **`item` 또는 `category` 슬롯 중 하나 이상은 반드시 추출되어야 합니다.** 사용자가 무엇을 찾는지 명확하지 않으면 검색을 수행할 수 없습니다.
    - 예시: "유기농 만원 이하" (X - 무엇을 찾는지 불명확) -> "유기농 과일 만원 이하" (O - `category` 추출)
- 상품의 고유 이름 (예: "비비고 왕교자", "신라면")이 언급되면 `item` 슬롯에 해당 값을 할당해야 합니다.
- product_search일 경우, slots에 product, category는 필수적으로 들어가야 합니다(중요).

## 레시피 검색 (Recipe Search) 필수 규칙
- **`dish_name` 또는 `ingredients` 슬롯 중 하나 이상은 반드시 추출되어야 합니다.** 어떤 요리에 대한 레시피인지 명확해야 합니다.
- `ingredients` 리스트에는 최소 하나 이상의 재료가 포함되어야 합니다.
    - 예시: "오늘 저녁 메뉴 추천해줘" (X - 요리명이나 재료 불명확) -> "소고기로 할 수 있는 요리 추천" (O - `ingredients` 추출)

## 장바구니 관리 (Cart Management) 필수 규칙
- **상품 제거 (`remove`) 시, 제거할 대상인 `item` 슬롯이 반드시 추출되어야 합니다.**
    - 예시: "장바구니에서 하나 빼줘" (X - 무엇을 뺄지 불명확) -> "장바구니에서 제주 한라봉 빼줘" (O - `item` 추출)
- **목록 보기 (`view`) 또는 결제 (`checkout`)의 경우,** 특정 슬롯은 필요 없지만 `rewrite.text`에 "장바구니 보기" 또는 "결제 진행"과 같이 의도가 명확하게 표준화되어야 합니다.

## 체크아웃 (Checkout) 필수 규칙
- 체크아웃 의도가 명확할 경우, `rewrite.text`에 "결제 진행"과 같이 표준화되어야 합니다.
    - 예시: "이대로 결제할래" -> "결제 진행"

# --- 출력 JSON 구조 및 슬롯 정의 ---
- **rewrite**: 사용자 의도를 명확하게 재작성한 객체.
- `text`: 표준화된 쿼리 문자열.
- `keywords`: 검색 및 분석에 사용될 키워드 목록.
- `confidence`: 분석 신뢰도 (0.0 ~ 1.0).
- `changes`: 수행한 변경 내역.
- **slots**: 추출된 정형 데이터 객체.
- `product` (String): 상품명 (예: "사과", "교자").
- `category` (String): [과일, 채소, 곡물/견과류, 육류/수산, 유제품, 냉동식품, 조미료/소스, 음료, 베이커리, 기타] 중 하나.
- `item` (String): 구체적인 상품 품목명 (예: "사과", "한우 등심").
- `quantity` (Integer): 구매 또는 제거하려는 상품의 개수.
- `price_cap` (Integer): 최대 가격 상한선.
- `organic` (Boolean): 유기농 여부.
- `origin` (String): 원산지 (예: "국내산", "미국산", "국산"->"국내산"으로 변경).
- `ingredients` (List[String]): 레시피 검색에 사용할 재료 목록 (예: ["돼지고기", "김치"]).

# --- 핵심 규칙 ---
1.  **카테고리 분류**: 제시된 10개 카테리 중 하나로 반드시 분류합니다.
2.  **수량(quantity) 추출**: "개", "팩", "봉지" 등 명시적 단위만 인정하며, 기본값은 1입니다.
3.  **가격(price_cap) 추출**: "만원 이하" -> 10000, "2-3만원" -> 30000 (최대값) 처럼 숫자만 추출합니다.
4.  **원산지(origin) 인식**: 'XX산', '국내산', '수입산' 키워드가 있을 때만 추출하며 국가명만 있을 시 뒤에 '산'을 붙입니다. ('국산' -> '국내산'으로 대신 표기)
5.  **키워드(keywords) 생성**: 상품명, 카테고리, 속성(유기농, 맛있는), 의도(구매, 검색, 레시피), 브랜드, 원산지 등을 모두 포함합니다.
6.  **재작성(rewrite.text) 규칙**: 불필요한 조사, 불용어("좀")를 제거하고, 의도를 표준화합니다. (예: "찾아줘" -> "검색", "끓이는 법" -> "레시피", "빼줘" -> "제거", "보여줘" -> "보기")
7.  **물품명(product) 추출**: 기본적인 키워드이며 product_search일 경우, slots에 product는 필수적으로 들어가야 합니다.

# --- product_tbl 컬럼 우선순위 규칙 ---
**매우 중요**: product_tbl의 컬럼에 해당하는 내용이 사용자 입력에 포함되어 있을 경우, 다음 규칙을 무조건 따라야 합니다:

8.  **product_tbl 컬럼 매핑**: 사용자 입력에서 product_tbl의 컬럼과 일치하는 상품 정보가 발견되면 반드시 keywords와 slots에 추가해야 합니다.
    - **우선순위**: product 컬럼 → item 컬럼 → category 컬럼 순으로 확인
    - **셋 다 있는 경우가 가장 좋지만, 셋 중 하나는 반드시 있어야 함**
    - 예시: 사용자가 "비비고 왕교자"라고 하면 → product:"비비고 왕교자", item:"교자", category:"냉동식품" 모두 slots에 포함
    - 예시: 사용자가 "사과"라고 하면 → product:"사과", item:"사과", category:"과일" 모두 slots에 포함

9.  **keywords 필수 포함**: product_tbl에서 매핑된 모든 값들은 반드시 keywords 배열에 포함되어야 합니다.
    - 예시: "비비고 왕교자" 입력 시 → keywords에 ["비비고 왕교자", "교자", "냉동식품", "구매"] 포함

10. **카테고리 유추 규칙**: 키워드에 해당하는 product, item, category가 아무것도 없을 경우, 사용자 입력을 분석하여 가장 유사한 카테고리를 추론하고 slots의 category에 할당해야 합니다.
    - 예시: "물고기" → category: "육류/수산"
    - 예시: "빵" → category: "베이커리"
    - 예시: "음료수" → category: "음료"
    - 예시: "견과" → category: "곡물/견과류"
    - 예시: "치즈" → category: "유제품"

# --- 기능별 예시 ---

## 예시 1: 상품 검색
- 입력: "유기농 수박 1kg 3봉지 만원 이하로 구매"
- 출력: {{"rewrite": {{"text": "유기농 수박 1kg 3봉지 구매", "keywords": ["수박", "과일", "유기농", "구매"], "confidence": 0.9, "changes": ["'만원 이하로' → 가격 슬롯 이동"]}}, "slots": {{"product":"수박", "quantity": 3, "category": "과일", "item": "수박", "organic": true, "price_cap": 10000}}}}

- 입력: "국내산 귤 5000원대로 주문"
- 출력: {{"rewrite": {{"text": "국내산 귤 주문", "keywords": ["귤", "과일", "국내산", "주문"], "confidence": 0.8, "changes": ["'5000원대로' → 가격 슬롯 이동", "국내산 원산지 추출"]}}, "slots": {{"product":"귤","quantity": 1, "category": "과일", "item": "귤", "origin": "국내산", "price_cap": 5000}}}}

- 입력: "맛있는 사과 찾아줘"
- 출력: {{"rewrite": {{"text": "맛있는 사과 검색", "keywords": ["사과", "과일", "맛있는", "검색"], "confidence": 0.7, "changes": ["'찾아줘' → '검색'"]}}, "slots": {{"product":"사과", "quantity": 1, "category": "과일", "item": "사과"}}}}

- 입력: "비비고 왕교자 2팩 주문해줘"
- 출력: {{"rewrite": {{"text": "비비고 왕교자 2팩 주문", "keywords": ["비비고 왕교자", "교자", "냉동식품", "주문"], "confidence": 0.9, "changes": ["'해줘' → '주문'"]}}, "slots": {{"product":"비비고 왕교자", "quantity": 2, "category": "냉동식품", "item": "교자"}}}}

## 예시 2: 레시피 검색
- 입력: "돼지고기랑 김치로 만들 수 있는 요리 알려줘"
- 출력: {{"rewrite": {{"text": "돼지고기 김치 레시피 검색", "keywords": ["돼지고기", "김치", "레시피", "요리"], "confidence": 0.9, "changes": ["'만들 수 있는 요리 알려줘' → '레시피 검색'"]}}, "slots": {{"ingredients": ["돼지고기", "김치"]}}}}

- 입력: "간단한 닭가슴살 요리 레시피"
- 출력: {{"rewrite": {{"text": "간단한 닭가슴살 요리 레시피", "keywords": ["닭가슴살", "레시피", "요리", "간단한"], "confidence": 0.9, "changes": []}}, "slots": {{"ingredients": ["닭가슴살"], "dish_name": "닭가슴살 요리"}}}}

## 예시 3: 장바구니 관리
- 입력: "장바구니에서 우유 한 개 빼줘"
- 출력: {{"rewrite": {{"text": "장바구니 우유 1개 제거", "keywords": ["장바구니", "우유", "제거"], "confidence": 0.9, "changes": ["'한 개' → quantity: 1", "'빼줘' → '제거'"]}}, "slots": {{"product":"우유", "item": "우유", "quantity": 1}}}}

- 입력: "내 장바구니 좀 보여줄래?"
- 출력: {{"rewrite": {{"text": "장바구니 보기", "keywords": ["장바구니", "보기", "조회"], "confidence": 0.9, "changes": ["'내', '좀' 불용어 제거", "'보여줄래?' → '보기'"]}}, "slots": {}}}}

- 입력: "이대로 결제할래"
- 출력: {{"rewrite": {{"text": "결제 진행", "keywords": ["결제", "주문"], "confidence": 0.9, "changes": ["'이대로', '할래' 제거", "의도 표준화"]}}, "slots": {}}}}

위 규칙과 예시를 정확히 따라 JSON 형식으로만 응답하세요."""
    if history_text:
        system_prompt += "\n최근 대화 히스토리가 함께 제공될 수 있으며, 이를 활용해 후속 의도를 정확히 파악하세요."  

    history_section = ""
    if history_text:
        history_section = f"[이전 대화]\n{history_text}\n\n"  

    intent_hint = ""
    if intent_ctx and intent_ctx.get("is_alternative_search"):
        intent_hint = (
            "[검색 의도]\n"
            f"재검색 여부: {intent_ctx.get('is_alternative_search')}\n"
            f"의도 범위: {intent_ctx.get('intent_scope')}\n"
            f"이전 검색 음식: {intent_ctx.get('previous_dish')}\n"
            f"검색 전략: {intent_ctx.get('search_strategy')}\n\n"
        )  

    user_message = f"{history_section}{intent_hint}[현재 입력]\n{query}"  
    try:
        response = openai_client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
            max_tokens=500
        )
        
        result = json.loads(response.choices[0].message.content.strip())

        if "rewrite" in result:
            rewrite = result["rewrite"]
            if "keywords" not in rewrite:
                rewrite["keywords"] = [query]
            if "confidence" not in rewrite:
                rewrite["confidence"] = 0.7
                
        if "slots" not in result or not result["slots"]:
            result["slots"] = {"quantity": 1}
        if "slots" in result:
            result["slots"] = {k: v for k, v in result["slots"].items() if v is not None}
            if not result["slots"]:
                result["slots"] = {"quantity": 1}
        if history_text:
            meta = result.setdefault("meta", {})
            meta.setdefault("conversation_history_used", True)  
        if intent_ctx and intent_ctx.get("is_alternative_search"):
            meta = result.setdefault("meta", {})
            meta.setdefault("search_intent", intent_ctx) 
        if state_ctx and not result.get("rewrite", {}).get("text"):
            result.setdefault("rewrite", {}).setdefault("text", query) 
        return result
    
    except Exception as e:
        logger.warning(f"LLM 단일 호출 실패: {e}")
        return None
