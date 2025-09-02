"""
recipe_search.py — 레시피 검색 모듈

책임:
- Tavily API를 통한 외부 레시피 검색
- 재료 → SKU 매핑 및 장바구니 제안
- 검색된 레시피 URL 제공
- 레이트 리밋 및 캐시 전략
"""

import logging
import os
from typing import Dict, Any, List, Optional
import json
import time

# 상대 경로로 graph_interfaces 임포트
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_interfaces import ChatState

logger = logging.getLogger("RECIPE_SEARCH")

# Tavily API 설정
try:
    from config import config
    TAVILY_API_KEY = config.TAVILY_API_KEY
    if TAVILY_API_KEY:
        logger.info("Tavily API key loaded successfully")
    else:
        logger.warning("Tavily API key not found, using mock recipes")
except ImportError:
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    logger.warning("Config module not found, falling back to environment variables")

# 재료 → SKU 매핑 (실제로는 상품 데이터베이스와 연동)
INGREDIENT_TO_SKU = {
    "사과": "유기농 사과",
    "당근": "유기농 당근", 
    "양파": "양파",
    "토마토": "토마토",
    "상추": "양상추",
    "바나나": "바나나",
    "감자": "감자",
    "배추": "배추",
    "무": "무",
    "고구마": "고구마"
}

# Mock 레시피 데이터 (Tavily API 없을 때 사용)
MOCK_RECIPES = {
    "김치찌개": {
        "title": "맛있는 김치찌개 만들기",
        "url": "https://example.com/recipe/kimchi-stew",
        "ingredients": ["김치", "돼지고기", "두부", "양파", "대파"],
        "description": "간단하고 맛있는 김치찌개 레시피입니다."
    },
    "된장찌개": {
        "title": "집된장으로 만드는 된장찌개",
        "url": "https://example.com/recipe/doenjang-stew", 
        "ingredients": ["된장", "두부", "감자", "양파", "애호박"],
        "description": "구수한 된장찌개 만들기"
    },
    "볶음밥": {
        "title": "간단한 계란 볶음밥",
        "url": "https://example.com/recipe/fried-rice",
        "ingredients": ["밥", "계란", "당근", "양파", "대파"],
        "description": "남은 밥으로 만드는 볶음밥"
    }
}

def recipe_search(state: ChatState) -> Dict[str, Any]:
    """
    레시피 검색(Tavily/API)
    - 요리/재료 기반으로 외부 레시피를 검색합니다.
    - 재료를 카탈로그 SKU로 매핑하여 장바구니 제안을 생성할 수 있습니다.
    """
    logger.info("레시피 검색 프로세스 시작", extra={
        "user_id": state.user_id,
        "query": state.query
    })
    
    try:
        # 쿼리에서 레시피 키워드 추출
        recipe_query = _extract_recipe_query(state.query, state.rewrite.get("text", ""))
        
        # 레시피 검색 실행
        if TAVILY_API_KEY:
            recipe_results = _search_with_tavily(recipe_query)
        else:
            recipe_results = _search_mock_recipes(recipe_query)
        
        # 재료 → SKU 매핑
        sku_suggestions = []
        if recipe_results:
            sku_suggestions = _map_ingredients_to_sku(recipe_results)
        
        logger.info("레시피 검색 완료", extra={
            "results_count": len(recipe_results),
            "sku_suggestions_count": len(sku_suggestions)
        })
        
        return {
            "recipe": {
                "results": recipe_results,
                "sku_suggestions": sku_suggestions,
                "search_query": recipe_query
            },
            "meta": {
                "recipe_message": f"{len(recipe_results)}개의 레시피를 찾았습니다." if recipe_results else "레시피를 찾을 수 없습니다.",
                "api_used": "tavily" if TAVILY_API_KEY else "mock"
            }
        }
        
    except Exception as e:
        logger.error(f"레시피 검색 실패: {e}")
        return {
            "recipe": {
                "results": [],
                "sku_suggestions": [],
                "error": str(e)
            }
        }

def _extract_recipe_query(original_query: str, rewrite_query: str = "") -> str:
    """레시피 관련 키워드 추출 및 검색 쿼리 생성"""
    
    all_text = f"{original_query} {rewrite_query}".lower()
    
    # 요리 관련 키워드 추출
    recipe_keywords = []
    
    # 음식명 키워드
    food_names = ["김치찌개", "된장찌개", "볶음밥", "파스타", "카레", "비빔밥", "잡채", "떡볶이"]
    for food in food_names:
        if food in all_text:
            recipe_keywords.append(food)
    
    # 요리 동작 키워드
    cooking_actions = ["만들기", "요리", "레시피", "조리법"]
    for action in cooking_actions:
        if action in all_text:
            recipe_keywords.append("레시피")
            break
    
    if recipe_keywords:
        return " ".join(recipe_keywords) + " 레시피"
    else:
        return f"{original_query} 레시피"

def _search_with_tavily(query: str) -> List[Dict[str, Any]]:
    """Tavily API를 사용한 레시피 검색"""
    
    try:
        # Tavily 패키지가 설치되어 있다면 사용
        try:
            from tavily import TavilyClient
            
            client = TavilyClient(api_key=TAVILY_API_KEY)
            
            # 레시피 관련 검색
            search_result = client.search(
                query=f"{query} 한국 요리 레시피",
                search_depth="basic",
                max_results=3
            )
            
            results = []
            for result in search_result.get("results", []):
                recipe_info = {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "description": result.get("content", "")[:200],
                    "ingredients": _extract_ingredients_from_content(result.get("content", "")),
                    "source": "tavily"
                }
                results.append(recipe_info)
            
            return results
            
        except ImportError:
            logger.warning("Tavily package not installed, falling back to mock data")
            return _search_mock_recipes(query)
            
    except Exception as e:
        logger.error(f"Tavily 검색 실패: {e}")
        return _search_mock_recipes(query)

def _search_mock_recipes(query: str) -> List[Dict[str, Any]]:
    """Mock 레시피 데이터에서 검색"""
    
    query_lower = query.lower()
    results = []
    
    for recipe_name, recipe_data in MOCK_RECIPES.items():
        if recipe_name in query_lower or any(word in recipe_data["title"].lower() for word in query_lower.split()):
            recipe_info = {
                "title": recipe_data["title"],
                "url": recipe_data["url"],
                "description": recipe_data["description"],
                "ingredients": recipe_data["ingredients"],
                "source": "mock"
            }
            results.append(recipe_info)
    
    return results

def _extract_ingredients_from_content(content: str) -> List[str]:
    """컨텐츠에서 재료 추출 (간단한 키워드 매칭)"""
    
    ingredients = []
    content_lower = content.lower()
    
    # 일반적인 재료 키워드들
    common_ingredients = [
        "양파", "마늘", "당근", "감자", "토마토", "상추", "배추", "무",
        "돼지고기", "소고기", "닭고기", "계란", "두부", "김치", "된장",
        "고추장", "간장", "설탕", "소금", "기름", "밥", "면"
    ]
    
    for ingredient in common_ingredients:
        if ingredient in content_lower:
            ingredients.append(ingredient)
    
    return ingredients[:10]  # 최대 10개만

def _map_ingredients_to_sku(recipe_results: List[Dict[str, Any]]) -> List[str]:
    """재료를 SKU로 매핑"""
    
    suggested_skus = []
    
    for recipe in recipe_results:
        ingredients = recipe.get("ingredients", [])
        
        for ingredient in ingredients:
            # 재료명에서 SKU 매핑 찾기
            for ingredient_key, sku in INGREDIENT_TO_SKU.items():
                if ingredient_key in ingredient:
                    if sku not in suggested_skus:
                        suggested_skus.append(sku)
    
    return suggested_skus[:5]  # 최대 5개 SKU 제안