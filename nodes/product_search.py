import logging
import os
import re
import json
from typing import Dict, List, Any, Optional

# DB 커넥터 및 커넥션 풀 임포트
from mysql.connector import Error
from mysql.connector.pooling import MySQLConnectionPool

# FastAPI 환경에 맞게 수정된 임포트
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_interfaces import ChatState

logger = logging.getLogger('chatbot.product_search')

# 조건부 임포트 - scikit-learn
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not available. Using simple text matching.")

# OpenAI 클라이언트 (환경변수에서 키를 가져옴)
try:
    import openai
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        openai_client = openai.OpenAI(api_key=openai_api_key)
    else:
        openai_client = None
        logger.warning("OpenAI API key not found. Text2SQL will be limited.")
except ImportError:
    openai_client = None
    logger.warning("OpenAI package not available.")

# --- DB 연결 설정 (환경 변수에서 로드) ---
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'user': os.getenv('DB_USER', 'qook_user'),
    'password': os.getenv('DB_PASS', 'qook_pass'),
    'database': os.getenv('DB_NAME', 'qook_chatbot'),
    'port': int(os.getenv('DB_PORT', 3306))
}

# --- DB 커넥션 풀 생성 ---
try:
    db_connection_pool = MySQLConnectionPool(pool_name="qook_pool",
                                             pool_size=5,
                                             **DB_CONFIG)
    logger.info("DB 커넥션 풀 생성 성공")
except Error as e:
    db_connection_pool = None
    logger.error(f"DB 커넥션 풀 생성 실패: {e}")

def get_db_connection():
    """데이터베이스 커넥션 풀에서 커넥션을 가져옵니다."""
    if db_connection_pool:
        try:
            return db_connection_pool.get_connection()
        except Error as e:
            logger.error(f"DB 커넥션 풀에서 연결 가져오기 실패: {e}")
            return None
    logger.error("DB 커넥션 풀이 초기화되지 않았습니다.")
    return None

def _format_product_from_db(p: Dict[str, Any]) -> Dict[str, Any]:
    """DB에서 가져온 상품 딕셔너리를 표준 포맷으로 정제합니다."""
    p['price'] = float(p.get('price', 0.0) or 0.0)
    p['stock'] = int(p.get('stock', 0) or 0)
    p['organic'] = p.get('organic') == 'Y'
    p['cart_add_count'] = p.get('cart_add_count', 0) or 0

    cat_map = {1: '과일', 2: '채소', 3: '곡물/견과류', 4: '육류/수산', 5: '유제품',
                6: '냉동식품', 7: '조미료/소스', 8: '음료', 9: '베이커리', 10: '기타'}
    p['category_text'] = cat_map.get(p.get('category_id'), '기타')
    
    # ## 변경된 부분: p.get('item', '')을 search_text에 추가
    p['search_text'] = f"{p.get('name', '')} {p.get('item', '')} {p.get('origin', '')} {p['category_text']} {'유기농' if p['organic'] else ''}"
    return p

class ProductSearchEngine:
    """통합 상품 검색 엔진"""
    
    def __init__(self):
        self.product_data = []
        self.tfidf_vectorizer = None
        self.tfidf_matrix = None
        self.db_schema = self._get_db_schema()
        self._load_data_from_db()
    
    def _get_db_schema(self) -> str:
        # ## 변경된 부분: 새로운 setup.sql의 스키마 정보를 반영
        return """
        CREATE TABLE product_tbl (
            product VARCHAR(45) PRIMARY KEY,
            item VARCHAR(45) NOT NULL,
            organic VARCHAR(45),
            unit_price VARCHAR(45) NOT NULL,
            origin VARCHAR(45),
            cart_add_count INT DEFAULT 0,
            FOREIGN KEY (item) REFERENCES category_tbl(item)
        );
        CREATE TABLE stock_tbl (
            product VARCHAR(45) PRIMARY KEY,
            stock VARCHAR(45) NOT NULL,
            FOREIGN KEY (product) REFERENCES product_tbl(product) ON DELETE CASCADE
        );
        CREATE TABLE category_tbl (
            item VARCHAR(45) PRIMARY KEY,
            category_id INT,
            FOREIGN KEY (category_id) REFERENCES category_definition_tbl(category_id)
        );
        CREATE TABLE category_definition_tbl (
            category_id INT PRIMARY KEY,
            category_name VARCHAR(45) NOT NULL
        );
        """
    
    def _load_data_from_db(self):
        """DB에서 상품 데이터를 로드하고 RAG 검색을 위한 인덱스를 구축합니다."""
        conn = get_db_connection()
        if not conn:
            logger.error("DB 연결 실패로 상품 데이터를 로드할 수 없습니다.")
            return

        try:
            with conn.cursor(dictionary=True) as cursor:
                # ## 변경된 부분: item_tbl JOIN을 제거하고 새로운 구조에 맞게 SQL 수정
                sql = """
                    SELECT 
                        p.product as name,
                        p.unit_price as price,
                        p.origin,
                        p.organic,
                        p.item,
                        s.stock,
                        c.category_id
                    FROM product_tbl p
                    LEFT JOIN stock_tbl s ON p.product = s.product
                    LEFT JOIN category_tbl c ON p.item = c.item
                """
                cursor.execute(sql)
                products = cursor.fetchall()
                self.product_data = [_format_product_from_db(p) for p in products]
                logger.info(f"데이터베이스에서 {len(self.product_data)}개의 상품 정보를 로드했습니다.")
            
            if SKLEARN_AVAILABLE and self.product_data:
                texts = [product['search_text'] for product in self.product_data]
                self.tfidf_vectorizer = TfidfVectorizer(max_features=1000, ngram_range=(1, 2))
                self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(texts)
                logger.info("TF-IDF 인덱스를 성공적으로 빌드했습니다.")

        except Error as e:
            logger.error(f"DB에서 상품 데이터 로드 실패: {e}")
        finally:
            if conn and conn.is_connected():
                conn.close()

    def search_products(self, query: str, slots: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"상품 검색 시작 - Query: {query}, Slots: {slots}")
        
        if openai_client:
            sql_query = self._generate_sql(query, slots)
            if sql_query:
                sql_result = self._execute_sql(sql_query)
                if sql_result:
                    logger.info("Text2SQL 검색 성공")
                    return {"success": True, "candidates": sql_result, "method": "text2sql", "sql_query": sql_query}
        
        logger.info("Text2SQL 실패 또는 미사용, RAG 검색으로 전환")
        rag_result = self._try_rag_search(query, slots)
        if rag_result:
            logger.info("RAG 검색 성공")
            return {"success": True, "candidates": rag_result, "method": "rag"}
        
        logger.warning("Text2SQL 및 RAG 검색 모두 실패")
        return {"success": False, "candidates": [], "method": "failed", "error": "검색 결과가 없습니다."}

    def _generate_sql(self, query: str, slots: Dict[str, Any]) -> Optional[str]:
        if not openai_client:
            logger.warning("OpenAI client 없음, SQL 생성 불가")
            return None
        try:
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(query, slots)
            
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            sql_response = response.choices[0].message.content.strip()
            sql_query = self._extract_sql_from_response(sql_response)
            
            if sql_query and self._validate_sql(sql_query):
                logger.info(f"SQL 생성 성공: {sql_query}")
                return sql_query
            else:
                logger.warning(f"SQL 검증 실패 또는 빈 쿼리: {sql_response}")
                return None
                
        except Exception as e:
            logger.error(f"SQL 생성 중 오류 발생: {e}")
            return None
    
    def _build_system_prompt(self) -> str:
        # ## 변경된 부분: LLM 프롬프트의 스키마와 예시 쿼리를 새 DB 구조에 맞게 전면 수정
        return f"""당신은 신선식품 쇼핑몰의 SQL 전문가입니다. 
사용자의 자연어 쿼리를 정확한 MySQL SQL로 변환하세요.

# 데이터베이스 스키마:
{self.db_schema}

# 카테고리 매핑:
1: 과일, 2: 채소, 3: 곡물/견과류, 4: 육류/수산, 5: 유제품, 6: 냉동식품, 7: 조미료/소스, 8: 음료, 9: 베이커리, 10: 기타

# Few-shot 예시들:

## 기본 검색 예시

예시 1:
사용자 쿼리: "사과 찾아줘"
사고 과정: '사과'라는 상품을 찾는 요청 -> product_tbl에서 상품명(product) 또는 품목(item)에 '사과'가 포함된 항목 검색 -> 가격, 원산지, 재고 정보 함께 조회
SQL: SELECT p.product, p.unit_price, p.origin, s.stock FROM product_tbl p LEFT JOIN stock_tbl s ON p.product = s.product WHERE p.product LIKE '%사과%' OR p.item LIKE '%사과%';

예시 2:
사용자 쿼리: "3000원 이하 과일 추천해줘"
사고 과정: 가격 조건(3000원 이하) + 카테고리(과일=1) -> product_tbl과 category_tbl 조인 -> p.item과 c.item을 연결 -> 가격 조건 적용
SQL: SELECT DISTINCT p.product, p.unit_price, p.origin, s.stock FROM product_tbl p LEFT JOIN stock_tbl s ON p.product = s.product LEFT JOIN category_tbl c ON p.item = c.item WHERE CAST(p.unit_price AS UNSIGNED) <= 3000 AND c.category_id = 1;

예시 3:
사용자 쿼리: "유기농 채소 있어?"
사고 과정: 유기농(organic='Y') + 채소(category_id=2) -> product_tbl의 organic 필드와 category_tbl 조인
SQL: SELECT p.product, p.unit_price, p.origin, s.stock FROM product_tbl p LEFT JOIN stock_tbl s ON p.product = s.product LEFT JOIN category_tbl c ON p.item = c.item WHERE p.organic = 'Y' AND c.category_id = 2;

예시 4:
사용자 쿼리: "재고 많은 상품 보여줘"
사고 과정: 재고량 기준 정렬 -> stock_tbl의 stock 컬럼으로 내림차순 정렬
SQL: SELECT p.product, p.unit_price, p.origin, s.stock FROM product_tbl p LEFT JOIN stock_tbl s ON p.product = s.product ORDER BY CAST(s.stock AS UNSIGNED) DESC LIMIT 10;

## 고급 및 개인화 검색 예시

예시 5 (인기 상품):
사용자 쿼리: "요즘 제일 잘 나가는 상품이 뭐야?"
사고 과정: 인기 상품은 장바구니 추가 횟수(cart_add_count)가 높은 상품 -> product_tbl의 cart_add_count를 기준으로 내림차순 정렬
SQL: SELECT p.product, p.unit_price, p.origin, s.stock FROM product_tbl p LEFT JOIN stock_tbl s ON p.product = s.product ORDER BY p.cart_add_count DESC LIMIT 5;

예시 6 (다중 조건 결합):
사용자 쿼리: "만원 이하로 살 수 있는 국산 유기농 과일 보여줘"
사고 과정: 여러 조건 결합 -> 가격(<=10000), 원산지('국내산'), 유기농('Y'), 카테고리(과일=1) -> 모든 조건을 AND로 연결
SQL: SELECT p.product, p.unit_price, p.origin, s.stock FROM product_tbl p LEFT JOIN stock_tbl s ON p.product = s.product LEFT JOIN category_tbl c ON p.item = c.item WHERE CAST(p.unit_price AS UNSIGNED) <= 10000 AND p.origin = '국내산' AND p.organic = 'Y' AND c.category_id = 1;

예시 7 (개인화 - 알러지):
사용자 쿼리: "user001입니다. 견과류 알러지가 있는데, 먹을만한 거 추천해주세요."
사고 과정: 사용자 정보(user_id='user001')와 알러지 정보('견과류') 확인 -> user_detail_tbl JOIN -> 알러지 정보를 바탕으로 상품명과 품목에서 해당 키워드를 제외 (`NOT LIKE`)
SQL: SELECT p.product, p.unit_price, p.origin FROM product_tbl p LEFT JOIN stock_tbl s ON p.product = s.product WHERE s.stock > 0 AND p.product NOT LIKE '%견과류%' AND p.item NOT LIKE '%아몬드%' AND p.item NOT LIKE '%호두%' AND p.item NOT LIKE '%땅콩%' ORDER BY p.cart_add_count DESC LIMIT 5;

예시 8 (개인화 - 비건):
사용자 쿼리: "비건을 위한 상품을 찾고 있어요."
사고 과정: 비건 사용자는 육류/수산(4), 유제품(5) 카테고리를 피해야 함 -> 카테고리 ID를 `NOT IN`으로 제외
SQL: SELECT p.product, p.unit_price, p.origin, s.stock FROM product_tbl p LEFT JOIN stock_tbl s ON p.product = s.product LEFT JOIN category_tbl c ON p.item = c.item WHERE c.category_id NOT IN (4, 5) ORDER BY p.cart_add_count DESC LIMIT 10;

예시 9 (유의어/확장 검색):
사용자 쿼리: "해산물 좀 찾아줘"
사고 과정: 사용자가 '해산물'을 찾고 있다. '해산물'은 '수산' 품목을 포함하는 개념이며, '육류/수산' 카테고리(ID=4)에 속한다. 따라서 category_id = 4인 상품들을 검색한다.
SQL: SELECT p.product, p.unit_price, p.origin, s.stock FROM product_tbl p LEFT JOIN stock_tbl s ON p.product = s.product LEFT JOIN category_tbl c ON p.item = c.item WHERE c.category_id = 4 ORDER BY p.cart_add_count DESC LIMIT 10;

예시 10 (의도 기반 검색):
사용자 쿼리: "아침에 간단하게 먹을만한 거 있어?"
사고 과정: 사용자가 '아침 식사'를 찾고 있다. 아침에는 보통 '빵'이나 '요거트', '우유' 등을 먹는다. 이는 '베이커리' 카테고리(ID=9)와 '유제품' 카테고리(ID=5)에 해당한다. 두 카테고리의 인기 상품을 추천한다.
SQL: SELECT p.product, p.unit_price, p.origin, s.stock FROM product_tbl p LEFT JOIN stock_tbl s ON p.product = s.product LEFT JOIN category_tbl c ON p.item = c.item WHERE c.category_id IN (5, 9) ORDER BY p.cart_add_count DESC LIMIT 10;

# 중요 규칙:
1. 항상 `LEFT JOIN`을 사용하여 모든 관련 테이블을 연결하세요.
2. `LIKE` 검색 시 `'%키워드%'` 패턴을 사용하세요.
3. 가격/재고 비교 시 `CAST(컬럼 AS UNSIGNED)` 사용하세요.
4. 카테고리 검색 시 `category_id` 컬럼을 사용하고 숫자 매핑을 정확히 사용하세요.
5. `category_tbl` 조인 시 `p.item = c.item` 조건을 사용하세요.
6. 유기농 검색 시 `product_tbl`의 `organic = 'Y'` 조건을 사용하세요.
7. 응답 형식: `SQL: [쿼리문]` 으로만 답하세요.
8. 인기 상품 문의는 `product_tbl`의 `cart_add_count`를 기준으로 `DESC` 정렬하세요.
9. 개인화 질문(알러지, 비건 등)이 오면 `user_detail_tbl`을 참조하여 `NOT LIKE` 또는 `NOT IN`으로 조건을 제외하세요.
10. 여러 조건이 동시에 주어지면 `AND`로 모두 연결하세요.
11. 사용자 정보는 `userinfo_tbl`, `user_detail_tbl`에 있으며, `user_id`로 JOIN 가능합니다.
12. 사용자의 키워드가 명확한 상품이나 카테고리와 일치하지 않을 경우, **단어의 의미를 추론하여 가장 관련성 높은 카테고리를 검색**하세요. (예: '해산물' -> '수산' -> `category_id=4`, '아침식사' -> '베이커리', '유제품' -> `category_id IN (5, 9)`)
"""
    

    def _build_user_prompt(self, query: str, slots: Dict[str, Any]) -> str:
        prompt_parts = [f"사용자 쿼리: \"{query}\""]
        if slots:
            prompt_parts.append("추출된 정보:")
            if slots.get('category'): prompt_parts.append(f"- 카테고리: {slots['category']}")
            if slots.get('price_cap'): prompt_parts.append(f"- 최대 가격: {slots['price_cap']}원")
            if slots.get('organic'): prompt_parts.append("- 유기농 선호")
        prompt_parts.append("\n위 정보를 바탕으로 SQL을 생성해주세요.")
        prompt_parts.append("사고 과정을 먼저 설명한 후, SQL을 제공하세요.")
        return "\n".join(prompt_parts)
    
    def _extract_sql_from_response(self, response: str) -> Optional[str]:
        match = re.search(r'SQL:\s*(.+?)(?:\n|$|;)', response, re.IGNORECASE | re.DOTALL)
        if match: return match.group(1).strip()
        match = re.search(r'```sql\s*(.+?)\s*```', response, re.IGNORECASE | re.DOTALL)
        if match: return match.group(1).strip().rstrip(';')
        match = re.search(r'(SELECT\s+.+)', response, re.IGNORECASE | re.DOTALL)
        if match: return match.group(1).strip().rstrip(';')
        return None
    
    def _validate_sql(self, sql: str) -> bool:
        if not sql or not sql.strip(): return False
        sql_upper = sql.upper()
        if not sql_upper.strip().startswith('SELECT'): return False
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE']
        if any(keyword in sql_upper for keyword in dangerous_keywords):
            logger.warning(f"위험한 SQL 키워드 감지")
            return False
        if 'PRODUCT_TBL' not in sql_upper:
            logger.warning("product_tbl이 SQL에 포함되지 않음")
            return False
        return True

    def _execute_sql(self, sql: str) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        if not conn: return []
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(sql)
                results = cursor.fetchall()
                formatted_results = []
                for row in results:
                    formatted_results.append({
                        'sku': row.get('product'), 'name': row.get('product'),
                        'price': float(row.get('unit_price', 0.0) or 0.0), 
                        'stock': int(row.get('stock', 0) or 0),
                        'origin': row.get('origin'), 'score': 0.9
                    })
                return formatted_results
        except Error as e:
            logger.error(f"SQL 실행 실패: {e}, SQL: {sql}")
            return []
        finally:
            if conn and conn.is_connected(): conn.close()

    def _try_rag_search(self, query: str, slots: Dict[str, Any]) -> List[Dict[str, Any]]:
        enhanced_query = self._enhance_query(query, slots)
        if SKLEARN_AVAILABLE and self.tfidf_vectorizer and self.tfidf_matrix is not None:
            candidates = self._tfidf_search(enhanced_query)
        else:
            candidates = self._simple_keyword_search(enhanced_query)
        filtered_candidates = [c for c in candidates if self._passes_slot_filters(c, slots)]
        return self._format_candidates(filtered_candidates[:20])
    
    def _enhance_query(self, query: str, slots: Dict[str, Any]) -> str:
        parts = [query]
        if slots.get('category'): parts.append(slots['category'])
        if slots.get('organic'): parts.append("유기농")
        return ' '.join(parts)
    
    def _tfidf_search(self, query: str) -> List[Dict[str, Any]]:
        query_vector = self.tfidf_vectorizer.transform([query])
        similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
        top_indices = similarities.argsort()[-20:][::-1]
        results = []
        for idx in top_indices:
            if similarities[idx] > 0:
                product = self.product_data[idx].copy()
                product['similarity_score'] = float(similarities[idx])
                results.append(product)
        return results
    
    def _simple_keyword_search(self, query: str) -> List[Dict[str, Any]]:
        keywords = query.lower().split()
        results = []
        for product in self.product_data:
            score = sum(2.0 if keyword in product.get('name', '').lower() else 1.0 for keyword in keywords if keyword in product.get('search_text', '').lower())
            if score > 0:
                product_copy = product.copy()
                product_copy['similarity_score'] = score
                results.append(product_copy)
        results.sort(key=lambda x: x['similarity_score'], reverse=True)
        return results[:20]
    
    def _passes_slot_filters(self, product: Dict[str, Any], slots: Dict[str, Any]) -> bool:
        if slots.get('price_cap') and product.get('price', 0.0) > float(slots['price_cap']): return False
        if product.get('stock', 0) <= 0: return False
        if slots.get('organic') and not product.get('organic', False): return False
        if slots.get('category') and slots['category'] != product.get('category_text', ''): return False
        return True
    
    def _format_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{
            'sku': c.get('name', ''), 'name': c.get('name', ''),
            'price': c.get('price', 0.0), 'stock': c.get('stock', 0),
            'score': c.get('similarity_score', 0.5), 'origin': c.get('origin', ''),
            'category': c.get('category_text', '')
        } for c in candidates]

_search_engine = None

def get_search_engine() -> ProductSearchEngine:
    global _search_engine
    if _search_engine is None: _search_engine = ProductSearchEngine()
    return _search_engine

def get_popular_products(state: ChatState) -> Dict[str, Any]:
    logger.info("=== Popular Products Recommendation Started ===")
    try:
        popular_data = _get_popular_products_from_db(state.query)
        if popular_data["success"]:
            return {"search": {**popular_data, "total_results": len(popular_data.get("candidates", []))}}
        else:
            return {"search": {"candidates": [], "method": "failed", "error": popular_data.get("error"), "total_results": 0}}
    except Exception as e:
        logger.error(f"Popular products recommendation failed: {e}", exc_info=True)
        return {"search": {"candidates": [], "method": "error", "error": str(e), "total_results": 0}}

def _get_popular_products_from_db(query: str) -> Dict[str, Any]:
    conn = get_db_connection()
    if not conn: return {"success": False, "error": "데이터베이스 연결 실패"}
    try:
        with conn.cursor(dictionary=True) as cursor:
            # ## 변경된 부분: item_tbl JOIN 제거, p.organic 직접 참조
            sql = """
                SELECT 
                    p.product as name, p.unit_price as price, p.origin, p.organic,
                    s.stock, p.cart_add_count, c.category_id
                FROM product_tbl p
                LEFT JOIN stock_tbl s ON p.product = s.product
                LEFT JOIN category_tbl c ON p.item = c.item
                WHERE s.stock > 0 ORDER BY p.cart_add_count DESC LIMIT 10
            """
            cursor.execute(sql)
            products = cursor.fetchall()
            if not products: return {"success": False, "error": "인기상품이 없습니다"}
            
            processed_products = [_format_product_from_db(p) for p in products]
            
            formatted_candidates = [{
                'sku': p.get('name', ''), 'name': p.get('name', ''),
                'price': p.get('price', 0.0), 'stock': p.get('stock', 0),
                'score': min(p.get('cart_add_count', 0) / 100.0, 1.0),
                'origin': p.get('origin', ''), 'category': p.get('category_text', ''),
                'cart_add_count': p.get('cart_add_count', 0)
            } for p in processed_products]
            
            message = _generate_popular_products_message(query, formatted_candidates)
            return {"success": True, "candidates": formatted_candidates, "method": "popular_products", "message": message}
    except Error as e:
        logger.error(f"인기상품 조회 실패: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if conn and conn.is_connected(): conn.close()

def _generate_popular_products_message(query: str, products: List[Dict[str, Any]]) -> str:
    if not openai_client or not products:
        return f"장바구니 등록 횟수가 많은 상위 {len(products)}개 인기상품을 추천드립니다."
    try:
        summary = ', '.join([f"{p['name']}({p['category']})" for p in products[:3]])
        system_prompt = f"신선식품 쇼핑몰 추천 전문가로서 친근한 1-2문장 추천 메시지를 작성하세요.\n인기상품: {summary}\n원칙: 간결하고 친근하게, 장바구니 등록 횟수 강조"
        user_prompt = f'"{query}" 사용자에게 인기상품 추천 메시지'
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.3, max_tokens=80, timeout=5
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"인기상품 메시지 생성 실패: {e}")
        top_category = products[0].get('category', '') if products else ''
        return f"고객들이 가장 많이 찾는{' ' + top_category if top_category else ''} 인기상품 {len(products)}개를 준비했어요!"

def product_search_rag_text2sql(state: ChatState) -> Dict[str, Any]:
    logger.info("=== Product Search Node Started ===")
    try:
        search_engine = get_search_engine()
        query = state.rewrite.get('text') or state.query
        slots = state.slots or {}
        
        # 1. Text2SQL 또는 RAG를 통해 1차 검색 수행
        result = search_engine.search_products(query, slots)
        
        if result["success"] and result.get("candidates"):
            
            # 2. <<-- 새로 추가된 부분 -->>
            # 1차 검색 결과를 LLM을 통해 연관성 필터링 수행
            initial_candidates = result["candidates"]
            
            # 전역 openai_client를 가져와서 사용
            global openai_client 
            
            filtered_candidates = _filter_products_with_llm(initial_candidates, query, openai_client)
            
            # 필터링된 결과로 업데이트
            result["candidates"] = filtered_candidates
            # <<---------------------->>
            
            search_result = {
                "candidates": result.get("candidates", []),
                "method": result.get("method"),
                # 필터링된 결과의 개수로 total_results 업데이트
                "total_results": len(result.get("candidates", [])) 
            }
            if result.get("sql_query"): search_result["sql"] = result["sql_query"]
            return {"search": search_result}
        else:
            return {"search": {"candidates": [], "method": "failed", "error": result.get("error"), "total_results": 0}}
            
    except Exception as e:
        logger.error(f"Product search failed with error: {e}", exc_info=True)
        return {"search": {"candidates": [], "method": "error", "error": str(e), "total_results": 0}}
    
def _filter_products_with_llm(
    products: List[Dict[str, Any]],
    query: str,
    llm_client: Optional[openai.OpenAI]
) -> List[Dict[str, Any]]:
    """
    LLM을 사용하여 사용자의 쿼리와 1차 검색된 상품 목록의 연관성을 판단하고,
    관련 없는 상품들을 정밀하게 필터링합니다.
    """
    # LLM 클라이언트가 없거나, 필터링할 상품이 1개 이하면 필터링을 건너뜁니다.
    if not llm_client or not products or len(products) <= 1:
        return products

    # LLM에 전달할 간단한 상품 정보 목록 생성 (이름과 카테고리만)
    candidate_info = [
        {"name": p.get("name"), "category": p.get("category")}
        for p in products
    ]

    logger.info(f"LLM 정밀 필터링 시작. Query: '{query}', Candidates: {[p['name'] for p in products]}")

    # LLM에게 전달할 시스템 프롬프트 정의 (상품 중심 필터링으로 개선)
    system_prompt = """
당신은 사용자의 쇼핑 쿼리 의도를 정확히 파악하여, 관련 없는 검색 결과를 제거하는 상품 필터링 전문가입니다.
당신의 임무는 주어진 쿼리와 상품 목록을 분석하여, 사용자의 의도에 부합하는 상품만 필터링하는 것입니다.

**필터링 규칙:**

1.  **쿼리 유형 분석:** 먼저 사용자의 쿼리가 '특정 상품'을 찾는지, '광범위한 카테고리'를 찾는지 분석합니다.
    * `특정 상품 쿼리`: "닭다리", "신라면", "유기농 우유"
    * `광범위한 카테고리 쿼리`: "해산물", "과일", "고기"

2.  **'특정 상품 쿼리' 처리:**
    * **1순위 (정확한 일치):** 상품 목록에 쿼리와 정확히 일치하는 상품이 있으면 **반드시 포함**합니다.
    * **2순위 (유사/대체 상품):** 정확히 일치하는 상품이 없을 경우, 주재료가 동일한 **가장 유사한 상품을 포함**합니다.
        * 쿼리 "닭다리" -> 목록에 "닭가슴살"이 있다면, 이는 주재료('닭')가 동일한 유사 상품이므로 **포함**합니다.
        * 쿼리 "사과" -> 목록에 "사과 주스"가 있다면, 이는 가공품이므로 사용자의 의도(원물 과일)와 다를 가능성이 높아 **제외**합니다.

3.  **'광범위한 카테고리 쿼리' 처리:**
    * 쿼리가 "해산물"이라면, 상품 목록에 있는 '고등어', '오징어', '새우' 등 **해산물 카테고리에 속하는 모든 상품을 포함**합니다.
    * 쿼리가 "고기"라면, '소고기', '돼지고기', '닭고기' 등을 모두 포함합니다.

4.  **제외 조건:** "돼지고기 빼고"와 같은 명시적인 제외 조건은 반드시 준수합니다.

5.  **최종 출력:** 위 규칙에 따라 필터링된 상품들의 `name`만을 리스트에 담아 아래 JSON 형식으로 반환합니다. 다른 설명은 절대 추가하지 마세요.
"""

    user_prompt = f"""
# 사용자 쿼리
"{query}"

# 1차 검색된 상품 목록
{json.dumps(candidate_info, ensure_ascii=False, indent=2)}

# 지시
위 필터링 규칙에 따라 쿼리의 의도에 부합하는 상품들의 `name`을 리스트로 추출하여 아래 JSON 형식으로만 응답해주세요.
"""

    # LLM에게 전달할 사용자 프롬프트 생성 (상품 목록 전체 전달)
    user_prompt = f"""
# 사용자 쿼리
"{query}"

# 1차 검색된 상품 목록
{json.dumps(candidate_info, ensure_ascii=False, indent=2)}

# 지시
위 쿼리의 의도에 **정확히 부합하는** 상품들의 `name`을 리스트로 추출하여 아래 JSON 형식으로만 응답해주세요.

{{
  "relevant_products": ["상품명1", "상품명2", ...]
}}
"""

    try:
        response = llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        response_data = json.loads(response.choices[0].message.content)
        relevant_names = response_data.get("relevant_products", [])
        
        # relevant_names가 리스트 형태인지 확인
        if not isinstance(relevant_names, list):
            logger.warning("LLM이 유효한 상품 이름 리스트를 반환하지 않았습니다. 필터링을 건너뜁니다.")
            return products

        logger.info(f"LLM 필터링 판단 결과 (유효 상품): {relevant_names}")

        # LLM이 선택한 이름들을 set으로 변환하여 검색 효율성 증대
        relevant_names_set = set(relevant_names)
        
        # 원본 상품 목록에서 LLM이 선택한 상품들만 필터링
        filtered_products = [
            p for p in products if p.get("name") in relevant_names_set
        ]

        # 필터링 후 결과가 없으면, 안전장치로 원본 반환
        if not filtered_products:
            logger.warning("LLM 정밀 필터링 후 모든 상품이 제외되었습니다. 원본 결과를 반환합니다.")
            return products
            
        return filtered_products

    except (json.JSONDecodeError, AttributeError, Exception) as e:
        logger.error(f"LLM 정밀 필터링 중 오류 발생: {e}. 필터링 없이 원본 반환.")
        return products
