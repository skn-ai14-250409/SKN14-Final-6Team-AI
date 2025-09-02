"""
router_clarify.py — A팀: 라우터 & 명확화

A팀의 책임:
- LLM 기반 의도 라우팅 (검색/주문 vs CS vs Clarify)
- 저신뢰도/모호한 상황에서 명확화 질문 생성
- 라우팅 신뢰도 기록 및 메트릭 수집
"""

import logging
import os
from typing import Dict, Any, Optional

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
    목적: 사용자 입력을 **검색/주문 허브**, **CS 허브**, **Clarify** 중 하나로 보냅니다.

    입력: state.query, state.attachments(선택), 세션 메타
    출력: state.route, state.metrics
    """
    logger.info("라우팅 프로세스 시작", extra={
        "user_id": state.user_id,
        "session_id": state.session_id,
        "query": state.query
    })
    
    try:
        # LLM 기반 라우팅 시도
        if openai_client:
            route_result = _llm_routing(state.query, state.attachments)
        else:
            # 폴백: 키워드 기반 라우팅
            route_result = _keyword_routing(state.query, state.attachments)
        
        logger.info("라우팅 완료", extra={
            "target": route_result["target"],
            "confidence": route_result["confidence"]
        })
        
        return {
            "route": route_result,
            "metrics": {
                "routing_confidence": route_result["confidence"],
                "routing_method": "llm" if openai_client else "keyword"
            }
        }
        
    except Exception as e:
        logger.error(f"라우팅 실패: {e}", extra={
            "user_id": state.user_id,
            "error": str(e)
        })
        
        # 실패 시 Clarify로 폴백
        return {
            "route": {"target": "clarify", "confidence": 0.1},
            "metrics": {"routing_confidence": 0.1, "routing_error": str(e)}
        }

def _llm_routing(query: str, attachments: list) -> Dict[str, Any]:
    """LLM 기반 의도 분류"""
    
    system_prompt = """
당신은 신선식품 쇼핑몰의 고객 의도를 분석하는 전문가입니다.
사용자의 입력을 다음 3가지 카테고리 중 하나로 분류하세요:

1. search_order: 상품 검색, 주문, 장바구니, 레시피 관련
   - 예: "사과 주문하고 싶어요", "김치찌개 레시피", "장바구니에 담아줘"
   
2. cs: 고객서비스, 문의, 불만, 환불, 배송 관련  
   - 예: "배송이 늦어요", "환불하고 싶어요", "상품에 문제가 있어요"
   
3. clarify: 모호하거나 이해하기 어려운 입력
   - 예: "안녕", "도움말", 불분명한 문장

응답은 반드시 다음 JSON 형식으로만 하세요:
{"target": "search_order|cs|clarify", "confidence": 0.0-1.0, "reason": "분류 이유"}
"""

    user_prompt = f"""
사용자 입력: "{query}"
첨부파일: {len(attachments)}개
"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=150
        )
        
        content = response.choices[0].message.content.strip()
        
        # JSON 파싱 시도
        import json
        try:
            result = json.loads(content)
            return {
                "target": result.get("target", "clarify"),
                "confidence": float(result.get("confidence", 0.5)),
                "reason": result.get("reason", "")
            }
        except json.JSONDecodeError:
            logger.warning(f"LLM 응답 파싱 실패: {content}")
            return _keyword_routing(query, attachments)
            
    except Exception as e:
        logger.error(f"LLM 라우팅 실패: {e}")
        return _keyword_routing(query, attachments)

def _keyword_routing(query: str, attachments: list) -> Dict[str, Any]:
    """키워드 기반 폴백 라우팅"""
    
    query_lower = query.lower()
    
    # CS 키워드
    cs_keywords = [
        "문의", "문제", "불만", "환불", "교환", "취소", "배송", "연락", "상담",
        "늦어", "안와", "잘못", "이상해", "고장", "불량", "실수", "도움"
    ]
    
    # 검색/주문 키워드  
    search_keywords = [
        "주문", "사고", "찾아", "검색", "장바구니", "담아", "결제", "구매",
        "사과", "바나나", "채소", "과일", "레시피", "요리", "만들기"
    ]
    
    # 첨부파일이 있으면 CS로 분류 확률 높임
    if attachments:
        return {"target": "cs", "confidence": 0.7, "reason": "첨부파일 있음"}
    
    # CS 키워드 체크
    cs_score = sum(1 for keyword in cs_keywords if keyword in query_lower)
    
    # 검색/주문 키워드 체크
    search_score = sum(1 for keyword in search_keywords if keyword in query_lower)
    
    if cs_score > search_score and cs_score > 0:
        return {"target": "cs", "confidence": 0.6, "reason": "CS 키워드 감지"}
    elif search_score > 0:
        return {"target": "search_order", "confidence": 0.6, "reason": "상품/주문 키워드 감지"}
    else:
        return {"target": "clarify", "confidence": 0.3, "reason": "명확한 의도 불분명"}

def clarify(state: ChatState) -> Dict[str, Any]:
    """
    Clarify(모호/무결과 상황 질의)
    - 결과가 부족하거나 해석이 여러 개인 경우, 후속 질문을 생성합니다.
    - 루프 예산(예: 최대 2~3회)을 상태/메타로 관리하세요.
    """
    logger.info("명확화 프로세스 시작", extra={
        "user_id": state.user_id,
        "query": state.query
    })
    
    try:
        # 현재 clarify 횟수 체크
        clarify_count = state.meta.get("clarify_count", 0)
        max_clarify = 3
        
        if clarify_count >= max_clarify:
            logger.info("최대 명확화 횟수 도달, 기본 응답으로 전환")
            return {
                "clarify": {
                    "questions": ["죄송합니다. 이해하지 못했습니다. 다른 방식으로 말씀해 주시겠어요?"]
                },
                "meta": {"clarify_count": clarify_count + 1}
            }
        
        # 상황별 명확화 질문 생성
        questions = _generate_clarify_questions(state)
        
        logger.info("명확화 질문 생성 완료", extra={
            "questions_count": len(questions),
            "clarify_count": clarify_count + 1
        })
        
        return {
            "clarify": {"questions": questions},
            "meta": {"clarify_count": clarify_count + 1}
        }
        
    except Exception as e:
        logger.error(f"명확화 실패: {e}")
        return {
            "clarify": {
                "questions": ["죄송합니다. 좀 더 구체적으로 말씀해 주시겠어요?"]
            },
            "meta": {"clarify_error": str(e)}
        }

def _generate_clarify_questions(state: ChatState) -> list:
    """상황별 명확화 질문 생성"""
    
    # 검색 결과가 없는 경우
    if state.search.get("candidates") is not None and len(state.search.get("candidates", [])) == 0:
        return [
            "찾으시는 상품이 없는 것 같습니다. 다른 이름이나 카테고리로 검색해보시겠어요?",
            "예를 들어 '과일', '채소', '유기농' 등의 키워드를 사용해보세요."
        ]
    
    # 너무 많은 검색 결과가 있는 경우
    elif state.search.get("candidates") is not None and len(state.search.get("candidates", [])) > 10:
        return [
            "검색 결과가 많습니다. 좀 더 구체적으로 말씀해 주시겠어요?",
            "원산지, 가격대, 또는 브랜드를 추가로 알려주시면 더 정확한 결과를 찾아드릴 수 있어요."
        ]
    
    # CS 관련 모호한 문의
    elif "문의" in state.query or "도움" in state.query:
        return [
            "어떤 도움이 필요하신지 좀 더 자세히 말씀해 주시겠어요?",
            "주문, 배송, 상품 문의 등 구체적인 내용을 알려주세요."
        ]
    
    # 일반적인 모호한 입력
    else:
        return [
            "무엇을 도와드릴까요?",
            "상품 검색, 주문, 또는 고객 문의 중 어떤 것을 원하시나요?"
        ]