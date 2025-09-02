#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_product_search_simple():
    """간단한 상품 검색 테스트"""
    try:
        from nodes.product_search import get_search_engine
        engine = get_search_engine()
        
        print(f"Loaded products: {len(engine.product_data)}")
        print("Sample products:")
        for i, product in enumerate(engine.product_data[:3]):
            print(f"{i+1}. {product['name']} - {product['price']}원 (재고: {product['stock']})")
        
        # 검색 테스트
        result = engine.search_products("사과", {"quantity": 1})
        candidates = result.candidates
        
        print(f"\nSearch results ({result.method}): {len(candidates)} found")
        for candidate in candidates:
            print(f"- {candidate['name']}: {candidate['price']}원")
        
        return len(candidates) > 0
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    print("Simple Product Search Test")
    print("=" * 30)
    
    if test_product_search_simple():
        print("\nSUCCESS: Product search is working!")
    else:
        print("\nFAIL: Product search has issues")