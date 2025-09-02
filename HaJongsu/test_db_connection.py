#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
데이터베이스 연결 및 하드코딩 수정 테스트
"""

import os
import sys
import logging

# 경로 설정
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_database_connection():
    """데이터베이스 연결 테스트"""
    print("=== 데이터베이스 연결 테스트 ===")
    
    try:
        from utils.database import test_connection, search_products, get_faq_data
        
        # 1. 연결 테스트
        if test_connection():
            print("✅ DB 연결 성공")
        else:
            print("❌ DB 연결 실패")
            return False
        
        # 2. 상품 검색 테스트
        products = search_products("사과")
        print(f"상품 검색 결과: {len(products)}개")
        for product in products[:3]:  # 상위 3개만
            print(f"  - {product.get('product', 'Unknown')}: {product.get('unit_price', 0)}원")
        
        # 3. FAQ 데이터 테스트
        faqs = get_faq_data()
        print(f"FAQ 데이터: {len(faqs)}개")
        
        return True
        
    except Exception as e:
        print(f"DB 테스트 실패: {e}")
        return False

def test_product_search():
    """상품 검색 모듈 테스트"""
    print("\n=== 상품 검색 모듈 테스트 ===")
    
    try:
        from nodes.product_search import get_search_engine
        from graph_interfaces import ChatState
        
        # 검색 엔진 초기화
        engine = get_search_engine()
        print(f"상품 데이터 로드: {len(engine.product_data)}개")
        
        # 테스트 상태 생성
        state = ChatState(
            user_id="test_user",
            session_id="test_session",
            turn_id=1,
            query="사과를 주문하고 싶어요",
            rewrite={"text": "사과 구매"},
            slots={"quantity": 2, "category": "과일"}
        )
        
        # 검색 테스트
        from nodes.product_search import product_search_rag_text2sql
        result = product_search_rag_text2sql(state)
        
        search_data = result.get("search", {})
        candidates = search_data.get("candidates", [])
        method = search_data.get("method", "unknown")
        
        print(f"검색 방법: {method}")
        print(f"검색 결과: {len(candidates)}개")
        
        for candidate in candidates[:3]:  # 상위 3개만
            print(f"  - {candidate.get('name', 'Unknown')}: {candidate.get('price', 0)}원, 재고: {candidate.get('stock', 0)}")
        
        return True
        
    except Exception as e:
        print(f"상품 검색 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_basic_workflow():
    """기본 워크플로우 테스트"""
    print("\n=== 기본 워크플로우 테스트 ===")
    
    try:
        from graph_interfaces import ChatState
        
        # 테스트 상태 생성
        state = ChatState(
            user_id="test_user",
            session_id="test_session", 
            turn_id=1,
            query="유기농 사과 2개 주문하고 싶어요"
        )
        
        # 1. 라우터 테스트
        from graph_interfaces import router_route
        route_result = router_route(state)
        print(f"라우팅 결과: {route_result.get('route', {})}")
        
        # 2. 쿼리 보강 테스트
        from graph_interfaces import enhance_query
        enhance_result = enhance_query(state)
        print(f"쿼리 보강: {enhance_result.get('rewrite', {}).get('text', '')}")
        print(f"슬롯 추출: {enhance_result.get('slots', {})}")
        
        return True
        
    except Exception as e:
        print(f"워크플로우 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Qook 챗봇 하드코딩 수정 검증 테스트")
    print("=" * 50)
    
    success_count = 0
    total_tests = 3
    
    # 테스트 실행
    if test_database_connection():
        success_count += 1
    
    if test_product_search():
        success_count += 1
    
    if test_basic_workflow():
        success_count += 1
    
    # 결과 출력
    print(f"\n=== 테스트 결과 ===")
    print(f"성공: {success_count}/{total_tests}")
    
    if success_count == total_tests:
        print("✅ 모든 테스트 통과! DB 연동이 정상적으로 작동합니다.")
    else:
        print("❌ 일부 테스트 실패. 추가 디버깅이 필요합니다.")