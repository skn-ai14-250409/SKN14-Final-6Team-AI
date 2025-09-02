"""
상품 검색 메인 모듈 - product_search_rag_text2sql 함수 구현

C 팀 담당: graph_interfaces.py의 product_search_rag_text2sql 함수를 실제로 구현
- Text2SQL 우선 시도
- 실패 시 RAG 폴백
- 통합된 검색 결과 반환
"""

import logging
from typing import Dict, Any
from graph_interfaces import ChatState
from .text2sql import create_text2sql_engine, SQLResult
from .rag_search import create_rag_engine, RAGResult

logger = logging.getLogger('chatbot.product_search')

class ProductSearchEngine:
    """상품 검색 통합 엔진"""
    
    def __init__(self):
        self.text2sql_engine = create_text2sql_engine()
        self.rag_engine = create_rag_engine()
        
    def search(self, state: ChatState) -> Dict[str, Any]:
        """
        상품 검색 메인 로직
        1. Text2SQL 우선 시도
        2. 실패 시 RAG 폴백
        3. 결과 포맷 및 반환
        """
        
        # None 값 안전 처리
        rewrite = state.rewrite or {}
        slots = state.slots or {}
        query = rewrite.get('text', state.query or '')
        
        logger.info(f"Product search initiated - Query: {query}")
        logger.info(f"Slots: {slots}")
        
        # 1차 시도: Text2SQL
        sql_result = self._try_text2sql(query, slots)
        
        if sql_result.success and sql_result.data:
            logger.info("Text2SQL search succeeded")
            candidates = self._format_sql_results(sql_result.data)
            return {
                "search": {
                    "candidates": candidates,
                    "method": "text2sql",
                    "sql": sql_result.sql_query,
                    "total_results": len(candidates)
                }
            }
        
        # 2차 시도: RAG 폴백
        logger.info("Falling back to RAG search")
        rag_result = self._try_rag(query, slots)
        
        if rag_result.success and rag_result.candidates:
            logger.info("RAG search succeeded")
            return {
                "search": {
                    "candidates": rag_result.candidates,
                    "method": "rag", 
                    "search_query": rag_result.search_query,
                    "total_results": len(rag_result.candidates)
                }
            }
        
        # 둘 다 실패한 경우
        logger.warning("Both Text2SQL and RAG search failed")
        return {
            "search": {
                "candidates": [],
                "method": "failed",
                "error": "검색 결과가 없습니다",
                "total_results": 0
            }
        }
    
    def _try_text2sql(self, query: str, slots: Dict[str, Any]) -> SQLResult:
        """Text2SQL 검색 시도"""
        try:
            logger.info("Attempting Text2SQL search")
            return self.text2sql_engine.search_products(query, slots)
        except Exception as e:
            logger.error(f"Text2SQL search error: {e}")
            return SQLResult(success=False, data=[], error=str(e))
    
    def _try_rag(self, query: str, slots: Dict[str, Any]) -> RAGResult:
        """RAG 검색 시도"""
        try:
            logger.info("Attempting RAG search")
            return self.rag_engine.search_products(query, slots)
        except Exception as e:
            logger.error(f"RAG search error: {e}")
            return RAGResult(success=False, candidates=[], error=str(e))
    
    def _format_sql_results(self, sql_data: list) -> list:
        """SQL 결과를 SearchCandidate 형태로 포맷"""
        candidates = []
        
        for row in sql_data:
            candidate = {
                'sku': row.get('name', ''),
                'name': row.get('name', ''),
                'price': float(row.get('unit_price', 0)) if row.get('unit_price') else 0.0,
                'stock': int(row.get('quantity', 0)) if row.get('quantity') else 0,
                'score': 1.0,  # SQL 결과는 모두 높은 점수
                'origin': row.get('origin', ''),
                'category': row.get('category', '')
            }
            candidates.append(candidate)
        
        return candidates


# 전역 엔진 인스턴스
_search_engine = None

def get_search_engine() -> ProductSearchEngine:
    """검색 엔진 싱글톤 인스턴스 반환"""
    global _search_engine
    if _search_engine is None:
        _search_engine = ProductSearchEngine()
    return _search_engine


def product_search_rag_text2sql(state: ChatState) -> Dict[str, Any]:
    """
    상품 검색 메인 함수 - graph_interfaces.py의 실제 구현
    
    C 팀 담당: 이 함수가 LangGraph에서 호출되는 실제 노드 함수입니다.
    
    Args:
        state: ChatState 객체
        
    Returns:
        Dict[str, Any]: 부분 상태 갱신 딕셔너리
            {
                "search": {
                    "candidates": List[SearchCandidate],
                    "method": "text2sql" | "rag",
                    "sql": str (옵션),
                    "search_query": str (옵션),
                    "total_results": int
                }
            }
    """
    
    logger.info("=== Product Search Node Started ===")
    logger.info(f"User Query: {state.query}")
    logger.info(f"Rewrite: {state.rewrite}")
    logger.info(f"Slots: {state.slots}")
    
    try:
        # 검색 엔진 가져오기
        search_engine = get_search_engine()
        
        # 검색 실행
        result = search_engine.search(state)
        
        logger.info(f"Search completed - Method: {result['search']['method']}, "
                   f"Results: {result['search']['total_results']}")
        
        return result
        
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