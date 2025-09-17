"""
casual_chat.py - 일상대화 처리 노드

사용자의 일상적인 인사나 대화에 친근하고 자연스러운 응답을 제공합니다.
적절한 경우 쇼핑몰의 기능으로 자연스럽게 연결합니다.
"""

import logging
import random
from typing import Dict, Any, List
import os
import sys

# 상대 경로로 graph_interfaces 임포트
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_interfaces import ChatState

# 히스토리 및 감정 분석 유틸 임포트
from utils.chat_history import (
    analyze_user_emotion,
    get_empathy_response,
    recommend_food_by_emotion,
    update_user_context,
    get_recent_context,
    get_contextual_analysis
)

logger = logging.getLogger("CASUAL_CHAT")

# OpenAI 클라이언트 설정
try:
    import openai
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        openai_client = openai.OpenAI(api_key=openai_api_key)
    else:
        openai_client = None
        logger.warning("OpenAI API key not found. Using predefined responses.")
except ImportError:
    openai_client = None
    logger.warning("OpenAI package not available.")

def casual_chat(state: ChatState) -> ChatState:
    """히스토리 기반 맥락적 일상대화 처리 함수"""
    logger.info(f"일상대화 처리: {state.query}")

    try:
        # 1. 히스토리 기반 감정 분석
        emotion_analysis = analyze_user_emotion(state.query, state.conversation_history)
        logger.info(f"감정 분석 결과: {emotion_analysis}")

        # 2. 사용자 컨텍스트 업데이트
        update_user_context(state, emotion_analysis)

        # 3. 공감 메시지 생성
        empathy_msg = get_empathy_response(
            emotion_analysis["primary_emotion"],
            emotion_analysis["context"],
            emotion_analysis.get("intensity", "medium")
        )
        logger.info(f"공감 메시지: {empathy_msg}")

        # 4. 사용자 선호도 가져오기
        user_preferences = {}
        if hasattr(state, 'user_id') and state.user_id:
            try:
                from policy import get_user_preferences
                user_preferences = get_user_preferences(state.user_id)
                logger.info(f"사용자 {state.user_id} 선호도: {user_preferences}")
            except Exception as e:
                logger.warning(f"사용자 선호도 조회 실패: {e}")

        # 5. 음식 추천 생성 (선호도 고려)
        food_rec = recommend_food_by_emotion(
            emotion_analysis["primary_emotion"],
            emotion_analysis["context"],
            emotion_analysis.get("food_mood", "")
        )

        # 선호도 정보를 food_rec에 추가
        if user_preferences:
            food_rec["user_preferences"] = user_preferences

        logger.info(f"음식 추천: {food_rec}")

        # 5. 통합 응답 구성
        if openai_client:
            response = generate_contextual_response_llm(
                state.query, state.conversation_history,
                emotion_analysis, empathy_msg, food_rec
            )
        else:
            response = generate_contextual_response_fallback(
                empathy_msg, food_rec
            )

        state.response = response
        logger.info(f"최종 응답 생성 완료: {response[:100]}...")

    except Exception as e:
        logger.error(f"일상대화 처리 오류: {e}")
        if openai_client:
            state.response = generate_fallback_response_llm(state.query)
        else:
            state.response = "안녕하세요! 😊 무엇을 도와드릴까요?"

    return state

# def casual_chat(state: ChatState) -> ChatState:
#     """히스토리 기반 맥락적 일상대화 처리 함수"""
#     logger.info(f"일상대화 처리: {state.query}")

#     try:
#         # [NEW] 히스토리 안전 확보
#         history: List[Dict] = getattr(state, "conversation_history", None) or []
#         if not isinstance(history, list):
#             history = []

#         # 1. 히스토리 기반 감정 분석
#         emotion_analysis = analyze_user_emotion(state.query, history)
#         logger.info(f"감정 분석 결과: {emotion_analysis}")

#         # 2. 사용자 컨텍스트 업데이트
#         update_user_context(state, emotion_analysis)

#         # 3. 공감 메시지 생성
#         empathy_msg = get_empathy_response(
#             emotion_analysis["primary_emotion"],
#             emotion_analysis["context"],
#             emotion_analysis.get("intensity", "medium")
#         )
#         logger.info(f"공감 메시지: {empathy_msg}")

#         # 4. 음식 추천 생성
#         food_rec = recommend_food_by_emotion(
#             emotion_analysis["primary_emotion"],
#             emotion_analysis["context"],
#             emotion_analysis.get("food_mood", "")
#         )
#         logger.info(f"음식 추천: {food_rec}")

#         # 5. 통합 응답 구성
#         if openai_client:
#             response = generate_contextual_response_llm(
#                 state.query, history, emotion_analysis, empathy_msg, food_rec
#             )
#         else:
#             response = generate_contextual_response_fallback(
#                 empathy_msg, food_rec
#             )

#         # [NEW] 히스토리가 없을 때 '기억' 서술 차단
#         response = _post_guard_filter(response, history)

#         state.response = response
#         logger.info(f"최종 응답 생성 완료: {response[:100]}...")

#     except Exception as e:
#         logger.error(f"일상대화 처리 오류: {e}")
#         if openai_client:
#             state.response = generate_fallback_response_llm(state.query)
#         else:
#             state.response = "안녕하세요! 😊 무엇을 도와드릴까요?"

#     return state



def generate_contextual_response_llm(query: str, history: List[Dict], emotion_analysis: Dict, empathy_msg: str, food_rec: Dict) -> str:
    """LLM 기반 맥락적 최종 응답 생성"""
    try:
        # 향상된 맥락 분석 사용
        contextual_analysis = get_contextual_analysis(history, query)
        recent_context = get_recent_context(history, turns=3) if history else "새로운 대화"

        # 히스토리 상태 확인
        is_empty_history = recent_context == "새로운 대화"

        system_prompt = f"""
당신은 신선식품 온라인 쇼핑몰의 따뜻하고 공감적인 챗봇입니다.
사용자의 감정과 상황을 이해하고, 자연스럽고 맥락적인 응답을 제공하세요.

🚨 **절대 규칙**: 대화 맥락이 "새로운 대화"이면 이전 추천을 절대 언급하지 마세요!

응답 가이드라인:
1. 사용자의 감정에 진심으로 공감하기
2. 상황에 맞는 음식이나 레시피를 자연스럽게 추천
3. **사용자의 알러지/비선호 음식을 절대 추천하지 말 것**
4. 친근하고 따뜻한 톤 유지
5. 2-3문장으로 간결하되 따뜻하게
6. 적절한 이모지 사용 (과하지 않게)
7. 쇼핑몰 서비스로 자연스럽게 연결
8. 대화를 이어갈 수 있는 열린 질문 포함

{"맥락 연속성 규칙 (기존 대화가 있을 때만):" if not is_empty_history else "새로운 대화 규칙:"}
{"- 이전 대화 내용을 참조하여 연속성 있는 응답" if not is_empty_history else "- 이전 추천을 절대 언급하지 말고 현재 상황에만 집중"}
{"- 이전 추천과 다른 새로운 옵션 제안" if not is_empty_history else "- '아까', '이전에', '방금' 등의 과거 지칭 표현 금지"}
{"- 사용자의 변화하는 취향 반영" if not is_empty_history else "- 현재 감정과 상황에 기반한 새로운 추천만"}

중요:
1. 공감 메시지와 음식 추천을 자연스럽게 융합된 응답으로 만들기
{"2. 이전 대화 맥락을 언급하여 연속성 확보하기" if not is_empty_history else "2. 현재 상황에만 집중하여 자연스러운 새로운 추천하기"}
3. 사용자가 계속 대화할 수 있도록 구체적이고 관련성 있는 질문으로 마무리하기
"""

        user_prompt = f"""
대화 상태: {"새로운 대화 (히스토리 없음)" if is_empty_history else "기존 대화 진행 중"}

최근 대화 맥락:
{recent_context}

현재 사용자 메시지: "{query}"

맥락 분석 결과:
- 이전 추천 내역: {', '.join(contextual_analysis.get('previous_recommendations', [])) or '없음'}
- 후속 의도: {contextual_analysis.get('followup_intent', 'none')}
- 제안 대안: {', '.join(contextual_analysis.get('suggested_alternatives', [])) or '없음'}
- 맥락 요약: {contextual_analysis.get('context_summary', '새로운 대화')}

감정 분석 결과:
- 주요 감정: {emotion_analysis.get('primary_emotion', 'neutral')}
- 상황: {emotion_analysis.get('context', '일상 대화')}
- 강도: {emotion_analysis.get('intensity', 'medium')}

공감 메시지 참고: {empathy_msg}

음식 추천 정보:
- 추천 음식: {', '.join(food_rec.get('keywords', ['맛있는 음식'])[:3])}
- 추천 이유: {food_rec.get('reason', '기분 전환에 도움이 될 거예요')}

사용자 선호도 정보:
{f"- 알러지: {food_rec.get('user_preferences', {}).get('allergy', '없음')}" if food_rec.get('user_preferences') else "- 선호도 정보 없음"}
{f"- 비선호 음식: {food_rec.get('user_preferences', {}).get('unfavorite', '없음')}" if food_rec.get('user_preferences') else ""}
{f"- 비건 여부: {'예' if food_rec.get('user_preferences', {}).get('vegan') else '아니오'}" if food_rec.get('user_preferences') else ""}

{"⚠️ 중요: 대화 상태가 '새로운 대화'이므로 이전 추천을 절대 언급하지 마세요!" if is_empty_history else ""}
⚠️ 선호도 준수: 사용자의 알러지나 비선호 음식이 있다면 절대 추천하지 마세요!

위 모든 정보를 종합해서 자연스럽고 따뜻한 응답을 생성해주세요.
{"현재 상황과 감정에만 기반한 새로운 추천을 해주세요." if is_empty_history else "후속 의도가 'alternative'인 경우 이전 추천을 언급하며 새로운 대안을 제시하세요."}
"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=200,
            temperature=0.7
        )

        result = response.choices[0].message.content.strip()
        logger.info(f"LLM 맥락적 응답 생성: {result}")
        return result

    except Exception as e:
        logger.error(f"LLM 맥락적 응답 생성 실패: {e}")
        return generate_contextual_response_fallback(empathy_msg, food_rec)


# def generate_contextual_response_llm(query: str, history: List[Dict], emotion_analysis: Dict, empathy_msg: str, food_rec: Dict) -> str:
#     """LLM 기반 맥락적 최종 응답 생성"""
#     try:
#         contextual_analysis = get_contextual_analysis(history, query)

#         # [NEW] 히스토리 직렬화 (모델이 볼 원천 증거)
#         def _fmt(m):
#             role = m.get("role", "user")
#             content = m.get("content", "")
#             return f"{role}: {content}"
#         history_text = "\n".join(_fmt(m) for m in history[-12:]) or "(비어 있음)"

#         recent_context = get_recent_context(history, turns=3) if history else "새로운 대화"

#         system_prompt = """
# 당신은 신선식품 온라인 쇼핑몰의 따뜻하고 공감적인 챗봇입니다.

# 아래 **절대 규칙**을 반드시 지키세요.
# 1) 오직 <HISTORY>에 있는 내용만 '이전에 대화했다/추천했다'고 말할 수 있습니다.
# 2) <HISTORY>에 근거가 없으면 과거를 추측하거나 만들어내지 않습니다.
# 3) <HISTORY>에 이전 추천이 없을 때는, '기록을 찾지 못했다'고 솔직히 말하고 다시 물어봅니다.
# 4) 공감 → 필요한 경우 간단 추천 → 열린 질문 순으로 2~3문장 내에 답하세요. (과장 금지, 이모지 과다 금지)
# """

#         user_prompt = f"""
# <HISTORY>
# {history_text}
# </HISTORY>

# 최근 대화 맥락: {recent_context}
# 현재 사용자 메시지: "{query}"

# 맥락 분석:
# - 이전 추천 내역: {', '.join(contextual_analysis.get('previous_recommendations', [])) or '없음'}
# - 후속 의도: {contextual_analysis.get('followup_intent', 'none')}
# - 제안 대안: {', '.join(contextual_analysis.get('suggested_alternatives', [])) or '없음'}
# - 맥락 요약: {contextual_analysis.get('context_summary', '새로운 대화')}

# 감정 분석:
# - 주요 감정: {emotion_analysis.get('primary_emotion', 'neutral')}
# - 상황: {emotion_analysis.get('context', '일상 대화')}
# - 강도: {emotion_analysis.get('intensity', 'medium')}

# 공감 메시지(참고): {empathy_msg}

# 음식 추천(참고):
# - 키워드: {', '.join(food_rec.get('keywords', ['맛있는 음식'])[:3])}
# - 이유: {food_rec.get('reason', '기분 전환에 도움이 될 거예요')}

# 주의:
# - <HISTORY>에 '칼국수' 등 과거 요청/추천이 **없으면** 절대 '아까 ~추천드렸는데' 같은 표현을 쓰지 마세요.
# - 과거가 없으면 "기록을 찾지 못했어요. 어떤 걸 찾고 계셨는지 알려주실래요?"처럼 정직하게 확인 질문으로 마무리하세요.
# """

#         response = openai_client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": user_prompt}
#             ],
#             max_tokens=200,
#             temperature=0.7
#         )

#         result = response.choices[0].message.content.strip()
#         logger.info(f"LLM 맥락적 응답 생성: {result}")
#         return result

#     except Exception as e:
#         logger.error(f"LLM 맥락적 응답 생성 실패: {e}")
#         return generate_contextual_response_fallback(empathy_msg, food_rec)



def generate_contextual_response_fallback(empathy_msg: str, food_rec: Dict) -> str:
    """폴백 맥락적 응답 생성"""
    food_keywords = food_rec.get('keywords', ['맛있는 음식'])[:3]
    food_reason = food_rec.get('reason', '기분 전환에 도움이 될 거예요')

    return f"{empathy_msg}\n\n{food_reason} {', '.join(food_keywords)} 어떠세요?"

# def generate_contextual_response_fallback(empathy_msg: str, food_rec: Dict) -> str:
#     """폴백 맥락적 응답 생성"""
#     food_keywords = food_rec.get('keywords', ['맛있는 음식'])[:3]
#     food_reason = food_rec.get('reason', '기분 전환에 도움이 될 거예요')
#     return f"{empathy_msg}\n\n{food_reason} {', '.join(food_keywords)} 어떠세요?"


def generate_fallback_response_llm(query: str) -> str:
    """LLM 기반 기본 폴백 응답"""
    try:
        system_prompt = """
당신은 신선식품 온라인 쇼핑몰의 친근한 챗봇입니다.
사용자에게 따뜻하고 도움이 되는 응답을 해주세요.
1-2문장으로 간결하게 답하되 친근한 톤을 유지하세요.
"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            max_tokens=100,
            temperature=0.6
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"LLM 폴백 응답 생성 실패: {e}")
        return "안녕하세요! 😊 무엇을 도와드릴까요?"


# 기존 함수들 백업 (참고용)
def casual_chat_legacy(state: ChatState) -> ChatState:
    """기존 일상대화 처리 함수 (백업)"""
    logger.info(f"일상대화 처리: {state.query}")

    try:
        if openai_client:
            response = _generate_llm_response(state.query)
        else:
            response = _get_predefined_response(state.query)

        state.response = response
        logger.info(f"일상대화 응답 생성 완료: {response[:50]}...")

    except Exception as e:
        logger.error(f"일상대화 처리 오류: {e}")
        state.response = "안녕하세요! 오늘 하루도 좋은 하루 되세요. 😊 무엇을 도와드릴까요?"

    return state

def _generate_llm_response(query: str) -> str:
    """LLM을 사용한 자연스러운 응답 생성"""

    system_prompt = """
    당신은 신선식품 온라인 쇼핑몰의 친근하고 도움이 되는 챗봇입니다.
    사용자의 일상적인 대화에 자연스럽고 친근하게 응답하세요.

    응답 가이드라인:
    1. 친근하고 따뜻한 톤으로 응답
    2. 적절한 이모지 사용 (과하지 않게)
    3. 상황에 따라 쇼핑몰의 서비스로 자연스럽게 연결
    4. 응답은 1-2문장으로 간결하게

    예시:
    - "안녕" → "안녕하세요! 😊 좋은 하루 보내고 계신가요? 오늘 필요한 신선한 식재료가 있으시면 언제든 말씀해 주세요!"
    - "고마워" → "천만에요! 😊 도움이 되어서 기뻐요. 또 필요한 것이 있으시면 언제든 말씀해 주세요."
    - "잘 지내?" → "저는 항상 건강하게 잘 지내고 있어요! 😊 고객님은 어떠신가요? 오늘 맛있는 요리 계획이 있으시나요?"
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            max_tokens=150,
            temperature=0.7
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"LLM 응답 생성 실패: {e}")
        return _get_predefined_response(query)

def _get_predefined_response(query: str) -> str:
    """미리 정의된 응답 패턴 매칭"""

    query_lower = query.lower()

    # 인사말 응답
    greeting_patterns = {
        "안녕": [
            "안녕하세요! 😊 좋은 하루 보내고 계신가요? 오늘 필요한 신선한 식재료가 있으시면 언제든 말씀해 주세요!",
            "안녕하세요! 😊 반가워요! 오늘 어떤 맛있는 요리를 계획하고 계신가요?",
            "안녕하세요! 😊 좋은 하루예요! 신선한 재료나 맛있는 레시피가 필요하시면 언제든 도와드릴게요!"
        ],
        "좋은": [
            "좋은 하루 되세요! 😊 오늘도 신선하고 맛있는 식재료로 건강한 식사 준비해 보세요!",
            "감사해요! 😊 고객님도 좋은 하루 보내세요! 맛있는 요리 계획이 있으시나요?"
        ],
        "아침": [
            "좋은 아침이에요! 🌅 오늘 아침 식사는 준비하셨나요? 신선한 재료로 건강한 하루를 시작해 보세요!",
            "좋은 아침입니다! 😊 오늘 하루도 맛있고 건강한 식사로 활기차게 보내세요!"
        ]
    }

    # 감사 표현 응답
    gratitude_patterns = {
        "고마워": [
            "천만에요! 😊 도움이 되어서 기뻐요. 또 필요한 것이 있으시면 언제든 말씀해 주세요!",
            "별말씀을요! 😊 언제든 도움이 필요하시면 불러주세요!"
        ],
        "감사": [
            "감사합니다! 😊 저희도 고객님께 도움이 될 수 있어서 기뻐요!",
            "고마운 말씀이에요! 😊 앞으로도 더 좋은 서비스로 보답하겠습니다!"
        ]
    }

    # 안부 문의 응답
    wellbeing_patterns = {
        "잘": [
            "저는 항상 건강하게 잘 지내고 있어요! 😊 고객님은 어떠신가요? 오늘 맛있는 요리 계획이 있으시나요?",
            "네, 잘 지내고 있어요! 😊 고객님께서도 건강하게 지내시길 바라요! 영양가 있는 식사 도와드릴까요?"
        ]
    }

    # 날씨 관련 응답
    weather_patterns = {
        "날씨": [
            "오늘 날씨가 어떤지에 따라 다른 요리가 생각나죠! 😊 따뜻한 날엔 시원한 샐러드, 추운 날엔 따뜻한 국물 요리는 어떠세요?",
            "날씨에 맞는 제철 재료로 요리해 보세요! 😊 어떤 요리를 원하시는지 말씀해 주시면 재료를 추천해 드릴게요!"
        ]
    }

    # 패턴 매칭 및 응답 선택
    all_patterns = {**greeting_patterns, **gratitude_patterns, **wellbeing_patterns, **weather_patterns}

    for pattern, responses in all_patterns.items():
        if pattern in query_lower:
            return random.choice(responses)

    # 기본 응답
    default_responses = [
        "안녕하세요! 😊 무엇을 도와드릴까요? 신선한 식재료나 맛있는 레시피를 찾고 계신가요?",
        "안녕하세요! 😊 오늘도 좋은 하루 보내세요! 필요한 것이 있으시면 언제든 말씀해 주세요!",
        "반가워요! 😊 어떤 도움이 필요하신가요? 맛있는 요리를 위한 재료를 찾아드릴게요!"
    ]

    return random.choice(default_responses)


def _post_guard_filter(reply: str, history: List[Dict]) -> str:
    """히스토리가 없을 때 과거 회상/추천을 말하는 문장을 차단"""
    if history:
        return reply
    triggers = ["아까", "이전에", "방금", "추천드렸", "말씀드렸", "기억하고"]
    if any(t in reply for t in triggers):
        return "창을 닫으셨다면 대화 기록이 비어 있어요. 어떤 내용을 찾고 계셨는지 알려주시면 바로 이어서 도와드릴게요! 😊"
    return reply
