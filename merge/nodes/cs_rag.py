"""
cs_rag.py — E팀: CS & RAG

E팀의 책임:
- CS 티켓 접수 및 분류
- 이미지 첨부 시 비전+LLM으로 분석
- FAQ/정책 통합 RAG 검색 및 답변
- 신뢰도 기반 응답 게이팅
"""

import logging
import uuid
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

# 상대 경로로 graph_interfaces 임포트
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_interfaces import ChatState

logger = logging.getLogger("E_CS_RAG")

# OpenAI 클라이언트 설정
try:
    import openai
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        openai_client = openai.OpenAI(api_key=openai_api_key)
    else:
        openai_client = None
        logger.warning("OpenAI API key not found. Using mock responses.")
except ImportError:
    openai_client = None
    logger.warning("OpenAI package not available.")

# Mock FAQ 데이터
MOCK_FAQ_DATA = [
    {
        "id": "faq_001",
        "question": "배송은 얼마나 걸리나요?",
        "answer": "일반적으로 주문 후 1-2일 내 배송됩니다. 제주/도서산간 지역은 추가 1-2일이 소요될 수 있습니다.",
        "category": "배송",
        "keywords": ["배송", "시간", "기간", "언제"]
    },
    {
        "id": "faq_002", 
        "question": "환불은 어떻게 하나요?",
        "answer": "구매일로부터 7일 이내에 고객센터로 연락주시면 환불 처리가 가능합니다. 신선식품 특성상 개봉하지 않은 상품에 한합니다.",
        "category": "환불",
        "keywords": ["환불", "취소", "반품", "돈"]
    },
    {
        "id": "faq_003",
        "question": "유기농 인증은 어떻게 확인하나요?",
        "answer": "모든 유기농 상품은 국가 인증을 받은 제품으로, 상품 상세 페이지에서 인증서를 확인하실 수 있습니다.",
        "category": "상품",
        "keywords": ["유기농", "인증", "확인", "친환경"]
    }
]

def cs_intake(state: ChatState) -> Dict[str, Any]:
    """
    CS 접수(반품/교환/배송/품질 등)
    - 이미지(영수증/상품사진) 인입 시 비전+LLM으로 간단히 분류/요약합니다.
    - 티켓을 생성하고 카테고리를 지정합니다.
    """
    logger.info("CS 접수 프로세스 시작", extra={
        "user_id": state.user_id,
        "query": state.query,
        "attachments": len(state.attachments)
    })
    
    try:
        # 1. 문의 카테고리 분류
        category = _classify_cs_category(state.query, state.attachments)
        
        # 2. 이미지 분석 (있는 경우)
        image_analysis = None
        if state.attachments:
            image_analysis = _analyze_attachments(state.attachments)
        
        # 3. 문의 요약 생성
        summary = _generate_inquiry_summary(state.query, image_analysis)
        
        # 4. 티켓 생성
        ticket_id = _generate_ticket_id()
        ticket_info = {
            "ticket_id": ticket_id,
            "category": category,
            "summary": summary,
            "priority": _determine_priority(category),
            "created_at": datetime.now().isoformat(),
            "status": "open",
            "image_analysis": image_analysis
        }
        
        logger.info("CS 티켓 생성 완료", extra={
            "ticket_id": ticket_id,
            "category": category,
            "priority": ticket_info["priority"]
        })
        
        return {
            "cs": {"ticket": ticket_info},
            "meta": {
                "cs_message": f"문의가 접수되었습니다. 티켓번호: {ticket_id}",
                "next_step": "faq_search"
            }
        }
        
    except Exception as e:
        logger.error(f"CS 접수 실패: {e}")
        return {
            "cs": {
                "ticket": {
                    "ticket_id": "ERROR-" + str(uuid.uuid4())[:8],
                    "category": "일반문의",
                    "summary": "문의 접수 중 오류 발생",
                    "error": str(e)
                }
            }
        }

def _classify_cs_category(query: str, attachments: List[str]) -> str:
    """CS 문의 카테고리 분류"""
    
    query_lower = query.lower()
    
    # 키워드 기반 분류
    categories = {
        "배송": ["배송", "도착", "언제", "늦어", "안와", "느려", "빨리"],
        "환불": ["환불", "취소", "반품", "돌려", "돈", "계좌"],
        "상품문의": ["상품", "품질", "상태", "신선", "상함", "이상"],
        "주문변경": ["변경", "수정", "주소", "시간", "바꿔"],
        "결제": ["결제", "카드", "계좌", "승인", "실패", "오류"],
        "기타": []
    }
    
    for category, keywords in categories.items():
        if any(keyword in query_lower for keyword in keywords):
            return category
    
    # 첨부파일이 있으면 상품문의로 분류
    if attachments:
        return "상품문의"
    
    return "일반문의"

def _analyze_attachments(attachments: List[str]) -> Optional[Dict[str, Any]]:
    """첨부파일 분석 (비전+LLM)"""
    
    if not attachments or not openai_client:
        return None
    
    # 실제로는 이미지를 OpenAI Vision API로 분석해야 함
    # 여기서는 Mock 분석 결과 반환
    return {
        "image_count": len(attachments),
        "detected_items": ["상품 사진", "포장재"],
        "quality_issues": ["없음"],
        "confidence": 0.7
    }

def _generate_inquiry_summary(query: str, image_analysis: Optional[Dict[str, Any]]) -> str:
    """문의 내용 요약 생성"""
    
    summary = query[:100]  # 기본적으로 처음 100자
    
    if image_analysis:
        items = ", ".join(image_analysis.get("detected_items", []))
        summary += f" (첨부된 이미지: {items})"
    
    return summary

def _generate_ticket_id() -> str:
    """티켓 ID 생성"""
    timestamp = datetime.now().strftime("%Y%m%d")
    random_suffix = str(uuid.uuid4())[:6]
    return f"CS-{timestamp}-{random_suffix.upper()}"

def _determine_priority(category: str) -> str:
    """문의 우선순위 결정"""
    high_priority = ["환불", "배송사고", "상품불량"]
    if category in high_priority:
        return "high"
    return "normal"

def faq_policy_rag(state: ChatState) -> Dict[str, Any]:
    """
    FAQ & Policy RAG(통합)
    - FAQ/정책 말뭉치에서 근거 문서를 검색하여 인용과 함께 답변합니다.
    - 신뢰도가 낮으면 handoff로 분기합니다.
    """
    logger.info("FAQ RAG 검색 시작", extra={
        "user_id": state.user_id,
        "query": state.query
    })
    
    try:
        # 1. FAQ 검색
        faq_results = _search_faq(state.query)
        
        # 2. 최적 답변 선택
        best_answer = _select_best_answer(faq_results, state.query)
        
        # 3. 답변 신뢰도 계산
        confidence = _calculate_confidence(best_answer, state.query)
        
        # 4. 답변 생성
        if confidence > 0.3:
            answer_text = best_answer["answer"]
            citations = [f"faq:{best_answer['category']}#{best_answer['id']}"]
        else:
            answer_text = "죄송하지만 정확한 답변을 찾지 못했습니다. 상담사가 도와드리겠습니다."
            citations = []
        
        answer_info = {
            "text": answer_text,
            "citations": citations,
            "confidence": confidence,
            "searched_faqs": len(faq_results)
        }
        
        logger.info("FAQ RAG 검색 완료", extra={
            "confidence": confidence,
            "citations": len(citations)
        })
        
        return {
            "cs": {"answer": answer_info},
            "meta": {
                "rag_method": "faq_search",
                "should_handoff": confidence < 0.3
            }
        }
        
    except Exception as e:
        logger.error(f"FAQ RAG 실패: {e}")
        return {
            "cs": {
                "answer": {
                    "text": "시스템 오류로 답변을 생성할 수 없습니다.",
                    "citations": [],
                    "confidence": 0.0,
                    "error": str(e)
                }
            }
        }

def _search_faq(query: str) -> List[Dict[str, Any]]:
    """FAQ 검색"""
    
    query_lower = query.lower()
    matching_faqs = []
    
    for faq in MOCK_FAQ_DATA:
        score = 0.0
        
        # 키워드 매칭
        for keyword in faq["keywords"]:
            if keyword in query_lower:
                score += 1.0
        
        # 질문 텍스트 매칭
        if any(word in faq["question"].lower() for word in query_lower.split()):
            score += 0.5
        
        if score > 0:
            faq_copy = faq.copy()
            faq_copy["score"] = score
            matching_faqs.append(faq_copy)
    
    # 점수 순으로 정렬
    matching_faqs.sort(key=lambda x: x["score"], reverse=True)
    
    return matching_faqs

def _select_best_answer(faq_results: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
    """최적 답변 선택"""
    
    if not faq_results:
        return {
            "id": "no_result",
            "answer": "관련 정보를 찾을 수 없습니다.",
            "category": "none",
            "score": 0.0
        }
    
    # 가장 높은 점수의 FAQ 반환
    return faq_results[0]

def _calculate_confidence(answer: Dict[str, Any], query: str) -> float:
    """답변 신뢰도 계산"""
    
    base_score = answer.get("score", 0.0)
    
    if base_score >= 2.0:
        return 0.9  # 높은 신뢰도
    elif base_score >= 1.0:
        return 0.7  # 중간 신뢰도
    elif base_score > 0.0:
        return 0.4  # 낮은 신뢰도
    else:
        return 0.1  # 매우 낮은 신뢰도