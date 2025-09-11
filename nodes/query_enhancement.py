"""
query_enhancement.py — B팀: 쿼리 보강

B팀의 책임:
- 사용자 입력 재작성 및 표준화
- 슬롯 추출 (수량, 카테고리, 가격, 식이제한 등)
- 키워드 생성 및 확장
"""

import logging
import os
import json
from typing import Dict, Any, Optional

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_interfaces import ChatState

logger = logging.getLogger("B_QUERY_ENHANCEMENT")

# OpenAI 클라이언트 설정
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
    
    try:
        result = _llm_enhance_all(state.query)
        logger.info(f"LLM 전체 호출 결과: {result}")
            
        filters = result.get("filters") or result.get("search_filters")
        if filters:
            result["meta"] = {"search_filters": filters, "enhance_path": "one_call"}

        logger.info("쿼리 보강(통합 LLM 호출) 완료", extra={
            "has_filters": bool(filters),
            "slots_extracted": len(result.get("slots", {})),
            "keywords_generated": len(result.get("rewrite", {}).get("keywords", []))
        })
        return result

    except Exception as e:
        logger.error(f"쿼리 보강 실패: {e}", extra={
            "user_id": state.user_id,
            "error": str(e)
        })
        
        # 실패 시 원문 유지
        return {
            "rewrite": {
                "text": state.query,
                "keywords": [state.query],
                "confidence": 0.1
            },
            "slots": {"quantity": 1}
        }

def _llm_enhance_all(query: str) -> Optional[Dict[str, Any]]:
    """전체 쿼리 보강 (재작성 + 슬롯 + 키워드)"""
    system_prompt = """당신은 신선식품 쇼핑몰의 전문 쿼리 분석가입니다.
아래 규칙을 정확히 따라 사용자 입력을 분석하세요.

**1. 카테고리 분류 (정확히 아래 10개 중에서만 선택)**:
- **과일**: 사과, 배, 바나나, 딸기, 포도, 멜론, 한라봉, 체리, 키위 등
- **채소**: 상추, 시금치, 브로콜리, 당근, 양파, 마늘, 대파, 토마토, 오이, 무, 콩나물 등
- **곡물/견과류**: 쌀, 현미, 귀리, 퀴노아, 아몬드, 호두 등
- **육류/수산**: 소고기, 돼지고기, 닭고기, 연어, 새우, 오징어, 명태 등
- **유제품**: 우유, 요거트, 치즈, 버터, 달걀, 두유 등
- **냉동식품**: 냉동만두, 냉동피자, 냉동베리, 냉동브로콜리 등
- **조미료/소스**: 간장, 된장, 고추장, 참기름, 올리브오일 등
- **음료**: 생수, 주스, 차 등
- **베이커리**: 식빵, 베이글 등
- **기타**

**2. 수량(quantity) 추출 규칙**:
- "개", "팩", "봉지", "상자", "병", "통", "마리" 등 명시적 개수 단위만 인정
- 중량(g, kg, L)은 상품 규격이므로 quantity가 아님
- 예시: "사과 500g 3개" → quantity: 3, "우유 1L" → quantity: 1, "바나나 1kg" → quantity: 1

**3. 가격(price_cap) 추출 규칙**:
- "만원 이하" → 10000, "3천원대" → 3000, "5000원 미만" → 5000
- "2-3만원" → 30000 (최대값 기준), "1만~2만원" → 20000
- "저렴한", "싸게", "비싸게" → 추출하지 않음 (구체적 금액만)

**4. 브랜드 인식 (정확히 이런 형태만)**:
- 풀무원, 오뚜기, 동원, 롯데, 농심, 샘표, 청정원, 대상, 매일, CJ, 서울우유, 남양, 빙그레
- 브랜드명이 명시되지 않으면 추출 안 함

**5. 원산지 인식**:
- 국내: 국산, 제주산, 경북산, 충남산, 전남산, 강원산
- 해외: 미국산, 칠레산, 뉴질랜드산, 일본산, 중국산
- "수입"만으로는 구체적 원산지 아님

**6. 키워드 생성 (정확히 4-6개)**:
- 상품명 한글: 원래 이름
- 상품명 영문: apple, banana 등
- 카테고리명: 과일, 채소 등
- 속성: 유기농, 신선한, 냉동 등의 핵심 키워드를 꾸며주는 말 포함
- 의도: 구매, 주문, 검색 등
- 브랜드명: 풀무원, 오뚜기 등

**7. 재작성(rewrite) 규칙**:
- 조사 제거: "을/를/이/가/은/는" 삭제
- 불용어 제거: "좀/살짝/하나/정도" 삭제
- 의도 표준화: "사고 싶어" → "구매", "찾아줘" → "검색", "주문하고 싶어" → "주문"
- 최종 길이: 15자 이내로 간결화

**8. 신뢰도(confidence) 기준**:
- 0.9: 모든 정보 명확, 표준 표현
- 0.8: 대부분 정보 추출, 약간의 추론
- 0.7: 기본 정보 추출, 일부 불확실
- 0.5: 최소 정보만 추출
- 0.3: 이해 어려움

**9. changes 기록**:
- "조사 '을' 제거", "'사고싶어' → '구매'", "불용어 '좀' 제거" 등 구체적으로 기록

**구체적 예시들**:

예시1: "사과 2개 주문하고 싶어요"
→ {{"rewrite": {{"text": "사과 2개 주문", "keywords": ["사과", "과일", "주문", "구매"], "confidence": 0.9, "changes": ["조사 제거", "'주문하고 싶어요' → '주문'"]}}, "slots": {{"quantity": 2, "category": "과일"}}}}

예시2: "유기농 당근 1kg 3봉지 만원 이하로 구매"  
→ {{"rewrite": {{"text": "유기농 당근 1kg 3봉지 구매", "keywords": ["당근", "채소", "유기농", "구매"], "confidence": 0.9, "changes": ["'만원 이하로' → 가격 슬롯 이동"]}}, "slots": {{"quantity": 3, "category": "채소", "organic": true, "price_cap": 10000}}}}

예시3: "풀무원 두부 좀 사고 싶어요"
→ {{"rewrite": {{"text": "풀무원 두부 구매", "keywords": ["두부", "풀무원", "구매", "유제품"], "confidence": 0.8, "changes": ["불용어 '좀' 제거", "'사고 싶어요' → '구매'"]}}, "slots": {{"quantity": 1, "brand": "풀무원"}}}}

예시4: "제주 귤 5000원대로 주문"
→ {{"rewrite": {{"text": "제주 귤 주문", "keywords": ["귤", "과일", "제주", "주문"], "confidence": 0.8, "changes": ["'5000원대로' → 가격 슬롯 이동"]}}, "slots": {{"quantity": 1, "category": "과일", "origin": "제주산", "price_cap": 5000}}}}

예시5: "뭔가 맛있는 과일"
→ {{"rewrite": {{"text": "과일 검색", "keywords": ["과일", "맛있는", "검색", "신선"], "confidence": 0.4, "changes": ["'뭔가' 제거", "의도 명확화"]}}, "slots": {{"quantity": 1, "category": "과일"}}}}

예시6: "연어 500g 2팩 3만원 미만"
→ {{"rewrite": {{"text": "연어 500g 2팩 구매", "keywords": ["연어", "육류수산", "구매", "생선"], "confidence": 0.9, "changes": ["'3만원 미만' → 가격 슬롯 이동"]}}, "slots": {{"quantity": 2, "category": "육류수산", "price_cap": 30000}}}}

위 규칙을 정확히 따라 JSON 형식으로만 응답하세요."""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"입력: {query}"}
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
            max_tokens=500
        )
        
        result = json.loads(response.choices[0].message.content.strip())
        
        # 데이터 정리
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
            # null 제거 후에도 슬롯이 비었다면 quantity 기본값 보장
            if not result["slots"]:
                result["slots"] = {"quantity": 1}

        return result
        
    except Exception as e:
        logger.warning(f"LLM 단일 호출 실패: {e}")
        return None