"""
query_enhancement.py — B팀: 쿼리 보강

B팀의 책임:
- 사용자 입력 재작성 및 표준화
- 슬롯 추출 (수량, 카테고리, 가격, 식이제한 등)
- 키워드 생성 및 확장
- PII(개인정보) 마스킹 및 안전 처리
"""

import logging
import os
import re
from typing import Dict, Any, List, Optional

# 상대 경로로 graph_interfaces 임포트
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
        logger.warning("OpenAI API key not found. Using rule-based enhancement.")
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
        # 1. 입력 전처리 및 PII 마스킹
        cleaned_query = _preprocess_query(state.query)
        
        # 2. 쿼리 재작성
        if openai_client:
            rewrite_result = _llm_rewrite(cleaned_query)
        else:
            rewrite_result = _rule_based_rewrite(cleaned_query)
        
        # 3. 슬롯 추출
        if openai_client:
            slots = _llm_slot_extraction(cleaned_query, rewrite_result["text"])
        else:
            slots = _rule_based_slot_extraction(cleaned_query)
        
        # 4. 키워드 생성
        keywords = _generate_keywords(cleaned_query, rewrite_result["text"])
        rewrite_result["keywords"] = keywords
        
        logger.info("쿼리 보강 완료", extra={
            "rewritten_text": rewrite_result["text"],
            "slots_extracted": len(slots),
            "keywords_generated": len(keywords)
        })
        
        return {
            "rewrite": rewrite_result,
            "slots": slots
        }
        
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

def _preprocess_query(query: str) -> str:
    """입력 전처리 및 PII 마스킹"""
    
    # 공백 정규화
    cleaned = re.sub(r'\s+', ' ', query.strip())
    
    # PII 마스킹
    # 전화번호 마스킹
    cleaned = re.sub(r'010-?\d{4}-?\d{4}', '[전화번호]', cleaned)
    cleaned = re.sub(r'01[016789]-?\d{3,4}-?\d{4}', '[전화번호]', cleaned)
    
    # 이메일 마스킹
    cleaned = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[이메일]', cleaned)
    
    # 주민등록번호 마스킹 (부분)
    cleaned = re.sub(r'\d{6}-?\d{7}', '[주민등록번호]', cleaned)
    
    # 카드번호 마스킹
    cleaned = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[카드번호]', cleaned)
    
    return cleaned

def _llm_rewrite(query: str) -> Dict[str, Any]:
    """LLM 기반 쿼리 재작성"""
    
    system_prompt = """
당신은 신선식품 쇼핑몰의 검색 쿼리를 개선하는 전문가입니다.
사용자의 자연어 입력을 명확하고 검색에 최적화된 형태로 재작성하세요.

재작성 원칙:
1. 모호한 표현을 구체적으로 변환
2. 상품명을 표준화 (예: "토마토" → "토마토")
3. 불필요한 조사, 감탄사 제거
4. 검색 의도를 명확히 표현
5. 원래 의미는 보존

예시:
- "사과 좀 사고 싶은데요" → "사과 구매"
- "김치찌개 만들 재료들" → "김치찌개 재료"
- "싸고 맛있는 과일" → "저렴한 과일"

JSON 형식으로 응답하세요:
{"text": "재작성된 텍스트", "confidence": 0.0-1.0, "changes": ["변경사항 목록"]}
"""
    
    user_prompt = f'원본 쿼리: "{query}"'
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=200
        )
        
        content = response.choices[0].message.content.strip()
        
        import json
        try:
            result = json.loads(content)
            return {
                "text": result.get("text", query),
                "confidence": float(result.get("confidence", 0.7)),
                "changes": result.get("changes", [])
            }
        except json.JSONDecodeError:
            logger.warning(f"LLM 재작성 응답 파싱 실패: {content}")
            return _rule_based_rewrite(query)
            
    except Exception as e:
        logger.error(f"LLM 재작성 실패: {e}")
        return _rule_based_rewrite(query)

def _rule_based_rewrite(query: str) -> Dict[str, Any]:
    """규칙 기반 쿼리 재작성"""
    
    rewritten = query
    changes = []
    
    # 조사 제거
    particles = ['을', '를', '이', '가', '은', '는', '에', '서', '로', '과', '와', '도', '만']
    for particle in particles:
        if rewritten.endswith(particle):
            rewritten = rewritten[:-len(particle)]
            changes.append(f"조사 '{particle}' 제거")
    
    # 불필요한 표현 제거
    unnecessary = ['좀', '좀더', '조금', '약간', '살짝', '하나', '개']
    for word in unnecessary:
        if word in rewritten:
            rewritten = rewritten.replace(word, '').strip()
            rewritten = re.sub(r'\s+', ' ', rewritten)  # 중복 공백 제거
            changes.append(f"불필요 표현 '{word}' 제거")
    
    # 의도 표준화
    intent_replacements = {
        '사고싶어': '구매',
        '사고 싶어': '구매',
        '주문하고싶어': '주문',
        '찾아줘': '검색',
        '찾아주세요': '검색',
        '만들고싶어': '요리',
        '만들고 싶어': '요리'
    }
    
    for old, new in intent_replacements.items():
        if old in rewritten:
            rewritten = rewritten.replace(old, new)
            changes.append(f"의도 표준화: '{old}' → '{new}'")
    
    return {
        "text": rewritten.strip(),
        "confidence": 0.6 if changes else 0.8,
        "changes": changes
    }

def _llm_slot_extraction(original_query: str, rewritten_query: str) -> Dict[str, Any]:
    """LLM 기반 슬롯 추출"""
    
    system_prompt = """
당신은 신선식품 주문에서 중요한 정보를 추출하는 전문가입니다.
사용자의 쿼리에서 다음 슬롯들을 추출하세요:

슬롯 종류:
- quantity: 수량 (숫자)
- category: 카테고리 (과일, 채소, 곡물, 육류수산, 유제품)  
- price_cap: 최대 가격 (숫자)
- organic: 유기농 여부 (true/false)
- origin: 원산지
- brand: 브랜드
- diet_restriction: 식이 제한 (비건, 글루텐프리 등)

JSON 형식으로 응답하세요. 없는 정보는 null로 설정하세요.
{"quantity": 2, "category": "과일", "price_cap": 10000, "organic": true, ...}
"""
    
    user_prompt = f"""
원본: "{original_query}"
재작성: "{rewritten_query}"
"""
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=300
        )
        
        content = response.choices[0].message.content.strip()
        
        import json
        try:
            slots = json.loads(content)
            # null 값들 제거
            return {k: v for k, v in slots.items() if v is not None}
        except json.JSONDecodeError:
            logger.warning(f"LLM 슬롯 추출 응답 파싱 실패: {content}")
            return _rule_based_slot_extraction(original_query)
            
    except Exception as e:
        logger.error(f"LLM 슬롯 추출 실패: {e}")
        return _rule_based_slot_extraction(original_query)

def _rule_based_slot_extraction(query: str) -> Dict[str, Any]:
    """규칙 기반 슬롯 추출"""
    
    slots = {}
    query_lower = query.lower()
    
    # 수량 추출
    quantity_patterns = [
        r'(\d+)개', r'(\d+)팩', r'(\d+)봉', r'(\d+)상자',
        r'(\d+)킬로', r'(\d+)kg', r'(\d+)g'
    ]
    
    for pattern in quantity_patterns:
        match = re.search(pattern, query_lower)
        if match:
            slots['quantity'] = int(match.group(1))
            break
    else:
        # 기본 수량
        slots['quantity'] = 1
    
    # 카테고리 추출
    category_keywords = {
        '과일': ['사과', '바나나', '오렌지', '딸기', '포도', '배', '감', '복숭아'],
        '채소': ['상추', '양상추', '당근', '브로콜리', '양파', '토마토', '배추', '무'],
        '곡물': ['쌀', '현미', '귀리', '퀴노아', '보리'],
        '육류수산': ['소고기', '돼지고기', '닭고기', '연어', '참치', '새우'],
        '유제품': ['우유', '요거트', '치즈', '달걀', '버터']
    }
    
    for category, keywords in category_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            slots['category'] = category
            break
    
    # 가격 추출
    price_patterns = [
        r'(\d+)원\s*이하', r'(\d+)원\s*미만', r'(\d+)원\s*아래',
        r'(\d+)\s*이하', r'(\d+)\s*미만'
    ]
    
    for pattern in price_patterns:
        match = re.search(pattern, query_lower)
        if match:
            slots['price_cap'] = int(match.group(1))
            break
    
    # 유기농 여부
    if any(keyword in query_lower for keyword in ['유기농', '친환경', '무농약']):
        slots['organic'] = True
    
    # 원산지
    origin_keywords = ['국산', '수입', '제주', '경북', '전남', '강원', '충북']
    for origin in origin_keywords:
        if origin in query_lower:
            slots['origin'] = origin
            break
    
    return slots

def _generate_keywords(original: str, rewritten: str) -> List[str]:
    """키워드 생성 및 확장"""
    
    keywords = []
    
    # 원본 및 재작성 텍스트에서 키워드 추출
    all_text = f"{original} {rewritten}".lower()
    
    # 기본 키워드 (공백으로 분할)
    basic_keywords = [word.strip() for word in all_text.split() if len(word.strip()) > 1]
    keywords.extend(basic_keywords)
    
    # 동의어 확장
    synonyms = {
        '사과': ['apple', '애플'],
        '바나나': ['banana'],
        '토마토': ['tomato'],
        '당근': ['carrot'],
        '양파': ['onion'],
        '상추': ['lettuce'],
        '유기농': ['친환경', '무농약'],
        '싸고': ['저렴', '경제적'],
        '맛있는': ['신선한', '좋은'],
        '빠른': ['신속', '즉시']
    }
    
    for keyword in basic_keywords:
        if keyword in synonyms:
            keywords.extend(synonyms[keyword])
    
    # 중복 제거
    keywords = list(set(keywords))
    
    # 불용어 제거
    stopwords = ['그', '저', '이', '것', '들', '에', '을', '를', '은', '는', '이', '가']
    keywords = [k for k in keywords if k not in stopwords and len(k) > 1]
    
    return keywords[:10]  # 상위 10개만 반환