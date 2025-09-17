"""
policy.py — 개인맞춤화 레시피 추천 정책 관리

책임:
- 사용자의 allergy, vegan, unfavorite 정보 조회
- 레시피 검색 및 재료 추천 시 개인맞춤화 필터링 정책 적용
- 개인 선호도 기반 검색 키워드 생성 및 필터링
"""

import logging
from mysql.connector import Error
from typing import Dict, Any, Optional, List, Tuple

from utils.db import get_db_connection

logger = logging.getLogger("PERSONALIZED_POLICY")

def get_user_preferences(user_id: str) -> Dict[str, Any]:
    """
    사용자의 개인 선호도 정보를 조회합니다.
    
    Args:
        user_id: 사용자 ID
        
    Returns:
        Dict containing allergy, vegan, unfavorite information
    """
    if not user_id:
        logger.warning("user_id가 제공되지 않음")
        return {"allergy": None, "vegan": False, "unfavorite": None}
    
    conn = get_db_connection()
    if not conn:
        logger.error("DB 연결 실패")
        return {"allergy": None, "vegan": False, "unfavorite": None}
    
    try:
        with conn.cursor(dictionary=True) as cursor:
            query = """
                SELECT allergy, vegan, unfavorite 
                FROM user_detail_tbl 
                WHERE user_id = %s
            """
            cursor.execute(query, (user_id,))
            result = cursor.fetchone()
            
            if result:
                logger.info(f"사용자 {user_id} 개인정보 조회 성공")
                return {
                    "allergy": result.get("allergy"),
                    "vegan": bool(result.get("vegan", 0)),
                    "unfavorite": result.get("unfavorite")
                }
            else:
                logger.warning(f"사용자 {user_id}의 개인정보를 찾을 수 없음")
                return {"allergy": None, "vegan": False, "unfavorite": None}
                
    except Error as e:
        logger.error(f"사용자 선호도 조회 실패: {e}")
        return {"allergy": None, "vegan": False, "unfavorite": None}
    finally:
        if conn and conn.is_connected():
            conn.close()

def create_personalized_search_keywords(base_query: str, user_preferences: Dict[str, Any]) -> Tuple[str, List[str]]:
    """
    사용자 선호도를 바탕으로 개인맞춤화된 검색 키워드를 생성합니다.
    
    Args:
        base_query: 기본 검색 쿼리
        user_preferences: 사용자 선호도 정보
        
    Returns:
        Tuple of (enhanced_query, exclusion_keywords)
    """
    enhanced_query = base_query
    exclusion_keywords = []

    if user_preferences.get("vegan", False):
        vegan_exclusions = [
            "고기", "돼지고기", "소고기", "닭고기", "생선", "새우", "오징어", "계란", 
            "우유", "치즈", "버터", "요구르트", "베이컨", "햄", "소시지", "참치"
        ]
        exclusion_keywords.extend(vegan_exclusions)
        enhanced_query += " 비건 채식"
        logger.info(f"비건 사용자 - 육류/유제품 제외 키워드 추가: {len(vegan_exclusions)}개")

    if user_preferences.get("allergy"):
        allergy_items = [item.strip() for item in user_preferences["allergy"].split(",")]
        exclusion_keywords.extend(allergy_items)
        logger.info(f"알러지 제외 키워드 추가: {allergy_items}")

    if user_preferences.get("unfavorite"):
        unfavorite_items = [item.strip() for item in user_preferences["unfavorite"].split(",")]
        exclusion_keywords.extend(unfavorite_items)
        logger.info(f"싫어하는 음식 제외 키워드 추가: {unfavorite_items}")
    
    return enhanced_query, exclusion_keywords

def filter_recipe_ingredients(ingredients: List[str], user_preferences: Dict[str, Any]) -> List[str]:
    """
    사용자 선호도에 따라 레시피 재료를 필터링합니다.
    
    Args:
        ingredients: 원본 재료 리스트
        user_preferences: 사용자 선호도 정보
        
    Returns:
        필터링된 재료 리스트
    """
    if not ingredients or not user_preferences:
        return ingredients
    
    filtered_ingredients = []
    exclusion_items = set()

    if user_preferences.get("vegan", False):
        vegan_exclusions = {
            "고기", "돼지고기", "소고기", "닭고기", "닭가슴살", "생선", "새우", "오징어", 
            "계란", "달걀", "우유", "치즈", "버터", "요구르트", "베이컨", "햄", "소시지", 
            "참치", "연어", "갈치", "조개", "굴", "멸치", "젓갈"
        }
        exclusion_items.update(vegan_exclusions)

    if user_preferences.get("allergy"):
        allergy_items = {item.strip() for item in user_preferences["allergy"].split(",")}
        exclusion_items.update(allergy_items)

    if user_preferences.get("unfavorite"):
        unfavorite_items = {item.strip() for item in user_preferences["unfavorite"].split(",")}
        exclusion_items.update(unfavorite_items)

    for ingredient in ingredients:
        ingredient_clean = ingredient.strip()
        should_exclude = False

        for exclusion in exclusion_items:
            if exclusion.lower() in ingredient_clean.lower() or ingredient_clean.lower() in exclusion.lower():
                should_exclude = True
                logger.info(f"재료 '{ingredient_clean}' 제외됨 (사유: '{exclusion}')")
                break
        
        if not should_exclude:
            filtered_ingredients.append(ingredient_clean)
    
    logger.info(f"재료 필터링 완료: {len(ingredients)} -> {len(filtered_ingredients)}")
    return filtered_ingredients

def should_exclude_recipe_content(title: str, content: str, user_preferences: Dict[str, Any]) -> bool:
    """
    레시피 제목과 내용을 바탕으로 사용자 선호도에 맞지 않는 레시피인지 판단합니다.
    
    Args:
        title: 레시피 제목
        content: 레시피 내용/설명
        user_preferences: 사용자 선호도 정보
        
    Returns:
        True if recipe should be excluded, False otherwise
    """
    if not user_preferences:
        return False

    combined_text = f"{title} {content}".lower()

    if user_preferences.get("vegan", False):
        vegan_exclusions = [
            "고기", "돼지", "소고기", "닭", "생선", "새우", "오징어", "계란", "달걀",
            "우유", "치즈", "버터", "요구르트", "베이컨", "햄", "소시지", "참치",
            "연어", "갈치", "조개", "굴", "멸치", "젓갈", "육수"
        ]
        
        for exclusion in vegan_exclusions:
            if exclusion in combined_text:
                logger.info(f"비건 사용자 - 레시피 제외됨 (사유: '{exclusion}' 포함)")
                return True

    if user_preferences.get("allergy"):
        allergy_items = [item.strip().lower() for item in user_preferences["allergy"].split(",")]
        for allergy in allergy_items:
            if allergy in combined_text:
                logger.info(f"알러지 사용자 - 레시피 제외됨 (사유: '{allergy}' 포함)")
                return True

    if user_preferences.get("unfavorite"):
        unfavorite_items = [item.strip().lower() for item in user_preferences["unfavorite"].split(",")]
        for unfavorite in unfavorite_items:
            if unfavorite in combined_text:
                logger.info(f"선호도 - 레시피 제외됨 (사유: '{unfavorite}' 포함)")
                return True
    
    return False

