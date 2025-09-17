"""
대화 히스토리 관리 유틸리티

히스토리 메시지 포맷:
{
    "role": "user" | "assistant",
    "content": "메시지 내용",
    "timestamp": "2025-01-20T10:30:00Z",
    "message_type": "text" | "recipe_request" | "emotional" | "casual",
    "emotion": "happy" | "sad" | "angry" | "stressed" | "neutral",
    "intent": "casual_chat" | "recipe_search" | "product_search"
}

사용자 컨텍스트 포맷:
{
    "current_mood": "stressed",
    "recent_topics": ["친구 싸움", "스트레스"],
    "preferred_food_types": ["매운음식", "따뜻한음식"],
    "conversation_theme": "emotional_support"
}
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
import logging
import json
import os

# ChatState import 추가
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_interfaces import ChatState

logger = logging.getLogger(__name__)

# OpenAI 클라이언트 설정
try:
    import openai
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        openai_client = openai.OpenAI(api_key=openai_api_key)
    else:
        openai_client = None
        logger.warning("OpenAI API key not found. Using fallback analysis.")
except ImportError:
    openai_client = None
    logger.warning("OpenAI package not available.")


def add_to_history(state: ChatState, role: str, content: str, **metadata) -> None:
    """
    ChatState의 conversation_history에 메시지 직접 추가 (메모리 기반)

    Args:
        state: ChatState 객체 (세션별로 영속적으로 관리됨)
        role: 'user' 또는 'assistant'
        content: 메시지 내용
        **metadata: 추가 메타데이터 (emotion, context 등)
    """
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        **metadata
    }

    state.conversation_history.append(message)

    logger.info(f"Added to memory history [{len(state.conversation_history)} total]: {role} - {content[:50]}...")

    # 히스토리 길이 자동 관리 (메모리 효율성)
    if len(state.conversation_history) > 20:  # 약간의 버퍼 제공
        manage_history_length(state, max_messages=15)


def manage_history_length(state: ChatState, max_messages: int = 15) -> None:
    """
    메모리 기반 히스토리 길이 관리

    Args:
        state: ChatState 객체
        max_messages: 유지할 최대 메시지 수

    Note:
        메모리에서 직접 히스토리를 관리하여 토큰 수 제한과 메모리 효율성 확보
    """
    if len(state.conversation_history) > max_messages:
        # 최근 메시지만 유지 (메모리에서 직접 처리)
        trimmed_count = len(state.conversation_history) - max_messages
        state.conversation_history = state.conversation_history[-max_messages:]

        logger.info(f"Memory history trimmed: removed {trimmed_count} old messages, kept {max_messages} recent messages")


def get_recent_context(history: List[Dict], turns: int = 3) -> str:
    """최근 대화 맥락 요약 (기존 호환성 유지)"""
    if not history:
        return "새로운 대화"

    recent_messages = history[-turns*2:] if len(history) >= turns*2 else history
    context_parts = []

    for msg in recent_messages:
        role = "사용자" if msg["role"] == "user" else "봇"
        content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
        context_parts.append(f"{role}: {content}")

    return "\n".join(context_parts)


def get_contextual_analysis(history: List[Dict], current_query: str) -> Dict[str, Any]:
    """향상된 맥락 분석 - 이전 추천 내역과 연관성 파악"""
    if not history:
        return {
            "previous_recommendations": [],
            "conversation_theme": "new_conversation",
            "followup_intent": "none",
            "suggested_alternatives": [],
            "context_summary": "새로운 대화 시작"
        }

    # LLM 기반 맥락 분석 시도
    if openai_client:
        return get_contextual_analysis_llm(history, current_query)
    else:
        return get_contextual_analysis_fallback(history, current_query)


# def get_contextual_analysis_llm(history: List[Dict], current_query: str) -> Dict[str, Any]:
#     """LLM 기반 고급 맥락 분석 (원본 버전 - 빈 히스토리 처리 문제 있음)"""
#     try:
#         recent_context = get_recent_context(history, turns=5)

#         system_prompt = """
# 당신은 대화 맥락을 분석하는 전문가입니다.
# 이전 대화에서 봇이 추천한 내용과 현재 사용자 질문의 연관성을 분석해주세요.

# 분석 항목:
# 1. 이전 추천 내역 추출
# 2. 현재 질문의 의도 파악 (새로운 요청 vs 연관 요청 vs 후속 질문)
# 3. 대화 주제 연속성
# 4. 제안할 대안 카테고리

# JSON 형태로만 답변하세요:
# {
#     "previous_recommendations": ["이전에 추천한 항목들"],
#     "conversation_theme": "대화 주제",
#     "followup_intent": "none|similar|alternative|clarification",
#     "suggested_alternatives": ["제안할 대안들"],
#     "context_summary": "맥락 요약"
# }

# followup_intent 설명:
# - none: 완전히 새로운 요청
# - similar: 비슷한 것 더 요청
# - alternative: 다른 대안 요청 ("다른 XX 없을까?")
# - clarification: 명확화 요청
# """

#         user_prompt = f"""
# 최근 대화 맥락:
# {recent_context}

# 현재 사용자 질문: "{current_query}"

# 위 정보를 분석해주세요.
# """

#         response = openai_client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": user_prompt}
#             ],
#             max_tokens=300,
#             temperature=0.3
#         )

#         result_text = response.choices[0].message.content.strip()

#         try:
#             result = json.loads(result_text)
#             logger.info(f"LLM contextual analysis: {result}")
#             return result
#         except json.JSONDecodeError:
#             logger.warning(f"Failed to parse LLM contextual analysis: {result_text}")
#             return get_contextual_analysis_fallback(history, current_query)

#     except Exception as e:
#         logger.error(f"LLM contextual analysis failed: {e}")
#         return get_contextual_analysis_fallback(history, current_query)


def get_contextual_analysis_llm(history: List[Dict], current_query: str) -> Dict[str, Any]:
    """LLM 기반 고급 맥락 분석 (빈 히스토리 처리 개선 버전)"""
    try:
        recent_context = get_recent_context(history, turns=5)
        is_empty_history = recent_context == "새로운 대화"

        system_prompt = """
🚨 **절대 규칙 - 반드시 준수하세요**:
1. 대화 맥락이 "새로운 대화"이면 previous_recommendations는 반드시 빈 배열 []이어야 합니다.
2. 현재 질문만으로 이전 추천을 절대 추측하거나 만들어내지 마세요.
3. 실제 이전 대화에서 봇이 추천한 내용만 추출하세요.
4. 빈 히스토리에서는 followup_intent가 반드시 "none"이어야 합니다.

당신은 대화 맥락을 분석하는 전문가입니다.
이전 대화에서 봇이 추천한 내용과 현재 사용자 질문의 연관성을 분석해주세요.

빈 히스토리 처리 규칙:
- 대화 맥락이 "새로운 대화"인 경우:
  * previous_recommendations: []
  * followup_intent: "none"
  * conversation_theme: "new_conversation"
  * context_summary: "새로운 대화 시작"

JSON 형태로만 답변하세요:
{
    "previous_recommendations": ["이전에 추천한 항목들 - 빈 히스토리면 반드시 []"],
    "conversation_theme": "대화 주제",
    "followup_intent": "none|similar|alternative|clarification",
    "suggested_alternatives": ["제안할 대안들"],
    "context_summary": "맥락 요약"
}

followup_intent 설명:
- none: 완전히 새로운 요청 (빈 히스토리는 항상 이것)
- similar: 비슷한 것 더 요청
- alternative: 다른 대안 요청 ("다른 XX 없을까?")
- clarification: 명확화 요청
"""

        user_prompt = f"""
히스토리 상태: {"EMPTY (빈 히스토리)" if is_empty_history else "EXISTS (히스토리 존재)"}

최근 대화 맥락:
{recent_context}

현재 사용자 질문: "{current_query}"

⚠️ 중요: 히스토리 상태가 EMPTY면 previous_recommendations는 반드시 []이어야 합니다.
현재 질문만으로 이전 추천을 추측하지 마세요.

위 정보를 분석해주세요.
"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=300,
            temperature=0.2  # 더 일관된 응답을 위해 temperature 낮춤
        )

        result_text = response.choices[0].message.content.strip()

        try:
            result = json.loads(result_text)

            # 빈 히스토리 상황에서 응답 검증 및 강제 수정
            if is_empty_history:
                if result.get("previous_recommendations") and len(result["previous_recommendations"]) > 0:
                    logger.warning(f"빈 히스토리인데 previous_recommendations가 존재함: {result['previous_recommendations']} -> [] 강제 수정")
                    result["previous_recommendations"] = []

                if result.get("followup_intent") != "none":
                    logger.warning(f"빈 히스토리인데 followup_intent가 'none'이 아님: {result['followup_intent']} -> 'none' 강제 수정")
                    result["followup_intent"] = "none"

                result["conversation_theme"] = "new_conversation"
                result["context_summary"] = "새로운 대화 시작"

            logger.info(f"LLM contextual analysis (개선 버전): {result}")
            return result

        except json.JSONDecodeError:
            logger.warning(f"Failed to parse LLM contextual analysis: {result_text}")
            return get_contextual_analysis_fallback(history, current_query)

    except Exception as e:
        logger.error(f"LLM contextual analysis failed: {e}")
        return get_contextual_analysis_fallback(history, current_query)


def get_contextual_analysis_fallback(history: List[Dict], current_query: str) -> Dict[str, Any]:
    """폴백 맥락 분석 (키워드 기반)"""
    # 최근 봇 메시지에서 추천 내역 추출
    previous_recommendations = []
    conversation_theme = "general"

    recent_bot_messages = [
        msg["content"] for msg in history[-10:]
        if msg["role"] == "assistant"
    ]

    # 간단한 키워드 기반 추천 내역 추출
    for content in recent_bot_messages:
        content_lower = content.lower()
        if any(keyword in content_lower for keyword in ["스프", "수프", "soup"]):
            if "치킨" in content_lower:
                previous_recommendations.append("치킨수프")
            if "토마토" in content_lower:
                previous_recommendations.append("토마토수프")
            if "바질" in content_lower:
                previous_recommendations.append("바질수프")

        # 기타 음식 카테고리들
        food_keywords = {
            "라면": ["라면", "면", "noodle"],
            "김치찌개": ["김치찌개", "찌개"],
            "치킨": ["치킨", "chicken", "닭"],
            "피자": ["피자", "pizza"]
        }

        for food, keywords in food_keywords.items():
            if any(k in content_lower for k in keywords):
                previous_recommendations.append(food)

    # 후속 의도 파악
    query_lower = current_query.lower()
    followup_intent = "none"

    if any(pattern in query_lower for pattern in ["다른", "또", "말고", "else", "other"]):
        followup_intent = "alternative"
    elif any(pattern in query_lower for pattern in ["비슷한", "similar", "같은"]):
        followup_intent = "similar"
    elif any(pattern in query_lower for pattern in ["뭐", "어떤", "what", "?"]):
        followup_intent = "clarification"

    # 대안 제안
    suggested_alternatives = []
    if "스프" in query_lower or "수프" in query_lower:
        suggested_alternatives = ["옥수수수프", "크림수프", "버섯수프", "호박수프"]
    elif "라면" in query_lower:
        suggested_alternatives = ["우동", "쫄면", "냉면", "비빔면"]
    elif "치킨" in query_lower:
        suggested_alternatives = ["삼겹살", "갈비", "불고기", "스테이크"]

    return {
        "previous_recommendations": list(set(previous_recommendations)),  # 중복 제거
        "conversation_theme": conversation_theme,
        "followup_intent": followup_intent,
        "suggested_alternatives": suggested_alternatives,
        "context_summary": f"이전 추천: {', '.join(previous_recommendations[:3]) if previous_recommendations else '없음'}"
    }


def analyze_user_emotion(query: str, history: List[Dict]) -> Dict[str, Any]:
    """LLM 기반 사용자 감정 상태와 상황 분석"""

    if openai_client:
        return analyze_user_emotion_llm(query, history)
    else:
        return analyze_user_emotion_fallback(query, history)


def analyze_user_emotion_llm(query: str, history: List[Dict]) -> Dict[str, Any]:
    """LLM을 사용한 동적 감정 분석"""
    try:
        # 최근 대화 맥락 구성
        recent_context = get_recent_context(history, turns=3) if history else "새로운 대화"

        system_prompt = """
당신은 사용자의 감정과 상황을 분석하는 전문가입니다.
사용자의 메시지와 대화 히스토리를 보고 감정 상태를 정확히 파악해주세요.

감정 분류:
- happy: 기쁨, 행복, 즐거움, 만족
- sad: 슬픔, 우울, 좌절, 실망
- angry: 화남, 짜증, 분노, 억울함
- stressed: 스트레스, 압박감, 바쁨, 부담
- lonely: 외로움, 고독, 쓸쓸함
- tired: 피곤, 지침, 무기력
- excited: 흥분, 기대, 설렘
- worried: 걱정, 불안, 염려
- neutral: 중립적, 일상적 대화

상황 분석도 포함해서 JSON 형태로만 답변하세요:
{
    "primary_emotion": "감정명",
    "confidence": 0.0-1.0,
    "context": "구체적인 상황 설명",
    "intensity": "low|medium|high",
    "food_mood": "어떤 스타일의 음식이 도움될지"
}
"""

        user_prompt = f"""
최근 대화 맥락:
{recent_context}

현재 사용자 메시지: "{query}"

위 정보를 바탕으로 사용자의 감정과 상황을 분석해주세요.
"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=200,
            temperature=0.3
        )

        result_text = response.choices[0].message.content.strip()

        # JSON 파싱 시도
        try:
            result = json.loads(result_text)
            logger.info(f"LLM emotion analysis: {result}")
            return result
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse LLM response as JSON: {result_text}")
            return analyze_user_emotion_fallback(query, history)

    except Exception as e:
        logger.error(f"LLM emotion analysis failed: {e}")
        return analyze_user_emotion_fallback(query, history)


def analyze_user_emotion_fallback(query: str, history: List[Dict]) -> Dict[str, Any]:
    """LLM 실패 시 폴백 키워드 기반 감정 분석"""
    emotion_keywords = {
        "sad": ["슬퍼", "우울해", "힘들어", "싸웠어", "속상해", "눈물", "아파"],
        "stressed": ["스트레스", "피곤해", "지쳐", "바빠", "힘들어", "답답해"],
        "happy": ["좋아", "기뻐", "행복해", "즐거워", "신나", "완전", "최고"],
        "angry": ["화나", "짜증", "분해", "억울해", "열받", "빡쳐"],
        "lonely": ["외로워", "혼자", "쓸쓸해", "심심해"],
        "tired": ["피곤", "졸려", "잠", "지쳐"]
    }

    query_lower = query.lower()
    detected_emotions = []

    for emotion, keywords in emotion_keywords.items():
        for keyword in keywords:
            if keyword in query_lower:
                detected_emotions.append(emotion)
                break

    primary_emotion = detected_emotions[0] if detected_emotions else "neutral"
    confidence = 0.8 if detected_emotions else 0.3
    context = extract_context_from_history(history, query)

    return {
        "primary_emotion": primary_emotion,
        "confidence": confidence,
        "context": context,
        "intensity": "medium",
        "food_mood": "일반적인 음식"
    }


def extract_context_from_history(history: List[Dict], current_query: str) -> str:
    """히스토리에서 상황 맥락 추출"""
    if not history:
        return "새로운 대화 시작"

    recent_user_messages = [
        msg["content"] for msg in history[-6:]
        if msg["role"] == "user"
    ]

    # 간단한 키워드 기반 맥락 추출
    context_keywords = {
        "친구": "친구 관계",
        "싸움": "갈등 상황",
        "직장": "직장 스트레스",
        "공부": "학업 스트레스",
        "가족": "가족 문제",
        "연애": "연애 고민"
    }

    all_text = " ".join(recent_user_messages + [current_query])

    for keyword, context in context_keywords.items():
        if keyword in all_text:
            return context

    return "일상 대화"


def get_empathy_response(emotion: str, context: str, intensity: str = "medium") -> str:
    """LLM 기반 공감 메시지 생성"""

    if openai_client:
        return get_empathy_response_llm(emotion, context, intensity)
    else:
        return get_empathy_response_fallback(emotion, context)


def get_empathy_response_llm(emotion: str, context: str, intensity: str) -> str:
    """LLM을 사용한 동적 공감 메시지 생성"""
    try:
        system_prompt = """
당신은 따뜻하고 공감적인 신선식품 쇼핑몰의 챗봇입니다.
사용자의 감정과 상황에 맞는 진심어린 공감 메시지를 생성해주세요.

가이드라인:
- 진심어린 공감과 위로 표현
- 적절한 이모지 사용 (과하지 않게)
- 1-2문장으로 간결하게
- 친근하고 따뜻한 톤
- 상황에 맞는 자연스러운 한국어

감정 강도에 따른 톤 조절:
- low: 가벼운 공감
- medium: 적당한 공감과 위로
- high: 깊은 공감과 진심어린 위로
"""

        user_prompt = f"""
사용자 감정: {emotion}
상황 맥락: {context}
감정 강도: {intensity}

위 정보를 바탕으로 공감 메시지를 생성해주세요. 메시지만 출력하세요.
"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=100,
            temperature=0.7
        )

        result = response.choices[0].message.content.strip()
        logger.info(f"LLM empathy response: {result}")
        return result

    except Exception as e:
        logger.error(f"LLM empathy response failed: {e}")
        return get_empathy_response_fallback(emotion, context)


def get_empathy_response_fallback(emotion: str, context: str) -> str:
    """폴백 공감 메시지 생성"""
    empathy_templates = {
        "sad": [
            "아이고, 마음이 많이 아프시겠어요. 😢",
            "힘든 일이 있으셨군요. 속상하셨을 텐데...",
            "마음이 무거우시겠네요. 😔"
        ],
        "stressed": [
            "아이고, 스트레스 받으셨군요. 😟 정말 힘드시겠어요.",
            "바쁘고 힘든 하루였나 보네요.",
            "스트레스가 많이 쌓이셨나 봐요. 😔"
        ],
        "angry": [
            "화가 많이 나셨군요. 😤 충분히 이해해요.",
            "정말 억울하고 화나셨을 것 같아요.",
            "그런 일이 있으면 당연히 화가 나죠."
        ],
        "lonely": [
            "외로우셨군요. 😢 혼자 있는 시간이 길면 그럴 수 있어요.",
            "쓸쓸한 기분이시군요. 이해해요."
        ],
        "tired": [
            "많이 피곤하시겠어요. 😴 몸이 힘드시죠?",
            "지치셨군요. 푹 쉬셔야겠어요."
        ]
    }

    import random
    messages = empathy_templates.get(emotion, empathy_templates.get("stressed", ["힘드셨군요."]))
    return random.choice(messages)


def recommend_food_by_emotion(emotion: str, context: str, food_mood: str = "") -> Dict[str, Any]:
    """LLM 기반 감정과 상황에 맞는 음식 추천"""

    if openai_client:
        return recommend_food_by_emotion_llm(emotion, context, food_mood)
    else:
        return recommend_food_by_emotion_fallback(emotion, context)


def recommend_food_by_emotion_llm(emotion: str, context: str, food_mood: str) -> Dict[str, Any]:
    """LLM을 사용한 동적 음식 추천"""
    try:
        system_prompt = """
당신은 신선식품 쇼핑몰의 음식 추천 전문가입니다.
사용자의 감정과 상황에 맞는 음식을 추천해주세요.

심리학적 근거와 영양학적 관점을 고려해서:
- 감정 상태에 도움이 되는 음식 종류
- 구체적인 요리명 3-5개
- 추천 이유를 간단히 설명

JSON 형태로 답변해주세요:
{
    "types": ["음식 카테고리1", "카테고리2"],
    "keywords": ["구체적 요리명1", "요리명2", "요리명3"],
    "reason": "추천 이유 설명"
}
"""

        user_prompt = f"""
사용자 감정: {emotion}
상황 맥락: {context}
음식 기분: {food_mood}

위 정보를 바탕으로 적절한 음식을 추천해주세요.
"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=200,
            temperature=0.5
        )

        result_text = response.choices[0].message.content.strip()

        try:
            result = json.loads(result_text)
            logger.info(f"LLM food recommendation: {result}")
            return result
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse LLM food response as JSON: {result_text}")
            return recommend_food_by_emotion_fallback(emotion, context)

    except Exception as e:
        logger.error(f"LLM food recommendation failed: {e}")
        return recommend_food_by_emotion_fallback(emotion, context)


def recommend_food_by_emotion_fallback(emotion: str, context: str) -> Dict[str, Any]:
    """폴백 음식 추천"""
    food_recommendations = {
        "sad": {
            "types": ["따뜻한음식", "달콤한음식", "부드러운음식"],
            "keywords": ["따뜻한 죽", "삼계탕", "핫초콜릿", "케이크", "아이스크림"],
            "reason": "따뜻하고 달콤한 음식이 마음을 위로해줄 거예요"
        },
        "stressed": {
            "types": ["매운음식", "따뜻한국물", "시원한음식"],
            "keywords": ["매운 떡볶이", "김치찌개", "라면", "매운갈비찜", "냉면"],
            "reason": "매운 음식이 엔돌핀 분비를 도와 스트레스 해소에 도움이 돼요"
        },
        "angry": {
            "types": ["매운음식", "바삭한음식"],
            "keywords": ["매운치킨", "떡볶이", "마라탕", "바삭한 튀김"],
            "reason": "매운 음식으로 화를 달래보세요! 바삭한 식감도 스트레스 해소에 좋아요"
        },
        "lonely": {
            "types": ["따뜻한음식", "간편식"],
            "keywords": ["라면", "김치찌개", "찜닭", "피자"],
            "reason": "혼자서도 맛있게 먹을 수 있는 따뜻한 음식 어떠세요?"
        },
        "tired": {
            "types": ["간편식", "영양식", "에너지식"],
            "keywords": ["삼계탕", "전복죽", "보양식", "간편도시락"],
            "reason": "피곤할 때는 영양 가득한 보양식이 최고예요"
        },
        "happy": {
            "types": ["축하음식", "달콤한음식"],
            "keywords": ["케이크", "피자", "치킨", "초밥"],
            "reason": "좋은 일이 있으시군요! 축하 겸 맛있는 음식 어떠세요?"
        }
    }

    return food_recommendations.get(emotion, food_recommendations["stressed"])


def update_user_context(state, emotion_analysis: Dict[str, Any]) -> None:
    """사용자 컨텍스트 정보 업데이트"""
    if not hasattr(state, 'user_context'):
        state.user_context = {}

    # 현재 감정 상태 업데이트
    state.user_context["current_mood"] = emotion_analysis["primary_emotion"]

    # 최근 주제 업데이트
    if "recent_topics" not in state.user_context:
        state.user_context["recent_topics"] = []

    context = emotion_analysis["context"]
    if context and context not in state.user_context["recent_topics"]:
        state.user_context["recent_topics"].append(context)
        # 최근 5개만 유지
        if len(state.user_context["recent_topics"]) > 5:
            state.user_context["recent_topics"] = state.user_context["recent_topics"][-5:]

    # 대화 테마 설정
    if emotion_analysis["primary_emotion"] in ["sad", "stressed", "angry"]:
        state.user_context["conversation_theme"] = "emotional_support"
    elif emotion_analysis["primary_emotion"] == "happy":
        state.user_context["conversation_theme"] = "celebration"
    else:
        state.user_context["conversation_theme"] = "casual"

    logger.info(f"Updated user context: {state.user_context}")


# 파일 I/O 기반 함수들 제거됨 (2025-01-16)
# 이제 conversation_history는 ChatState에서 메모리 기반으로 자동 관리됨
# utils/session_manager.py의 get_or_create_session_state()를 통해 영속성 확보

# ===== 레시피 검색 히스토리 관리 (ChatState.user_context 기반) =====

def save_recipe_search_result(state: ChatState, search_context: Dict[str, Any]) -> None:
    """
    레시피 검색 결과를 ChatState.user_context에 저장 (메모리 기반 휘발성)

    Args:
        state: ChatState 객체
        search_context: 검색 결과 및 메타데이터
            - query_type: "specific_dish" | "general_menu" (LLM이 분류)
            - original_query: 사용자 원문 쿼리
            - search_query: 실제 검색에 사용된 쿼리
            - results: [{"title": "...", "url": "..."}] 형태의 결과 리스트
            - search_type: "initial" | "alternative"
            - dish_category: LLM이 분석한 음식 카테고리 (선택사항)
            - cuisine_type: LLM이 분석한 요리 유형 (선택사항)
    """
    try:
        # user_context 초기화
        if "recipe_search_history" not in state.user_context:
            state.user_context["recipe_search_history"] = []

        # 타임스탬프 추가
        search_context["timestamp"] = datetime.now().isoformat()

        # 히스토리에 추가
        state.user_context["recipe_search_history"].append(search_context)

        # 최대 5개만 유지 (메모리 효율성)
        if len(state.user_context["recipe_search_history"]) > 5:
            state.user_context["recipe_search_history"] = state.user_context["recipe_search_history"][-5:]

        logger.info(f"레시피 검색 히스토리 저장: {search_context.get('search_query', 'unknown')} " +
                   f"(총 {len(state.user_context['recipe_search_history'])}개)")

    except Exception as e:
        logger.error(f"레시피 검색 히스토리 저장 실패: {e}")


def get_recent_recipe_search_context(state: ChatState, current_query: str) -> Dict[str, Any]:
    """
    현재 쿼리와 연관된 최근 레시피 검색 맥락 반환 (LLM 기반 연관성 분석)

    Args:
        state: ChatState 객체
        current_query: 현재 사용자 쿼리

    Returns:
        Dict with:
        - has_previous_search: bool
        - most_recent_search: Dict (가장 최근 검색 정보)
        - related_searches: List[Dict] (연관된 검색들)
        - context_summary: str (맥락 요약)
    """
    try:
        history = state.user_context.get("recipe_search_history", [])

        if not history:
            return {
                "has_previous_search": False,
                "most_recent_search": None,
                "related_searches": [],
                "context_summary": "이전 레시피 검색 기록 없음"
            }

        most_recent = history[-1]  # 가장 최근 검색

        # LLM을 사용한 연관성 분석 (사용 가능한 경우)
        if openai_client:
            related_searches = _analyze_search_relatedness_llm(history, current_query)
        else:
            related_searches = _analyze_search_relatedness_fallback(history, current_query)

        context_summary = _generate_context_summary(most_recent, related_searches, current_query)

        return {
            "has_previous_search": True,
            "most_recent_search": most_recent,
            "related_searches": related_searches,
            "context_summary": context_summary
        }

    except Exception as e:
        logger.error(f"레시피 검색 맥락 조회 실패: {e}")
        return {
            "has_previous_search": False,
            "most_recent_search": None,
            "related_searches": [],
            "context_summary": "맥락 분석 실패"
        }


def analyze_search_intent_with_history(state: ChatState, current_query: str) -> Dict[str, Any]:
    """
    LLM이 히스토리를 참조하여 재검색 의도 분석

    Args:
        state: ChatState 객체
        current_query: 현재 사용자 쿼리

    Returns:
        Dict with:
        - is_alternative_search: bool (재검색 여부)
        - intent_scope: "same_dish" | "different_menu" | "clarification"
        - previous_dish: str (이전 검색 음식명)
        - similarity_level: float (0.0-1.0, 이전 검색과 유사도)
        - search_strategy: str (추천 검색 전략)
    """
    try:
        search_context = get_recent_recipe_search_context(state, current_query)

        if not search_context["has_previous_search"]:
            return {
                "is_alternative_search": False,
                "intent_scope": "new_search",
                "previous_dish": None,
                "similarity_level": 0.0,
                "search_strategy": "INITIAL_SEARCH"
            }

        if openai_client:
            return _analyze_search_intent_llm(search_context, current_query)
        else:
            return _analyze_search_intent_fallback(search_context, current_query)

    except Exception as e:
        logger.error(f"검색 의도 분석 실패: {e}")
        return {
            "is_alternative_search": False,
            "intent_scope": "error",
            "previous_dish": None,
            "similarity_level": 0.0,
            "search_strategy": "FALLBACK_SEARCH"
        }


def generate_alternative_search_strategy(previous_search: Dict[str, Any], current_query: str) -> Dict[str, Any]:
    """
    LLM이 이전 검색 기반으로 대안 검색 전략 생성

    Args:
        previous_search: 이전 검색 정보
        current_query: 현재 쿼리

    Returns:
        Dict with:
        - strategy_type: "SAME_DISH_ALTERNATIVE" | "CATEGORY_EXPANSION" | "DIFFERENT_MENU"
        - alternative_queries: List[str] (대안 검색 쿼리들)
        - exclude_urls: List[str] (제외할 URL들)
        - search_modifiers: List[str] (검색 수정자들, 예: "간단한", "매운")
        - reasoning: str (전략 선택 이유)
    """
    try:
        if openai_client:
            return _generate_alternative_strategy_llm(previous_search, current_query)
        else:
            return _generate_alternative_strategy_fallback(previous_search, current_query)

    except Exception as e:
        logger.error(f"대안 검색 전략 생성 실패: {e}")
        return {
            "strategy_type": "FALLBACK_SEARCH",
            "alternative_queries": [previous_search.get("search_query", "레시피")],
            "exclude_urls": [],
            "search_modifiers": [],
            "reasoning": f"전략 생성 오류로 인한 폴백: {e}"
        }


# ===== LLM 기반 분석 함수들 =====

def _analyze_search_relatedness_llm(history: List[Dict], current_query: str) -> List[Dict]:
    """LLM을 사용하여 검색 연관성 분석"""
    try:
        # 최근 3개 검색만 분석 (토큰 효율성)
        recent_history = history[-3:]

        system_prompt = """
당신은 레시피 검색 패턴을 분석하는 전문가입니다.
사용자의 검색 히스토리와 현재 질문을 보고, 연관된 이전 검색들을 찾아주세요.

연관성 기준:
1. 동일한 음식의 다른 레시피 (예: "김치찌개" 관련)
2. 같은 카테고리 음식 (예: "한식", "찌개류", "매운음식")
3. 비슷한 조리법이나 재료

JSON 형식으로만 응답하세요:
{
    "related_searches": [
        {
            "search_query": "관련 검색어",
            "relatedness_score": 0.0-1.0,
            "relation_type": "same_dish|same_category|similar_ingredient|different"
        }
    ]
}
"""

        history_summary = "\n".join([
            f"- {search.get('search_query', 'unknown')}: {search.get('query_type', 'unknown')}"
            for search in recent_history
        ])

        user_prompt = f"""
검색 히스토리:
{history_summary}

현재 질문: "{current_query}"

위 정보를 분석해서 연관된 검색들을 찾아주세요.
"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=300,
            temperature=0.3
        )

        result_text = response.choices[0].message.content.strip()
        result = json.loads(result_text)

        logger.info(f"LLM 검색 연관성 분석: {len(result.get('related_searches', []))}개")
        return result.get("related_searches", [])

    except Exception as e:
        logger.error(f"LLM 검색 연관성 분석 실패: {e}")
        return _analyze_search_relatedness_fallback(history, current_query)


def _analyze_search_relatedness_fallback(history: List[Dict], current_query: str) -> List[Dict]:
    """폴백 검색 연관성 분석 (키워드 기반)"""
    related = []
    current_lower = current_query.lower()

    # 간단한 키워드 매칭으로 연관성 판단
    for search in history[-3:]:  # 최근 3개만
        search_query = search.get("search_query", "").lower()

        # 완전 일치 (동일 음식)
        if search_query in current_lower or current_lower in search_query:
            related.append({
                "search_query": search.get("search_query", ""),
                "relatedness_score": 0.9,
                "relation_type": "same_dish"
            })
        # 부분 일치 (관련 카테고리)
        elif any(word in current_lower for word in search_query.split()):
            related.append({
                "search_query": search.get("search_query", ""),
                "relatedness_score": 0.6,
                "relation_type": "same_category"
            })

    return related


def _analyze_search_intent_llm(search_context: Dict, current_query: str) -> Dict[str, Any]:
    """LLM 기반 검색 의도 분석"""
    try:
        recent_search = search_context["most_recent_search"]

        system_prompt = """
당신은 사용자의 검색 의도를 분석하는 전문가입니다.
이전 레시피 검색과 현재 질문을 보고, 사용자가 무엇을 원하는지 분석해주세요.

의도 분류:
- same_dish: 같은 음식의 다른 레시피 ("다른 김치찌개 레시피")
- different_menu: 완전히 다른 메뉴 ("다른 요리 추천")
- clarification: 명확화 요청 ("더 자세히", "재료가 뭐야")

JSON 형식으로만 응답:
{
    "is_alternative_search": true/false,
    "intent_scope": "same_dish|different_menu|clarification",
    "previous_dish": "이전 검색한 음식명",
    "similarity_level": 0.0-1.0,
    "search_strategy": "SAME_DISH_ALTERNATIVE|CATEGORY_EXPANSION|DIFFERENT_MENU|CLARIFICATION",
    "confidence": 0.0-1.0
}
"""

        user_prompt = f"""
이전 검색:
- 쿼리: "{recent_search.get('original_query', '')}"
- 검색어: "{recent_search.get('search_query', '')}"
- 음식 종류: {recent_search.get('query_type', 'unknown')}

현재 질문: "{current_query}"

사용자의 의도를 분석해주세요.
"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=200,
            temperature=0.2
        )

        result_text = response.choices[0].message.content.strip()
        result = json.loads(result_text)

        logger.info(f"LLM 검색 의도 분석: {result.get('intent_scope', 'unknown')}")
        return result

    except Exception as e:
        logger.error(f"LLM 검색 의도 분석 실패: {e}")
        return _analyze_search_intent_fallback(search_context, current_query)


def _analyze_search_intent_fallback(search_context: Dict, current_query: str) -> Dict[str, Any]:
    """폴백 검색 의도 분석 (키워드 기반)"""
    recent_search = search_context["most_recent_search"]
    query_lower = current_query.lower()

    # 재검색 키워드 감지
    alternative_keywords = ["다른", "또", "별의", "새로운", "다시", "말고", "else", "other", "another"]
    is_alternative = any(keyword in query_lower for keyword in alternative_keywords)

    if not is_alternative:
        return {
            "is_alternative_search": False,
            "intent_scope": "new_search",
            "previous_dish": None,
            "similarity_level": 0.0,
            "search_strategy": "INITIAL_SEARCH"
        }

    # 동일 음식 vs 다른 메뉴 판단
    previous_dish = recent_search.get("search_query", "")
    dish_in_query = previous_dish.lower() in query_lower if previous_dish else False

    if dish_in_query or recent_search.get("query_type") == "specific_dish":
        intent_scope = "same_dish"
        strategy = "SAME_DISH_ALTERNATIVE"
        similarity = 0.8
    else:
        intent_scope = "different_menu"
        strategy = "DIFFERENT_MENU"
        similarity = 0.2

    return {
        "is_alternative_search": True,
        "intent_scope": intent_scope,
        "previous_dish": previous_dish,
        "similarity_level": similarity,
        "search_strategy": strategy
    }


def _generate_alternative_strategy_llm(previous_search: Dict, current_query: str) -> Dict[str, Any]:
    """LLM 기반 대안 검색 전략 생성"""
    try:
        system_prompt = """
당신은 레시피 검색 전략을 설계하는 전문가입니다.
이전 검색 결과와 현재 사용자 요청을 보고, 최적의 대안 검색 전략을 제안해주세요.

전략 종류:
1. SAME_DISH_ALTERNATIVE: 같은 음식의 다른 레시피
   - 기존 결과 제외하고 검색 수정자 추가
2. CATEGORY_EXPANSION: 카테고리 확장
   - 관련 음식 카테고리로 확장
3. DIFFERENT_MENU: 완전 다른 메뉴
   - 다른 음식 카테고리 검색

JSON 형식으로만 응답:
{
    "strategy_type": "전략 타입",
    "alternative_queries": ["대안 쿼리1", "쿼리2"],
    "exclude_urls": ["제외할 URL들"],
    "search_modifiers": ["수정자1", "수정자2"],
    "reasoning": "전략 선택 이유"
}
"""

        exclude_urls = [result.get("url", "") for result in previous_search.get("results", [])]

        user_prompt = f"""
이전 검색:
- 검색어: "{previous_search.get('search_query', '')}"
- 음식 종류: {previous_search.get('query_type', 'unknown')}
- 결과 개수: {len(previous_search.get('results', []))}개

현재 요청: "{current_query}"

제외할 URL들: {len(exclude_urls)}개

최적의 대안 검색 전략을 제안해주세요.
"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=300,
            temperature=0.4
        )

        result_text = response.choices[0].message.content.strip()
        result = json.loads(result_text)

        # exclude_urls 추가
        result["exclude_urls"] = exclude_urls

        logger.info(f"LLM 대안 전략 생성: {result.get('strategy_type', 'unknown')}")
        return result

    except Exception as e:
        logger.error(f"LLM 대안 전략 생성 실패: {e}")
        return _generate_alternative_strategy_fallback(previous_search, current_query)


def _generate_alternative_strategy_fallback(previous_search: Dict, current_query: str) -> Dict[str, Any]:
    """폴백 대안 전략 생성"""
    previous_query = previous_search.get("search_query", "")
    exclude_urls = [result.get("url", "") for result in previous_search.get("results", [])]

    # 간단한 수정자 추가
    modifiers = ["간단한", "쉬운", "매콤한", "전통", "집에서 만드는", "특별한"]
    alternative_queries = [f"{modifier} {previous_query}" for modifier in modifiers[:3]]

    return {
        "strategy_type": "SAME_DISH_ALTERNATIVE",
        "alternative_queries": alternative_queries,
        "exclude_urls": exclude_urls,
        "search_modifiers": modifiers[:3],
        "reasoning": "폴백 전략: 기본 수정자를 추가한 동일 음식 검색"
    }


def _generate_context_summary(most_recent: Dict, related_searches: List, current_query: str) -> str:
    """맥락 요약 생성"""
    recent_dish = most_recent.get("search_query", "unknown")
    recent_time = most_recent.get("timestamp", "")

    if related_searches:
        return f"최근 '{recent_dish}' 검색 후 연관 검색 {len(related_searches)}개 발견"
    else:
        return f"최근 '{recent_dish}' 검색, 현재 질문과 연관성 낮음"


# hjs 수정: 도메인 전반에서 재사용 가능한 히스토리 헬퍼 추가 # 멀티턴 기능
def get_recent_messages_by_intents(state: ChatState, intents: List[str], limit: int = 5) -> List[Dict[str, Any]]:
    """지정된 intent 목록에 해당하는 최근 메시지 추출"""
    history = getattr(state, "conversation_history", [])
    if not history:
        return []

    collected: List[Dict[str, Any]] = []
    for message in reversed(history):
        if message.get("intent") in intents:
            collected.append(message)
            if len(collected) >= limit:
                break

    return list(reversed(collected))


def summarize_product_search_with_history(state: ChatState, current_query: str, limit: int = 3) -> Dict[str, Any]:
    """상품 검색 멀티턴 컨텍스트 요약"""
    recent_messages = get_recent_messages_by_intents(state, ["product_search", "product_recommendation"], limit)
    recent_queries = [msg.get("content", "") for msg in recent_messages]

    last_slots = {}
    recent_candidates: List[Dict[str, Any]] = []  # hjs 수정 # 멀티턴 기능
    for msg in reversed(recent_messages):
        slots = msg.get("slots") or {}
        if slots and not last_slots:
            last_slots = slots
        search_payload = msg.get("search") or {}  # hjs 수정 # 멀티턴 기능
        if search_payload.get("candidates") and not recent_candidates:
            recent_candidates = search_payload.get("candidates")

    return {
        "has_previous_search": bool(recent_messages),
        "recent_queries": recent_queries,
        "last_slots": last_slots,
        "recent_candidates": recent_candidates,
        "current_query": current_query
    }


def summarize_cart_actions_with_history(state: ChatState, limit: int = 5) -> Dict[str, Any]:
    """장바구니 관련 멀티턴 맥락 요약"""
    intents = ["cart_add", "cart_remove", "cart_view", "checkout"]
    recent_actions = get_recent_messages_by_intents(state, intents, limit)

    normalized_actions = []
    last_cart_snapshot: Dict[str, Any] = {}  # hjs 수정 # 멀티턴 기능
    for action in recent_actions:
        normalized_actions.append({
            "intent": action.get("intent"),
            "content": action.get("content"),
            "timestamp": action.get("timestamp"),
            "slots": action.get("slots", {})
        })

        if not last_cart_snapshot and action.get("cart"):
            last_cart_snapshot = action.get("cart")
        if action.get("meta") and action["meta"].get("added_items"):
            last_cart_snapshot.setdefault("last_added_items", action["meta"].get("added_items"))  # hjs 수정 # 멀티턴 기능

    last_action = normalized_actions[-1] if normalized_actions else None

    return {
        "has_cart_activity": bool(normalized_actions),
        "recent_actions": normalized_actions,
        "last_action": last_action,
        "selected_products": last_action.get("slots", {}).get("items") if last_action else [],
        "last_cart_snapshot": last_cart_snapshot
    }


def summarize_cs_history(state: ChatState, limit: int = 5) -> Dict[str, Any]:
    """고객센터(배송/환불 등) 대화 맥락 요약"""
    intents = ["cs_inquiry", "cs_followup", "refund", "delivery"]
    recent_cs = get_recent_messages_by_intents(state, intents, limit)

    topics = []
    for msg in recent_cs:
        topic = msg.get("cs_topic") or msg.get("intent")
        if topic:
            topics.append(topic)

    return {
        "has_cs_history": bool(recent_cs),
        "recent_topics": topics,
        "recent_messages": recent_cs
    }


def build_global_context_snapshot(state: ChatState, current_query: str) -> Dict[str, Any]:
    """각 도메인의 맥락 요약을 통합한 스냅샷 생성"""
    return {
        "product": summarize_product_search_with_history(state, current_query),
        "cart": summarize_cart_actions_with_history(state),
        "cs": summarize_cs_history(state)
    }
