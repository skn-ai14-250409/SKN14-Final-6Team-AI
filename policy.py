"""
policy.py — 개인맞춤화 레시피 추천 정책 관리

책임:
- 사용자의 allergy, vegan, unfavorite 정보 조회
- 레시피 검색 및 재료 추천 시 개인맞춤화 필터링 정책 적용
- 개인 선호도 기반 검색 키워드 생성 및 필터링
"""

import logging
from mysql.connector import Error
from typing import Dict, Any, List, Tuple

from utils.db import get_db_connection

logger = logging.getLogger("PERSONALIZED_POLICY")

VEGAN_POSITIVE_KEYWORDS = ["비건"]

VEGAN_EXCLUSIONS = [
    "고기", "돼지", "소고기", "닭", "닭고기", "닭가슴살",
    "생선", "새우", "오징어", "계란", "달걀", "우유", "치즈",
    "버터", "요구르트", "베이컨", "햄", "소시지", "참치",
    "연어", "갈치", "조개", "굴", "멸치", "젓갈", "육수"
]

EXCLUDED_DOMAINS = [
    "youtube", "instagram", "facebook.",
    "tiktok.", "blog.naver.", "m.blog.naver"
]

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

    # 1) 비건: 검색어에 "비건" 붙이기
    if user_preferences.get("vegan", False):
        if "비건" not in enhanced_query:
            enhanced_query = f"{enhanced_query} 비건"
        logger.info("비건 사용자 - positive 키워드 적용 (검색어에 '비건' 추가)")

    # 2) 알러지: 검색어 제외 키워드로만 반영
    if user_preferences.get("allergy"):
        allergy_items = [item.strip() for item in user_preferences["allergy"].split(",")]
        exclusion_keywords.extend(allergy_items)
        logger.info(f"알러지 제외 키워드 추가: {allergy_items}")

    # 3) 비선호: 검색에서는 무시 (재료 단계에서만 반영)    
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
        exclusion_items.update(VEGAN_EXCLUSIONS)

    if user_preferences.get("allergy"):
        exclusion_items.update({item.strip() for item in user_preferences["allergy"].split(",")})

    if user_preferences.get("unfavorite"):
        exclusion_items.update({item.strip() for item in user_preferences["unfavorite"].split(",")})

    for ingredient in ingredients:
        ingredient_clean = ingredient.strip()
        should_exclude = any(ex.lower() in ingredient_clean.lower() for ex in exclusion_items)

        if should_exclude:
            logger.info(f"재료 '{ingredient_clean}' 제외됨 (사유: 사용자 선호도)")
        else:
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
        if any(ex in combined_text for ex in VEGAN_EXCLUSIONS):
            logger.info("비건 사용자 - 레시피 제외됨 (동물성 재료 포함)")
            return True

    if user_preferences.get("allergy"):
        if any(allergy.strip().lower() in combined_text for allergy in user_preferences["allergy"].split(",")):
            logger.info("알러지 사용자 - 레시피 제외됨")
            return True

    if user_preferences.get("unfavorite"):
        if any(unfav.strip().lower() in combined_text for unfav in user_preferences["unfavorite"].split(",")):
            logger.info("선호도 사용자 - 레시피 제외됨")
            return True
    
    return False


def get_vegan_query_enhancement(user_preferences: Dict[str, Any]):
    """
    비건 사용자라면 positive/exclusion 반환
    """
    if user_preferences.get("vegan", False):
        return VEGAN_POSITIVE_KEYWORDS, VEGAN_EXCLUSIONS
    return [], []
