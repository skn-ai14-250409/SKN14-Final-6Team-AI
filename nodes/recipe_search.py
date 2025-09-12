"""
recipe_search.py — 레시피 검색 및 재료 추천 모듈 
책임:
- 시나리오 1: 일반 레시피 검색 (Tavily API) 후 사이드바에 결과 URL 표시
- 시나리오 2: 특정 레시피 선택 시, URL 크롤링 및 LLM을 통한 재료/조리법 추출
- 추출된 재료를 기반으로 쇼핑몰 상품(SKU)을 DB에서 검색하여 사이드바에 제안
- 최종 응답 메시지(AIMessage)를 프론트엔드 규격에 맞는 'response' 키로 포맷팅
"""
import random
import logging
import os
import requests
import re
import json
from typing import Dict, Any, List, Optional
import mysql.connector
from mysql.connector import Error
from bs4 import BeautifulSoup

# 프로젝트 루트 경로 추가 (환경에 맞게 조정)
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_interfaces import ChatState

# 로거 설정
logger = logging.getLogger("RECIPE_SEARCH")

# --- 환경 변수 및 클라이언트 설정 ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

try:
    import openai
    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_client = openai.OpenAI(api_key=openai_api_key) if openai_api_key else None
    if not openai_client:
        logger.warning("OpenAI API key not found. LLM-based features will be disabled.")
except ImportError:
    openai_client = None
    logger.warning("OpenAI package not available. LLM-based features will be disabled.")

# --- DB 설정 ---
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'user': os.getenv('DB_USER', 'qook_user'),
    'password': os.getenv('DB_PASS', 'qook_pass'),
    'database': os.getenv('DB_NAME', 'qook_chatbot'),
    'port': int(os.getenv('DB_PORT', 3306))
}

# --- 메인 라우팅 함수 ---
def recipe_search(state: ChatState) -> Dict[str, Any]:
    """
    사용자 쿼리를 분석하여 두 가지 시나리오 중 하나를 실행합니다.
    1. 일반 레시피 검색
    2. 선택된 레시피의 재료 추천
    """
    logger.info("레시피 검색 프로세스 시작")
    query = state.query

    try:
        # 시나리오 2: 사용자가 사이드바에서 특정 레시피의 '재료 추천받기'를 클릭한 경우
        if "선택된 레시피:" in query and "URL:" in query:
            logger.info("시나리오 2: 선택된 레시피 재료 추천 시작")
            recipe = _handle_selected_recipe(query)
            return recipe
        
        # 시나리오 1: 일반적인 레시피 관련 질문인 경우
        else:
            logger.info("시나리오 1: 일반 레시피 검색 시작")
            rewrite_query = state.rewrite.get("text", "")
            return _handle_general_recipe_search(query, rewrite_query)

    except Exception as e:
        logger.error(f"레시피 검색 중 심각한 오류 발생: {e}", exc_info=True)
        return {
            "recipe": {"results": [], "ingredients": [], "error": str(e)},
            "response": "죄송합니다, 레시피를 검색하는 중 오류가 발생했습니다."
        }

# --- 시나리오 1: 일반 레시피 검색 핸들러 ---
def _handle_general_recipe_search(original_query: str, rewrite_query: str) -> Dict[str, Any]:
    """Tavily API로 레시피를 검색하고 사이드바에 표시할 URL 목록을 반환합니다."""
    
    # LLM 또는 규칙 기반으로 검색에 최적화된 쿼리 생성
    recipe_query = _extract_recipe_query(original_query, rewrite_query)
    
    # Tavily로 외부 레시피 검색
    recipe_results = _search_with_tavily(recipe_query)
    
    # 프론트엔드로 보낼 최종 메시지 생성
    if recipe_results:
        message = (
            f"{len(recipe_results)}개의 레시피를 찾았습니다.\n\n"
            "💡 원하는 레시피를 클릭하여 '재료 추천받기' 버튼을 누르면 필요한 재료들을 추천해드립니다!"
        )
    else:
        message = "관련 레시피를 찾지 못했습니다. 다른 키워드로 검색해보세요."

    return {
        "recipe": {
            "results": recipe_results,      # 사이드바에 표시될 레시피 URL 목록
            "ingredients": [],              # 이 시나리오에서는 재료 목록이 비어있음
            "search_query": recipe_query
        },
        "response": message  # chat.js가 인식할 수 있도록 'response' 키 사용
    }

# --- 시나리오 2: 선택된 레시피 재료 추천 핸들러 ---

def _handle_selected_recipe(query: str, state: ChatState = None) -> Dict[str, Any]:
    """선택된 레시피 URL을 크롤링하고, 재료를 추출하여 DB 상품과 매핑합니다."""
    
    # 쿼리에서 URL 추출
    recipe_url = _extract_recipe_url(query)
    if not recipe_url:
        logger.info("레시피 URL을 찾지 못함")
        return {
            "recipe": {"results": [], "ingredients": []},
            "response": "레시피 URL을 찾을 수 없어 재료를 추천할 수 없습니다."
        }
    
    # URL 크롤링 및 LLM을 통한 내용 구조화
    structured_content = _scrape_and_structure_recipe(recipe_url)
    if not structured_content or not structured_content.get("ingredients"):
        logger.info("레시피 내용을 분석할 수 없음")
        return {
            "recipe": {"results": [], "ingredients": []},
            "response": "레시피 내용을 분석할 수 없어 재료 추천이 어렵습니다."
        }
    
    logger.info(f"레시피 구조화 완료: {structured_content.get('title', '제목 없음')}")
    
    # 추출된 재료 목록 (예: ["사과", "돼지고기", "양파"])
    extracted_ingredients = structured_content.get("ingredients", [])
    
    # ✅ 추가: state에서 rewrite.keywords도 활용
    additional_keywords = []
    if state and state.rewrite.get("keywords"):
        # 재료 관련 키워드만 필터링 (구매, 재료 등은 제외)
        filtered_keywords = [
            k for k in state.rewrite["keywords"] 
            if k not in ['재료', '구매', '상품', '추천', '쇼핑몰']
        ]
        additional_keywords.extend(filtered_keywords)
    
    # 재료명과 키워드 합치기 (중복 제거)
    all_search_terms = list(set(extracted_ingredients + additional_keywords))
    logger.info(f"DB 검색 키워드: {all_search_terms}")
    
    # 재료명으로 DB의 상품 목록 검색 (LIKE 검색)
    matched_products = _get_product_details_from_db(all_search_terms)
    
    # AIMessage로 보여줄 레시피 내용 포맷팅
    formatted_recipe_message = _format_recipe_content(structured_content)
    
    logger.info(f"레시피 처리 완료: 재료 {len(all_search_terms)}개, 추천 상품 {len(matched_products)}개")
    print("recipe_search.py matched_products:",matched_products)
    print("recipe_search.py formatted_recipe_message:",formatted_recipe_message)
    print("recipe_search.py structured_content:",structured_content)
    return {
        "recipe": {
            "results": [],
            "ingredients": matched_products,
            "selected_recipe": structured_content
        },
        "meta": {
            "final_message": formatted_recipe_message 
        }
    }

def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        logger.error(f"DB 연결 실패: {e}")
        return None

def _get_product_details_from_db(ingredient_names: List[str]) -> List[Dict[str, Any]]:
    """DB에서 재료명을 포함(LIKE)하는 상품 상세 정보를 조회합니다."""
    if not ingredient_names:
        return []

    conn = get_db_connection()
    if not conn:
        return []

    try:
        with conn.cursor(dictionary=True) as cursor:
            # 여러 LIKE 조건을 OR로 연결하는 쿼리 생성
            where_clauses = ' OR '.join(['p.product LIKE %s'] * len(ingredient_names))
            sql = f"""
                SELECT p.product as name, p.unit_price as price, p.origin, p.organic
                FROM product_tbl p
                WHERE {where_clauses}
                LIMIT 15
            """
            
            # LIKE 검색을 위한 파라미터 생성 (예: '사과' -> '%사과%')
            params = [f"%{name}%" for name in ingredient_names]
            
            cursor.execute(sql, params)
            products = cursor.fetchall()

            # 프론트엔드가 기대하는 형태로 데이터 포맷팅
            formatted_products = []
            for p in products:
                formatted_products.append({
                    'name': p.get('name', ''),
                    'price': float(p.get('price', 0.0)),
                    'origin': p.get('origin', '정보 없음'),
                    'organic': True if p.get('organic') == 'Y' else False
                })
            return formatted_products
            
    except Error as e:
        logger.error(f"상품 상세 정보 조회 실패: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            conn.close()

# --- Helper Functions: 외부 API 및 크롤링 ---
def _is_crawlable_url(url: str) -> bool:
    """URL이 크롤링 가능한지 간단히 판단합니다."""
    from urllib.parse import urlparse
    
    try:
        parsed = urlparse(url.lower())
        domain = parsed.netloc.replace('www.', '')
        
        # 확실히 제외할 사이트들 (동영상/SNS)
        excluded_patterns = ['youtube.', 'youtu.be', 'instagram.', 'facebook.', 'tiktok.', 'pinterest.']
        if any(pattern in domain for pattern in excluded_patterns):
            return False
        
        # HTML 페이지인지 간단 확인 (확장자 체크)
        path = parsed.path.lower()
        if path.endswith(('.mp4', '.avi', '.mov', '.pdf', '.jpg', '.png', '.gif')):
            return False
            
        return True
        
    except Exception:
        return False

def _quick_validate_url(url: str) -> bool:
    """URL이 실제로 접근 가능한지 빠르게 확인합니다."""
    try:
        import requests
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.head(url, headers=headers, timeout=3)
        
        # 200대 응답이고 HTML 콘텐츠인지 확인
        if 200 <= response.status_code < 300:
            content_type = response.headers.get('content-type', '').lower()
            return 'text/html' in content_type
            
        return False
    except Exception:
        return False

def _search_with_tavily(query: str) -> List[Dict[str, Any]]:
    """Tavily API로 레시피를 검색하고, 결과를 섞은 후 검증합니다."""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)
        
        logger.info(f"Tavily 검색 실행: '{query}'")
        
        # 검색 쿼리에 제외 키워드 추가
        enhanced_query = f"{query} 레시피 -youtube -instagram -facebook -tiktok -blog.naver.com"
        
        search_result = client.search(
            query=enhanced_query,
            search_depth="basic",
            max_results=20  # ## 변경점 2: 검색 결과 요청 개수를 20개로 늘림
        )
        
        # ## 변경점 3: 받아온 검색 결과를 리스트로 만들고 순서를 무작위로 섞음
        search_results_list = search_result.get("results", [])
        random.shuffle(search_results_list)

        validated_results = []
        
        # 무작위로 섞인 리스트를 순회하며 검증 시작
        for res in search_results_list:
            url = res.get("url", "")
            
            # 1단계: 기본 URL 패턴 검증
            if not url or not _is_crawlable_url(url):
                continue
            
            # 2단계: 실제 접근 가능성 검증 (네트워크 요청 최소화를 위해 필요한 만큼만)
            if not _quick_validate_url(url):
                logger.info(f"접근 불가능한 URL 제외: {url}")
                continue
            
            validated_results.append({
                "title": res.get("title", "제목 없음"),
                "url": url,
                "description": res.get("content", "")[:150]
            })
            
            # 원하는 개수(3개)만큼 찾으면 중단
            if len(validated_results) >= 3:
                break
        
        logger.info(f"검증된 레시피 URL: {len(validated_results)}개")
        return validated_results
        
    except Exception as e:
        logger.error(f"Tavily 검색 실패: {e}")
        return []

def _scrape_and_structure_recipe(url: str) -> Optional[Dict[str, Any]]:
    """URL을 크롤링하고 LLM을 사용해 내용을 구조화합니다."""
    logger.info(f"URL 크롤링 및 분석 시작: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        page_text = soup.get_text(separator='\n', strip=True)
        
        if not openai_client:
            logger.warning("OpenAI 클라이언트가 없어 레시피 구조화 불가.")
            return None
            
        return _llm_extract_recipe_content(page_text[:4000])

    except Exception as e:
        logger.error(f"URL 크롤링 및 구조화 실패 {url}: {e}")
        return None

# --- Helper Functions: LLM 처리 ---
def _extract_recipe_query(original_query: str, rewrite_query: str = "") -> str:
    """사용자 쿼리에서 검색에 사용할 핵심 레시피명을 추출합니다."""
    if not openai_client:
        return f"{original_query} 레시피"

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "사용자의 질문에서 핵심 요리 이름만 추출해줘. 예를 들어 '김치찌개 맛있게 끓이는 법 알려줘' -> '김치찌개'"},
                {"role": "user", "content": f"원본: '{original_query}', 재작성: '{rewrite_query}'"}
            ],
            temperature=0.1, max_tokens=50
        )
        return response.choices[0].message.content.strip().strip('"')
    except Exception as e:
        logger.error(f"LLM 쿼리 추출 실패: {e}")
        return f"{original_query} 레시피"

def _llm_extract_recipe_content(page_text: str) -> Dict[str, Any]:
    """LLM을 사용하여 웹페이지 텍스트에서 레시피 정보를 JSON 형태로 구조화합니다."""
    system_prompt = """당신은 신선식품 쇼핑몰을 위한 레시피 분석 전문가입니다.
웹페이지 텍스트에서 레시피 정보를 추출하여 고객에게 필요한 재료를 추천할 수 있도록 도와주세요.

**추출 규칙:**
1. **title**: 요리의 정확한 이름 (예: "김치찌개", "수박화채")
2. **ingredients**: 쇼핑몰에서 구매 가능한 신선식품 재료만 추출
    - name: 재료의 핵심 명사 형태로 표준화합니다. (예: '대파', '양파', '돼지고기')
    - quantity: 수량을 정확히 추출합니다. 분수('1/2')는 소수점(0.5)으로 변환하고, 수량이 명시되지 않으면 1로 간주합니다.
    - unit: 단위를 정확히 추출합니다. (예: 'g', '개', '컵', 'T', 't')
    - 포함할 것: 신선식품(육류, 채소, 과일), 구매 가능한 가공식품(두부, 면, 통조림), 양념/조미료(간장, 된장, 참기름, 다진 마늘)
    - 제외할 것: 물, 소금, 후추, 설탕, 식용유 등 사용자가 기본적으로 보유하고 있을 법한 품목
3. **instructions**: 고객이 이해하기 쉬운 조리법 요약
    - 초보자도 쉽게 이해할 수 있도록 각 단계를 상세하고 친절하게 설명합니다.
    - 각 단계는 '\n'으로 구분(중요)
    - 전문 용어보다는 일반적인 표현 사용
    - 가열 온도(예: 중불), 조리 시간(예: 5분간) 등 구체적인 정보를 포함합니다.

**출력 형식:**
반드시 다음 JSON 구조로만 응답하세요:
```json
{
    "title": "요리명",
    "ingredients": ["재료1", "재료2", "재료3"],
    "instructions": "1단계 설명\n2단계 설명\n3단계 설명"
}
```

**예시:**
입력: "돼지고기 김치찌개 레시피... 돼지고기 200g, 김치 300g, 양파 1개, 대파 2대, 두부 1모..."
출력:
```json
{
  "title": "돼지고기 김치찌개",
  "ingredients": ["돼지고기", "김치", "두부", "양파", "대파", "국간장", "고춧가루"],
  "instructions": "1. 달군 냄비에 돼지고기를 넣고 중불에서 겉면이 익을 때까지 약 3분간 볶아줍니다.\n2. 돼지고기가 익으면 김치를 넣고 5분간 함께 충분히 볶아 깊은 맛을 더해줍니다.\n3. 물을 자작하게 붓고 끓어오르면, 국간장과 고춧가루를 넣고 중불에서 10분간 더 끓여줍니다.\n4. 마지막으로 두부, 양파, 대파를 넣고 5분간 한소끔 더 끓여 완성합니다."
}
```

중요: JSON 형식 외에 다른 텍스트는 출력하지 마세요."""
    user_prompt = f"다음 웹페이지 텍스트에서 레시피 정보를 추출해줘:\n\n---\n{page_text}\n---"

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2, max_tokens=1024
    )
    
    try:
        content = json.loads(response.choices[0].message.content)
        if isinstance(content.get("ingredients"), str):
            content["ingredients"] = [item.strip() for item in content["ingredients"].split(',')]
        return content
    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(f"LLM JSON 파싱 실패: {e}")
        return {}

def _extract_recipe_url(query: str) -> Optional[str]:
    """쿼리 문자열에서 URL을 추출합니다."""
    match = re.search(r'URL:\s*(https?://[^\s]+)', query)
    if match:
        return match.group(1)
    logger.warning(f"쿼리에서 URL을 찾지 못함: {query}")
    return None

def _format_recipe_content(structured_content: Dict[str, Any]) -> str:
    """구조화된 레시피 데이터를 AIMessage에 표시할 문자열로 포맷팅합니다."""
    title = structured_content.get("title", "레시피 정보")
    ingredients = structured_content.get("ingredients", [])
    instructions = structured_content.get("instructions", "조리법 정보가 없습니다.")
    
    ingredients_text = "\n".join(f"- {ing}" for ing in ingredients[:10])
    if len(ingredients) > 10:
        ingredients_text += "\n- 등..."

    formatted_message = (
        f"**{title}**\n\n"
        f"**필요한 재료:**\n{ingredients_text}\n\n"
        f"**조리법 요약:**\n{instructions}\n\n"
        "---\n"
        "**우측 사이드바에서 추천 재료들을 바로 장바구니에 담아보세요!**"
    )
    
    return formatted_message