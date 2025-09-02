"""
graph_interfaces.py — Qook 신선식품 챗봇 공통 인터페이스 (통합 버전)

- LangGraph의 각 노드에 대응하는 **함수 시그니처**와 **공용 상태 타입**을 정의합니다.
- 모든 노드는 `ChatState`를 입력으로 받아 **부분 상태 갱신(dict)** 을 반환합니다.
- 구현 충돌을 피하기 위해 여기서는 외부 의존성을 최소화하고, 실제 로직은 각 팀 모듈에서 작성하세요.
- 라우팅은 하드코딩된 의도 분류가 아니라 **LLM 라우팅**을 전제로 합니다.
- CS 영역의 문서 질의는 **FAQ & Policy RAG(통합)** 을 사용합니다.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TypedDict

# ---------- 상태(STATE) 관련 타입 ----------

class CartItem(TypedDict, total=False):
    """
    장바구니 아이템 구조
    - sku: 상품 식별자
    - name: 상품명
    - qty: 수량
    - unit_price: 단가
    - variant: 옵션/규격(선택)
    """
    sku: str
    name: str
    qty: int
    unit_price: float
    variant: Optional[str]

class SearchCandidate(TypedDict, total=False):
    """
    상품 검색 후보 결과 구조
    - sku: 상품 식별자
    - name: 상품명
    - price: 가격
    - stock: 재고 수량
    - score: 랭킹/관련도 점수
    """
    sku: str
    name: str
    price: float
    stock: int
    score: float

@dataclass
class ChatState:
    """
    대화 전역 상태
    - 모든 노드는 이 상태를 읽고 일부 필드를 갱신한 **diff(dict)** 를 반환합니다.
    - 필드 추가/변경은 팀 합의 하에 진행하고, 가능하면 **하위 호환**을 유지하세요.
    """

    # 세션 메타
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    turn_id: Optional[int] = None

    # 사용자 입력
    query: str = ""
    attachments: List[str] = field(default_factory=list)  # 이미지/영수증 등 파일 식별자

    # 쿼리 보강 결과
    rewrite: Dict[str, Any] = field(default_factory=dict)  # {text, keywords[]...}
    slots: Dict[str, Any] = field(default_factory=dict)    # {quantity, category, price_cap...}

    # 검색/Clarify 중간 상태
    search: Dict[str, Any] = field(default_factory=dict)   # {candidates[], method, sql?}
    clarify: Dict[str, Any] = field(default_factory=dict)  # {questions[]...}

    # 주문 관련
    cart: Dict[str, Any] = field(default_factory=lambda: {
        "items": [],       # List[CartItem]
        "subtotal": 0.0,
        "discounts": [],
        "total": 0.0
    })
    checkout: Dict[str, Any] = field(default_factory=dict) # {address, slot, payment_method, confirmed?}
    order: Dict[str, Any] = field(default_factory=dict)    # {order_id, status ...}

    # 부가 기능
    recipe: Dict[str, Any] = field(default_factory=dict)   # {results[], sku_suggestions[]?}
    cs: Dict[str, Any] = field(default_factory=dict)       # {ticket, answer ...}
    handoff: Dict[str, Any] = field(default_factory=dict)  # {ticket_id, crm_id, status ...}

    # 라우팅/세션 종료
    route: Dict[str, Any] = field(default_factory=dict)    # {target, confidence}
    end: Dict[str, Any] = field(default_factory=dict)      # {reason, artifacts[]}

    # 계측/메타
    metrics: Dict[str, Any] = field(default_factory=dict)  # {routing_confidence, latencies ...}
    meta: Dict[str, Any] = field(default_factory=dict)     # 기타

# ---------- 노드 함수 스텁(부분 상태 diff 반환) ----------

def router_route(state: ChatState) -> Dict[str, Any]:
    """
    LLM 기반 라우터
    목적: 사용자 입력을 **검색/주문 허브**, **CS 허브**, **Clarify** 중 하나로 보냅니다.

    입력:
      - state.query, state.attachments(선택), 세션 메타
    출력 예시(부분 상태 갱신 dict):
      {
        "route": {"target": "search_order" | "cs" | "clarify", "confidence": 0.0~1.0},
        "metrics": {"routing_confidence": 0.87}
      }
    실패 처리:
      - LLM 호출 실패 시 Clarify로 폴백 권장
    """
    # 기본 구현 - 추후 A팀에서 완성
    return {
        "route": {"target": "search_order", "confidence": 0.5},
        "metrics": {"routing_confidence": 0.5}
    }

def enhance_query(state: ChatState) -> Dict[str, Any]:
    """
    쿼리 보강(재작성/키워드/슬롯 추출)
    - 원문(query)은 폐기하지 말고 `rewrite.text`와 함께 보존하세요.

    출력 예시:
      {
        "rewrite": {"text": "...", "keywords": ["...", "..."]},
        "slots": {"quantity": 2, "category": "채소", "price_cap": 15000}
      }
    """
    # 기본 구현 - 추후 B팀에서 완성
    return {
        "rewrite": {"text": state.query, "keywords": [state.query]},
        "slots": {"quantity": 1}
    }

def product_search_rag_text2sql(state: ChatState) -> Dict[str, Any]:
    """
    상품 검색(RAG 또는 Text2SQL)
    - 상황에 따라 카탈로그 RAG와 Text2SQL 중 경로를 선택합니다.
    - SQL 생성 시 스키마 프라이밍/검증을 거쳐야 하며, 실패 시 RAG로 폴백합니다.

    출력 예시:
      {
        "search": {
          "candidates": [
            {"sku": "SKU001", "name": "친환경 상추", "price": 3900, "stock": 24, "score": 0.82},
            {"sku": "SKU002", "name": "로메인", "price": 4100, "stock": 11, "score": 0.79}
          ],
          "method": "text2sql",   # 또는 "rag"
          "sql": "SELECT ... LIMIT 20"  # 경로가 text2sql일 때 선택적
        }
      }
    """
    # 기본 구현 - C팀 구현체로 교체 예정
    return {
        "search": {
            "candidates": [
                {"sku": "DEMO001", "name": "샘플 상품", "price": 1000, "stock": 10, "score": 0.5}
            ],
            "method": "demo",
            "total_results": 1
        }
    }

def clarify(state: ChatState) -> Dict[str, Any]:
    """
    Clarify(모호/무결과 상황 질의)
    - 결과가 부족하거나 해석이 여러 개인 경우, 후속 질문을 생성합니다.
    - 루프 예산(예: 최대 2~3회)을 상태/메타로 관리하세요.

    출력 예시:
      {
        "clarify": {"questions": ["더 선호하는 산지나 등급이 있나요?"]},
        "slots": {"price_cap": 12000}  # 사용자가 답하면 슬롯 업데이트
      }
    """
    # 기본 구현 - A팀에서 완성 예정
    return {
        "clarify": {"questions": ["좀 더 구체적으로 설명해 주시겠어요?"]},
    }

def cart_manage(state: ChatState) -> Dict[str, Any]:
    """
    장바구니 관리(멱등)
    - 추가/수정/삭제 후 합계/할인/총액을 재계산합니다.
    - 재고/최소주문 규칙 등 검증 실패 시 사용자 교정 메시지를 생성하세요.

    출력 예시:
      {
        "cart": {
          "items": [{"sku": "SKU001", "name": "친환경 상추", "qty": 2, "unit_price": 3900}],
          "subtotal": 7800, "discounts": [], "total": 7800
        }
      }
    """
    # 기본 구현 - D팀에서 완성 예정  
    return {
        "cart": {
            "items": [],
            "subtotal": 0.0,
            "discounts": [],
            "total": 0.0
        }
    }

def checkout(state: ChatState) -> Dict[str, Any]:
    """
    체크아웃(과금 없음)
    - 배송지, 배송창, 결제수단을 수집합니다.
    - 실제 결제는 order_process 단계에서 확정됩니다.

    출력 예시:
      {"checkout": {"address": "...", "slot": "내일 오전", "payment_method": "CARD", "confirmed": False}}
    """
    # 기본 구현 - D팀에서 완성 예정
    return {
        "checkout": {"address": "", "slot": "", "payment_method": "CARD", "confirmed": False}
    }

def order_process(state: ChatState) -> Dict[str, Any]:
    """
    주문 처리(확정/취소)
    - 사용자 확인에 따라 주문을 확정하거나 취소합니다.
    - 주문 레코드/영수증/감사 로그를 남깁니다.

    출력 예시:
      {"order": {"order_id": "QK-2025-000001", "status": "confirmed"}}
    """
    # 기본 구현 - D팀에서 완성 예정
    return {
        "order": {"order_id": "DEMO-000001", "status": "pending"}
    }

def recipe_search(state: ChatState) -> Dict[str, Any]:
    """
    레시피 검색(Tavily/API)
    - 요리/재료 기반으로 외부 레시피를 검색합니다.
    - 재료를 카탈로그 SKU로 매핑하여 장바구니 제안을 생성할 수 있습니다.

    출력 예시:
      {"recipe": {"results": [...], "sku_suggestions": ["SKU001", "SKU010"]}}
    """
    # 기본 구현 - 추후 완성 예정
    return {
        "recipe": {"results": [], "sku_suggestions": []}
    }

def cs_intake(state: ChatState) -> Dict[str, Any]:
    """
    CS 접수(반품/교환/배송/품질 등)
    - 이미지(영수증/상품사진) 인입 시 비전+LLM으로 간단히 분류/요약합니다.
    - 티켓을 생성하고 카테고리를 지정합니다.

    출력 예시:
      {"cs": {"ticket": {"ticket_id": "T-12345", "category": "배송지연", "summary": "예정보다 2일 지연"}}}
    """
    # 기본 구현 - E팀에서 완성 예정
    return {
        "cs": {"ticket": {"ticket_id": "T-DEMO", "category": "일반문의", "summary": "고객 문의"}}
    }

def faq_policy_rag(state: ChatState) -> Dict[str, Any]:
    """
    FAQ & Policy RAG(통합)
    - FAQ/정책 말뭉치에서 근거 문서를 검색하여 인용과 함께 답변합니다.
    - 신뢰도가 낮으면 handoff로 분기합니다.

    출력 예시:
      {"cs": {"answer": {"text": "...", "citations": ["faq:배송정책#3"], "confidence": 0.76}}}
    """
    # 기본 구현 - E팀에서 완성 예정
    return {
        "cs": {"answer": {"text": "죄송합니다. 정확한 답변을 찾지 못했습니다.", "citations": [], "confidence": 0.1}}
    }

# handoff와 end_session은 F팀의 완성된 구현체를 그대로 import하여 사용 예정
def handoff(state: ChatState) -> Dict[str, Any]:
    """
    상담사 이관
    - 저신뢰/예외 케이스에서 인간 상담사/CRM으로 이관합니다.
    - 대화 요약/근거/사용자 메타를 함께 전달합니다.

    출력 예시:
      {"handoff": {"ticket_id": "T-12345", "crm_id": "ZENDESK-777", "status": "sent"}}
    """
    # F팀 구현체를 import하여 사용 예정
    return {
        "handoff": {"ticket_id": "DEMO-TICKET", "crm_id": "DEMO-CRM", "status": "pending"}
    }

def end_session(state: ChatState) -> Dict[str, Any]:
    """
    세션 종료
    - 주문/CS 결과에 따라 마무리 메시지, 영수증/링크/요약 등의 아티팩트를 제공합니다.

    출력 예시:
      {"end": {"reason": "order_complete", "artifacts": ["영수증 링크", "주문 요약 PDF"]}}
    """
    # F팀 구현체를 import하여 사용 예정
    return {
        "end": {"reason": "demo_complete", "artifacts": []}
    }