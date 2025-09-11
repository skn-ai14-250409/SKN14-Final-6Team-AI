import logging
import os
import json # JSON 파싱을 위해 추가
from typing import Dict, List, Any, Optional

# DB 커넥터 임포트
import mysql.connector
from mysql.connector import Error

# FastAPI 환경에 맞게 수정된 임포트
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 오류 수정을 위해 ChatState 임포트 활성화
from graph_interfaces import ChatState

logger = logging.getLogger('chatbot.product_search')

# OpenAI 클라이언트 (환경변수에서 키를 가져옴)
try:
    import openai
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        openai_client = openai.OpenAI(api_key=openai_api_key)
    else:
        openai_client = None
        logger.warning("OpenAI API key not found. Smart matching will be limited.")
except ImportError:
    openai_client = None
    logger.warning("OpenAI package not available.")

# --- DB 연결 설정 ---
DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'qook_user',
    'password': 'qook_pass',
    'database': 'qook_chatbot',
    'port': 3306
}

def get_db_connection():
    """데이터베이스 연결을 생성하고 반환합니다."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        logger.error(f"DB 연결 실패: {e}")
        return None

class ProductSearchEngine:
    """통합 상품 검색 엔진 - LLM 기반 쿼리 구조화 (NLU-driven)"""
    
    def __init__(self):
        # NLU 방식에서는 상품명 리스트를 미리 로드할 필요가 없습니다.
        logger.info("NLU-driven Product Search Engine initialized.")

    def search_products(self, query: str, slots: Dict[str, Any]) -> Dict[str, Any]:
        """상품 검색 메인 함수 - NLU 기반 동적 SQL 생성"""
        logger.info(f"NLU 검색 시작 - Query: {query}, Slots: {slots}")
        
        # 1. LLM을 사용하여 사용자 쿼리를 구조화된 필터로 변환
        search_filters = self._extract_filters_with_llm(query, slots)
        if not search_filters:
            logger.error("LLM 기반 쿼리 구조화 실패")
            return {"success": False, "candidates": [], "error": "쿼리 분석에 실패했습니다."}
        
        # 2. 구조화된 필터를 기반으로 DB에서 상품 검색
        results = self._execute_dynamic_search(search_filters)
        
        if results:
            logger.info(f"NLU 기반 검색 성공. {len(results)}개 상품 발견.")
            return {"success": True, "candidates": results, "method": "nlu_driven_search"}
        else:
            logger.warning("NLU 기반 검색 결과 없음.")
            return {"success": False, "candidates": [], "error": "검색 결과가 없습니다."}

    def _extract_filters_with_llm(self, query: str, slots: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """사용자 쿼리를 분석하여 검색에 사용할 JSON 필터를 추출합니다."""
        if not openai_client:
            # LLM 사용 불가 시, 쿼리 자체를 키워드로 사용하는 기본 필터 반환
            return {"product_keywords": [query]}

        system_prompt = """
당신은 사용자의 자연어 쇼핑 문의를 분석하여 JSON 형식의 검색 조건으로 변환하는 NLU 엔진입니다.
사용자의 질문에서 다음 항목들을 추출하세요:
- product_keywords (list of strings): 상품명과 관련된 모든 키워드. **오타를 교정하고** 동의어(예: 달걀, 계란)를 포함하세요.
- category (string): 상품 카테고리 (예: 과일, 채소, 유제품).
- is_organic (boolean): 유기농 상품 언급 여부.
- price_max (integer): 최대 가격.
- price_min (integer): 최소 가격.
- origin (string): 원산지.

규칙:
1. 반드시 유효한 JSON 객체 형식으로만 응답해야 합니다.
2. 질문에 언급되지 않은 항목은 결과 JSON에 포함하지 마세요.
3. 숫자 값에서 콤마(,)나 '원' 같은 단위는 제거하세요.
**4. 사용자가 입력한 상품명에 오타가 있다면, 가장 가능성이 높은 올바른 상품명으로 교정하여 처리하세요.**

예시 1: "2만원 이하 유기농 국산 계란 찾아줘"
{
  "product_keywords": ["계란", "달걀"],
  "is_organic": true,
  "price_max": 20000,
  "origin": "국산"
}
예시 2: "신선한 과일 뭐있어?"
{
  "category": "과일"
}
**예시 3: "맛있는 국산 사가랑 샤인머스캐 파나요?"**
**{**
** "product_keywords": ["사과", "샤인머스켓"],**
** "origin": "국산"**
**}**
"""
        # slots 정보를 사용자 쿼리에 추가하여 더 정확한 분석 유도
        full_query = query
        if slots:
            full_query += f" (추가 조건: {json.dumps(slots, ensure_ascii=False)})"

        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_query}
                ],
                temperature=0.0,
                response_format={"type": "json_object"} # JSON 출력 모드 활성화
            )
            
            extracted_json = response.choices[0].message.content
            logger.info(f"LLM 추출 필터: {extracted_json}")
            return json.loads(extracted_json)
            
        except Exception as e:
            logger.error(f"LLM 필터 추출 중 오류 발생: {e}")
            return None

    def _execute_dynamic_search(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """추출된 필터를 기반으로 동적 SQL 쿼리를 생성하고 실행합니다."""
        conn = get_db_connection()
        if not conn:
            return []

        try:
            with conn.cursor(dictionary=True) as cursor:
                # 기본 SQL 쿼리 (필요한 모든 테이블 JOIN)
                base_sql = """
                    SELECT 
                        p.product as name, p.unit_price as price, p.origin, s.stock, p.item,
                        cd.category_name as category
                    FROM product_tbl p
                    LEFT JOIN stock_tbl s ON p.product = s.product
                    LEFT JOIN category_tbl c ON p.item = c.item
                    LEFT JOIN category_definition_tbl cd ON c.category_id = cd.category_id
                """
                
                conditions = ["s.stock > 0"] # WHERE 조건 리스트
                params = [] # SQL 인젝션 방지를 위한 파라미터 리스트

                # 1. 상품 키워드 조건 추가
                if filters.get("product_keywords"):
                    keywords = filters["product_keywords"]
                    keyword_conditions = []
                    for keyword in keywords:
                        keyword_conditions.append("p.product LIKE %s")
                        params.append(f"%{keyword}%")
                    if keyword_conditions:
                        conditions.append(f"({' OR '.join(keyword_conditions)})")

                # 2. 카테고리 조건 추가
                if filters.get("category"):
                    conditions.append("cd.category_name = %s")
                    params.append(filters["category"])
                
                # 3. 유기농 조건 추가
                if filters.get("is_organic") is True:
                    conditions.append("p.organic = 'Y'")
                
                # 4. 가격 조건 추가
                if filters.get("price_max"):
                    conditions.append("CAST(p.unit_price AS UNSIGNED) <= %s")
                    params.append(int(filters["price_max"]))
                if filters.get("price_min"):
                    conditions.append("CAST(p.unit_price AS UNSIGNED) >= %s")
                    params.append(int(filters["price_min"]))
                
                # 5. 원산지 조건 추가
                if filters.get("origin"):
                    conditions.append("p.origin = %s")
                    params.append(filters["origin"])
                
                # 최종 쿼리 생성
                if conditions:
                    final_sql = base_sql + " WHERE " + " AND ".join(conditions)
                else:
                    final_sql = base_sql
                    
                final_sql += " ORDER BY p.cart_add_count DESC LIMIT 10"
                
                logger.info(f"실행될 동적 SQL: {final_sql}")
                logger.info(f"SQL 파라미터: {params}")

                cursor.execute(final_sql, params)
                results = cursor.fetchall()
                
                # 결과 포맷팅
                formatted_results = []
                for row in results:
                    formatted_results.append({
                        'sku': row.get('name'), 'name': row.get('name'),
                        'price': float(row.get('price', 0)), 'stock': int(row.get('stock', 0)),
                        'origin': row.get('origin', ''), 'category': row.get('category', ''),
                        'score': 0.8 # NLU 기반 검색 결과 신뢰도
                    })
                return formatted_results

        except Error as e:
            logger.error(f"동적 검색 실행 실패: {e}")
            return []
        finally:
            if conn and conn.is_connected():
                conn.close()

# 전역 검색 엔진 인스턴스
_search_engine = None

def get_search_engine() -> ProductSearchEngine:
    """검색 엔진 싱글톤 반환"""
    global _search_engine
    if _search_engine is None:
        _search_engine = ProductSearchEngine()
    return _search_engine

def get_popular_products(state: ChatState) -> Dict[str, Any]:
    """
    인기상품 추천 함수 - cart_add_count 기반 LLM 추천
    """
    logger.info("=== Popular Products Recommendation Started ===")
    logger.info(f"User Query: {state.query}")
    
    try:
        # 인기상품 데이터 조회
        popular_data = _get_popular_products_from_db(state.query)
        
        if popular_data["success"]:
            candidates = popular_data.get("candidates", [])
            method = popular_data.get("method")
            logger.info(f"Popular products found - Method: {method}, Results: {len(candidates)}")
            
            return {
                "search": {
                    "candidates": candidates,
                    "method": method,
                    "total_results": len(candidates),
                    "message": popular_data.get("message", "")
                }
            }
        else:
            logger.warning("No popular products found")
            return {
                "search": {
                    "candidates": [],
                    "method": "failed",
                    "error": popular_data.get("error", "인기상품을 찾지 못했습니다"),
                    "total_results": 0
                }
            }
        
    except Exception as e:
        logger.error(f"Popular products recommendation failed with error: {e}", exc_info=True)
        return {
            "search": {
                "candidates": [],
                "method": "error", 
                "error": str(e),
                "total_results": 0
            }
        }

def _get_popular_products_from_db(query: str) -> Dict[str, Any]:
    """
    데이터베이스에서 인기상품을 조회하고 LLM으로 메시지 생성
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    try:
        with conn.cursor(dictionary=True) as cursor:
            # cart_add_count 기반 인기상품 조회 (상위 10개)
            sql = """
                SELECT 
                    p.product as name,
                    p.unit_price as price,
                    p.origin,
                    s.stock,
                    p.cart_add_count,
                    c.category_id,
                    p.organic
                FROM product_tbl p
                LEFT JOIN stock_tbl s ON p.product = s.product
                LEFT JOIN category_tbl c ON p.item = c.item
                WHERE s.stock > 0
                ORDER BY p.cart_add_count DESC
                LIMIT 10
            """
            cursor.execute(sql)
            products = cursor.fetchall()
            
            if not products:
                return {"success": False, "error": "인기상품이 없습니다"}
            
            # 데이터 정제
            formatted_products = []
            for p in products:
                # None 값 처리
                p['price'] = float(p['price']) if p['price'] is not None else 0.0
                p['stock'] = int(p['stock']) if p['stock'] is not None else 0
                p['organic'] = True if p.get('organic') == 'Y' else False
                p['cart_add_count'] = p['cart_add_count'] if p['cart_add_count'] is not None else 0
                
                # 카테고리 ID를 텍스트로 변환
                cat_map = {1: '과일', 2: '채소', 3: '곡물/견과류', 4: '육류/수산', 5: '유제품', 
                           6: '냉동식품', 7: '조미료/소스', 8: '음료', 9: '베이커리', 10: '기타'}
                p['category_text'] = cat_map.get(p['category_id'], '기타')
                
                formatted_products.append({
                    'sku': p.get('name', ''),
                    'name': p.get('name', ''),
                    'price': p.get('price', 0.0),
                    'stock': p.get('stock', 0),
                    'score': min(p.get('cart_add_count', 0) / 100.0, 1.0),  # 정규화된 점수
                    'origin': p.get('origin', ''),
                    'category': p.get('category_text', ''),
                    'cart_add_count': p.get('cart_add_count', 0)
                })
            
            # LLM으로 최적화된 개인화된 메시지 생성
            message = _generate_popular_products_message(query, formatted_products)
            
            return {
                "success": True,
                "candidates": formatted_products,
                "method": "popular_products",
                "message": message
            }
            
    except Error as e:
        logger.error(f"인기상품 조회 실패: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()

def _generate_popular_products_message(query: str, products: List[Dict[str, Any]]) -> str:
    """
    LLM을 활용하여 인기상품 추천 메시지를 생성
    """
    if not openai_client or not products:
        return f"장바구니 등록 횟수가 많은 상위 {len(products)}개 인기상품을 추천드립니다."
    
    try:
        # 상품 정보를 간결하게 정리 (최대 3개만)
        product_summary = []
        for i, product in enumerate(products[:3], 1):
            product_summary.append(f"{product['name']}({product['category']})")
        
        # 최적화된 간결한 프롬프트
        system_prompt = f"""신선식품 쇼핑몰 추천 전문가로서 친근한 1-2문장 추천 메시지를 작성하세요.
인기상품: {', '.join(product_summary)}
원칙: 간결하고 친근하게, 장바구니 등록 횟수 강조"""

        user_prompt = f'"{query}" 사용자에게 인기상품 추천 메시지'

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=80,
            timeout=5
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"인기상품 메시지 생성 실패: {e}")
        # 빠른 폴백 메시지
        top_category = products[0].get('category', '') if products else ''
        return f"고객들이 가장 많이 찾는{' ' + top_category if top_category else ''} 인기상품 {len(products)}개를 준비했어요!"

def product_search_rag_text2sql(state: ChatState) -> Dict[str, Any]:
    """
    상품 검색 노드 함수 - LLM 스마트 매칭 기반
    """
    logger.info("=== Product Search Node Started ===")
    logger.info(f"User Query: {state.query}")
    logger.info(f"Rewrite: {state.rewrite}")
    logger.info(f"Slots: {state.slots}")
    
    try:
        search_engine = get_search_engine()
        query = state.rewrite.get('text') if state.rewrite.get('text') else state.query
        slots = state.slots or {}

        # enhance 단계에서 전달된 필터가 있으면 Text2SQL 호출 생략
        filters = (state.meta or {}).get('search_filters') if hasattr(state, 'meta') else None
        if filters:
            logger.info(f"Enhance 전달 필터 사용: {filters}")
            results = search_engine._execute_dynamic_search(filters)
            if results:
                search_result = {
                    "candidates": results,
                    "method": "nlu_driven_search",
                    "total_results": len(results)
                }
                return {"search": search_result}
            else:
                logger.warning("Enhance 전달 필터로 결과 없음. 내부 추출로 폴백.")

        result = search_engine.search_products(query, slots)
        
        if result["success"]:
            candidates = result.get("candidates", [])
            method = result.get("method")
            logger.info(f"Search completed - Method: {method}, Results: {len(candidates)}")
            
            search_result = {
                "candidates": candidates,
                "method": method,
                "total_results": len(candidates)
            }
            
            if result.get("matched_products"):
                search_result["matched_products"] = result["matched_products"]
            
            return {"search": search_result}
        else:
            logger.warning("Search failed")
            return {
                "search": {
                    "candidates": [],
                    "method": "failed",
                    "error": result.get("error", "검색에 실패했습니다"),
                    "total_results": 0
                }
            }
        
    except Exception as e:
        logger.error(f"Product search failed with error: {e}", exc_info=True)
        return {
            "search": {
                "candidates": [],
                "method": "error",
                "error": str(e),
                "total_results": 0
            }
        }
