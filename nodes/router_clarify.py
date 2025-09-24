import logging
import os
import json
from typing import Dict, Any
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_interfaces import ChatState
from utils.chat_history import build_global_context_snapshot
from config import Config

logger = logging.getLogger("A_ROUTER_CLARIFY")

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
        history_snapshot = build_global_context_snapshot(state, state.query) 
        enriched_request = {
            "query": state.query,
            "history": history_snapshot,
            "recent_messages": state.conversation_history[-6:]
        } 

        routing_method = "llm" if openai_client else "keyword" 

        if openai_client:
            try:
                route_result = _llm_routing_with_history(state.query, enriched_request)
            except Exception as history_error:
                logger.warning(f"히스토리 기반 라우팅 실패, 기존 방식 사용: {history_error}")
                route_result = _llm_routing(state.query)
        else:
            route_result = _keyword_routing(state.query)
        
        if route_result.get('target') == 'popular_products':
            route_result['target'] = 'product_search'
            route_result['reason'] = (route_result.get('reason') or '') + ' (popular→product_search 일원화)'
        logger.info(
            f"라우팅 완료: Target='{route_result['target']}', "
            f"Confidence={route_result['confidence']:.2f}, Reason={route_result['reason']}"
        )

        if _is_inappropriate_reason(route_result.get("reason")): 
            prior_count = int(state.meta.get("profanity_count", 0) or 0)  
            profanity_count = prior_count + 1 
            state.meta["profanity_count"] = profanity_count  
            route_result = {
                **route_result,
                "target": "clarify",
                "confidence": 1.0,
                "reason": "부적절 발언 감지"
            }
            return {
                "route": route_result,
                "metrics": {
                    "routing_confidence": route_result["confidence"],
                    "routing_method": routing_method
                },
                "meta": {
                    "profanity_count": profanity_count,
                    "moderation": {
                        "blocked": True,
                        "type": "profanity",
                        "count": profanity_count
                    }
                }
            }

        return {
            "route": route_result,
            "metrics": {
                "routing_confidence": route_result["confidence"],
                "routing_method": routing_method
            }
        }

    except Exception as e:
        logger.error(f"라우팅 실패: {e}")
        return {
            "route": {"target": "clarify", "confidence": 0.1},
            "metrics": {"routing_confidence": 0.1, "routing_error": str(e)}
        }

def _llm_routing(query: str) -> Dict[str, Any]:
    """LLM 기반 의도 분류"""
    
    system_prompt = """
    당신은 신선식품 쇼핑몰의 고객 의도를 분석하는 전문가입니다.
    사용자의 입력을 다음 카테고리 중 가장 적합한 하나로 분류하세요:

    ⚠️ 중요: 후속 질문과 맥락적 대화를 정확히 구분하세요!

    🚫 사용자가 욕설, 비방, 혐오, 성적 불쾌감 또는 기타 정책 위반 표현을 사용하면:
    - target을 clarify로 설정합니다.
    - confidence는 0.0~0.2 사이로 설정합니다.
    - reason은 반드시 "부적절 발언 감지"로만 작성합니다. 다른 텍스트를 덧붙이지 마세요.

1. product_search: 특정 상품을 찾거나, 추천(인기/베스트 포함)을 요청할 때.
   - 예: "유기농 사과 찾아줘", "오늘 저녁에 먹을만한 고기 있나요?"

2. recipe_search: 특정 요리의 레시피나 추천을 원할 때.
   - 예: "김치찌개 레시피 알려줘", "오늘 저녁 뭐 해먹지?"
   - 재검색: "다른 레시피 없어?", "또 다른 요리 추천해줘", "말고 다른 요리", "다른 음식 없나?"

3. vision_recipe: 이미지가 포함된 입력에서 만들어진 음식 사진을 인식하고 해당 음식의 레시피를 찾을 때.
   - 예: 음식 사진과 함께 "이거 어떻게 만들어?", "이 요리 레시피 알려줘"
   - 중요: 이미지가 포함되고 음식/요리와 관련된 질문인 경우에만 선택

4. cart_add: 특정 상품을 장바구니에 추가할 때.
   - 예: "사과 2개 담아줘", "이거 장바구니에 추가"

5. cart_remove: 특정 상품을 장바구니에서 제거할 때.
   - 예: "바나나 빼줘", "사과 장바구니에서 삭제"

6. cart_view: 현재 장바구니의 내용을 확인할 때.
   - 예: "장바구니 보여줘", "내 카트 좀 보자"

7. checkout: 주문을 시작하거나 결제를 진행하고 싶을 때.
   - 예: "결제할게요", "이제 주문하고 싶어요"

8. cs_intake: 고객서비스 일반 문의. 주문내역, 배송, 환불 요청/진행, 상품 문제 등.
   - 예: "주문내역 확인하고 싶어요", "배송이 너무 늦어요", "환불하고 싶어요"

9. faq_policy_rag: 이용 약관/정책/규정/FAQ/환불 규정 등 문서성 정책 질문.
   - 예: "환불 규정이 어떻게 돼?", "이용 약관 알려줘", "개인정보 처리방침 있어?", "자주 묻는 질문"

10. handoff: 상담사와 직접 대화하고 싶을 때.
   - 예: "상담원 연결해줘", "사람이랑 말하고 싶어"

11. clarify: 의도가 모호하거나, 일반적인 인사, 혹은 관련 없는 질문일 때.
   - 예: "안녕", "고마워", "도움말"

12. casual_chat: 일상적인 인사, 감정적 대화, 일반적인 상황 기반 추천.
   - 인사/감사: "안녕", "안녕하세요", "좋은 아침", "고마워", "잘지내?", "오늘 날씨 어때?"
   - 감정적 상황: "기분이 안 좋아", "스트레스 받아", "친구와 싸웠어", "우울해"
   - 상황 기반 추천: "비오는 날에 뭐 먹지?", "추운 날 음식 추천", "기분 좋을 때 음식"

   ⚠️ casual_chat vs product_search 구분 기준:
   - casual_chat: 이전 대화 맥락 기반의 연관 요청, 감정적 상황에서의 추천
   - product_search: 완전히 새로운 상품 검색, 구체적인 상품명/브랜드 지정
   
    응답은 반드시 다음 JSON 형식으로만 하세요:
    {"target": "분류된 카테고리", "confidence": 0.0-1.0, "reason": "분류 이유"}
    """

    user_prompt = f'사용자 입력: "{query}"'

    try:
        response = openai_client.chat.completions.create(
            model=Config.OPENAI_MODEL,
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

def _llm_routing_with_history(query: str, context_payload: Dict[str, Any]) -> Dict[str, Any]:
    """히스토리 스냅샷을 포함한 라우팅"""

    system_prompt = """
    당신은 신선식품 쇼핑몰의 고객 의도를 분석하는 전문가입니다.
    사용자의 입력을 다음 카테고리 중 가장 적합한 하나로 분류하세요:

    ⚠️ 중요: 후속 질문과 맥락적 대화를 정확히 구분하세요!

    🚫 사용자가 욕설, 비방, 혐오, 성적 불쾌감 또는 기타 정책 위반 표현을 사용하면:
    - target을 clarify로 설정합니다.
    - confidence는 0.0~0.2 사이로 설정합니다.
    - reason은 반드시 "부적절 발언 감지"로만 작성합니다. 다른 텍스트를 덧붙이지 마세요.

1. product_search: 특정 상품을 찾거나, 추천(인기/베스트 포함)을 요청할 때.
   - 예: "유기농 사과 찾아줘", "오늘 저녁에 먹을만한 고기 있나요?"

2. recipe_search: 특정 요리의 레시피나 해당 레시피에 필요한 재료들의 추천을 원할 때.
   - 예: "김치찌개 레시피 알려줘", "오늘 저녁 뭐 해먹지?", "이 레시피에 필요한 재료들을 우리 쇼핑몰에서 구매 가능한 상품으로 추천해주세요."
   - 재검색: "다른 레시피 없어?", "또 다른 요리 추천해줘", "말고 다른 요리", "다른 음식 없나?"

3. vision_recipe: 이미지가 포함된 입력에서 만들어진 음식 사진을 인식하고 해당 음식의 레시피를 찾을 때.
   - 예: 음식 사진과 함께 "이거 어떻게 만들어?", "이 요리 레시피 알려줘"
   - 중요: 이미지가 포함되고 음식/요리와 관련된 질문인 경우에만 선택

4. cart_add: 특정 상품을 장바구니에 추가할 때.
   - 예: "사과 2개 담아줘", "이거 장바구니에 추가"

5. cart_remove: 특정 상품을 장바구니에서 제거할 때.
   - 예: "바나나 빼줘", "사과 장바구니에서 삭제"

6. cart_view: 현재 장바구니의 내용을 확인할 때.
   - 예: "장바구니 보여줘", "내 카트 좀 보자"

7. checkout: 주문을 시작하거나 결제를 진행하고 싶을 때.
   - 예: "결제할게요", "이제 주문하고 싶어요"

8. cs_intake: 고객서비스 일반 문의. 주문내역, 배송, 환불 요청/진행, 상품 문제 등.
   - 예: "주문내역 확인하고 싶어요", "배송이 너무 늦어요", "환불하고 싶어요"

9. faq_policy_rag: 이용 약관/정책/규정/FAQ/환불 규정 등 문서성 정책 질문.
   - 예: "환불 규정이 어떻게 돼?", "이용 약관 알려줘", "개인정보 처리방침 있어?", "자주 묻는 질문"

10. handoff: 상담사와 직접 대화하고 싶을 때.
   - 예: "상담원 연결해줘", "사람이랑 말하고 싶어"

11. clarify: 의도가 모호하거나, 일반적인 인사, 혹은 관련 없는 질문일 때.
   - 예: "안녕", "고마워", "도움말"

12. casual_chat: 일상적인 인사, 감정적 대화, 일반적인 상황 기반 추천.
   - 인사/감사: "안녕", "안녕하세요", "좋은 아침", "고마워", "잘지내?", "오늘 날씨 어때?"
   - 감정적 상황: "기분이 안 좋아", "스트레스 받아", "친구와 싸웠어", "우울해"
   - 상황 기반 추천: "비오는 날에 뭐 먹지?", "추운 날 음식 추천", "기분 좋을 때 음식"

   ⚠️ casual_chat vs product_search 구분 기준:
   - casual_chat: 이전 대화 맥락 기반의 연관 요청, 감정적 상황에서의 추천
   - product_search: 완전히 새로운 상품 검색, 구체적인 상품명/브랜드 지정
   
    응답은 반드시 다음 JSON 형식으로만 하세요:
    {"target": "분류된 카테고리", "confidence": 0.0-1.0, "reason": "분류 이유"}
    """

    history_json = json.dumps(context_payload, ensure_ascii=False) 
    user_prompt = f'사용자 입력: "{query}"\n\n최근 맥락 정보(JSON): {history_json}'

    response = openai_client.chat.completions.create(
        model=Config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1,
        max_tokens=180,
        response_format={"type": "json_object"} 
    )

    try:
        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise ValueError("empty history routing response")  
        result = json.loads(content)
    except Exception as e:
        logger.warning(f"히스토리 라우팅 파싱 실패: {e}")
        return _llm_routing(query)

    raw_reason = result.get("reason", "")
    if _is_inappropriate_reason(raw_reason):
        normalized_reason = "부적절 발언 감지"
    else:
        normalized_reason = (raw_reason + " (history-aware)").strip()

    return {
        "target": result.get("target", "clarify"),
        "confidence": float(result.get("confidence", 0.5)),
        "reason": normalized_reason
    }

def _keyword_routing(query: str) -> Dict[str, Any]:
    """키워드 기반 폴백 라우팅"""
    
    query_lower = query.lower()
    
    intent_keywords = {

        "faq_policy_rag": ["약관", "이용 약관", "규정", "정책", "faq", "환불 규정", "환불규정", "개인정보", "처리방침"],
        "handoff": ["상담원", "상담사", "사람", "직원"],
        "cs_intake": ["주문내역", "주문 내역", "주문내역확인", "주문 내역 확인", "문의", "문제", "환불", "교환", "취소", "배송", "고장", "불량"],
        "checkout": ["결제", "주문하기", "구매하기", "계산"],
        "cart_remove": ["빼줘", "빼기", "제거", "삭제"],
        "cart_add": ["담아", "추가", "넣어"],
        "cart_view": ["장바구니", "카트", "담은 거", "목록"],
        "vision_recipe": ["이미지", "사진", "이거 어떻게", "이 요리", "음식 사진"],
        "recipe_search": ["레시피", "요리법", "만들기", "뭐 먹지", "끓이는 법"],
        "product_search": ["찾아", "검색", "있어?", "얼마", "가격", "추천", "인기상품", "베스트", "많이 팔린", "인기있는", "인기", "베스트셀러", "사고싶", "사고 싶"]
    }

    for intent, keywords in intent_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            return {"target": intent, "confidence": 0.7, "reason": f"'{keywords[0]}' 키워드 감지"}

    return {"target": "clarify", "confidence": 0.3, "reason": "명확한 의도 키워드 불분명"}


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
    
    clarify_reason = state.route.get("reason")
    if _is_inappropriate_reason(clarify_reason):  
        prior_count = int(state.meta.get("profanity_count", 0) or 0)  
        profanity_count = prior_count if prior_count else 1 
        state.meta["profanity_count"] = profanity_count  
        logger.info(f"Profanity_count = {profanity_count}")  
        if profanity_count >= 2: 
            warning = "부적절한 표현이 반복되어 상담을 종료합니다. 정중한 표현으로 다시 문의해주세요."
        else:
            warning = "부적절한 표현은 삼가 주세요. 도움이 필요하시면 말씀해 주세요."
        return {
            "clarify": {"questions": []},
            "meta": {
                "clarify_count": clarify_count + 1,
                "final_message": warning,
                "escalate": False,
                "profanity_count": profanity_count
            }
        }

    questions = _generate_clarify_questions(state)

    return {
        "clarify": {"questions": questions},
        "meta": {"clarify_count": clarify_count + 1}
    }


def _is_inappropriate_reason(reason: Any) -> bool:
    reason_text = str(reason or "")
    return "부적절 발언 감지" in reason_text  


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
