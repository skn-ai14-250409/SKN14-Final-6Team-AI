"""
쿼리 보강 모듈 (B 역할)
- 사용자 쿼리를 작업 지향 문장으로 재작성
- 슬롯 추출 (수량, 카테고리, 예산, 배송창, 식이제한 등)  
- 키워드 확장 (BM25 검색 친화적)
- PII/민감정보 마스킹
"""

import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from graph_interfaces import ChatState

# 로거 설정
logger = logging.getLogger("query_enhancer")

@dataclass
class SlotExtractionResult:
    """슬롯 추출 결과"""
    quantity: Optional[float] = None  # 사용자가 입력한 원본 수량
    quantity_standard: Optional[float] = None  # 표준 단위로 변환된 수량 (동치 비교용)
    unit_original: Optional[str] = None  # 사용자가 입력한 원본 단위 (예: "팩")
    unit_standard: Optional[str] = None  # 표준화된 단위 (예: "ea") 
    unit_category: Optional[str] = None  # 단위 카테고리 (예: "count")
    category: Optional[str] = None
    price_cap: Optional[int] = None
    delivery_window: Optional[str] = None
    dietary_restrictions: List[str] = None
    allergens: List[str] = None
    origin: Optional[str] = None
    freshness_level: Optional[str] = None
    
    def __post_init__(self):
        if self.dietary_restrictions is None:
            self.dietary_restrictions = []
        if self.allergens is None:
            self.allergens = []

class QueryEnhancer:
    """쿼리 보강 처리 클래스"""
    
    def __init__(self):
        self.pii_patterns = self._init_pii_patterns()
        self.category_mapping = self._init_category_mapping()
        self.unit_normalizer = self._init_unit_normalizer()
        
    def _init_pii_patterns(self) -> List[tuple]:
        """PII 패턴 정의"""
        return [
            # 주문번호 패턴
            (r'QK-\d{4}-\d{6}', '[주문번호]'),
            (r'주문번호[\s]*:?[\s]*([A-Z0-9-]{10,})', '[주문번호]'),
            
            # 전화번호 패턴
            (r'01[0-9]-\d{3,4}-\d{4}', '[전화번호]'),
            (r'(\d{2,3}-\d{3,4}-\d{4})', '[전화번호]'),
            
            # 이메일 패턴
            (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[이메일]'),
            
            # 신용카드 번호 (4자리씩 구분)
            (r'\d{4}-\d{4}-\d{4}-\d{4}', '[카드번호]'),
            (r'\d{16}', '[카드번호]'),
        ]
    
    def _init_category_mapping(self) -> Dict[str, List[str]]:
        """카테고리 키워드 매핑"""
        return {
            "채소": ["상추", "양배추", "배추", "시금치", "케일", "브로콜리", "당근", "무", "감자", "고구마", "양파", "마늘", "대파", "쪽파"],
            "과일": ["사과", "배", "포도", "오렌지", "바나나", "딸기", "블루베리", "키위", "망고", "파인애플", "체리", "복숭아"],
            "육류": ["소고기", "돼지고기", "닭고기", "양고기", "삼겹살", "등심", "안심", "갈비", "목살"],
            "해산물": ["연어", "참치", "고등어", "새우", "오징어", "문어", "조개", "홍합", "굴", "게"],
            "유제품": ["우유", "요거트", "치즈", "버터", "크림", "아이스크림"],
            "곡물": ["쌀", "현미", "귀리", "퀴노아", "보리", "밀", "파스타", "국수"],
            "조미료": ["소금", "설탕", "후추", "간장", "된장", "고추장", "식초", "참기름", "올리브오일"],
            "음료": ["물", "차", "커피", "주스", "탄산수", "맥주", "와인"]
        }
    
    def _init_unit_normalizer(self) -> Dict[str, Dict[str, str]]:
        """단위 정규화 매핑 (원본 + 표준화 + 동치 변환)"""
        return {
            # 중량 단위 (kg 기준으로 표준화)
            "킬로": {"original": "킬로", "standard": "kg", "category": "weight", "to_standard": 1.0},
            "키로": {"original": "키로", "standard": "kg", "category": "weight", "to_standard": 1.0}, 
            "kg": {"original": "kg", "standard": "kg", "category": "weight", "to_standard": 1.0},
            "그램": {"original": "그램", "standard": "kg", "category": "weight", "to_standard": 0.001},  # 1g = 0.001kg
            "g": {"original": "g", "standard": "kg", "category": "weight", "to_standard": 0.001},
            
            # 부피 단위 (L 기준으로 표준화)
            "리터": {"original": "리터", "standard": "L", "category": "volume", "to_standard": 1.0},
            "l": {"original": "l", "standard": "L", "category": "volume", "to_standard": 1.0},
            "L": {"original": "L", "standard": "L", "category": "volume", "to_standard": 1.0},
            "ml": {"original": "ml", "standard": "L", "category": "volume", "to_standard": 0.001},  # 1ml = 0.001L
            "mL": {"original": "mL", "standard": "L", "category": "volume", "to_standard": 0.001},
            "ML": {"original": "ML", "standard": "L", "category": "volume", "to_standard": 0.001},
            "밀리리터": {"original": "밀리리터", "standard": "L", "category": "volume", "to_standard": 0.001},
            
            # 개수 단위 (의미 보존 + ea 표준화, 변환 없음)
            "개": {"original": "개", "standard": "ea", "category": "count", "to_standard": 1.0},
            "마리": {"original": "마리", "standard": "ea", "category": "count", "to_standard": 1.0},
            "팩": {"original": "팩", "standard": "ea", "category": "count", "to_standard": 1.0},
            "봉": {"original": "봉", "standard": "ea", "category": "count", "to_standard": 1.0},
            "병": {"original": "병", "standard": "ea", "category": "count", "to_standard": 1.0},
            "캔": {"original": "캔", "standard": "ea", "category": "count", "to_standard": 1.0},
            "상자": {"original": "상자", "standard": "ea", "category": "count", "to_standard": 1.0},
        }

    def enhance_query(self, state: ChatState) -> Dict[str, Any]:
        """메인 쿼리 보강 함수"""
        logger.info(f"쿼리 보강 시작: {state.query}")
        
        # 1. PII 마스킹
        masked_query = self._mask_pii(state.query)
        
        # 2. 쿼리 재작성
        rewrite_result = self._rewrite_query(masked_query)
        
        # 3. 슬롯 추출
        slots_result = self._extract_slots(masked_query)
        
        # 4. 키워드 생성
        keywords = self._generate_keywords(rewrite_result, slots_result)
        
        # 결과 반환
        result = {
            "rewrite": {
                "text": rewrite_result,
                "keywords": keywords,
                "original": state.query,
                "masked": masked_query
            },
            "slots": self._slots_to_dict(slots_result)
        }
        
        logger.info(f"쿼리 보강 완료: {result}")
        return result
    
    def _mask_pii(self, query: str) -> str:
        """PII/민감정보 마스킹"""
        masked_query = query
        
        for pattern, replacement in self.pii_patterns:
            masked_query = re.sub(pattern, replacement, masked_query, flags=re.IGNORECASE)
        
        return masked_query
    
    def _rewrite_query(self, query: str) -> str:
        """쿼리를 작업 지향적으로 재작성"""
        # 간단한 규칙 기반 재작성 (실제로는 LLM 호출)
        rewritten = query.strip()
        
        # 질문형 → 요청형 변환
        question_patterns = [
            (r'(.+)\s*있[나나요어요][\?\s]*$', r'\1 찾아줘'),
            (r'(.+)\s*어[떠디][\?\s]*$', r'\1 추천해줘'),
            (r'(.+)\s*얼마[\?\s]*$', r'\1 가격 알려줘'),
            (r'(.+)\s*어[떠디서느][\?\s]*$', r'\1 주문하고 싶어'),
        ]
        
        for pattern, replacement in question_patterns:
            rewritten = re.sub(pattern, replacement, rewritten, flags=re.IGNORECASE)
        
        # 생략된 주어/목적어 보완
        if not any(word in rewritten for word in ['주문', '구매', '찾', '검색', '추천']):
            if any(category_word in rewritten for category_list in self.category_mapping.values() for category_word in category_list):
                rewritten = rewritten + " 주문하고 싶어"
        
        return rewritten
    
    def _extract_slots(self, query: str) -> SlotExtractionResult:
        """슬롯 정보 추출"""
        slots = SlotExtractionResult()
        
        # 수량 추출 (소수점 지원 + 단위 정규화 + 동치 변환)
        quantity_patterns = [
            # 소수점 패턴: 0.5kg, 1.8L, 2.5개, 500ml 등
            r'(\d*\.?\d+)\s*(개|마리|팩|봉|kg|g|L|킬로|키로|그램|리터|ml|mL|ML|밀리리터|병|캔|상자)',
        ]
        for pattern in quantity_patterns:
            match = re.search(pattern, query)
            if match:
                # 문자열을 float로 변환 (소수점 지원)
                quantity_str = match.group(1)
                try:
                    original_quantity = float(quantity_str)
                    # 정수인 경우 .0 제거 (예: 2.0 -> 2)
                    if original_quantity.is_integer():
                        slots.quantity = int(original_quantity)
                    else:
                        slots.quantity = original_quantity
                except ValueError:
                    # 변환 실패 시 건너뛰기
                    continue
                    
                original_unit = match.group(2)
                
                # 단위 정규화 및 동치 변환 적용
                unit_info = self.unit_normalizer.get(original_unit)
                if unit_info:
                    slots.unit_original = unit_info['original']
                    slots.unit_standard = unit_info['standard'] 
                    slots.unit_category = unit_info['category']
                    
                    # 동치 변환 (500g -> 0.5kg, 1500ml -> 1.5L)
                    conversion_factor = unit_info['to_standard']
                    converted_quantity = original_quantity * conversion_factor
                    
                    # 변환된 수량도 정수 처리
                    if converted_quantity.is_integer():
                        slots.quantity_standard = int(converted_quantity)
                    else:
                        slots.quantity_standard = round(converted_quantity, 3)  # 소수점 3자리까지
                        
                else:
                    # 정의되지 않은 단위는 원본 그대로
                    slots.unit_original = original_unit
                    slots.unit_standard = original_unit
                    slots.unit_category = 'unknown'
                    slots.quantity_standard = slots.quantity
                break
        
        # 카테고리 추출
        for category, keywords in self.category_mapping.items():
            if any(keyword in query for keyword in keywords):
                slots.category = category
                break
        
        # 가격 추출
        price_patterns = [
            r'(\d+)만원\s*이하',
            r'(\d+)천원\s*이하', 
            r'(\d+)원\s*이하',
            r'예산\s*(\d+)',
        ]
        for pattern in price_patterns:
            match = re.search(pattern, query)
            if match:
                price = int(match.group(1))
                if '만원' in pattern:
                    price *= 10000
                elif '천원' in pattern:
                    price *= 1000
                slots.price_cap = price
                break
        
        # 배송창 추출
        delivery_patterns = [
            r'(오늘|내일|모레)',
            r'(아침|오전|점심|오후|저녁)',
            r'(\d+)일\s*안',
        ]
        for pattern in delivery_patterns:
            match = re.search(pattern, query)
            if match:
                slots.delivery_window = match.group(1)
                break
        
        # 식이제한/알러지 추출
        dietary_keywords = ['비건', '베지테리안', '글루텐프리', '무설탕', '저염', '할랄']
        allergen_keywords = ['견과류', '우유', '계란', '대두', '밀', '새우', '게']
        
        slots.dietary_restrictions = [kw for kw in dietary_keywords if kw in query]
        slots.allergens = [kw for kw in allergen_keywords if kw in query]
        
        # 원산지 추출
        origin_patterns = [r'(국산|수입산|미국산|호주산|유럽산|일본산)']
        origin_match = re.search('|'.join(origin_patterns), query)
        if origin_match:
            slots.origin = origin_match.group(1)
        
        # 신선도 추출
        freshness_keywords = ['신선한', '유기농', '친환경', '무농약', '저농약']
        for keyword in freshness_keywords:
            if keyword in query:
                slots.freshness_level = keyword
                break
        
        return slots
    
    def _generate_keywords(self, rewritten_query: str, slots: SlotExtractionResult) -> List[str]:
        """BM25 검색용 키워드 생성"""
        keywords = []
        
        # 재작성된 쿼리에서 명사 추출 (간단한 형태소 분석 대신 규칙 기반)
        # 실제로는 KoNLPy 등을 사용하는 것이 좋음
        base_words = re.findall(r'[가-힣]{2,}', rewritten_query)
        keywords.extend(base_words)
        
        # 슬롯에서 키워드 추가
        if slots.category:
            keywords.append(slots.category)
            # 카테고리 관련 키워드도 추가
            if slots.category in self.category_mapping:
                keywords.extend(self.category_mapping[slots.category][:3])  # 상위 3개만
        
        if slots.origin:
            keywords.append(slots.origin)
        
        if slots.freshness_level:
            keywords.append(slots.freshness_level)
        
        # 중복 제거 및 길이 필터링
        keywords = list(set([kw for kw in keywords if len(kw) >= 2]))
        
        return keywords[:10]  # 최대 10개로 제한
    
    def _slots_to_dict(self, slots: SlotExtractionResult) -> Dict[str, Any]:
        """슬롯 결과를 딕셔너리로 변환"""
        result = {}
        
        if slots.quantity is not None:
            result['quantity'] = slots.quantity
        if slots.quantity_standard is not None:
            result['quantity_standard'] = slots.quantity_standard  # 동치 비교용
        if slots.unit_original:
            result['unit_original'] = slots.unit_original
        if slots.unit_standard:
            result['unit_standard'] = slots.unit_standard  
        if slots.unit_category:
            result['unit_category'] = slots.unit_category
        if slots.category:
            result['category'] = slots.category  
        if slots.price_cap is not None:
            result['price_cap'] = slots.price_cap
        if slots.delivery_window:
            result['delivery_window'] = slots.delivery_window
        if slots.dietary_restrictions:
            result['dietary_restrictions'] = slots.dietary_restrictions
        if slots.allergens:
            result['allergens'] = slots.allergens
        if slots.origin:
            result['origin'] = slots.origin
        if slots.freshness_level:
            result['freshness_level'] = slots.freshness_level
            
        return result


# 메인 함수 (graph_interfaces.py의 스텁 구현)
def enhance_query(state: ChatState) -> Dict[str, Any]:
    """
    쿼리 보강 메인 함수
    - A 역할(라우터)에서 받은 쿼리를 보강하여 C 역할(상품검색)에 전달
    """
    enhancer = QueryEnhancer()
    return enhancer.enhance_query(state)


# 테스트용 함수들
if __name__ == "__main__":
    # 간단한 테스트
    test_state = ChatState()
    test_state.query = "신선한 상추 2팩 내일까지 받고싶어. 예산은 1만원 이하로"
    
    result = enhance_query(test_state)
    print("테스트 결과:")
    print(f"재작성: {result['rewrite']['text']}")
    print(f"키워드: {result['rewrite']['keywords']}")
    print(f"슬롯: {result['slots']}")