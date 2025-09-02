"""
cs_module.py — CS(고객지원) 관련 기능 구현
팀 역할 E 담당: CS 접수, 이미지 분류, FAQ&Policy RAG

주요 구현 함수:
- cs_intake: CS 접수 및 이미지 분류
- faq_policy_rag: FAQ & Policy 통합 RAG 답변 생성
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import asdict
import base64
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from pinecone import Pinecone

# 환경변수 및 설정
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "qook")

logger = logging.getLogger("cs_module")

# CS 카테고리 상수
CS_CATEGORIES = {
    "배송지연": "delivery_delay",
    "배송오류": "delivery_error", 
    "상품불량": "product_defect",
    "반품요청": "return_request",
    "교환요청": "exchange_request",
    "환불요청": "refund_request",
    "품질문제": "quality_issue",
    "주문오류": "order_error",
    "결제문제": "payment_issue",
    "기타문의": "general_inquiry"
}

class CSModule:
    """CS 모듈 클래스"""
    
    def __init__(self):
        self.setup_logging()
        self.faq_index = None
        self.policy_index = None
        
        # OpenAI 클라이언트 초기화
        if OPENAI_API_KEY:
            self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
            logger.info("OpenAI 클라이언트 초기화 완료")
        else:
            self.openai_client = None
            logger.warning("OpenAI API 키가 설정되지 않았습니다. 시뮬레이션 모드로 동작합니다.")
        
        # Pinecone 클라이언트 초기화
        if PINECONE_API_KEY:
            self.pinecone_client = Pinecone(api_key=PINECONE_API_KEY)
            logger.info("Pinecone 클라이언트 초기화 완료")
        else:
            self.pinecone_client = None
            logger.warning("Pinecone API 키가 설정되지 않았습니다. 모의 데이터로 동작합니다.")
        
        self._load_rag_indices()
    
    def setup_logging(self):
        """로깅 설정"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def _load_rag_indices(self):
        """FAQ & Policy RAG 인덱스 로드 (Pinecone)"""
        try:
            logger.info("FAQ & Policy RAG 인덱스 로딩 중...")
            
            if self.pinecone_client:
                # Pinecone 인덱스 연결 (단일 인덱스 사용)
                try:
                    self.index = self.pinecone_client.Index(PINECONE_INDEX_NAME)
                    logger.info(f"Pinecone 인덱스 '{PINECONE_INDEX_NAME}' 연결 완료")
                except Exception as e:
                    logger.warning(f"Pinecone 인덱스 연결 실패: {e}")
                    self.index = None
            else:
                logger.info("Pinecone 클라이언트가 없어 모의 모드로 동작합니다")
                
        except Exception as e:
            logger.warning(f"RAG 인덱스 로드 실패: {e}")
            self.index = None
    
    def analyze_image_with_vision_llm(self, image_path: str) -> Dict[str, Any]:
        """
        비전+LLM으로 이미지 분석 및 분류 (멀티모달 기능 추가)
        
        환불/교환 관련 상품 이미지 분석:
        - 상품이 불량인지 판단
        - 고객이 말한 상품과 일치하는지 확인  
        - 신뢰도 점수 산출
        
        Args:
            image_path: 이미지 파일 경로
            
        Returns:
            분석 결과 딕셔너리
        """
        try:
            # 이미지 존재 확인
            if not os.path.exists(image_path):
                return {"error": "이미지 파일을 찾을 수 없습니다"}
            
            # 이미지를 base64로 인코딩
            with open(image_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # 멀티모달 비전 LLM 프롬프트 (환불/교환 중심)
            vision_prompt = """
            이 이미지를 분석하여 상품 상태 및 CS 문의 유형을 분류해주세요.
            
            주요 분석 항목:
            1. 상품 불량 여부 판단
            2. 상품 종류 식별 
            3. 품질 문제 유형 파악
            4. 환불/교환 가능성 평가
            
            분류 카테고리:
            - 배송지연: 배송 관련 문제
            - 배송오류: 잘못된 배송지나 상품 배송
            - 상품불량: 상품 품질이나 상태 문제 (곰팡이, 부패, 손상 등)
            - 반품요청: 상품 반품 요청
            - 교환요청: 상품 교환 요청  
            - 환불요청: 환불 관련 요청
            - 품질문제: 신선도나 품질 관련 문제
            - 주문오류: 주문 내용 오류 (다른 상품 배송)
            - 결제문제: 결제 관련 문제
            - 기타문의: 기타 문의사항
            
            JSON 형태로 응답해주세요:
            {
                "category": "카테고리명",
                "confidence": 0.0-1.0,
                "description": "이미지 설명",
                "issue_summary": "문제 요약",
                "is_defective": true/false,
                "detected_issue": "구체적 문제점",
                "matched_product": "인식된 상품명",
                "auto_resolvable": true/false
            }
            """
            
            # 실제 OpenAI Vision API 호출
            if self.openai_client:
                try:
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": vision_prompt
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{encoded_image}"
                                        }
                                    }
                                ]
                            }
                        ],
                        max_tokens=1000,
                        temperature=0.3
                    )
                    
                    # JSON 응답 파싱
                    result_text = response.choices[0].message.content.strip()
                    
                    # JSON 시작/종료 마커 제거
                    if result_text.startswith("```json"):
                        result_text = result_text[7:-3].strip()
                    elif result_text.startswith("```"):
                        result_text = result_text[3:-3].strip()
                    
                    try:
                        vision_result = json.loads(result_text)
                        logger.info(f"Vision API 분석 완료: {vision_result['category']}")
                        return vision_result
                    except json.JSONDecodeError as e:
                        logger.error(f"Vision API JSON 파싱 오류: {e}")
                        logger.error(f"Raw response: {result_text}")
                        # 폴백: 기본 결과 반환
                        return self._get_fallback_vision_result(image_path)
                    
                except Exception as e:
                    logger.error(f"OpenAI Vision API 호출 오류: {e}")
                    return self._get_fallback_vision_result(image_path)
            else:
                logger.warning("OpenAI API 키가 설정되지 않아 폴백 모드로 동작")
                return self._get_fallback_vision_result(image_path)
            
        except Exception as e:
            logger.error(f"이미지 분석 오류: {e}")
            return {"error": f"이미지 분석 중 오류 발생: {str(e)}"}
    
    def _get_fallback_vision_result(self, image_path: str) -> Dict[str, Any]:
        """폴백 비전 분석 결과 (파일명 기반)"""
        try:
            # 이미지 파일명 기반 모의 분석 (테스트용)
                filename = os.path.basename(image_path).lower()
                
                if "apple" in filename or "사과" in filename:
                    mock_result = {
                        "category": "상품불량",
                        "confidence": 0.92,
                        "description": "사과 상품 이미지 - 표면에 곰팡이 발생",
                        "issue_summary": "사과에 곰팡이가 발생하여 식용 불가 상태",
                        "is_defective": True,
                        "detected_issue": "곰팡이 발생",
                        "matched_product": "사과 1kg",
                        "auto_resolvable": True
                    }
                elif "damage" in filename or "손상" in filename:
                    mock_result = {
                        "category": "배송오류", 
                        "confidence": 0.88,
                        "description": "포장 손상된 상품 이미지",
                        "issue_summary": "배송 중 포장 손상으로 상품이 훼손됨",
                        "is_defective": True,
                        "detected_issue": "포장 손상",
                        "matched_product": "신선채소",
                        "auto_resolvable": True
                    }
                else:
                    # 기본 모의 결과
                    mock_result = {
                        "category": "상품불량",
                        "confidence": 0.75,
                        "description": "상품 포장 및 상태 이미지",
                        "issue_summary": "상품 상태 확인 필요",
                        "is_defective": False,
                        "detected_issue": "품질 검토 필요",
                        "matched_product": "미인식 상품",
                        "auto_resolvable": False
                    }
                
                return mock_result
        except Exception as e:
            logger.error(f"폴백 비전 분석 오류: {e}")
            return {
                "category": "기타문의",
                "confidence": 0.5,
                "description": "이미지 분석 실패",
                "issue_summary": "이미지 분석을 수행할 수 없습니다",
                "is_defective": False,
                "detected_issue": "분석 불가",
                "matched_product": "알 수 없음",
                "auto_resolvable": False
            }
            
            logger.info(f"멀티모달 이미지 분석 완료: {image_path}")
            return mock_result
            
        except Exception as e:
            logger.error(f"이미지 분석 실패: {e}")
            return {"error": f"이미지 분석 중 오류 발생: {str(e)}"}
    
    def generate_ticket_id(self) -> str:
        """티켓 ID 생성"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"T-{timestamp}-{unique_id}"
    
    def categorize_cs_issue(self, query: str, image_analysis: Optional[Dict] = None) -> Dict[str, Any]:
        """
        CS 문의 카테고리 분류 (실제 LLM 기반)
        
        Args:
            query: 사용자 문의 내용
            image_analysis: 이미지 분석 결과 (선택)
            
        Returns:
            분류 결과
        """
        try:
            # LLM 기반 카테고리 분류 프롬프트
            classification_prompt = f"""
다음 고객 문의를 분석하여 적절한 카테고리로 분류해주세요.

고객 문의: "{query}"

분류 카테고리:
1. 배송지연 - 배송이 늦어지거나 지연되는 문제
2. 배송오류 - 잘못된 배송지나 상품이 잘못 배송된 경우
3. 상품불량 - 상품에 품질 문제나 손상이 있는 경우
4. 반품요청 - 상품을 반품하고자 하는 요청
5. 교환요청 - 상품을 다른 것으로 교환하고자 하는 요청
6. 환불요청 - 결제 금액을 환불받고자 하는 요청
7. 품질문제 - 신선도나 상품 품질에 대한 문의
8. 주문오류 - 주문 과정에서 발생한 오류
9. 결제문제 - 결제 관련 문의나 오류
10. 기타문의 - 위 카테고리에 해당하지 않는 일반적인 문의

응답 형식 (JSON):
{{
    "category": "카테고리명",
    "confidence": 0.0-1.0,
    "reasoning": "분류 근거"
}}

다음과 같은 기준으로 신뢰도를 결정하세요:
- 0.9-1.0: 매우 명확한 키워드나 표현이 포함된 경우
- 0.7-0.89: 명확한 의도가 파악되는 경우
- 0.5-0.69: 어느 정도 추론 가능한 경우
- 0.3-0.49: 모호하거나 불분명한 경우
"""

            # 이미지 분석 결과가 있으면 추가 컨텍스트 제공
            if image_analysis:
                classification_prompt += f"""

추가 정보 - 이미지 분석 결과:
- 이미지 카테고리: {image_analysis.get('category', 'N/A')}
- 감지된 문제: {image_analysis.get('detected_issue', 'N/A')}
- 불량 여부: {image_analysis.get('is_defective', 'N/A')}
- 이미지 신뢰도: {image_analysis.get('confidence', 'N/A')}

텍스트와 이미지 분석을 종합하여 최종 분류를 결정하세요.
"""

            # 실제 OpenAI LLM 호출
            if self.openai_client:
                try:
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "user",
                                "content": classification_prompt
                            }
                        ],
                        max_tokens=500,
                        temperature=0.1
                    )
                    
                    # JSON 응답 파싱
                    result_text = response.choices[0].message.content.strip()
                    
                    # JSON 시작/종료 마커 제거
                    if result_text.startswith("```json"):
                        result_text = result_text[7:-3].strip()
                    elif result_text.startswith("```"):
                        result_text = result_text[3:-3].strip()
                    
                    try:
                        llm_result = json.loads(result_text)
                        logger.info(f"OpenAI LLM 분류 완료: {llm_result.get('category')}")
                    except json.JSONDecodeError as e:
                        logger.error(f"OpenAI LLM JSON 파싱 오류: {e}")
                        logger.error(f"Raw response: {result_text}")
                        # 폴백: 키워드 기반 분류 사용
                        llm_result = self._fallback_keyword_classification(query, image_analysis)
                    
                except Exception as e:
                    logger.error(f"OpenAI LLM API 호출 오류: {e}")
                    llm_result = self._fallback_keyword_classification(query, image_analysis)
            else:
                logger.warning("OpenAI API 키가 설정되지 않아 키워드 기반 분류로 동작")
                llm_result = self._fallback_keyword_classification(query, image_analysis)
            
            # 결과 검증 및 정리
            category = llm_result.get("category", "기타문의")
            confidence = llm_result.get("confidence", 0.7)
            reasoning = llm_result.get("reasoning", "LLM 분석 결과")
            
            # 카테고리 유효성 검사
            if category not in CS_CATEGORIES:
                category = "기타문의"
                confidence = 0.5
            
            logger.info(f"LLM 분류 결과: {category} (신뢰도: {confidence}) - {reasoning}")
            
            return {
                "category": category,
                "confidence": confidence,
                "category_code": CS_CATEGORIES.get(category, "general_inquiry"),
                "reasoning": reasoning
            }
            
        except Exception as e:
            logger.error(f"LLM 기반 카테고리 분류 실패: {e}")
            # 폴백으로 키워드 기반 분류
            return self._fallback_keyword_classification(query, image_analysis)
    
    
    def _fallback_keyword_classification(self, query: str, image_analysis: Optional[Dict] = None) -> Dict[str, Any]:
        """폴백용 키워드 기반 분류"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["배송", "늦", "지연"]):
            category = "배송지연"
            confidence = 0.7
        elif any(word in query_lower for word in ["불량", "상함", "썩"]):
            category = "상품불량"
            confidence = 0.75
        elif any(word in query_lower for word in ["반품", "돌려"]):
            category = "반품요청"
            confidence = 0.8
        elif any(word in query_lower for word in ["교환", "바꿔"]):
            category = "교환요청"
            confidence = 0.8
        elif any(word in query_lower for word in ["환불", "취소"]):
            category = "환불요청"
            confidence = 0.75
        else:
            category = "기타문의"
            confidence = 0.5
        
        return {
            "category": category,
            "confidence": confidence,
            "category_code": CS_CATEGORIES.get(category, "general_inquiry"),
            "reasoning": "폴백 키워드 분류"
        }
    
    def create_cs_ticket(self, query: str, category_info: Dict, image_analysis: Optional[Dict] = None) -> Dict[str, Any]:
        """
        CS 티켓 생성 (멀티모달 환불/교환 처리 지원)
        
        티켓 = 고객 문의 기록 카드
        - 챗봇이 즉시 답변 가능한 경우 → 티켓 필요 없음
        - 챗봇이 바로 처리할 수 없는 경우 → 티켓 생성 (기록하고 추적)
        """
        ticket_id = self.generate_ticket_id()
        
        # 이슈 요약 생성
        summary = query[:100] + "..." if len(query) > 100 else query
        if image_analysis and "issue_summary" in image_analysis:
            summary = image_analysis["issue_summary"]
        
        # 자동 해결 가능 여부 판단
        auto_resolvable = self._can_auto_resolve(category_info, image_analysis)
        requires_human = not auto_resolvable
        
        ticket = {
            "ticket_id": ticket_id,
            "category": category_info["category"],
            "category_code": category_info["category_code"],
            "summary": summary,
            "confidence": category_info["confidence"],
            "created_at": datetime.now().isoformat(),
            "status": "open",
            "priority": self._determine_priority(category_info["category"]),
            "has_image": image_analysis is not None,
            "auto_resolvable": auto_resolvable,
            "requires_human": requires_human,
            "message": query
        }
        
        # 멀티모달 정보 추가
        if image_analysis:
            ticket.update({
                "image_analysis": {
                    "is_defective": image_analysis.get("is_defective", False),
                    "detected_issue": image_analysis.get("detected_issue", ""),
                    "matched_product": image_analysis.get("matched_product", ""),
                    "vision_confidence": image_analysis.get("confidence", 0.0)
                }
            })
        
        logger.info(f"CS 티켓 생성: {ticket_id} - {category_info['category']} (자동해결: {auto_resolvable})")
        return ticket
        
    def _can_auto_resolve(self, category_info: Dict, image_analysis: Optional[Dict] = None) -> bool:
        """자동 해결 가능 여부 판단"""
        category = category_info["category"]
        confidence = category_info["confidence"]
        
        # 신뢰도가 너무 낮으면 수동 처리
        if confidence < 0.7:
            return False
        
        # 이미지 분석 결과가 있는 경우
        if image_analysis:
            # 상품이 명확히 불량이고 신뢰도가 높으면 자동 처리 가능
            if (image_analysis.get("is_defective", False) and 
                image_analysis.get("confidence", 0) > 0.85):
                return True
            
            # 자동 해결 가능 플래그 확인
            return image_analysis.get("auto_resolvable", False)
        
        # 텍스트 기반 판단
        auto_categories = ["배송지연", "품질문제", "반품요청", "교환요청", "환불요청"]
        return category in auto_categories and confidence > 0.8
    
    def _generate_auto_resolution(self, ticket: Dict, image_analysis: Optional[Dict] = None) -> Dict[str, Any]:
        """자동 해결 응답 생성"""
        category = ticket["category"]
        
        if image_analysis and image_analysis.get("is_defective", False):
            # 이미지 분석 결과 불량품인 경우
            resolution_text = f"""
상품 이미지 분석 결과, {image_analysis.get('detected_issue', '품질 문제')}가 확인되었습니다.
{image_analysis.get('matched_product', '해당 상품')}에 대해 즉시 교환 또는 환불 처리를 진행해드리겠습니다.

처리 방법:
1. 즉시 교환 - 새로운 상품을 당일 또는 익일 배송
2. 전액 환불 - 결제 수단으로 3-5 영업일 내 환불

고객님께서 원하시는 처리 방법을 선택해주시면 바로 진행해드리겠습니다.
            """.strip()
            
            return {
                "text": resolution_text,
                "confidence": 0.9,
                "resolution_type": "auto_refund_exchange",
                "options": ["즉시 교환", "전액 환불"],
                "estimated_resolution": "즉시"
            }
        
        elif category == "배송지연":
            resolution_text = """
배송 지연으로 인해 불편을 드려 죄송합니다. 
현재 배송 상황을 확인하여 예상 도착 시간을 안내해드리겠습니다.
또한 지연에 대한 보상으로 다음 주문 시 사용 가능한 할인 쿠폰을 제공해드립니다.
            """.strip()
            
            return {
                "text": resolution_text,
                "confidence": 0.8,
                "resolution_type": "delay_compensation",
                "compensation": "할인 쿠폰 제공",
                "estimated_resolution": "24시간 이내"
            }
        
        else:
            # 기본 자동 응답
            resolution_text = f"""
{category} 관련 문의를 접수했습니다. 
고객님의 불편사항을 신속히 해결하기 위해 담당 부서에서 우선 처리하겠습니다.
처리 결과는 24시간 이내에 연락드리겠습니다.
            """.strip()
            
            return {
                "text": resolution_text, 
                "confidence": 0.7,
                "resolution_type": "standard_processing",
                "estimated_resolution": "24시간 이내"
            }
    
    def _determine_priority(self, category: str) -> str:
        """카테고리별 우선순위 결정"""
        high_priority = ["상품불량", "품질문제", "배송오류"]
        medium_priority = ["배송지연", "반품요청", "교환요청", "환불요청"]
        
        if category in high_priority:
            return "high"
        elif category in medium_priority:
            return "medium"
        else:
            return "low"
    
    def search_faq_policy(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        FAQ & Policy 문서 검색 (Pinecone 기반)
        
        Args:
            query: 검색 질의
            k: 반환할 문서 수
            
        Returns:
            관련 문서 리스트
        """
        try:
            # Pinecone을 사용한 벡터 검색
            if self.index and self.openai_client:
                return self._search_with_pinecone(query, k)
            else:
                logger.warning("Pinecone 또는 OpenAI 클라이언트가 없어 모의 데이터 사용")
                return self._search_with_mock_data(query, k)
                
        except Exception as e:
            logger.error(f"FAQ/Policy 검색 실패: {e}")
            return self._search_with_mock_data(query, k)
    
    def _search_with_pinecone(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Pinecone을 사용한 벡터 검색"""
        try:
            # OpenAI로 쿼리 임베딩 생성
            query_embedding = self._get_query_embedding(query)
            
            # 단일 인덱스에서 검색 (FAQ와 Policy 구분은 메타데이터로)
            results = self.index.query(
                vector=query_embedding,
                top_k=k,
                include_metadata=True,
                filter={"type": {"$in": ["faq", "policy"]}}  # FAQ와 Policy 문서만 검색
            )
            
            search_results = []
            for match in results.matches:
                search_results.append({
                    "id": match.id,
                    "title": match.metadata.get("title", ""),
                    "content": match.metadata.get("content", ""),
                    "category": match.metadata.get("category", ""),
                    "score": float(match.score),
                    "source": match.metadata.get("type", "").upper()  # "faq" -> "FAQ", "policy" -> "POLICY"
                })
            
            logger.info(f"Pinecone에서 {len(search_results)}개 문서 검색 완료")
            return search_results
            
        except Exception as e:
            logger.error(f"Pinecone 벡터 검색 실패: {e}")
            return self._search_with_mock_data(query, k)
    
    def _get_query_embedding(self, query: str) -> List[float]:
        """OpenAI를 사용해 쿼리 임베딩 생성"""
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=query
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"쿼리 임베딩 생성 실패: {e}")
            raise e
    
    def _search_with_mock_data(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """모의 데이터를 사용한 검색 (폴백용)"""
        # 기존 모의 FAQ 데이터
        mock_docs = [
            {
                "id": "faq_delivery_001",
                "title": "배송 지연 안내",
                "content": "배송이 지연되는 경우 고객님께 별도 연락드리며, 평균 1-2일 추가 소요됩니다.",
                "category": "배송",
                "score": 0.85,
                "source": "FAQ"
            },
            {
                "id": "policy_return_001", 
                "title": "반품 정책",
                "content": "신선식품 특성상 수령 후 24시간 이내에만 반품이 가능합니다.",
                "category": "반품",
                "score": 0.82,
                "source": "Policy"
            },
            {
                "id": "faq_quality_001",
                "title": "상품 품질 문제 대응",
                "content": "상품에 품질 문제가 있는 경우 사진과 함께 문의해주시면 즉시 교환/환불 처리해드립니다.",
                "category": "품질",
                "score": 0.78,
                "source": "FAQ"
            }
        ]
        
        # 간단한 키워드 매칭으로 관련도 점수 조정
        query_lower = query.lower()
        for doc in mock_docs:
            content_lower = doc["content"].lower()
            title_lower = doc["title"].lower()
            
            # 키워드 매칭 점수 조정
            keyword_score = 0
            for word in query_lower.split():
                if word in content_lower or word in title_lower:
                    keyword_score += 0.1
            
            doc["score"] = min(doc["score"] + keyword_score, 1.0)
        
        # 점수 순으로 정렬 후 상위 k개 반환
        sorted_docs = sorted(mock_docs, key=lambda x: x["score"], reverse=True)
        return sorted_docs[:k]
    
    def generate_rag_answer(self, query: str, retrieved_docs: List[Dict]) -> Dict[str, Any]:
        """
        검색된 문서들을 기반으로 RAG 답변 생성
        
        Args:
            query: 원본 질의
            retrieved_docs: 검색된 문서들
            
        Returns:
            생성된 답변과 메타데이터
        """
        try:
            if not retrieved_docs:
                return {
                    "text": "죄송합니다. 관련 정보를 찾을 수 없습니다. 상담사 연결을 도와드리겠습니다.",
                    "citations": [],
                    "confidence": 0.1
                }
            
            # 인용 정보 생성
            citations = []
            context_texts = []
            
            for doc in retrieved_docs:
                citations.append(f"{doc['source']}:{doc['category']}#{doc['id']}")
                context_texts.append(doc['content'])
            
            # 실제 OpenAI API를 사용한 RAG 답변 생성
            context = "\n\n".join(context_texts)
            
            if self.openai_client:
                try:
                    rag_prompt = f"""
다음 문서들을 참고하여 고객 질마에 대해 친절하고 정확한 답변을 생성해주세요.

고객 질문: {query}

참고 문서:
{context}

답변 가이드라인:
1. 친과한 차 사용 (고객님을 처람 외에)
2. 참고 문서에 기반한 정확한 정보 제공
3. 구체적이고 실용적인 사버 제공
4. 추가 도움 여부 안내
5. 200자 이내로 간결하게 작성

답변:"""
                    
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "user",
                                "content": rag_prompt
                            }
                        ],
                        max_tokens=400,
                        temperature=0.3
                    )
                    
                    answer_text = response.choices[0].message.content.strip()
                    
                    # 신뢰도 계산 (간단한 휴리스틱)
                    confidence = min(0.9, 0.6 + len(retrieved_docs) * 0.1)
                    if len(answer_text) > 50 and "죄송합니다" not in answer_text:
                        confidence = min(confidence + 0.1, 0.95)
                    
                    logger.info(f"OpenAI RAG 답변 생성 완료 (confidence: {confidence})")
                    
                except Exception as e:
                    logger.error(f"OpenAI RAG API 호출 오류: {e}")
                    # 폴백: 시뮬레이션 답변 사용
                    return self._get_fallback_rag_answer(query, retrieved_docs)
            else:
                logger.warning("OpenAI API 키가 설정되지 않아 폴백 RAG 모드로 동작")
                return self._get_fallback_rag_answer(query, retrieved_docs)
            
            return {
                "text": answer_text,
                "citations": citations[:3],  # 최대 3개 인용
                "confidence": confidence,
                "retrieved_docs_count": len(retrieved_docs)
            }
            
        except Exception as e:
            logger.error(f"RAG 답변 생성 실패: {e}")
            return {
                "text": "답변 생성 중 오류가 발생했습니다. 상담사 연결을 도와드리겠습니다.",
                "citations": [],
                "confidence": 0.1
            }
    
    def _get_fallback_rag_answer(self, query: str, retrieved_docs: List[Dict]) -> Dict[str, Any]:
        """OpenAI API 실패 시 사용할 폴백 RAG 답변"""
        try:
            citations = []
            for doc in retrieved_docs:
                citations.append(f"{doc['source']}:{doc['category']}#{doc['id']}")
            
            # 키워드 기반 간단한 답변 생성
            if "배송" in query.lower():
                answer_text = "배송 관련 문의주셔서 감사합니다. 배송이 지연되는 경우 고객님께 별도 연락드리며, 평균 1-2일 추가 소요됩니다. 추가 문의사항이 있으시면 언제든 연락주세요."
                confidence = 0.75
            elif any(word in query.lower() for word in ["반품", "교환", "환불"]):
                answer_text = "반품/교환/환불 문의주셔서 감사합니다. 신선식품 특성상 수령 후 24시간 이내에만 반품이 가능하며, 상품에 품질 문제가 있는 경우 사진과 함께 문의해주시면 즉시 처리해드립니다."
                confidence = 0.72
            elif "불량" in query.lower() or "상함" in query.lower():
                answer_text = "상품 품질에 불만이 있으시군요. 신선식품은 품질에 특별히 신경쓰고 있습니다. 상품 상태를 확인할 수 있는 사진과 함께 문의해주시면 즉시 교환 또는 환불 처리해드리겠습니다."
                confidence = 0.78
            else:
                answer_text = "문의해주신 내용을 확인했습니다. 구체적인 해결 방안을 위해 추가 정보가 필요할 수 있습니다. 언제든 편하게 문의해주세요."
                confidence = 0.65
            
            return {
                "text": answer_text,
                "citations": citations[:3],
                "confidence": confidence,
                "retrieved_docs_count": len(retrieved_docs)
            }
            
        except Exception as e:
            logger.error(f"폴백 RAG 답변 생성 실패: {e}")
            return {
                "text": "시스템 오류가 발생했습니다. 전문 상담사와 연결해드리겠습니다.",
                "citations": [],
                "confidence": 0.1
            }
    
    def generate_contextual_rag_answer(self, query: str, retrieved_docs: List[Dict], context_info: Dict) -> Dict[str, Any]:
        """
        컨텍스트를 고려한 향상된 RAG 답변 생성
        
        Args:
            query: 원본 질의
            retrieved_docs: 검색된 문서들
            context_info: 컨텍스트 정보 (티켓 여부, 카테고리 등)
            
        Returns:
            생성된 답변과 메타데이터 (향상된 버전)
        """
        try:
            if not retrieved_docs:
                return self._generate_no_result_response(context_info)
            
            # 인용 정보 생성
            citations = []
            context_texts = []
            
            for doc in retrieved_docs:
                citations.append(f"{doc['source']}:{doc['category']}#{doc['id']}")
                context_texts.append(doc['content'])
            
            # 컨텍스트 기반 답변 생성
            if context_info.get("has_ticket", False):
                return self._generate_ticket_based_answer(query, retrieved_docs, context_info)
            elif context_info.get("follow_up_query", False):
                return self._generate_followup_answer(query, retrieved_docs, context_info)
            else:
                return self._generate_standard_answer(query, retrieved_docs)
                
        except Exception as e:
            logger.error(f"컨텍스트 RAG 답변 생성 실패: {e}")
            return {
                "text": "답변 생성 중 오류가 발생했습니다. 전문 상담사와 연결해드리겠습니다.",
                "citations": [],
                "confidence": 0.1
            }
    
    def _generate_no_result_response(self, context_info: Dict) -> Dict[str, Any]:
        """검색 결과 없을 때 응답 생성"""
        if context_info.get("has_ticket", False):
            text = f"고객님의 문의사항({context_info.get('category', '문의')})에 대해 관련 정보를 찾을 수 없습니다. 전문 상담사가 직접 도움을 드리겠습니다."
        else:
            text = "죄송합니다. 관련 정보를 찾을 수 없습니다. 전문 상담사와 연결해드리겠습니다."
            
        return {
            "text": text,
            "citations": [],
            "confidence": 0.1
        }
    
    def _generate_ticket_based_answer(self, query: str, retrieved_docs: List[Dict], context_info: Dict) -> Dict[str, Any]:
        """티켓 기반 맞춤형 답변 생성"""
        category = context_info.get("category", "")
        priority = context_info.get("priority", "medium")
        has_image = context_info.get("has_image", False)
        
        # 카테고리별 특화 답변
        if "배송" in category:
            answer_text = f"""
배송 관련 문의를 확인했습니다. 

{retrieved_docs[0]['content'] if retrieved_docs else '일반적으로 배송은 주문 후 1-2일 소요됩니다.'}

현재 상황:
- 우선순위: {priority}
- 이미지 첨부: {'있음' if has_image else '없음'}

추가 조치가 필요한 경우 즉시 처리하겠습니다.
            """.strip()
            confidence = 0.8
            
        elif any(word in category for word in ["반품", "교환", "환불"]):
            answer_text = f"""
{category} 요청을 접수했습니다.

정책 안내:
{retrieved_docs[0]['content'] if retrieved_docs else '신선식품 특성상 수령 후 24시간 이내에 처리 가능합니다.'}

처리 절차:
1. 상품 상태 확인 {'(첨부 이미지 검토 중)' if has_image else ''}
2. 반품/교환 승인 처리
3. 수거 및 재배송/환불 진행

신속하게 처리해드리겠습니다.
            """.strip()
            confidence = 0.85
            
        else:
            # 기본 티켓 기반 답변
            answer_text = f"""
{category} 문의를 접수했습니다.

관련 정보:
{retrieved_docs[0]['content'] if retrieved_docs else '담당 부서에서 확인 중입니다.'}

티켓번호: {context_info.get('ticket_id', 'N/A')}
처리상태: 접수 완료

24시간 이내에 처리 결과를 연락드리겠습니다.
            """.strip()
            confidence = 0.75
        
        citations = [f"{doc['source']}:{doc['category']}#{doc['id']}" for doc in retrieved_docs[:3]]
        
        return {
            "text": answer_text,
            "citations": citations,
            "confidence": confidence,
            "response_type": "ticket_based",
            "category": category
        }
    
    def _generate_followup_answer(self, query: str, retrieved_docs: List[Dict], context_info: Dict) -> Dict[str, Any]:
        """후속 질의에 대한 답변 생성"""
        answer_text = f"""
추가 문의사항에 대해 답변드리겠습니다.

{retrieved_docs[0]['content'] if retrieved_docs else '관련 정보를 확인 중입니다.'}

이미 진행 중인 처리와 함께 추가 사항도 검토하겠습니다.
궁금한 점이 더 있으시면 언제든 말씀해주세요.
        """.strip()
        
        citations = [f"{doc['source']}:{doc['category']}#{doc['id']}" for doc in retrieved_docs[:3]]
        
        return {
            "text": answer_text,
            "citations": citations,
            "confidence": 0.7,
            "response_type": "followup"
        }
    
    def _generate_standard_answer(self, query: str, retrieved_docs: List[Dict]) -> Dict[str, Any]:
        """표준 FAQ 답변 생성"""
        return self.generate_rag_answer(query, retrieved_docs)  # 기존 함수 재사용
    
    def _determine_next_action(self, confidence: float, context_info: Dict) -> str:
        """다음 액션 결정"""
        if confidence < 0.3:
            return "handoff"
        elif confidence < 0.6 and context_info.get("priority") == "high":
            return "handoff"  # 높은 우선순위는 낮은 신뢰도에서도 handoff
        elif context_info.get("auto_resolvable", False) and confidence > 0.7:
            return "auto_resolve"
        else:
            return "complete"


# 전역 CS 모듈 인스턴스
cs_module = CSModule()


def cs_intake(state) -> Dict[str, Any]:
    """
    CS 접수 (멀티모달 환불/교환 처리 지원)
    
    통합 플로우:
    1. 사용자 입력(텍스트+이미지)
    2. cs_intake (환불/교환 분류) 
    3. analyze_product_image (멀티모달 분석)
    4. 조건 분기:
       - 신뢰도 높음 → 챗봇이 자동 환불/교환 처리
       - 신뢰도 낮음 → 티켓 생성 → 상담원에게 전달
    """
    try:
        logger.info("CS 접수 처리 시작 (멀티모달)")
        
        query = state.query
        attachments = getattr(state, 'attachments', [])
        
        # 이미지 분석 (첨부파일이 있는 경우)
        image_analysis = None
        if attachments:
            # 첫 번째 첨부파일을 이미지로 가정
            image_path = attachments[0]
            image_analysis = cs_module.analyze_image_with_vision_llm(image_path)
            logger.info(f"멀티모달 이미지 분석 결과: {image_analysis.get('category', 'N/A')}")
        
        # CS 이슈 카테고리 분류
        category_info = cs_module.categorize_cs_issue(query, image_analysis)
        
        # CS 티켓 생성
        ticket = cs_module.create_cs_ticket(query, category_info, image_analysis)
        
        # 자동 처리 가능 여부에 따른 분기
        if ticket.get("auto_resolvable", False):
            logger.info(f"자동 처리 가능한 티켓: {ticket['ticket_id']}")
            # 자동 해결 응답 생성
            auto_response = cs_module._generate_auto_resolution(ticket, image_analysis)
            
            return {
                "cs": {
                    "ticket": ticket,
                    "image_analysis": image_analysis,
                    "auto_response": auto_response,
                    "next_action": "auto_resolve"  # 자동 해결
                }
            }
        else:
            logger.info(f"수동 처리 필요한 티켓: {ticket['ticket_id']}")
            return {
                "cs": {
                    "ticket": ticket,
                    "image_analysis": image_analysis,
                    "next_action": "manual_review"  # 수동 검토 필요
                }
            }
        
    except Exception as e:
        logger.error(f"CS 접수 처리 실패: {e}")
        return {
            "cs": {
                "ticket": {
                    "ticket_id": cs_module.generate_ticket_id(),
                    "category": "기타문의",
                    "category_code": "general_inquiry", 
                    "summary": "시스템 오류로 인한 자동 생성 티켓",
                    "confidence": 0.1,
                    "created_at": datetime.now().isoformat(),
                    "status": "open",
                    "priority": "medium",
                    "has_image": False,
                    "auto_resolvable": False,
                    "requires_human": True
                },
                "error": str(e),
                "next_action": "handoff"
            }
        }


def faq_policy_rag(state) -> Dict[str, Any]:
    """
    FAQ & Policy RAG(통합) - 향상된 버전
    - FAQ/정책 말뭉치에서 근거 문서를 검색하여 인용과 함께 답변
    - 신뢰도가 낮으면 handoff로 분기 유도
    - CS 티켓 상황에 맞는 맞춤형 답변 생성
    """
    try:
        logger.info("FAQ & Policy RAG 처리 시작 (향상된 버전)")
        
        # 질의 추출 및 컨텍스트 파악
        query = ""
        context_info = {}
        
        if hasattr(state, 'cs') and state.cs:
            cs_data = state.cs
            
            # CS 티켓이 있는 경우
            if 'ticket' in cs_data:
                ticket = cs_data['ticket']
                query = f"{ticket['category']} {ticket['summary']}"
                context_info = {
                    "has_ticket": True,
                    "ticket_id": ticket.get('ticket_id', ''),
                    "category": ticket.get('category', ''),
                    "priority": ticket.get('priority', 'medium'),
                    "auto_resolvable": ticket.get('auto_resolvable', False),
                    "has_image": ticket.get('has_image', False)
                }
                logger.info(f"CS 티켓 기반 질의: {query}")
            
            # 자동 해결 응답이 이미 있는 경우 (자동 처리 후 추가 질의)
            elif 'auto_response' in cs_data:
                query = state.query  # 사용자 후속 질의
                context_info = {
                    "has_auto_response": True,
                    "follow_up_query": True
                }
                logger.info(f"자동 해결 후 후속 질의: {query}")
        else:
            # 직접 CS 질의인 경우
            query = state.query
            context_info = {"direct_cs_query": True}
            logger.info(f"직접 CS 질의: {query}")
        
        # FAQ & Policy 문서 검색 (강화된 검색)
        retrieved_docs = cs_module.search_faq_policy(query, k=5)
        logger.info(f"검색된 문서 수: {len(retrieved_docs)}")
        
        # 컨텍스트를 고려한 RAG 답변 생성
        answer_result = cs_module.generate_contextual_rag_answer(query, retrieved_docs, context_info)
        
        # 신뢰도 확인 및 분기 힌트
        confidence = answer_result["confidence"]
        next_action = cs_module._determine_next_action(confidence, context_info)
        
        # 신뢰도별 후처리
        if confidence < 0.3:
            logger.info("낮은 신뢰도로 인한 handoff 권장")
            answer_result["text"] += "\n\n정확한 답변을 위해 전문 상담사와 연결해드리겠습니다."
        elif confidence < 0.6:
            answer_result["text"] += "\n\n추가로 궁금한 사항이 있으시면 언제든 말씀해주세요."
        elif confidence >= 0.8:
            answer_result["text"] += "\n\n문제가 해결되셨나요? 추가 도움이 필요하시면 말씀해주세요."
        
        logger.info(f"향상된 RAG 답변 생성 완료 (신뢰도: {confidence})")
        
        return {
            "cs": {
                "answer": answer_result,
                "next_action": next_action,
                "context_info": context_info
            }
        }
        
    except Exception as e:
        logger.error(f"FAQ & Policy RAG 처리 실패: {e}")
        return {
            "cs": {
                "answer": {
                    "text": "죄송합니다. 시스템 오류로 인해 답변을 생성할 수 없습니다. 전문 상담사와 연결해드리겠습니다.",
                    "citations": [],
                    "confidence": 0.1
                },
                "next_action": "handoff",
                "error": str(e)
            }
        }


# 개발/테스트용 함수들
def test_cs_module():
    """CS 모듈 테스트 함수"""
    print("=== CS 모듈 테스트 시작 ===")
    
    # 모의 상태 객체 생성
    from graph_interfaces import ChatState
    
    # 테스트 1: 일반적인 CS 문의
    test_state = ChatState()
    test_state.query = "배송이 너무 늦어요. 언제 받을 수 있나요?"
    
    print("\n1. 일반 CS 문의 테스트:")
    result1 = cs_intake(test_state)
    print(f"티켓 ID: {result1['cs']['ticket']['ticket_id']}")
    print(f"카테고리: {result1['cs']['ticket']['category']}")
    print(f"요약: {result1['cs']['ticket']['summary']}")
    
    # 테스트 2: FAQ RAG
    print("\n2. FAQ RAG 테스트:")
    result2 = faq_policy_rag(test_state)
    print(f"답변: {result2['cs']['answer']['text']}")
    print(f"신뢰도: {result2['cs']['answer']['confidence']}")
    print(f"인용: {result2['cs']['answer']['citations']}")
    
    print("\n=== CS 모듈 테스트 완료 ===")


if __name__ == "__main__":
    test_cs_module()