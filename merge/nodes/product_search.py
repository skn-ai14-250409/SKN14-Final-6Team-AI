"""
product_search.py — C팀: 상품 검색 (RAG + Text2SQL 통합)

C팀의 책임:
- Text2SQL 우선 시도, 실패 시 RAG 폴백
- 상품 검색 결과 표준화
- 검색 결과 점수 계산 및 랭킹
"""

import logging
import os
import re
import pickle
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# FastAPI 환경에 맞게 수정된 임포트
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_interfaces import ChatState

logger = logging.getLogger('chatbot.product_search')

# 조건부 임포트 - scikit-learn
try:
    import numpy as np
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

@dataclass
class SearchResult:
    """검색 결과를 담는 데이터 클래스"""
    success: bool
    candidates: List[Dict[str, Any]]
    method: str
    error: Optional[str] = None
    sql_query: Optional[str] = None
    search_query: Optional[str] = None

class ProductSearchEngine:
    """통합 상품 검색 엔진"""
    
    def __init__(self):
        self.vector_store_dir = os.path.join(os.path.dirname(__file__), '..', 'var', 'index')
        self.product_data = []
        self.tfidf_vectorizer = None
        self.tfidf_matrix = None
        self.db_schema = self._get_db_schema()
        
        self._ensure_directories()
        self._load_or_create_mock_data()
    
    def _ensure_directories(self):
        """필요한 디렉토리 생성"""
        os.makedirs(self.vector_store_dir, exist_ok=True)
    
    def _get_db_schema(self) -> str:
        """데이터베이스 스키마 정보"""
        return """
        CREATE TABLE product_tbl (
            name VARCHAR(45) PRIMARY KEY,
            unit_price VARCHAR(45) NOT NULL,
            origin VARCHAR(45)
        );
        
        CREATE TABLE item_tbl (
            product VARCHAR(45) NOT NULL,
            item VARCHAR(45) PRIMARY KEY,
            organic VARCHAR(45),
            FOREIGN KEY (product) REFERENCES product_tbl(product)
        );
        
        CREATE TABLE stock_tbl (
            product VARCHAR(45) PRIMARY KEY,
            stock VARCHAR(45) NOT NULL,
            FOREIGN KEY (product) REFERENCES product_tbl(product)
        );
        
        CREATE TABLE category_tbl (
            item VARCHAR(45) PRIMARY KEY,
            category INT
        );
        """
    
    def _load_or_create_mock_data(self):
        """목 데이터 로드 또는 생성"""
        index_file = os.path.join(self.vector_store_dir, 'mock_products.pkl')
        
        if os.path.exists(index_file):
            try:
                with open(index_file, 'rb') as f:
                    data = pickle.load(f)
                    self.product_data = data['products']
                    self.tfidf_vectorizer = data.get('tfidf_vectorizer')
                    self.tfidf_matrix = data.get('tfidf_matrix')
                logger.info(f"Loaded {len(self.product_data)} products from cache")
                return
            except Exception as e:
                logger.warning(f"Failed to load cached data: {e}")
        
        # 목 데이터 생성
        self.product_data = [
            {
                'name': '유기농 사과',
                'price': 3000.0,
                'origin': '경북 안동',
                'stock': 50,
                'category': '과일',
                'organic': True,
                'search_text': '유기농 사과 경북 안동 과일'
            },
            {
                'name': '바나나',
                'price': 2500.0,
                'origin': '필리핀',
                'stock': 30,
                'category': '과일',
                'organic': False,
                'search_text': '바나나 필리핀 과일'
            },
            {
                'name': '유기농 당근',
                'price': 1800.0,
                'origin': '제주',
                'stock': 25,
                'category': '채소',
                'organic': True,
                'search_text': '유기농 당근 제주 채소'
            },
            {
                'name': '양상추',
                'price': 1500.0,
                'origin': '경기',
                'stock': 40,
                'category': '채소',
                'organic': False,
                'search_text': '양상추 경기 채소'
            },
            {
                'name': '토마토',
                'price': 2200.0,
                'origin': '전남',
                'stock': 35,
                'category': '채소',
                'organic': False,
                'search_text': '토마토 전남 채소'
            }
        ]
        
        # TF-IDF 인덱스 생성
        if SKLEARN_AVAILABLE:
            texts = [product['search_text'] for product in self.product_data]
            self.tfidf_vectorizer = TfidfVectorizer(
                max_features=1000,
                ngram_range=(1, 2)
            )
            self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(texts)
        
        # 캐시 저장
        try:
            with open(index_file, 'wb') as f:
                pickle.dump({
                    'products': self.product_data,
                    'tfidf_vectorizer': self.tfidf_vectorizer,
                    'tfidf_matrix': self.tfidf_matrix
                }, f)
            logger.info("Mock product data cached successfully")
        except Exception as e:
            logger.warning(f"Failed to cache mock data: {e}")
    
    def search_products(self, query: str, slots: Dict[str, Any]) -> SearchResult:
        """상품 검색 메인 함수"""
        logger.info(f"Product search started - Query: {query}, Slots: {slots}")
        
        # 1차 시도: Text2SQL
        if openai_client:
            sql_result = self._try_text2sql(query, slots)
            if sql_result.success and sql_result.candidates:
                logger.info("Text2SQL search succeeded")
                return SearchResult(
                    success=True,
                    candidates=sql_result.candidates,
                    method="text2sql",
                    sql_query=sql_result.sql_query
                )
        
        # 2차 시도: RAG 폴백
        logger.info("Falling back to RAG search")
        rag_result = self._try_rag_search(query, slots)
        
        if rag_result.success:
            logger.info("RAG search succeeded")
            return SearchResult(
                success=True,
                candidates=rag_result.candidates,
                method="rag",
                search_query=rag_result.search_query
            )
        
        # 둘 다 실패
        logger.warning("Both Text2SQL and RAG search failed")
        return SearchResult(
            success=False,
            candidates=[],
            method="failed",
            error="검색 결과가 없습니다"
        )
    
    def _try_text2sql(self, query: str, slots: Dict[str, Any]) -> SearchResult:
        """Text2SQL 검색 시도"""
        try:
            # SQL 생성
            sql_query = self._generate_sql(query, slots)
            if not sql_query:
                return SearchResult(success=False, candidates=[], method="text2sql_failed")
            
            # Mock SQL 실행 (실제 DB 연결 없이 시뮬레이션)
            mock_results = self._execute_mock_sql(sql_query, query, slots)
            
            return SearchResult(
                success=True,
                candidates=mock_results,
                method="text2sql",
                sql_query=sql_query
            )
            
        except Exception as e:
            logger.error(f"Text2SQL search error: {e}")
            return SearchResult(success=False, candidates=[], method="text2sql_error", error=str(e))
    
    def _generate_sql(self, query: str, slots: Dict[str, Any]) -> Optional[str]:
        """자연어 쿼리를 SQL로 변환"""
        if not openai_client:
            return None
        
        system_prompt = f"""
당신은 신선식품 데이터베이스를 위한 Text2SQL 전문가입니다.
사용자의 자연어 질의를 안전하고 정확한 SQL 쿼리로 변환하세요.

데이터베이스 스키마:
{self.db_schema}

중요한 규칙:
1. SELECT 쿼리만 생성하세요
2. 항상 LIMIT 20을 사용하세요
3. 한국어 상품명을 정확히 매칭하세요

예시:
"사과 찾아줘" -> SELECT * FROM product_tbl WHERE name LIKE '%사과%' LIMIT 20;
"""
        
        user_prompt = f"질의: {query}\n추출된 정보: {slots}"
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            sql_query = response.choices[0].message.content.strip()
            
            # SQL 검증
            if self._validate_sql(sql_query):
                return sql_query
            else:
                logger.warning(f"Invalid SQL generated: {sql_query}")
                return None
                
        except Exception as e:
            logger.error(f"SQL generation failed: {e}")
            return None
    
    def _validate_sql(self, sql: str) -> bool:
        """SQL 안전성 검증"""
        sql_lower = sql.lower().strip()
        
        # 위험한 키워드 체크
        dangerous = ['drop', 'delete', 'insert', 'update', 'alter', 'create']
        if any(keyword in sql_lower for keyword in dangerous):
            return False
        
        # SELECT로 시작하는지 확인
        if not sql_lower.startswith('select'):
            return False
        
        return True
    
    def _execute_mock_sql(self, sql: str, query: str, slots: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Mock SQL 실행 (실제 DB 없이 시뮬레이션)"""
        # 간단한 키워드 기반 필터링으로 SQL 실행 시뮬레이션
        query_lower = query.lower()
        results = []
        
        for product in self.product_data:
            # 키워드 매칭
            if any(keyword in product['name'].lower() or keyword in product['category'].lower() 
                   for keyword in query_lower.split()):
                
                # 슬롯 필터링
                if self._passes_slot_filters(product, slots):
                    results.append({
                        'sku': product['name'],
                        'name': product['name'],
                        'price': product['price'],
                        'stock': product['stock'],
                        'score': 0.9,
                        'origin': product['origin'],
                        'category': product['category']
                    })
        
        return results[:20]  # LIMIT 20 시뮬레이션
    
    def _try_rag_search(self, query: str, slots: Dict[str, Any]) -> SearchResult:
        """RAG 검색 시도"""
        try:
            # 쿼리 향상
            enhanced_query = self._enhance_query(query, slots)
            
            # 검색 실행
            if SKLEARN_AVAILABLE and self.tfidf_vectorizer and self.tfidf_matrix is not None:
                candidates = self._tfidf_search(enhanced_query)
            else:
                candidates = self._simple_keyword_search(enhanced_query)
            
            # 슬롯 필터링
            filtered_candidates = [c for c in candidates if self._passes_slot_filters(c, slots)]
            
            # 상위 20개만
            final_candidates = filtered_candidates[:20]
            
            # 결과 포맷팅
            search_candidates = self._format_candidates(final_candidates)
            
            return SearchResult(
                success=True,
                candidates=search_candidates,
                method="rag",
                search_query=enhanced_query
            )
            
        except Exception as e:
            logger.error(f"RAG search error: {e}")
            return SearchResult(success=False, candidates=[], method="rag_error", error=str(e))
    
    def _enhance_query(self, query: str, slots: Dict[str, Any]) -> str:
        """검색 쿼리 향상"""
        enhanced_parts = [query]
        
        if slots.get('category'):
            enhanced_parts.append(slots['category'])
        
        if slots.get('organic'):
            enhanced_parts.append("유기농")
        
        return ' '.join(enhanced_parts)
    
    def _tfidf_search(self, query: str) -> List[Dict[str, Any]]:
        """TF-IDF 기반 검색"""
        query_vector = self.tfidf_vectorizer.transform([query])
        similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
        
        # 상위 결과 추출
        top_indices = similarities.argsort()[-20:][::-1]
        
        results = []
        for idx in top_indices:
            if similarities[idx] > 0:
                product = self.product_data[idx].copy()
                product['similarity_score'] = float(similarities[idx])
                results.append(product)
        
        return results
    
    def _simple_keyword_search(self, query: str) -> List[Dict[str, Any]]:
        """간단한 키워드 검색"""
        query_lower = query.lower()
        keywords = query_lower.split()
        
        results = []
        for product in self.product_data:
            score = 0.0
            search_text = product.get('search_text', '').lower()
            
            for keyword in keywords:
                if keyword in search_text:
                    if keyword in product.get('name', '').lower():
                        score += 2.0
                    else:
                        score += 1.0
            
            if score > 0:
                product_copy = product.copy()
                product_copy['similarity_score'] = score
                results.append(product_copy)
        
        results.sort(key=lambda x: x['similarity_score'], reverse=True)
        return results[:20]
    
    def _passes_slot_filters(self, product: Dict[str, Any], slots: Dict[str, Any]) -> bool:
        """슬롯 기반 필터링"""
        # 가격 필터
        if slots.get('price_cap'):
            try:
                if product['price'] > float(slots['price_cap']):
                    return False
            except (ValueError, TypeError):
                pass
        
        # 재고 필터
        if product.get('stock', 0) <= 0:
            return False
        
        # 유기농 필터
        if slots.get('organic') and not product.get('organic', False):
            return False
        
        # 카테고리 필터
        if slots.get('category'):
            category = slots['category']
            product_category = product.get('category', '')
            if category not in product_category and product_category not in category:
                return False
        
        return True
    
    def _format_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """후보를 표준 형식으로 포맷"""
        formatted = []
        for candidate in candidates:
            formatted.append({
                'sku': candidate.get('name', ''),
                'name': candidate.get('name', ''),
                'price': candidate.get('price', 0.0),
                'stock': candidate.get('stock', 0),
                'score': candidate.get('similarity_score', 0.5),
                'origin': candidate.get('origin', ''),
                'category': candidate.get('category', '')
            })
        return formatted

# 전역 검색 엔진 인스턴스
_search_engine = None

def get_search_engine() -> ProductSearchEngine:
    """검색 엔진 싱글톤 반환"""
    global _search_engine
    if _search_engine is None:
        _search_engine = ProductSearchEngine()
    return _search_engine

def product_search_rag_text2sql(state: ChatState) -> Dict[str, Any]:
    """
    상품 검색 노드 함수 - graph_interfaces.py 구현
    
    이 함수가 LangGraph에서 실제로 호출되는 노드 함수입니다.
    """
    logger.info("=== Product Search Node Started ===")
    logger.info(f"User Query: {state.query}")
    logger.info(f"Rewrite: {state.rewrite}")
    logger.info(f"Slots: {state.slots}")
    
    try:
        # 검색 엔진 가져오기
        search_engine = get_search_engine()
        
        # 검색 쿼리 준비
        query = state.rewrite.get('text') if state.rewrite.get('text') else state.query
        slots = state.slots or {}
        
        # 검색 실행
        result = search_engine.search_products(query, slots)
        
        if result.success:
            logger.info(f"Search completed - Method: {result.method}, Results: {len(result.candidates)}")
            
            search_result = {
                "candidates": result.candidates,
                "method": result.method,
                "total_results": len(result.candidates)
            }
            
            # SQL 쿼리가 있으면 추가
            if result.sql_query:
                search_result["sql"] = result.sql_query
            
            # 검색 쿼리가 있으면 추가
            if result.search_query:
                search_result["search_query"] = result.search_query
            
            return {"search": search_result}
        else:
            logger.warning("Search failed")
            return {
                "search": {
                    "candidates": [],
                    "method": "failed",
                    "error": result.error or "검색에 실패했습니다",
                    "total_results": 0
                }
            }
        
    except Exception as e:
        logger.error(f"Product search failed with error: {e}")
        return {
            "search": {
                "candidates": [],
                "method": "error",
                "error": str(e),
                "total_results": 0
            }
        }