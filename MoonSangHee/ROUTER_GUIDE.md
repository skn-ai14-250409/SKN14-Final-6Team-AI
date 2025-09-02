# Router & Query Enhancement 기술 가이드

## 📋 개요
사용자 입력을 분석하여 적절한 처리 경로로 라우팅하고, 검색 쿼리를 최적화하는 핵심 모듈입니다.

## 🎯 핵심 기능

### 1. Intent Routing (의도 라우팅)
- **검색/주문** vs **고객응대** 분류
- LLM 기반 자연어 이해
- 신뢰도 기반 분기 처리

### 2. Query Enhancement (쿼리 향상)
- 검색어 재작성 및 확장
- 구조화된 정보 추출 (슬롯 필링)
- 검색 최적화

## 🛠 구현 상세

### Router 구현
```python
# apps/core/router.py

import openai
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class RouteResult:
    route: str  # "search_order" | "customer_service"
    confidence: float
    reasoning: str
    clarification_needed: bool = False
    suggested_question: Optional[str] = None

class IntentRouter:
    def __init__(self, openai_api_key: str):
        self.client = openai.OpenAI(api_key=openai_api_key)
        self.confidence_threshold = 0.7
        
    def route_user_intent(self, user_input: str, context: Dict = None) -> RouteResult:
        \"\"\"사용자 의도를 분석하여 라우팅\"\"\"
        
        system_prompt = \"\"\"
        당신은 신선식품 쇼핑몰의 의도 분류 전문가입니다.
        사용자의 입력을 다음 2가지로 분류해주세요:
        
        1. search_order: 상품 검색, 주문, 장바구니, 레시피 관련
        2. customer_service: 배송 문의, 환불, 불만, 계정 문제 등
        
        응답 형식:
        {
            "route": "search_order" or "customer_service",
            "confidence": 0.0-1.0,
            "reasoning": "판단 근거"
        }
        \"\"\"
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"사용자 입력: {user_input}"}
                ],
                temperature=0.1
            )
            
            result = self._parse_route_response(response.choices[0].message.content)
            
            # 신뢰도가 낮으면 명확화 필요
            if result.confidence < self.confidence_threshold:
                result.clarification_needed = True
                result.suggested_question = self._generate_clarification(user_input)
                
            return result
            
        except Exception as e:
            # 에러 시 기본값 반환
            return RouteResult(
                route="search_order",  # 기본값
                confidence=0.5,
                reasoning=f"분류 오류로 인한 기본 라우팅: {str(e)}"
            )
    
    def _parse_route_response(self, response: str) -> RouteResult:
        \"\"\"LLM 응답 파싱\"\"\"
        # JSON 파싱 로직
        pass
    
    def _generate_clarification(self, user_input: str) -> str:
        \"\"\"명확화 질문 생성\"\"\"
        clarification_prompts = {
            "product": "상품을 찾고 계신가요, 아니면 주문/배송 관련 문의인가요?",
            "general": "구체적으로 어떤 도움이 필요하신지 말씀해 주세요.",
            "ambiguous": "상품 검색인지, 고객 문의인지 명확히 해주시겠어요?"
        }
        return clarification_prompts.get("general", "어떤 도움이 필요하신가요?")
```

### Query Enhancement 구현
```python
# apps/core/query_enhancer.py

from typing import Dict, List, Optional
from dataclasses import dataclass, field

@dataclass
class EnhancedQuery:
    original_query: str
    enhanced_query: str
    keywords: List[str]
    filters: Dict[str, any] = field(default_factory=dict)
    slots: Dict[str, any] = field(default_factory=dict)

class QueryEnhancer:
    def __init__(self, openai_api_key: str):
        self.client = openai.OpenAI(api_key=openai_api_key)
        
    def enhance_search_query(self, user_input: str, context: Dict = None) -> EnhancedQuery:
        \"\"\"검색 쿼리 향상\"\"\"
        
        # 1. 쿼리 재작성
        rewritten_query = self._rewrite_query(user_input)
        
        # 2. 키워드 추출
        keywords = self._extract_keywords(rewritten_query)
        
        # 3. 슬롯 추출
        slots = self._extract_slots(user_input)
        
        # 4. 필터 생성
        filters = self._generate_filters(slots)
        
        return EnhancedQuery(
            original_query=user_input,
            enhanced_query=rewritten_query,
            keywords=keywords,
            filters=filters,
            slots=slots
        )
    
    def _rewrite_query(self, query: str) -> str:
        \"\"\"검색어 재작성\"\"\"
        system_prompt = \"\"\"
        사용자의 자연어 검색어를 상품 검색에 최적화된 형태로 재작성해주세요.
        
        예시:
        입력: "저녁에 먹을 간단한 거 있나요?"
        출력: "간편식 즉석식품 저녁식사"
        
        입력: "다이어트할 때 먹으면 좋은 것들"
        출력: "다이어트 식품 저칼로리 건강식품"
        \"\"\"
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.1
        )
        
        return response.choices[0].message.content.strip()
    
    def _extract_keywords(self, query: str) -> List[str]:
        \"\"\"키워드 추출\"\"\"
        # BM25 친화적 키워드 생성
        prompt = f"다음 검색어에서 핵심 키워드들을 추출해주세요: {query}"
        # ... LLM 호출 및 파싱
        
    def _extract_slots(self, query: str) -> Dict[str, any]:
        \"\"\"구조화된 정보 추출\"\"\"
        system_prompt = \"\"\"
        사용자 입력에서 다음 정보를 추출해주세요:
        
        {
            "product_name": "구체적인 상품명",
            "quantity": "수량 (숫자)",
            "category": "카테고리",
            "price_range": {"min": 숫자, "max": 숫자},
            "dietary_restrictions": ["채식", "글루텐프리", "저나트륨"],
            "urgency": "오늘", "내일", "이번주" 등
        }
        
        정보가 없으면 null로 설정하세요.
        \"\"\"
        
        # ... LLM 호출 및 JSON 파싱
        
    def _generate_filters(self, slots: Dict) -> Dict:
        \"\"\"검색 필터 생성\"\"\"
        filters = {}
        
        if slots.get("category"):
            filters["category"] = slots["category"]
            
        if slots.get("price_range"):
            filters["price_min"] = slots["price_range"].get("min")
            filters["price_max"] = slots["price_range"].get("max")
            
        if slots.get("dietary_restrictions"):
            filters["tags"] = slots["dietary_restrictions"]
            
        return filters
```

## 🔧 Django Integration

### Views 연결
```python
# apps/api/views.py

from apps.core.router import IntentRouter
from apps.core.query_enhancer import QueryEnhancer

class ChatAPIView(APIView):
    def __init__(self):
        self.router = IntentRouter(settings.OPENAI_API_KEY)
        self.enhancer = QueryEnhancer(settings.OPENAI_API_KEY)
    
    def post(self, request):
        user_input = request.data.get('message')
        
        # 1. 라우팅
        route_result = self.router.route_user_intent(user_input)
        
        if route_result.clarification_needed:
            return Response({
                'response': route_result.suggested_question,
                'needs_clarification': True
            })
        
        # 2. 쿼리 향상 (검색/주문 경로인 경우)
        if route_result.route == "search_order":
            enhanced = self.enhancer.enhance_search_query(user_input)
            # 상품 검색으로 전달
            
        else:  # customer_service
            # CS 처리로 전달
            pass
```

## 📊 테스트 케이스

### 라우팅 테스트
```python
# tests/test_router.py

class TestIntentRouter:
    def test_search_intent(self):
        router = IntentRouter(api_key)
        
        test_cases = [
            "사과 주문하고 싶어요",
            "저녁 요리 재료 찾아주세요",
            "다이어트 식품 추천해주세요"
        ]
        
        for case in test_cases:
            result = router.route_user_intent(case)
            assert result.route == "search_order"
            assert result.confidence > 0.7
    
    def test_cs_intent(self):
        test_cases = [
            "주문한 상품이 안 왔어요",
            "환불 신청하고 싶습니다",
            "배송 언제 되나요?"
        ]
        
        for case in test_cases:
            result = router.route_user_intent(case)
            assert result.route == "customer_service"
```

### 쿼리 향상 테스트
```python
# tests/test_query_enhancer.py

class TestQueryEnhancer:
    def test_query_rewriting(self):
        enhancer = QueryEnhancer(api_key)
        
        result = enhancer.enhance_search_query("저녁에 간단히 먹을 수 있는 것")
        
        assert "간편식" in result.enhanced_query or "즉석식품" in result.enhanced_query
        assert len(result.keywords) > 0
        assert "category" in result.filters or "tags" in result.filters
```

## 🚀 성능 최적화

### 캐싱 전략
```python
from django.core.cache import cache

class IntentRouter:
    def route_user_intent(self, user_input: str, context: Dict = None) -> RouteResult:
        # 캐시 키 생성
        cache_key = f"route:{hash(user_input)}"
        
        # 캐시에서 조회
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
            
        # LLM 호출
        result = self._call_llm(user_input)
        
        # 캐시 저장 (5분)
        cache.set(cache_key, result, 300)
        
        return result
```

### 배치 처리
- 여러 사용자 요청을 배치로 처리하여 LLM API 호출 최적화
- 비동기 처리로 응답 시간 개선

## 📈 모니터링

### 로깅
```python
import structlog

logger = structlog.get_logger(__name__)

def route_user_intent(self, user_input: str) -> RouteResult:
    logger.info("intent_routing_started", 
               user_input=user_input[:100],  # 처음 100자만 로깅
               input_length=len(user_input))
    
    result = self._process_routing(user_input)
    
    logger.info("intent_routing_completed",
               route=result.route,
               confidence=result.confidence,
               clarification_needed=result.clarification_needed)
    
    return result
```

### 메트릭 수집
- 라우팅 정확도
- 평균 신뢰도 점수
- 명확화 요청 비율
- 처리 시간

## 🔒 보안 고려사항

### 입력 검증
```python
def validate_user_input(user_input: str) -> bool:
    \"\"\"사용자 입력 검증\"\"\"
    # 길이 제한
    if len(user_input) > 1000:
        return False
        
    # 악성 패턴 검사
    malicious_patterns = [
        r'<script.*?>',
        r'javascript:',
        r'eval\(',
        # SQL injection 패턴들
    ]
    
    for pattern in malicious_patterns:
        if re.search(pattern, user_input, re.IGNORECASE):
            return False
    
    return True
```

### PII 필터링
```python
def filter_sensitive_info(text: str) -> str:
    \"\"\"개인정보 마스킹\"\"\"
    # 전화번호 마스킹
    text = re.sub(r'010-?\d{4}-?\d{4}', '010-****-****', text)
    
    # 이메일 마스킹
    text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', 
                  '***@***.***', text)
    
    return text
```

## 📝 개발 체크리스트

- [ ] IntentRouter 클래스 구현
- [ ] QueryEnhancer 클래스 구현
- [ ] Django views 연결
- [ ] 단위 테스트 작성
- [ ] 통합 테스트 작성
- [ ] 성능 테스트 작성
- [ ] 로깅 구현
- [ ] 캐싱 구현
- [ ] 보안 검증 구현
- [ ] API 문서화