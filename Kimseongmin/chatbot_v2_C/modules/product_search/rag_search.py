"""
RAG 기반 상품 검색 모듈

C 팀 담당: 상품 검색 기능의 RAG 구현
- 벡터 검색을 통한 상품 매칭
- 하이브리드 검색 (의미적 + 키워드)
- Text2SQL 실패 시 폴백으로 사용
"""

import logging
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from django.db import connection
from django.conf import settings
import openai
import json
import pickle

# 조건부 임포트 - NumPy 호환성 문제 처리
try:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError as e:
    SKLEARN_AVAILABLE = False
    logger = logging.getLogger('chatbot.product_search')
    logger.warning(f"scikit-learn not available: {e}. RAG will use simple text matching.")

logger = logging.getLogger('chatbot.product_search')

@dataclass
class RAGResult:
    """RAG 검색 결과를 담는 데이터 클래스"""
    success: bool
    candidates: List[Dict[str, Any]]
    method: str = "rag"
    error: Optional[str] = None
    search_query: Optional[str] = None

class ProductRAGEngine:
    """RAG 기반 상품 검색 엔진"""
    
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.tfidf_vectorizer = None
        self.product_embeddings = {}
        self.product_data = []
        self.index_dir = settings.VECTOR_STORE_DIR
        self._ensure_index_dir()
        self._load_or_build_index()
    
    def _ensure_index_dir(self):
        """인덱스 디렉토리 생성"""
        os.makedirs(self.index_dir, exist_ok=True)
    
    def _load_or_build_index(self):
        """인덱스 로드 또는 새로 빌드"""
        index_file = os.path.join(self.index_dir, 'product_index.pkl')
        
        if os.path.exists(index_file):
            logger.info("Loading existing product index...")
            try:
                with open(index_file, 'rb') as f:
                    data = pickle.load(f)
                    self.product_data = data['products']
                    self.tfidf_vectorizer = data['tfidf_vectorizer']
                    self.product_embeddings = data.get('embeddings', {})
                logger.info(f"Loaded index with {len(self.product_data)} products")
            except Exception as e:
                logger.warning(f"Failed to load index: {e}, rebuilding...")
                self._build_index()
        else:
            logger.info("Building new product index...")
            self._build_index()
    
    def _build_index(self):
        """상품 인덱스 빌드"""
        try:
            # 데이터베이스에서 상품 정보 로드
            self.product_data = self._load_products_from_db()
            
            if not self.product_data:
                logger.error("No products found in database")
                return
            
            # TF-IDF 벡터 생성
            self._build_tfidf_index()
            
            # 임베딩 생성 (옵션)
            self._build_embeddings_index()
            
            # 인덱스 저장
            self._save_index()
            
            logger.info(f"Successfully built index with {len(self.product_data)} products")
            
        except Exception as e:
            logger.error(f"Failed to build index: {e}")
    
    def _load_products_from_db(self) -> List[Dict[str, Any]]:
        """데이터베이스에서 상품 정보 로드"""
        products = []
        
        try:
            with connection.cursor() as cursor:
                # 상품, 카테고리, 재고 정보를 조인하여 가져오기
                sql = """
                SELECT 
                    p.name,
                    p.unit_price,
                    p.origin,
                    COALESCE(s.quantity, 0) as stock,
                    COALESCE(c.category_id, 0) as category_id,
                    COALESCE(GROUP_CONCAT(i.item_name), '') as items,
                    COALESCE(GROUP_CONCAT(i.organic), '') as organic_info
                FROM product_tbl p
                LEFT JOIN stock_tbl s ON p.id = s.product_id
                LEFT JOIN category_tbl c ON p.category_id = c.id
                LEFT JOIN item_tbl i ON p.id = i.product_id
                GROUP BY p.id, p.name, p.unit_price, p.origin, s.quantity, c.category_id
                """
                
                cursor.execute(sql)
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                
                for row in rows:
                    product_dict = dict(zip(columns, row))
                    
                    # 데이터 정규화
                    product_dict['price'] = float(product_dict['unit_price']) if product_dict['unit_price'] else 0.0
                    # stock이 이미 int일 수 있으므로 타입 체크
                    if isinstance(product_dict['stock'], int):
                        product_dict['stock_qty'] = product_dict['stock']
                    elif isinstance(product_dict['stock'], str) and product_dict['stock'].isdigit():
                        product_dict['stock_qty'] = int(product_dict['stock'])
                    else:
                        product_dict['stock_qty'] = 0
                    product_dict['category_name'] = self._get_category_name(product_dict['category_id'])
                    
                    # 검색용 텍스트 생성
                    search_text = f"{product_dict['name']} {product_dict['origin']} {product_dict['category_name']}"
                    if product_dict.get('items'):
                        search_text += f" {product_dict['items']}"
                    product_dict['search_text'] = search_text
                    
                    products.append(product_dict)
                    
        except Exception as e:
            logger.error(f"Failed to load products from DB: {e}")
            
        return products
    
    def _get_category_name(self, category_id: int) -> str:
        """카테고리 ID를 이름으로 변환"""
        category_map = {
            1: "과일",
            2: "채소",  
            3: "곡물",
            4: "육류수산",
            5: "유제품"
        }
        return category_map.get(category_id, "기타")
    
    def _build_tfidf_index(self):
        """TF-IDF 인덱스 생성"""
        if not self.product_data:
            return
        
        if SKLEARN_AVAILABLE:
            # 검색용 텍스트 추출
            texts = [product['search_text'] for product in self.product_data]
            
            # TF-IDF 벡터화
            self.tfidf_vectorizer = TfidfVectorizer(
                max_features=1000,
                ngram_range=(1, 2),
                stop_words=None  # 한국어는 별도 처리 필요
            )
            
            self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(texts)
            logger.info("TF-IDF index built successfully")
        else:
            # scikit-learn이 없는 경우 간단한 키워드 매칭으로 대체
            logger.info("Using simple keyword matching instead of TF-IDF")
    
    def _build_embeddings_index(self):
        """OpenAI 임베딩 인덱스 생성 (선택사항)"""
        # 임베딩 생성은 비용이 많이 들기 때문에 필요시에만 구현
        # 현재는 TF-IDF만 사용
        logger.info("Embeddings index skipped (using TF-IDF only)")
    
    def _save_index(self):
        """인덱스 저장"""
        try:
            index_file = os.path.join(self.index_dir, 'product_index.pkl')
            data = {
                'products': self.product_data,
                'tfidf_vectorizer': self.tfidf_vectorizer,
                'embeddings': self.product_embeddings
            }
            
            with open(index_file, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info("Index saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
    
    def search_products(self, query: str, slots: Dict[str, Any], top_k: int = 20) -> RAGResult:
        """RAG 기반 상품 검색"""
        
        logger.info(f"RAG search started - Query: {query}, Slots: {slots}")
        
        if not self.product_data or self.tfidf_vectorizer is None:
            logger.error("Index not available")
            return RAGResult(success=False, candidates=[], error="Index not available")
        
        try:
            # 검색 쿼리 확장
            enhanced_query = self._enhance_search_query(query, slots)
            
            # 검색 방법 선택
            if SKLEARN_AVAILABLE:
                # TF-IDF 검색
                candidates = self._tfidf_search(enhanced_query, top_k * 2)
            else:
                # 간단한 키워드 매칭
                candidates = self._simple_keyword_search(enhanced_query, top_k * 2)
            
            # 슬롯 기반 필터링
            filtered_candidates = self._apply_slot_filters(candidates, slots)
            
            # 상위 k개만 선택
            final_candidates = filtered_candidates[:top_k]
            
            # 결과를 SearchCandidate 형태로 변환
            search_candidates = self._format_search_candidates(final_candidates)
            
            logger.info(f"RAG search completed: {len(search_candidates)} candidates")
            return RAGResult(
                success=True, 
                candidates=search_candidates,
                search_query=enhanced_query
            )
            
        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            return RAGResult(success=False, candidates=[], error=str(e))
    
    def _enhance_search_query(self, query: str, slots: Dict[str, Any]) -> str:
        """검색 쿼리 향상"""
        enhanced_parts = [query]
        
        # 슬롯 정보를 쿼리에 추가
        if slots.get('category'):
            enhanced_parts.append(slots['category'])
        
        if slots.get('organic'):
            enhanced_parts.append("유기농")
            
        # 동의어 확장
        synonyms = {
            '사과': ['애플', 'apple'],
            '바나나': ['banana'],
            '토마토': ['tomato'], 
            '당근': ['carrot'],
            '양파': ['onion']
        }
        
        for word, syns in synonyms.items():
            if word in query.lower():
                enhanced_parts.extend(syns)
        
        return ' '.join(enhanced_parts)
    
    def _tfidf_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """TF-IDF 기반 검색"""
        
        # 쿼리 벡터화
        query_vector = self.tfidf_vectorizer.transform([query])
        
        # 코사인 유사도 계산
        similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
        
        # 상위 k개 인덱스 추출
        top_indices = similarities.argsort()[-top_k:][::-1]
        
        # 결과 구성
        results = []
        for idx in top_indices:
            if similarities[idx] > 0:  # 유사도가 0보다 큰 것만
                product = self.product_data[idx].copy()
                product['similarity_score'] = float(similarities[idx])
                results.append(product)
        
        return results
    
    def _simple_keyword_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """간단한 키워드 매칭 검색 (scikit-learn 대체)"""
        
        query_lower = query.lower()
        keywords = query_lower.split()
        
        results = []
        
        for product in self.product_data:
            search_text = product.get('search_text', '').lower()
            score = 0.0
            
            # 키워드 매칭 점수 계산
            for keyword in keywords:
                if keyword in search_text:
                    if keyword in product.get('name', '').lower():
                        score += 2.0  # 상품명에 있으면 높은 점수
                    else:
                        score += 1.0  # 기타 필드에 있으면 낮은 점수
            
            if score > 0:
                product_copy = product.copy()
                product_copy['similarity_score'] = score
                results.append(product_copy)
        
        # 점수 순으로 정렬
        results.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        return results[:top_k]
    
    def _apply_slot_filters(self, candidates: List[Dict[str, Any]], slots: Dict[str, Any]) -> List[Dict[str, Any]]:
        """슬롯 기반 필터링"""
        
        filtered = []
        
        for candidate in candidates:
            # 가격 필터
            if slots.get('price_cap'):
                try:
                    if candidate['price'] > float(slots['price_cap']):
                        continue
                except (ValueError, TypeError):
                    pass
            
            # 재고 필터 (재고가 있는 것만)
            if candidate.get('stock_qty', 0) <= 0:
                continue
            
            # 유기농 필터
            if slots.get('organic'):
                organic_info = candidate.get('organic_info', '')
                if 'Y' not in organic_info:
                    continue
            
            # 카테고리 필터
            if slots.get('category'):
                category_name = candidate.get('category_name', '')
                if slots['category'] not in category_name and category_name not in slots['category']:
                    continue
            
            filtered.append(candidate)
        
        return filtered
    
    def _format_search_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """검색 결과를 SearchCandidate 형태로 포맷"""
        
        search_candidates = []
        
        for candidate in candidates:
            search_candidate = {
                'sku': candidate.get('name', ''),  # 상품명을 SKU로 사용
                'name': candidate.get('name', ''),
                'price': candidate.get('price', 0.0),
                'stock': candidate.get('stock_qty', 0),
                'score': candidate.get('similarity_score', 0.0),
                'origin': candidate.get('origin', ''),
                'category': candidate.get('category_name', '')
            }
            search_candidates.append(search_candidate)
        
        return search_candidates


def create_rag_engine() -> ProductRAGEngine:
    """RAG 엔진 팩토리 함수"""
    return ProductRAGEngine()