"""
workflow.py — Qook 신선식품 챗봇 LangGraph 워크플로우

이 파일은 전체 대화 플로우를 정의하고, 각 노드 간의 연결 및 조건부 라우팅을 관리합니다.
"""

from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
# from langgraph.graph import CompiledStateGraph

from graph_interfaces import (
    ChatState, 
    router_route, 
    enhance_query,
    product_search_rag_text2sql,
    clarify,
    cart_manage,
    checkout,
    order_process,
    recipe_search,
    cs_intake,
    faq_policy_rag,
    handoff,
    end_session
)

def should_clarify(state: ChatState) -> Literal["clarify", "enhance_query", "cs_intake"]:
    """라우팅 결과에 따라 clarify, enhance_query, 또는 cs_intake로 분기"""
    route_target = state.route.get("target", "")
    route_confidence = state.route.get("confidence", 0.0)
    
    # CS 문의인 경우
    if route_target == "cs":
        return "cs_intake"
    # 신뢰도가 낮거나 clarify 대상인 경우
    elif route_target == "clarify" or route_confidence < 0.5:
        return "clarify"
    else:
        return "enhance_query"

def should_search_or_recipe(state: ChatState) -> Literal["product_search", "recipe_search"]:
    """쿼리 내용에 따라 상품 검색 또는 레시피 검색으로 분기"""
    query = state.query.lower()
    rewrite_text = state.rewrite.get("text", "").lower()
    
    # 레시피 관련 키워드 체크
    recipe_keywords = ["레시피", "요리법", "만들기", "조리법", "음식", "요리"]
    
    if any(keyword in query or keyword in rewrite_text for keyword in recipe_keywords):
        return "recipe_search"
    else:
        return "product_search"

def should_continue_or_cart(state: ChatState) -> Literal["cart_manage", "clarify", "END"]:
    """검색 결과에 따라 장바구니 또는 clarify로 분기"""
    candidates = state.search.get("candidates", [])
    
    if not candidates:
        # 결과가 없으면 clarify로
        return "clarify"
    elif len(candidates) == 1:
        # 결과가 하나면 바로 장바구니로
        return "cart_manage"
    else:
        # 여러 결과가 있으면 사용자 선택 대기 (일단 장바구니로)
        return "cart_manage"

def should_checkout_or_end(state: ChatState) -> Literal["checkout", "END"]:
    """장바구니 상태에 따라 체크아웃 또는 종료로 분기"""
    cart_items = state.cart.get("items", [])
    
    if cart_items:
        return "checkout"
    else:
        return "END"

def should_handoff_or_answer(state: ChatState) -> Literal["handoff", "faq_policy_rag", "END"]:
    """CS 티켓에 따라 FAQ 검색 또는 핸드오프로 분기"""
    ticket_category = state.cs.get("ticket", {}).get("category", "")
    
    # 복잡한 문의는 바로 핸드오프
    complex_categories = ["환불", "분쟁", "법적문의", "배송사고"]
    if ticket_category in complex_categories:
        return "handoff"
    else:
        return "faq_policy_rag"

def should_handoff_after_faq(state: ChatState) -> Literal["handoff", "end_session"]:
    """FAQ 응답 신뢰도에 따라 핸드오프 또는 세션 종료로 분기"""
    confidence = state.cs.get("answer", {}).get("confidence", 0.0)
    
    if confidence < 0.3:
        return "handoff"
    else:
        return "end_session"

def create_workflow():
    """
    Qook 챗봇의 전체 워크플로우를 생성하고 컴파일된 그래프를 반환합니다.
    """
    
    # StateGraph 생성
    workflow = StateGraph(ChatState)
    
    # 노드 추가
    workflow.add_node("router", router_route)
    workflow.add_node("enhance_query", enhance_query)
    workflow.add_node("product_search", product_search_rag_text2sql)
    workflow.add_node("recipe_search", recipe_search)
    workflow.add_node("clarify", clarify)
    workflow.add_node("cart_manage", cart_manage)
    workflow.add_node("checkout", checkout)
    workflow.add_node("order_process", order_process)
    workflow.add_node("cs_intake", cs_intake)
    workflow.add_node("faq_policy_rag", faq_policy_rag)
    workflow.add_node("handoff", handoff)
    workflow.add_node("end_session", end_session)
    
    # 시작점 설정
    workflow.set_entry_point("router")
    
    # 라우터에서 분기
    workflow.add_conditional_edges(
        "router",
        should_clarify,
        {
            "clarify": "clarify",
            "enhance_query": "enhance_query",
            "cs_intake": "cs_intake"
        }
    )
    
    # Clarify에서 enhance_query로
    workflow.add_edge("clarify", "enhance_query")
    
    # 쿼리 보강 후 검색 타입 결정
    workflow.add_conditional_edges(
        "enhance_query",
        should_search_or_recipe,
        {
            "product_search": "product_search",
            "recipe_search": "recipe_search"
        }
    )
    
    # 상품 검색 후 분기
    workflow.add_conditional_edges(
        "product_search",
        should_continue_or_cart,
        {
            "cart_manage": "cart_manage",
            "clarify": "clarify",
            "END": END
        }
    )
    
    # 레시피 검색 후 장바구니로
    workflow.add_edge("recipe_search", "cart_manage")
    
    # 장바구니에서 체크아웃으로
    workflow.add_conditional_edges(
        "cart_manage",
        should_checkout_or_end,
        {
            "checkout": "checkout",
            "END": END
        }
    )
    
    # 체크아웃에서 주문 처리로
    workflow.add_edge("checkout", "order_process")
    
    # 주문 처리 후 세션 종료로
    workflow.add_edge("order_process", "end_session")
    
    # CS 경로 - 라우터에서 CS로 직접 분기하는 경우 (추가 조건부 엣지 필요)
    workflow.add_edge("cs_intake", "faq_policy_rag")
    
    # FAQ RAG에서 핸드오프 또는 세션 종료로 분기
    workflow.add_conditional_edges(
        "faq_policy_rag",
        should_handoff_after_faq,
        {
            "handoff": "handoff",
            "end_session": "end_session"
        }
    )
    
    # 핸드오프에서 세션 종료로
    workflow.add_edge("handoff", "end_session")
    
    # 세션 종료는 END로
    workflow.add_edge("end_session", END)
    
    # 워크플로우 컴파일
    compiled_workflow = workflow.compile()
    
    return compiled_workflow

def create_cs_workflow():
    """
    CS 전용 간소화된 워크플로우를 생성합니다.
    """
    workflow = StateGraph(ChatState)
    
    # CS 전용 노드들
    workflow.add_node("cs_intake", cs_intake)
    workflow.add_node("faq_policy_rag", faq_policy_rag)
    workflow.add_node("handoff", handoff)
    workflow.add_node("end_session", end_session)
    
    # 시작점
    workflow.set_entry_point("cs_intake")
    
    # CS 접수 후 FAQ로
    workflow.add_conditional_edges(
        "cs_intake",
        should_handoff_or_answer,
        {
            "faq_policy_rag": "faq_policy_rag",
            "handoff": "handoff",
            "END": END
        }
    )
    
    # FAQ 후 핸드오프 또는 종료
    workflow.add_conditional_edges(
        "faq_policy_rag",
        should_handoff_after_faq,
        {
            "handoff": "handoff",
            "end_session": "end_session"
        }
    )
    
    # 핸드오프 후 종료
    workflow.add_edge("handoff", "end_session")
    
    # 세션 종료
    workflow.add_edge("end_session", END)
    
    return workflow.compile()

# 전역 워크플로우 인스턴스
_main_workflow = None
_cs_workflow = None

def get_main_workflow():
    """메인 워크플로우 인스턴스를 반환합니다."""
    global _main_workflow
    if _main_workflow is None:
        _main_workflow = create_workflow()
    return _main_workflow

def get_cs_workflow():
    """CS 워크플로우 인스턴스를 반환합니다."""
    global _cs_workflow
    if _cs_workflow is None:
        _cs_workflow = create_cs_workflow()
    return _cs_workflow

# 워크플로우 실행 헬퍼 함수
async def run_workflow(initial_state: ChatState, workflow_type: str = "main") -> Dict[str, Any]:
    """
    워크플로우를 실행하고 결과를 반환합니다.
    
    Args:
        initial_state: 초기 대화 상태
        workflow_type: "main" 또는 "cs"
    
    Returns:
        최종 상태 딕셔너리
    """
    if workflow_type == "cs":
        workflow = get_cs_workflow()
    else:
        workflow = get_main_workflow()
    
    # 워크플로우 실행
    result = await workflow.ainvoke(initial_state)
    
    return result

if __name__ == "__main__":
    # 테스트 실행
    import asyncio
    
    async def test_workflow():
        """워크플로우 테스트"""
        test_state = ChatState(
            user_id="test_user",
            session_id="test_session",
            turn_id=1,
            query="사과를 주문하고 싶어요"
        )
        
        result = await run_workflow(test_state)
        print("워크플로우 실행 결과:")
        print(result)
    
    # 비동기 테스트 실행
    asyncio.run(test_workflow())