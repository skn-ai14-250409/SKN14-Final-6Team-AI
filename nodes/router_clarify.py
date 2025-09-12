"""
router_clarify.py — A팀: 라우터 & 명확화 (개선 버전)

A팀의 책임:
- LLM 기반 의도 라우팅 (상품검색, 레시피, 장바구니 관리, CS 등 세분화)
- 저신뢰도/모호한 상황에서 명확화 질문 생성
- 라우팅 신뢰도 기록 및 메트릭 수집
"""

import logging
import os
import json
from typing import Dict, Any

# 상대 경로로 graph_interfaces 임포트
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_interfaces import ChatState

logger = logging.getLogger("A_ROUTER_CLARIFY")

# OpenAI 클라이언트 설정
try:
    import openai
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        openai_client = openai.OpenAI(api_key=openai_api_key)
    else:
        openai_client = None
        logger.warning("OpenAI API key not found. Using fallback routing.")
except ImportError:
    openai_client = None
    logger.warning("OpenAI package not available.")

def router_route(state: ChatState) -> Dict[str, Any]:
    """
    LLM 기반 라우터
    목적: 사용자 입력을 구체적인 기능 노드로 라우팅합니다.
    """
    logger.info(f"라우팅 프로세스 시작: \"{state.query}\"")
    
    try:
        if openai_client:
            route_result = _llm_routing(state.query)
            print(route_result)
        else:
            route_result = _keyword_routing(state.query)
        
        logger.info(f"라우팅 완료: Target='{route_result['target']}', Confidence={route_result['confidence']:.2f}")
        
        return {
            "route": route_result,
            "metrics": {
                "routing_confidence": route_result["confidence"],
                "routing_method": "llm" if openai_client else "keyword"
            }
        }
        
    except Exception as e:
        logger.error(f"라우팅 실패: {e}")
        return {
            "route": {"target": "clarify", "confidence": 0.1},
            "metrics": {"routing_confidence": 0.1, "routing_error": str(e)}
        }

def _llm_routing(query: str) -> Dict[str, Any]:
    """LLM 기반 의도 분류 (cart_remove 추가)"""
    
    system_prompt = """
당신은 신선식품 쇼핑몰의 고객 의도를 분석하는 전문가입니다.
사용자의 입력을 다음 10가지 카테고리 중 가장 적합한 하나로 분류하세요:

1. product_search: 특정 상품을 찾거나, 추천을 요청할 때.
   - 예: "유기농 사과 찾아줘", "오늘 저녁에 먹을만한 고기 있나요?"

2. recipe_search: 특정 요리의 레시피나 추천을 원할 때.
   - 예: "김치찌개 레시피 알려줘", "오늘 저녁 뭐 해먹지?"

3. cart_add: 특정 상품을 장바구니에 추가할 때.
   - 예: "사과 2개 담아줘", "이거 장바구니에 추가"

4. cart_remove: 특정 상품을 장바구니에서 제거할 때.
   - 예: "바나나 빼줘", "사과 장바구니에서 삭제"

5. cart_view: 현재 장바구니의 내용을 확인할 때.
   - 예: "장바구니 보여줘", "내 카트 좀 보자"

6. checkout: 주문을 시작하거나 결제를 진행하고 싶을 때.
   - 예: "결제할게요", "이제 주문하고 싶어요"

7. cs: 고객서비스 관련 문의. 주문내역, 배송, 환불, 상품 문제 등.
   - 예: "주문내역 확인하고 싶어요", "배송이 너무 늦어요", "환불 정책이 어떻게 되나요?"

8. popular_products: 인기상품이나 베스트셀러를 추천받고 싶을 때.
   - 예: "인기상품 추천해줘", "베스트셀러 뭐야?", "많이 팔린 상품", "인기있는 과일"

9. handoff: 상담사와 직접 대화하고 싶을 때.
   - 예: "상담원 연결해줘", "사람이랑 말하고 싶어"

10. clarify: 의도가 모호하거나, 일반적인 인사, 혹은 관련 없는 질문일 때.
   - 예: "안녕", "고마워", "도움말"

응답은 반드시 다음 JSON 형식으로만 하세요:
{"target": "분류된 카테고리", "confidence": 0.0-1.0, "reason": "분류 이유"}
"""

    user_prompt = f'사용자 입력: "{query}"'

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=150
        )
        content = response.choices[0].message.content.strip()
        
        result = json.loads(content)
        return {
            "target": result.get("target", "clarify"),
            "confidence": float(result.get("confidence", 0.5)),
            "reason": result.get("reason", "")
        }
    except Exception as e:
        logger.error(f"LLM 라우팅 실패: {e}, 키워드 기반으로 전환합니다.")
        return _keyword_routing(query)

def _keyword_routing(query: str) -> Dict[str, Any]:
    """키워드 기반 폴백 라우팅 (더 세분화된 규칙)"""
    
    query_lower = query.lower()
    
    # 각 의도별 키워드 정의 (우선순위가 높은 순서대로)
    intent_keywords = {
        "handoff": ["상담원", "상담사", "사람", "직원"],
        "cs": ["주문내역", "주문 내역", "주문내역확인", "주문 내역 확인", "문의", "문제", "환불", "교환", "취소", "배송", "고장", "불량"],
        "checkout": ["결제", "주문하기", "구매하기", "계산"],
        "popular_products": ["인기상품", "베스트", "많이 팔린", "인기있는", "인기", "베스트셀러"],
        "cart_remove": ["빼줘", "빼기", "제거", "삭제"], 
        "cart_add": ["담아", "추가", "넣어"],
        "cart_view": ["장바구니", "카트", "담은 거", "목록"],
        "recipe_search": ["레시피", "요리법", "만들기", "뭐 먹지", "끓이는 법"],
        "product_search": ["찾아", "검색", "있어?", "얼마", "가격", "추천"]
    }

    # 가장 구체적인 의도부터 확인
    for intent, keywords in intent_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            return {"target": intent, "confidence": 0.7, "reason": f"'{keywords[0]}' 키워드 감지"}

    # 아무 키워드도 해당되지 않으면 clarify
    return {"target": "clarify", "confidence": 0.3, "reason": "명확한 의도 키워드 불분명"}


# clarify 함수는 기존과 동일하게 유지됩니다.
def clarify(state: ChatState) -> Dict[str, Any]:
    """
    Clarify(모호/무결과 상황 질의)
    - 결과가 부족하거나 해석이 여러 개인 경우, 후속 질문을 생성합니다.
    """
    logger.info("명확화 프로세스 시작")
    
    clarify_count = state.meta.get("clarify_count", 0)
    if clarify_count >= 3:
        return {
            "clarify": {
                "questions": ["죄송합니다. 이해하지 못했습니다. 다른 방식으로 말씀해 주시겠어요?"]
            },
            "meta": {"clarify_count": clarify_count + 1}
        }
    
    questions = _generate_clarify_questions(state)
    
    return {
        "clarify": {"questions": questions},
        "meta": {"clarify_count": clarify_count + 1}
    }

def _generate_clarify_questions(state: ChatState) -> list:
    """상황별 명확화 질문 생성"""
    
    search_results = state.search.get("candidates")
    if search_results is not None:
        if len(search_results) == 0:
            return ["찾으시는 상품이 없는 것 같습니다. 다른 이름으로 검색해보시겠어요?"]
        elif len(search_results) > 10:
            return ["검색 결과가 많습니다. 좀 더 구체적으로 말씀해 주시겠어요?"]

    if "문의" in state.query or "도움" in state.query:
        return ["어떤 도움이 필요하신지 좀 더 자세히 말씀해 주시겠어요?"]
    
    return [
        "무엇을 도와드릴까요?",
        "상품 검색, 레시피, 또는 장바구니 확인 등을 말씀해주세요."
    ]