"""
vision_recipe.py — 비전 AI 기반 레시피 검색 모듈
책임:
- 이미지를 분석하여 만들어진 음식인지 판단
- 음식 이름을 추출하여 레시피 검색용 데이터 생성
- query_enhancement와 동일한 형식으로 데이터 구조화
"""
import logging
import os
import base64
import json
from typing import Dict, Any, Optional
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_interfaces import ChatState

logger = logging.getLogger("VISION_RECIPE")

# OpenAI 클라이언트 설정
try:
    import openai
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        openai_client = openai.OpenAI(api_key=openai_api_key)
    else:
        openai_client = None
        logger.warning("OpenAI API key not found. Vision features will be disabled.")
except ImportError:
    openai_client = None
    logger.warning("OpenAI package not available. Vision features will be disabled.")

def vision_recipe(state: ChatState) -> Dict[str, Any]:
    """
    이미지를 분석하여 음식을 인식하고 레시피 검색용 데이터를 생성합니다.
    """
    logger.info("비전 레시피 검색 프로세스 시작")

    if not openai_client:
        return {
            "route": {"target": "clarify", "confidence": 0.1},
            "response": "죄송합니다. 이미지 분석 기능을 사용할 수 없습니다."
        }

    try:
        # 이미지 데이터 확인
        image_data = _extract_image_from_state(state)
        if not image_data:
            logger.warning("이미지 데이터를 찾을 수 없음")
            return {
                "route": {"target": "clarify", "confidence": 0.1},
                "response": "이미지를 찾을 수 없습니다. 이미지를 업로드해 주세요."
            }

        # 이미지 분석으로 음식 인식
        food_analysis = _analyze_food_image(image_data)
        if not food_analysis or not food_analysis.get("is_food"):
            logger.info("음식 이미지가 아님")
            return {
                "route": {"target": "clarify", "confidence": 0.3},
                "response": "음식 이미지를 인식할 수 없습니다. 요리된 음식 사진을 업로드해 주세요."
            }

        # 음식 이름 추출
        food_name = food_analysis.get("food_name", "")
        if not food_name:
            logger.warning("음식 이름을 추출할 수 없음")
            return {
                "route": {"target": "clarify", "confidence": 0.3},
                "response": "음식을 정확히 인식할 수 없습니다. 더 명확한 음식 사진을 업로드해 주세요."
            }

        logger.info(f"음식 인식 완료: {food_name}")

        # 음식 분석 결과를 상태에 저장 (빠른 분석용)
        state.food_analysis = food_analysis

        # 빠른 분석 모드인 경우 음식 이름만 반환
        if getattr(state, 'quick_analysis', False):
            return {
                "rewrite": {
                    "text": food_name,
                    "keywords": [food_name],
                    "confidence": food_analysis.get("confidence", 0.8),
                    "changes": ["이미지에서 음식 이름 추출"]
                },
                "slots": {"dish_name": food_name},
                "food_analysis": food_analysis
            }

        # query_enhancement와 동일한 형식으로 데이터 생성
        enhanced_data = _create_recipe_query_data(food_name, food_analysis)

        # query_enhancement와 완전 동일한 형식으로 리턴하되, recipe_search로 라우팅 정보 추가
        enhanced_data["route"] = {"target": "recipe_search", "confidence": 0.9}
        return enhanced_data

    except Exception as e:
        logger.error(f"비전 레시피 검색 중 오류 발생: {e}", exc_info=True)
        return {
            "route": {"target": "clarify", "confidence": 0.1},
            "response": "이미지 분석 중 오류가 발생했습니다. 다시 시도해 주세요."
        }

def _extract_image_from_state(state: ChatState) -> Optional[str]:
    """
    ChatState에서 이미지 데이터를 추출합니다.
    이미지는 base64 인코딩된 문자열 또는 파일 경로로 전달될 수 있습니다.
    """
    try:
        # state에서 이미지 데이터 확인 (다양한 경로 시도)
        image_data = None

        # 방법 1: state.query에서 이미지 경로 추출
        if hasattr(state, 'query') and state.query:
            if state.query.startswith('data:image/') or 'base64,' in state.query:
                image_data = state.query
            elif state.query.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                # 파일 경로인 경우 base64로 인코딩
                image_data = _encode_image_to_base64(state.query)

        # 방법 2: state에 image 속성이 있는 경우
        if hasattr(state, 'image') and state.image:
            image_data = state.image

        # 방법 3: state에 files 속성이 있는 경우
        if hasattr(state, 'files') and state.files:
            for file_data in state.files:
                if isinstance(file_data, dict) and file_data.get('type', '').startswith('image/'):
                    image_data = file_data.get('data') or file_data.get('content')
                    break

        return image_data

    except Exception as e:
        logger.error(f"이미지 데이터 추출 실패: {e}")
        return None

def _encode_image_to_base64(image_path: str) -> Optional[str]:
    """
    이미지 파일을 base64로 인코딩합니다.
    """
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            # 적절한 data URL 형식으로 변환
            file_extension = image_path.split('.')[-1].lower()
            mime_type = f"image/{file_extension if file_extension in ['png', 'jpg', 'jpeg', 'gif', 'bmp'] else 'jpeg'}"
            return f"data:{mime_type};base64,{encoded_string}"
    except Exception as e:
        logger.error(f"이미지 base64 인코딩 실패: {e}")
        return None

def _analyze_food_image(image_data: str) -> Optional[Dict[str, Any]]:
    """
    OpenAI Vision API를 사용하여 이미지에서 음식을 분석합니다.
    """
    try:
        # base64 데이터에서 실제 이미지 부분만 추출
        if image_data.startswith('data:image/'):
            image_data = image_data.split(',')[1]

        system_prompt = """당신은 음식 이미지 분석 전문가입니다.
이미지를 분석하여 다음 정보를 JSON 형식으로 제공해주세요:

1. is_food: 이미지가 요리된 음식인지 판단 (true/false)
2. food_name: 음식의 정확한 한국어 이름 (예: "김치찌개", "불고기", "파스타")
3. confidence: 분석 신뢰도 (0.0-1.0)
4. description: 음식에 대한 간단한 설명
5. ingredients: 보이는 주요 재료들 (배열)

규칙:
- 요리된 음식(완성된 요리)만 is_food: true로 판단
- 생재료, 식재료, 과일, 채소만 있는 경우는 is_food: false
- 음식 이름은 가장 일반적인 한국어 명칭 사용
- 확신이 없으면 confidence를 낮게 설정

JSON 형식 예시:
{
  "is_food": true,
  "food_name": "김치찌개",
  "confidence": 0.9,
  "description": "김치와 돼지고기가 들어간 한국 전통 찌개",
  "ingredients": ["김치", "돼지고기", "두부", "대파"]
}"""

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "이 이미지에서 음식을 분석해주세요."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=500
        )

        result = json.loads(response.choices[0].message.content)
        logger.info(f"이미지 분석 결과: {result}")
        return result

    except Exception as e:
        logger.error(f"이미지 분석 실패: {e}")
        return None

def _create_recipe_query_data(food_name: str, food_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    음식 이름을 기반으로 query_enhancement와 동일한 형식의 데이터를 생성합니다.
    """
    try:
        # 기본 키워드 생성
        keywords = [food_name, "레시피", "요리법"]

        # 분석된 재료가 있으면 키워드에 추가
        ingredients = food_analysis.get("ingredients", [])
        if ingredients:
            keywords.extend(ingredients)

        # 중복 제거
        keywords = list(set(keywords))

        # query_enhancement와 동일한 형식으로 데이터 구조화
        enhanced_data = {
            "rewrite": {
                "text": f"{food_name} 레시피 검색",
                "keywords": keywords,
                "confidence": food_analysis.get("confidence", 0.8),
                "changes": ["이미지에서 음식 이름 추출", "레시피 검색용 쿼리 생성"]
            },
            "slots": {
                "dish_name": food_name,
                "ingredients": ingredients[:5]  # 최대 5개 재료만
            }
        }

        return enhanced_data

    except Exception as e:
        logger.error(f"레시피 쿼리 데이터 생성 실패: {e}")
        # 실패 시 기본 데이터 반환
        return {
            "rewrite": {
                "text": f"{food_name} 레시피 검색",
                "keywords": [food_name, "레시피"],
                "confidence": 0.5,
                "changes": ["기본 레시피 검색 쿼리 생성"]
            },
            "slots": {
                "dish_name": food_name
            }
        }