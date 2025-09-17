"""
recipe_search.py — 레시피 검색 및 재료 추천 모듈 
책임:
- 시나리오 1: 일반 레시피 검색 (Tavily API) 후 사이드바에 결과 URL 표시
- 시나리오 2: 특정 레시피 선택 시, URL 크롤링 및 LLM을 통한 재료/조리법 추출
- 추출된 재료를 기반으로 쇼핑몰 상품(SKU)을 DB에서 검색하여 사이드바에 제안
- 최종 응답 메시지(AIMessage)를 프론트엔드 규격에 맞는 'response' 키로 포맷팅
"""
import random
import logging
import os
import requests
import re
import json
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed  # hjs 수정
from mysql.connector import Error
from bs4 import BeautifulSoup

# 프로젝트 루트 경로 추가 (환경에 맞게 조정)
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_interfaces import ChatState

# 개인맞춤화 정책 임포트
from policy import (
    get_user_preferences, 
    create_personalized_search_keywords, 
    filter_recipe_ingredients,
    should_exclude_recipe_content
)

from utils.chat_history import save_recipe_search_result, generate_alternative_search_strategy
from nodes.product_search import get_search_engine  # hjs 수정 # 멀티턴 기능
from utils.db import get_db_connection  # hjs 수정

logger = logging.getLogger("RECIPE_SEARCH")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

try:
    import openai
    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_client = openai.OpenAI(api_key=openai_api_key) if openai_api_key else None
    if not openai_client:
        logger.warning("OpenAI API key not found. LLM-based features will be disabled.")
except ImportError:
    openai_client = None
    logger.warning("OpenAI package not available. LLM-based features will be disabled.")

# --- 메인 라우팅 함수 ---
# def recipe_search(state: ChatState) -> Dict[str, Any]:
#     """
#     사용자 쿼리를 분석하여 두 가지 시나리오 중 하나를 실행합니다.
#     1. 일반 레시피 검색
#     2. 선택된 레시피의 재료 추천
#     """
#     logger.info("레시피 검색 프로세스 시작")
#     query = state.query

#     try:
#         # 시나리오 2: 사용자가 사이드바에서 특정 레시피의 '재료 추천받기'를 클릭한 경우
#         if "선택된 레시피:" in query and "URL:" in query:
#             logger.info("시나리오 2: 선택된 레시피 재료 추천 시작")
#             recipe = _handle_selected_recipe(query, state)
#             return recipe
        
#         # 시나리오 1: 일반적인 레시피 관련 질문인 경우
#         else:
#             logger.info("시나리오 1: 일반 레시피 검색 시작")
#             rewrite_query = state.rewrite.get("text", "")
#             return _handle_general_recipe_search(query, rewrite_query, state)

#     except Exception as e:
#         logger.error(f"레시피 검색 중 심각한 오류 발생: {e}", exc_info=True)
#         return {
#             "recipe": {"results": [], "ingredients": [], "error": str(e)},
#             "response": "죄송합니다, 레시피를 검색하는 중 오류가 발생했습니다."
#         }

def recipe_search(state: ChatState) -> Dict[str, Any]:
    """
    히스토리 기반 레시피 검색 (재검색 개선 버전)
    - 기존 시나리오 1, 2 완전 유지
    - 검색 완료 후 히스토리 저장 추가
    - 재검색일 경우 이전 결과 필터링 적용
    - 실패 시 기존 방식으로 완벽 폴백
    """
    logger.info("히스토리 기반 레시피 검색 프로세스 시작")
    query = state.query

    try:
        # 재검색 여부 확인 (안전한 방식)
        is_alternative_search = False
        search_strategy = None
        previous_urls = []

        try:
            search_context = state.slots.get('search_context')
            if search_context and search_context.get('type') == 'alternative':
                is_alternative_search = True
                logger.info(f"재검색 감지: {search_context.get('intent_scope', 'unknown')}")

                # 대안 검색 전략 생성
                if search_context.get('previous_dish'):
                    # 실제 히스토리에서 이전 검색 결과 가져오기
                    from utils.chat_history import get_recent_recipe_search_context
                    recent_context = get_recent_recipe_search_context(state, query)

                    previous_results = []
                    if recent_context["has_previous_search"] and recent_context["most_recent_search"]:
                        previous_results = recent_context["most_recent_search"].get("results", [])
                        logger.info(f"히스토리에서 가져온 이전 검색 결과: {len(previous_results)}개")

                    previous_search = {
                        "search_query": search_context.get('previous_dish'),
                        "query_type": "specific_dish",
                        "results": previous_results  # 실제 히스토리 결과 사용
                    }
                    search_strategy = generate_alternative_search_strategy(previous_search, query)
                    previous_urls = search_strategy.get('exclude_urls', [])
                    logger.info(f"대안 검색 전략: {search_strategy.get('strategy_type', 'unknown')}")
                    logger.info(f"제외할 URL: {len(previous_urls)}개")

        except Exception as e:
            logger.warning(f"재검색 분석 실패, 기존 방식 사용: {e}")
            is_alternative_search = False

        # 기존 시나리오 분기 (완전 동일)
        if "선택된 레시피:" in query and "URL:" in query:
            logger.info("시나리오 2: 선택된 레시피 재료 추천 시작")
            result = _handle_selected_recipe(query, state)
        else:
            logger.info("시나리오 1: 일반 레시피 검색 시작")
            rewrite_query = state.rewrite.get("text", "")

            # 재검색인 경우 검색 전략 적용
            if is_alternative_search and search_strategy:
                result = _handle_general_recipe_search_with_history(
                    query, rewrite_query, state, search_strategy, previous_urls
                )
            else:
                # 기존 방식 그대로 사용
                result = _handle_general_recipe_search(query, rewrite_query, state)

        # 검색 완료 후 히스토리 저장 (실패해도 무시)
        try:
            recipe_results = result.get("recipe", {}).get("results")
            if recipe_results:
                logger.info(f"히스토리 저장 대상 레시피: {len(recipe_results)}개")

                # URL 정보 로깅
                for i, r in enumerate(recipe_results[:3]):
                    logger.info(f"  {i+1}. {r.get('title', 'No title')[:30]}... | URL: {r.get('url', 'No URL')[:50]}...")

                search_context_to_save = {
                    "query_type": "specific_dish",  # LLM으로 개선 가능
                    "original_query": query,
                    "search_query": rewrite_query or query,
                    "results": [
                        {"title": r.get("title", ""), "url": r.get("url", "")}
                        for r in recipe_results[:3]  # 처음 3개만 저장
                    ],
                    "search_type": "alternative" if is_alternative_search else "initial"
                }

                logger.info(f"저장할 히스토리 결과: {len(search_context_to_save['results'])}개")
                save_recipe_search_result(state, search_context_to_save)
                logger.info("검색 히스토리 저장 완료")
            else:
                logger.warning("검색 결과가 없어서 히스토리 저장하지 않음")
        except Exception as e:
            logger.warning(f"히스토리 저장 실패 (무시): {e}")

        return result

    except Exception as e:
        logger.error(f"히스토리 기반 레시피 검색 실패, 기존 방식으로 폴백: {e}", exc_info=True)
        # 완전 실패 시 기존 방식으로 폴백
        try:
            if "선택된 레시피:" in query and "URL:" in query:
                return _handle_selected_recipe(query, state)
            else:
                rewrite_query = state.rewrite.get("text", "")
                return _handle_general_recipe_search(query, rewrite_query, state)
        except Exception as fallback_e:
            logger.error(f"폴백도 실패: {fallback_e}")
            return {
                "recipe": {"results": [], "ingredients": [], "error": str(fallback_e)},
                "response": "죄송합니다, 레시피를 검색하는 중 오류가 발생했습니다."
            }

def _handle_general_recipe_search_with_history(
    original_query: str, rewrite_query: str, state: ChatState,
    search_strategy: Dict[str, Any], previous_urls: List[str]
) -> Dict[str, Any]:
    """히스토리 기반 레시피 검색 (재검색 전용)"""
    logger.info(f"히스토리 기반 검색 시작: 전략={search_strategy.get('strategy_type', 'unknown')}")

    try:
        user_preferences = {}
        if state and state.user_id:
            user_preferences = get_user_preferences(state.user_id)
            logger.info(f"사용자 {state.user_id} 개인 선호도: {user_preferences}")

        strategy_type = search_strategy.get('strategy_type', 'SAME_DISH_ALTERNATIVE')
        alternative_queries = search_strategy.get('alternative_queries', [])

        if alternative_queries:
            base_query = alternative_queries[0]
            logger.info(f"LLM 생성 대안 쿼리 사용: {base_query}")
        else:
            base_query = _extract_recipe_query(original_query, rewrite_query)

        if user_preferences:
            personalized_query, exclusion_keywords = create_personalized_search_keywords(base_query, user_preferences)
            logger.info(f"개인맞춤화된 쿼리: {personalized_query}")
            recipe_query = personalized_query
        else:
            recipe_query = base_query
            exclusion_keywords = []

        # Tavily로 외부 레시피 검색 (히스토리 기반)
        recipe_results = _search_with_tavily_filtered(recipe_query, user_preferences, previous_urls)

        # 중복 URL 필터링 결과가 부족한 경우 추가 검색
        if len(recipe_results) < 2 and len(alternative_queries) > 1:
            logger.info("결과 부족으로 추가 대안 쿼리 검색")
            for alt_query in alternative_queries[1:3]:  # 2-3번째 대안 쿼리 시도
                additional_results = _search_with_tavily_filtered(alt_query, user_preferences, previous_urls)
                recipe_results.extend(additional_results)
                if len(recipe_results) >= 3:
                    break

        if recipe_results:
            personalized_msg = ""
            if user_preferences.get("vegan"):
                personalized_msg = " (비건 레시피 위주로 검색됨)"
            elif user_preferences.get("allergy") or user_preferences.get("unfavorite"):
                personalized_msg = " (개인 선호도 반영됨)"

            strategy_msg = ""
            if strategy_type == "SAME_DISH_ALTERNATIVE":
                strategy_msg = " 다른 레시피들을 찾았습니다"
            elif strategy_type == "DIFFERENT_MENU":
                strategy_msg = " 새로운 요리들을 추천합니다"

            message = (
                f"{len(recipe_results)}개의{strategy_msg}{personalized_msg}.\n\n"
                "💡 원하는 레시피를 클릭하여 '재료 추천받기' 버튼을 누르면 필요한 재료들을 추천해드립니다!"
            )
        else:
            message = "새로운 레시피를 찾지 못했습니다. 다른 키워드로 검색해보세요."

        logger.info(f"히스토리 기반 검색 완료: {len(recipe_results)}개 결과")
        return {
            "recipe": {
                "results": recipe_results,
                "ingredients": [],
                "search_query": recipe_query,
                "search_strategy": strategy_type
            },
            "response": message
        }

    except Exception as e:
        logger.error(f"히스토리 기반 검색 실패, 기존 방식으로 폴백: {e}")
        return _handle_general_recipe_search(original_query, rewrite_query, state)

def _handle_general_recipe_search(original_query: str, rewrite_query: str, state: ChatState = None) -> Dict[str, Any]:
    """Tavily API로 레시피를 검색하고 사이드바에 표시할 URL 목록을 반환합니다."""
    
    user_preferences = {}
    if state and state.user_id:
        user_preferences = get_user_preferences(state.user_id)
        logger.info(f"사용자 {state.user_id} 개인 선호도: {user_preferences}")
    
    base_query = _extract_recipe_query(original_query, rewrite_query)
    
    if user_preferences:
        personalized_query, exclusion_keywords = create_personalized_search_keywords(base_query, user_preferences)
        logger.info(f"개인맞춤화된 쿼리: {personalized_query}")
        logger.info(f"제외 키워드: {exclusion_keywords}")
        recipe_query = personalized_query
    else:
        recipe_query = base_query
        exclusion_keywords = []
    
    recipe_results = _search_with_tavily(recipe_query, user_preferences)
    
    if recipe_results:
        personalized_msg = ""
        if user_preferences.get("vegan"):
            personalized_msg = " (비건 레시피 위주로 검색됨)"
        elif user_preferences.get("allergy") or user_preferences.get("unfavorite"):
            personalized_msg = " (개인 선호도 반영됨)"
            
        message = (
            f"{len(recipe_results)}개의 레시피를 찾았습니다{personalized_msg}.\n\n"
            "💡 원하는 레시피를 클릭하여 '재료 추천받기' 버튼을 누르면 필요한 재료들을 추천해드립니다!"
        )
    else:
        message = "관련 레시피를 찾지 못했습니다. 다른 키워드로 검색해보세요."

    return {
        "recipe": {
            "results": recipe_results, 
            "ingredients": [],
            "search_query": recipe_query
        },
        "response": message
    }


def _handle_selected_recipe(query: str, state: ChatState = None) -> Dict[str, Any]:
    """선택된 레시피 URL을 크롤링하고, 재료를 추출하여 DB 상품과 매핑합니다."""
    
    user_preferences = {}
    if state and state.user_id:
        user_preferences = get_user_preferences(state.user_id)
        logger.info(f"사용자 {state.user_id} 개인 선호도: {user_preferences}")
    
    recipe_url = _extract_recipe_url(query)
    if not recipe_url:
        logger.info("레시피 URL을 찾지 못함")
        return {
            "recipe": {"results": [], "ingredients": []},
            "response": "레시피 URL을 찾을 수 없어 재료를 추천할 수 없습니다."
        }
    
    structured_content = _scrape_and_structure_recipe(recipe_url)
    if not structured_content or not structured_content.get("ingredients"):
        logger.info("레시피 내용을 분석할 수 없음")
        return {
            "recipe": {"results": [], "ingredients": []},
            "response": "레시피 내용을 분석할 수 없어 재료 추천이 어렵습니다."
        }
    
    logger.info(f"레시피 구조화 완료: {structured_content.get('title', '제목 없음')}")
    
    extracted_ingredients = structured_content.get("ingredients", [])
    
    if user_preferences:
        filtered_ingredients = filter_recipe_ingredients(extracted_ingredients, user_preferences)
        logger.info(f"개인맞춤화 필터링: {len(extracted_ingredients)} -> {len(filtered_ingredients)}")
        extracted_ingredients = filtered_ingredients
        
        structured_content["ingredients"] = extracted_ingredients
    
    additional_keywords = []
    if state and state.rewrite.get("keywords"):
        filtered_keywords = [
            k for k in state.rewrite["keywords"] 
            if k not in ['재료', '구매', '상품', '추천', '쇼핑몰']
        ]
        additional_keywords.extend(filtered_keywords)
    
    all_search_terms = list(set(extracted_ingredients + additional_keywords))
    logger.info(f"DB 검색 키워드: {all_search_terms}")
    
    matched_products = _get_product_details_from_db(all_search_terms, user_preferences, state)  # hjs 수정 # 멀티턴 기능
    
    formatted_recipe_message = _format_recipe_content(structured_content, user_preferences)
    
    logger.info(f"레시피 처리 완료: 재료 {len(all_search_terms)}개, 추천 상품 {len(matched_products)}개")
    # print("recipe_search.py matched_products:",matched_products)
    # print("recipe_search.py formatted_recipe_message:",formatted_recipe_message)
    # print("recipe_search.py structured_content:",structured_content)
    return {
        "recipe": {
            "results": [],
            "ingredients": matched_products,
            "selected_recipe": structured_content
        },
        "meta": {
            "final_message": formatted_recipe_message 
        }
    }

def _get_product_details_from_db(
    ingredient_names: List[str],
    user_preferences: Dict[str, Any] = None,
    state: Optional[ChatState] = None
) -> List[Dict[str, Any]]:
    """상품 검색 노드를 활용해 레시피 재료에 맞는 상품을 조회합니다."""  # hjs 수정 # 멀티턴 기능
    if not ingredient_names:
        return []

    search_engine = get_search_engine()

    aggregated_products: List[Dict[str, Any]] = []
    seen_products: set = set()

    # hjs 수정: 중복 제거 및 병렬 검색 준비
    normalized_terms: List[str] = []
    seen_terms = set()
    for raw_term in ingredient_names:
        term = (raw_term or "").strip()
        if term and term not in seen_terms:
            seen_terms.add(term)
            normalized_terms.append(term)

    if not normalized_terms:
        return []

    base_user_id = state.user_id if state and state.user_id else 'anonymous'
    base_session_id = state.session_id if state else None
    history_tail = state.conversation_history[-6:] if state and state.conversation_history else []

    CHUNK_SIZE = 3  # 한 번의 검색에 사용할 재료 수 (hjs 수정)
    MAX_WORKERS = min(4, max(1, len(normalized_terms)))

    def _chunk_terms(seq: List[str], size: int) -> List[List[str]]:
        return [seq[i:i + size] for i in range(0, len(seq), size)]

    def _run_chunk(chunk_terms: List[str]) -> List[Dict[str, Any]]:
        query = " ".join(chunk_terms)
        temp_state = ChatState(user_id=base_user_id, session_id=base_session_id)
        temp_state.query = query
        temp_state.route = {"target": "product_search"}
        temp_state.rewrite = {"text": query, "keywords": chunk_terms}
        temp_state.slots = {"product": chunk_terms[0], "item": chunk_terms[0]}
        temp_state.search = {}
        temp_state.conversation_history = history_tail

        try:
            search_result = search_engine.search_products(temp_state)
        except Exception as err:
            logger.warning(f"레시피 연동 상품 검색 실패 (terms={chunk_terms}): {err}")
            return []

        if not search_result.get("success") or not search_result.get("candidates"):
            return []

        return search_result["candidates"]

    chunks = _chunk_terms(normalized_terms, CHUNK_SIZE)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_chunk = {executor.submit(_run_chunk, chunk): chunk for chunk in chunks}
        for future in as_completed(future_to_chunk):
            try:
                candidates = future.result()
            except Exception as err:
                logger.warning(f"병렬 상품 검색 중 오류 발생: {err}")
                continue

            for candidate in candidates:
                name = candidate.get("name") or candidate.get("sku") or ""
                if not name or name in seen_products:
                    continue
                if not _passes_user_preferences(name, user_preferences):
                    continue

                aggregated_products.append({
                    'name': name,
                    'price': float(candidate.get('price') or 0.0),
                    'origin': candidate.get('origin') or '정보 없음',
                    'organic': bool(candidate.get('organic')) if candidate.get('organic') is not None else False
                })
                seen_products.add(name)

                if len(aggregated_products) >= 15:
                    break

            if len(aggregated_products) >= 15:
                break

    if aggregated_products:
        logger.info(f"상품 검색 엔진 기반 추천 {len(aggregated_products)}개 확보")  # hjs 수정 # 멀티턴 기능
        return aggregated_products

    logger.info("상품 검색 엔진 결과 없음, 기존 DB 조회 폴백 수행")  # hjs 수정 # 멀티턴 기능
    return _legacy_product_details_lookup(ingredient_names, user_preferences)


def _passes_user_preferences(product_name: str, user_preferences: Optional[Dict[str, Any]]) -> bool:
    """사용자 선호/제약 조건을 만족하는지 확인합니다."""  # hjs 수정 # 멀티턴 기능
    if not user_preferences:
        return True

    lowered = product_name.lower()

    if user_preferences.get("vegan", False):
        vegan_exclusions = [
            "고기", "돼지", "소고기", "닭", "생선", "새우", "오징어",
            "계란", "달걀", "우유", "치즈", "버터", "요구르트", "베이컨",
            "햄", "소시지", "참치", "연어", "멸치", "젓갈"
        ]
        if any(exclusion in lowered for exclusion in vegan_exclusions):
            return False

    if user_preferences.get("allergy"):
        allergy_items = [item.strip().lower() for item in user_preferences["allergy"].split(",") if item.strip()]
        if any(allergen and allergen in lowered for allergen in allergy_items):
            return False

    if user_preferences.get("unfavorite"):
        unfavorite_items = [item.strip().lower() for item in user_preferences["unfavorite"].split(",") if item.strip()]
        if any(unfavorite and unfavorite in lowered for unfavorite in unfavorite_items):
            return False

    return True


def _legacy_product_details_lookup(ingredient_names: List[str], user_preferences: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """기존 SQL 기반 상품 조회 (폴백용)."""  # hjs 수정 # 멀티턴 기능
    conn = get_db_connection()
    if not conn:
        return []

    try:
        with conn.cursor(dictionary=True) as cursor:
            exclusion_conditions = []

            if user_preferences:
                if user_preferences.get("vegan", False):
                    vegan_exclusions = [
                        "고기", "돼지", "소고기", "닭", "생선", "새우", "오징어",
                        "계란", "달걀", "우유", "치즈", "버터", "요구르트", "베이컨",
                        "햄", "소시지", "참치", "연어", "멸치", "젓갈"
                    ]
                    for exclusion in vegan_exclusions:
                        exclusion_conditions.append(f"p.product NOT LIKE '%{exclusion}%'")
                    logger.info("비건 사용자 - 동물성 제품 제외 조건 추가")

                if user_preferences.get("allergy"):
                    allergy_items = [item.strip() for item in user_preferences["allergy"].split(",")]
                    for allergy in allergy_items:
                        exclusion_conditions.append(f"p.product NOT LIKE '%{allergy}%'")
                    logger.info(f"알러지 제외 조건 추가: {allergy_items}")

                if user_preferences.get("unfavorite"):
                    unfavorite_items = [item.strip() for item in user_preferences["unfavorite"].split(",")]
                    for unfavorite in unfavorite_items:
                        exclusion_conditions.append(f"p.product NOT LIKE '%{unfavorite}%'")
                    logger.info(f"선호도 제외 조건 추가: {unfavorite_items}")

            where_clauses = ' OR '.join(['p.product LIKE %s'] * len(ingredient_names))

            exclusion_clause = ""
            if exclusion_conditions:
                exclusion_clause = " AND " + " AND ".join(exclusion_conditions)

            sql = f"""
                SELECT p.product as name, p.unit_price as price, p.origin, p.organic
                FROM product_tbl p
                WHERE ({where_clauses}){exclusion_clause}
                LIMIT 15
            """

            params = [f"%{name}%" for name in ingredient_names]

            cursor.execute(sql, params)
            products = cursor.fetchall()

            formatted_products = []
            for p in products:
                formatted_products.append({
                    'name': p.get('name', ''),
                    'price': float(p.get('price', 0.0)),
                    'origin': p.get('origin', '정보 없음'),
                    'organic': True if p.get('organic') == 'Y' else False
                })

            logger.info(f"폴백 DB 조회 결과: {len(formatted_products)}개 상품")
            return formatted_products

    except Error as e:
        logger.error(f"상품 상세 정보 조회 실패: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            conn.close()

def _is_crawlable_url(url: str) -> bool:
    """URL이 크롤링 가능한지 간단히 판단합니다."""
    from urllib.parse import urlparse
    
    try:
        parsed = urlparse(url.lower())
        domain = parsed.netloc.replace('www.', '')
        
        excluded_patterns = ['youtube.', 'youtu.be', 'instagram.', 'facebook.', 'tiktok.', 'pinterest.']
        if any(pattern in domain for pattern in excluded_patterns):
            return False
        
        path = parsed.path.lower()
        if path.endswith(('.mp4', '.avi', '.mov', '.pdf', '.jpg', '.png', '.gif')):
            return False
            
        return True
        
    except Exception:
        return False

def _quick_validate_url(url: str) -> bool:
    """URL이 실제로 접근 가능한지 빠르게 확인합니다."""
    try:
        import requests
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.head(url, headers=headers, timeout=3)
        
        if 200 <= response.status_code < 300:
            content_type = response.headers.get('content-type', '').lower()
            return 'text/html' in content_type
            
        return False
    except Exception:
        return False

def _search_with_tavily_filtered(query: str, user_preferences: Dict[str, Any] = None, exclude_urls: List[str] = None) -> List[Dict[str, Any]]:
    """히스토리 기반 Tavily 검색 (이전 결과 제외)"""
    exclude_urls = exclude_urls or []

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)

        logger.info(f"히스토리 기반 Tavily 검색 실행: '{query}' (제외 URL: {len(exclude_urls)}개)")

        exclusion_terms = ["-youtube", "-instagram", "-facebook", "-tiktok", "-blog.naver.com"]

        if user_preferences:
            if user_preferences.get("vegan", False):
                meat_exclusions = ["-고기", "-돼지고기", "-소고기", "-닭고기", "-생선", "-육류"]
                exclusion_terms.extend(meat_exclusions)
                logger.info("비건 사용자 - 육류 관련 검색 결과 제외")

            if user_preferences.get("allergy"):
                allergy_items = user_preferences["allergy"].split(",")
                for item in allergy_items:
                    exclusion_terms.append(f"-{item.strip()}")
                logger.info(f"알러지 기반 제외 키워드 추가: {allergy_items}")

            if user_preferences.get("unfavorite"):
                unfavorite_items = user_preferences["unfavorite"].split(",")
                for item in unfavorite_items:
                    exclusion_terms.append(f"-{item.strip()}")
                logger.info(f"선호도 기반 제외 키워드 추가: {unfavorite_items}")

        enhanced_query = f"{query} 레시피 {' '.join(exclusion_terms)}"

        search_result = client.search(
            query=enhanced_query,
            search_depth="basic",
            max_results=30
        )

        search_results_list = search_result.get("results", [])
        random.shuffle(search_results_list)

        validated_results = []

        for res in search_results_list:
            url = res.get("url", "")

            if url in exclude_urls:
                logger.info(f"히스토리 기반 URL 제외: {url[:50]}...")
                continue

            if not url or not _is_crawlable_url(url):
                continue

            if not _quick_validate_url(url):
                logger.info(f"접근 불가능한 URL 제외: {url}")
                continue

            if user_preferences and should_exclude_recipe_content(
                res.get("title", ""), res.get("content", ""), user_preferences
            ):
                logger.info(f"개인 선호도에 의해 제외된 레시피: {res.get('title', 'Unknown')}")
                continue

            original_title = res.get("title", "제목 없음")
            content = res.get("content", "")

            title = original_title[:30] + ("..." if len(original_title) > 30 else "")
            description = content[:150]

            if openai_client and (original_title or content):
                try:
                    if original_title:
                        title_response = openai_client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "다음 레시피 제목을 30글자 내로 간단명료하게 요약해줘. 예시: '자취생도 쉽게 만드는 초간단 김치찌개 레시피' / '자꾸 땡기는 마약양념의 매콤한 닭볶음탕 조리법"},
                                {"role": "user", "content": f"제목 요약: {original_title}"}
                            ],
                            temperature=0.1, max_tokens=20
                        )
                        title_summary = title_response.choices[0].message.content.strip()
                        
                        title_summary = title_summary.strip('"').strip("'")
                        title = title_summary[:30] + ("..." if len(title_summary) > 30 else "")

                    if content:
                        desc_response = openai_client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "다음 레시피 내용을 20~30글자로 간단명료하게 요약해줘. 답변 예시 1: 김치·참치 볶아 두부 올린 매콤찌개 완성. 답변 예시 2: 닭고기 데쳐 채소 넣고 매콤하게 끓인 닭볶음탕"},
                                {"role": "user", "content": f"요약: {content[:300]}"}
                            ],
                            temperature=0.1, max_tokens=30
                        )
                        desc_summary = desc_response.choices[0].message.content.strip()
                        description = desc_summary[:30] + ("..." if len(desc_summary) > 30 else "")
                except Exception:
                    pass

            validated_results.append({
                "title": title,
                "url": url,
                "description": description
            })

            if len(validated_results) >= 3:
                break

        logger.info(f"히스토리 필터링된 레시피 URL: {len(validated_results)}개 (제외된 URL: {len(exclude_urls)}개)")
        return validated_results

    except Exception as e:
        logger.error(f"히스토리 기반 Tavily 검색 실패: {e}")
        return []

def _search_with_tavily(query: str, user_preferences: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Tavily API로 레시피를 검색하고, 결과를 섞은 후 검증합니다."""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)
        
        logger.info(f"Tavily 검색 실행: '{query}'")
        
        exclusion_terms = ["-youtube", "-instagram", "-facebook", "-tiktok", "-blog.naver.com", "-m.blog.naver.com"]

        if user_preferences:
            if user_preferences.get("vegan", False):
                meat_exclusions = ["-고기", "-돼지고기", "-소고기", "-닭고기", "-생선", "-육류"]
                exclusion_terms.extend(meat_exclusions)
                logger.info("비건 사용자 - 육류 관련 검색 결과 제외")

            if user_preferences.get("allergy"):
                allergy_items = user_preferences["allergy"].split(",")
                for item in allergy_items:
                    exclusion_terms.append(f"-{item.strip()}")
                logger.info(f"알러지 기반 제외 키워드 추가: {allergy_items}")

            if user_preferences.get("unfavorite"):
                unfavorite_items = user_preferences["unfavorite"].split(",")
                for item in unfavorite_items:
                    exclusion_terms.append(f"-{item.strip()}")
                logger.info(f"선호도 기반 제외 키워드 추가: {unfavorite_items}")
        
        enhanced_query = f"{query} 레시피 {' '.join(exclusion_terms)}"
        
        search_result = client.search(
            query=enhanced_query,
            search_depth="basic",
            max_results=20 
        )
        
        search_results_list = search_result.get("results", [])
        random.shuffle(search_results_list)

        validated_results = []
        
        for res in search_results_list:
            url = res.get("url", "")
            
            if not url or not _is_crawlable_url(url):
                continue
            
            if not _quick_validate_url(url):
                logger.info(f"접근 불가능한 URL 제외: {url}")
                continue
            
            if user_preferences and should_exclude_recipe_content(
                res.get("title", ""), res.get("content", ""), user_preferences
            ):
                logger.info(f"개인 선호도에 의해 제외된 레시피: {res.get('title', 'Unknown')}")
                continue
            
            original_title = res.get("title", "제목 없음")
            content = res.get("content", "")
            
            title = original_title[:30] + ("..." if len(original_title) > 30 else "")
            description = content[:150]
            
            if openai_client and (original_title or content):
                try:
                    if original_title:
                        title_response = openai_client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "다음 레시피 제목을 30글자 내로 간단명료하게 요약해줘. 예시: '자취생도 쉽게 만드는 초간단 김치찌개 레시피' / '자꾸 땡기는 마약양념의 매콤한 닭볶음탕 조리법"},
                                {"role": "user", "content": f"제목 요약: {original_title}"}
                            ],
                            temperature=0.1, max_tokens=20
                        )
                        title_summary = title_response.choices[0].message.content.strip()
                        title_summary = title_summary.strip('"').strip("'")
                        title = title_summary[:30] + ("..." if len(title_summary) > 30 else "")
                    
                    if content:
                        desc_response = openai_client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "다음 레시피 내용을 20~30글자로 간단명료하게 요약해줘. 답변 예시 1: 김치·참치 볶아 두부 올린 매콤찌개 완성. 답변 예시 2: 닭고기 데쳐 채소 넣고 매콤하게 끓인 닭볶음탕"},
                                {"role": "user", "content": f"요약: {content[:300]}"}
                            ],
                            temperature=0.1, max_tokens=30
                        )
                        desc_summary = desc_response.choices[0].message.content.strip()
                        description = desc_summary[:30] + ("..." if len(desc_summary) > 30 else "")
                except Exception:
                    pass

            validated_results.append({
                "title": title,
                "url": url,
                "description": description            
            })
            
            if len(validated_results) >= 3:
                break
        
        logger.info(f"검증된 레시피 URL: {len(validated_results)}개")
        return validated_results
        
    except Exception as e:
        logger.error(f"Tavily 검색 실패: {e}")
        return []

def _scrape_and_structure_recipe(url: str) -> Optional[Dict[str, Any]]:
    """URL을 크롤링하고 LLM을 사용해 내용을 구조화합니다."""
    logger.info(f"URL 크롤링 및 분석 시작: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        page_text = soup.get_text(separator='\n', strip=True)
        
        if not openai_client:
            logger.warning("OpenAI 클라이언트가 없어 레시피 구조화 불가.")
            return None
            
        return _llm_extract_recipe_content(page_text[:4000])

    except Exception as e:
        logger.error(f"URL 크롤링 및 구조화 실패 {url}: {e}")
        return None

def _extract_recipe_query(original_query: str, rewrite_query: str = "") -> str:
    """사용자 쿼리에서 검색에 사용할 핵심 레시피명을 추출합니다."""
    if not openai_client:
        return f"{original_query} 레시피"

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "사용자의 질문에서 핵심 요리 이름만 추출해줘. 예를 들어 '김치찌개 맛있게 끓이는 법 알려줘' -> '김치찌개'"},
                {"role": "user", "content": f"원본: '{original_query}', 재작성: '{rewrite_query}'"}
            ],
            temperature=0.1, max_tokens=50
        )
        return response.choices[0].message.content.strip().strip('"')
    except Exception as e:
        logger.error(f"LLM 쿼리 추출 실패: {e}")
        return f"{original_query} 레시피"

def _get_all_items_from_db() -> List[str]:
    """DB에서 모든 품목명(item)을 가져와서 중복 제거된 리스트로 반환합니다."""
    conn = get_db_connection()
    if not conn:
        logger.warning("DB 연결 실패로 품목명을 가져올 수 없습니다.")
        return []

    try:
        with conn.cursor() as cursor:
            sql = "SELECT DISTINCT item FROM product_tbl WHERE item IS NOT NULL ORDER BY item"
            cursor.execute(sql)
            items = [row[0] for row in cursor.fetchall()]
            logger.info(f"DB에서 {len(items)}개의 품목명을 가져왔습니다.")
            return items
    except Error as e:
        logger.error(f"품목명 조회 실패: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            conn.close()

def _llm_extract_recipe_content(page_text: str) -> Dict[str, Any]:
    """LLM을 사용하여 웹페이지 텍스트에서 레시피 정보를 JSON 형태로 구조화합니다."""
    
    db_items = _get_all_items_from_db()
    db_items_str = ", ".join(db_items) if db_items else "품목 데이터를 가져올 수 없음"
    
    system_prompt = f"""당신은 신선식품 쇼핑몰을 위한 레시피 분석 전문가입니다.
웹페이지 텍스트에서 레시피 정보를 추출하여 고객에게 필요한 재료를 추천할 수 있도록 도와주세요.

**🔍 DB 품목 참조 데이터:**
{{{db_items_str}}}

**추출 규칙:**
1. **title**: 요리의 정확한 이름 (예: "김치찌개", "볶음밥")
2. **ingredients**: 쇼핑몰에서 구매 가능한 신선식품 재료만 추출
## 기본 원칙
재료의 **핵심 명사 형태**로 표준화합니다.
예: '대파', '양파', '돼지고기'
---
## 1단계: 복합어 분해
**복합어를 반드시 분해하여 기본 재료만 추출하세요**
**분해 예시:**
- '신김치' → '김치' (신선도 표현 제거)
- '다진마늘' → '마늘' (조리 상태 제거)
- '볶은깨' → '깨' (조리법 제거)
- '으깬감자' → '감자' (조리 상태 제거)
- '썬양파' → '양파' (썰기 방법 제거)
- '데친시금치' → '시금치' (전처리 제거)

**분해 원칙:**

**제거해야 할 수식어들:**
- 형용사/관형어: 신선한, 다진, 썬, 데친, 볶은, 으깬 등
- 조리법: 볶음, 무침, 절임 등
- 상태 표현: 익은, 생, 마른, 젖은 등
- 크기/형태: 큰, 작은, 얇은, 두꺼운 등

**특수 케이스:**
- "풋고추" → "고추"
- "애호박" → "호박"
- "새우젓" → "새우"

**핵심**: 하나의 단어로 보이더라도 반드시 의미 단위로 분해하세요
---
## 2단계: DB 품목명 표준화

**분해된 재료를 DB 품목 참조 데이터와 비교하여 표준화하세요**

**DB 표준화 예시:**
- '계란' → '달걀' (DB에 있는 정확한 품목명 사용)
- '삼겹살', '목살', '갈비살' → '돼지고기' (DB에 '돼지고기'로 통합)
- '치킨', '닭다리', '닭가슴살' → '닭고기' (DB에 '닭고기'로 통합)
- '쪽파', '파' → '대파' (DB에 '대파'로 표준화)
- '양배추' → '배추' (DB에 '배추'로 등록)
- '고춧가루', '빨간 고추' → '고추' (DB에 '고추'로 표준화)
- '청경채', '로메인' → '상추' (DB에 '상추'로 분류)

**표준화 원칙:**
1. 먼저 DB 품목 데이터에서 정확히 일치하는 명칭이 있는지 확인
2. 일치하는 명칭이 없으면 유사한 카테고리의 대표 품목명으로 매핑
3. DB에 전혀 없는 재료는 일반적인 명칭 사용

---

## 전체 처리 예시

**입력 레시피:**
"다진마늘 2쪽, 신김치 200g, 삼겹살 300g"

**1단계 처리 (복합어 분해):**
"다진마늘" → "마늘"
"신김치" → "김치" 
"삼겹살" → "삼겹살" (이미 기본형)

**2단계 처리 (DB 표준화):**
"마늘" → "마늘" (DB에 있음)
"김치" → "김치" (일반 명칭 유지)
"삼겹살" → "돼지고기" (DB 표준명)

**최종 결과:**
["마늘", "김치", "돼지고기"]
---

## 주의사항
1. 반드시 1단계(분해) → 2단계(표준화) 순서로 처리하세요
2. 각 단계를 건너뛰지 말고 순차적으로 적용하세요
3. 절대로 복합어를 그대로 사용하지 마세요
4. DB 품목 데이터에서 정확한 명칭을 찾아 사용하세요

- quantity: 수량을 정확히 추출합니다. 분수('1/2')는 소수점(0.5)으로 변환하고, 수량이 명시되지 않으면 1로 간주합니다.
- unit: 단위를 정확히 추출합니다. (예: 'g', '개', '컵', 'T', 't')
- 포함할 것: 신선식품(육류, 채소, 과일), 구매 가능한 가공식품(두부, 면, 통조림), 양념/조미료(간장, 된장, 참기름, 다진 마늘)
3. **instructions**: 고객이 이해하기 쉬운 조리법 요약
    - 초보자도 쉽게 이해할 수 있도록 각 단계를 상세하고 친절하게 설명합니다.
    - 각 단계는 '\\n'으로 구분(중요)
    - 전문 용어보다는 일반적인 표현 사용
    - 가열 온도(예: 중불), 조리 시간(예: 5분간), 구체적인 양(예: 5g, 한 스푼) 등 구체적인 정보를 포함합니다.

**출력 형식:**
반드시 다음 JSON 구조로만 응답하세요:
```json
{{
    "title": "요리명",
    "ingredients": ["재료1", "재료2", "재료3"],
    "instructions": "1단계 설명\\n2단계 설명\\n3단계 설명"
}}
```

**예시:**
입력: "돼지고기 김치찌개 레시피... 돼지고기 200g, 김치 300g, 양파 1개, 대파 2대, 두부 1모..."
출력:
```json
{{
  "title": "돼지고기 김치찌개",
  "ingredients": ["돼지고기", "김치", "두부", "양파", "대파", "국간장", "고춧가루"],
  "instructions": "1. 달군 냄비에 돼지고기를 200g 넣고 중불에서 겉면이 익을 때까지 약 3분간 볶아줍니다.\\n2. 돼지고기가 익으면 김치를 300g 넣고 5분간 함께 충분히 볶아 깊은 맛을 더해줍니다.\\n3. 물 한 컵을 붓고 끓어오르면, 국간장과 고춧가루를 각각 반 스푼, 한 스푼씩 넣고 중불에서 10분간 더 끓여줍니다.\\n4. 마지막으로 두부, 양파, 대파를 잘게 썰어넣고 5분간 한소끔 더 끓여 완성합니다."
}}
입력:"달걀볶음밥 레시피... 신선한달걀 3개, 찬밥 2공기, 다진당근 100g, 매운양파 반개, 썬대파 2대, 진간장 2스푼, 참기름 1스푼
출력
{{
  "title": "달걀 볶음밥",
  "ingredients": ["달걀", "쌀", "당근", "양파", "대파", "간장", "참기름"],
  "instructions": "1. 달걀 3개를 그릇에 풀어서 소금 한 꼬집을 넣고 잘 섞어줍니다.\\n2. 팬에 기름을 두르고 달걀물을 넣어 젓가락으로 빠르게 저어가며 스크램블을 만듭니다.\\n3. 당근과 양파는 잘게 다져서 팬에 넣고 2분간 볶아줍니다.\\n4. 찬밥 2공기를 넣고 간장 2스푼, 참기름 1스푼을 넣어 3분간 볶습니다.\\n5. 마지막에 대파와 달걀을 넣고 30초간 더 볶아 완성합니다."
}}
입력:"시금치나물 만드는법... 신선한시금치 200g, 다진마늘 2쪽, 국간장 1스푼, 고소한참기름 2스푼, 향긋한깻잎 5장
출력:
{{
  "title": "시금치 나물",
  "ingredients": ["시금치", "마늘", "간장", "참기름", "깻잎"],
  "instructions": "1. 시금치 200g을 깨끗이 씻어서 끓는 물에 30초간 데쳐줍니다.\\n2. 찬물에 헹궈서 물기를 꼭 짜낸 후 3-4cm 길이로 썰어줍니다.\\n3. 마늘 2쪽을 곱게 다져서 준비합니다.\\n4. 시금치에 다진 마늘, 간장 1스푼, 참기름 2스푼을 넣고 잘 무쳐줍니다.\\n5. 깻잎을 잘게 썰어서 마지막에 올려 완성합니다."
}}
입력:"연어구이 레시피... 노르웨이산연어 300g, 상큼한레몬 1개, 엑스트라버진올리브오일 2스푼, 다진마늘 3쪽, 데친브로콜리 150g
출력:
{{
  "title": "연어 구이",
  "ingredients": ["연어", "레몬", "올리브오일", "마늘", "브로콜리"],
  "instructions": "1. 연어 300g을 한입 크기로 썰어서 소금, 후추로 밑간을 해줍니다.\\n2. 마늘 3쪽을 편으로 썰고 레몬은 반달 모양으로 썰어 준비합니다.\\n3. 팬에 올리브오일을 두르고 중약불에서 마늘을 1분간 볶아 향을 냅니다.\\n4. 연어를 넣고 한 면당 3분씩 노릇하게 구워줍니다.\\n5. 브로콜리를 데쳐서 함께 담고 레몬을 올려 완성합니다."
}}
입력:"닭고기찜 만들기... 토종닭고기 500g, 큰감자 2개, 단당근 1개, 매운양파 1개, 시원한된장 2스푼, 다진마늘 5쪽, 썬생강 1쪽
출력:
{{
  "title": "닭고기 찜",
  "ingredients": ["닭고기", "감자", "당근", "양파", "된장", "마늘", "생강"],
  "instructions": "1. 닭고기 500g을 찬물에 30분간 담가 핏물을 제거합니다.\\n2. 감자와 당근은 큼직하게 썰고, 양파는 4등분으로 썰어줍니다.\\n3. 마늘 5쪽과 생강 1쪽을 편으로 썰어 준비합니다.\\n4. 냄비에 닭고기를 넣고 물을 자작하게 부은 후 된장 2스푼을 풀어 넣습니다.\\n5. 마늘, 생강을 넣고 센불에서 끓인 후 중불로 줄여 20분간 끓입니다.\\n6. 감자, 당근, 양파를 넣고 15분간 더 끓여 완성합니다."
}}
입력:"돼지고기김치찌개 레시피... 삼겹살 200g, 신김치 300g, 부드러운두부 1모, 매운양파 1개, 썬대파 2대, 진간장 반스푼, 고춧가루 1스푼
출력:
{{
  "title": "돼지고기 김치찌개",
  "ingredients": ["돼지고기", "김치", "두부", "양파", "대파", "간장", "고추"],
  "instructions": "1. 달군 냄비에 돼지고기를 200g 넣고 중불에서 겉면이 익을 때까지 약 3분간 볶아줍니다.\\n2. 돼지고기가 익으면 김치를 300g 넣고 5분간 함께 충분히 볶아 깊은 맛을 더해줍니다.\\n3. 물 한 컵을 붓고 끓어오르면, 간장과 고춧가루를 각각 반 스푼, 한 스푼씩 넣고 중불에서 10분간 더 끓여줍니다.\\n4. 마지막으로 두부, 양파, 대파를 잘게 썰어넣고 5분간 한소끔 더 끓여 완성합니다."
}}
```

중요: JSON 형식 외에 다른 텍스트는 출력하지 마세요."""
    user_prompt = f"다음 웹페이지 텍스트에서 레시피 정보를 추출해줘:\n\n---\n{page_text}\n---"

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2, max_tokens=1024
    )
    
    try:
        content = json.loads(response.choices[0].message.content)
        if isinstance(content.get("ingredients"), str):
            content["ingredients"] = [item.strip() for item in content["ingredients"].split(',')]
        return content
    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(f"LLM JSON 파싱 실패: {e}")
        return {}

def _extract_recipe_url(query: str) -> Optional[str]:
    """쿼리 문자열에서 URL을 추출합니다."""
    match = re.search(r'URL:\s*(https?://[^\s]+)', query)
    if match:
        return match.group(1)
    logger.warning(f"쿼리에서 URL을 찾지 못함: {query}")
    return None

def _format_recipe_content(structured_content: Dict[str, Any], user_preferences: Dict[str, Any] = None) -> str:
    """구조화된 레시피 데이터를 AIMessage에 표시할 문자열로 포맷팅합니다."""
    title = structured_content.get("title", "레시피 정보")
    ingredients = structured_content.get("ingredients", [])
    instructions = structured_content.get("instructions", "조리법 정보가 없습니다.")
    
    ingredients_text = "\n".join(f"- {ing}" for ing in ingredients[:10])
    if len(ingredients) > 10:
        ingredients_text += "\n- 등..."

    personalized_note = ""
    if user_preferences:
        if user_preferences.get("vegan"):
            personalized_note += "**🌱 비건 레시피로 개인맞춤화되었습니다.**\n"
        if user_preferences.get("allergy"):
            personalized_note += f"**⚠️ 알러지({user_preferences['allergy']}) 정보가 반영되었습니다.**\n"
        if user_preferences.get("unfavorite"):
            personalized_note += f"**❌ 선호하지 않는 음식({user_preferences['unfavorite']})이 제외되었습니다.**\n"
        if personalized_note:
            personalized_note += "\n"

    formatted_message = (
        f"**{title}**\n\n"
        f"{personalized_note}"
        f"**필요한 재료:**\n{ingredients_text}\n\n"
        f"**조리법 요약:**\n{instructions}\n\n"
        "---\n"
        "**우측 사이드바에서 추천 재료들을 바로 장바구니에 담아보세요!**\n"
        "**필요한 재료가 상품에 없는 경우 대체 상품이 추천될 수 있습니다.**"
    )
    
    return formatted_message
