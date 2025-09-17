import logging
from langgraph.graph import StateGraph, END
from graph_interfaces import ChatState

from nodes.router_clarify import router_route, clarify
from nodes.query_enhancement import enhance_query
from nodes.product_search import product_search_rag_text2sql
from nodes.recipe_search import recipe_search
from nodes.vision_recipe import vision_recipe
from nodes.cart_order import cart_manage, view_cart, remove_from_cart, checkout
from nodes.cs_impl import cs_intake
from nodes.cs_rag_faq import faq_policy_rag
from nodes.handoff_end import handoff
from nodes.casual_chat import casual_chat

logger = logging.getLogger(__name__)

def search_hub(state: ChatState) -> ChatState:
    """검색 관련 요청을 처리하는 허브 함수 - conditional_edges가 분기 처리"""
    target = state.route.get("target")
    logger.info(f"Search hub: Processing '{target}'")
    return state

def cs_hub(state: ChatState) -> ChatState:
    """CS 관련 요청을 처리하는 허브 함수 - conditional_edges가 분기 처리"""
    target = state.route.get("target")
    logger.info(f"CS hub: Processing '{target}'")
    
    if target == 'handoff':
        state.cs["classification"] = "handoff"
        return state

    if target in ('cs_intake', 'faq_policy_rag'):
        state.cs["classification"] = 'faq_policy' if target == 'faq_policy_rag' else 'cs_intake'
        return state
    
    return state

def determine_search_target(state: ChatState) -> str:
    """search_hub에서 다음 노드를 결정하는 조건부 함수 (if문 없이 딕셔너리 매핑)"""
    target = state.route.get("target")
    logger.info(f"Search target decision: '{target}'")

    target_mapping = {
        'cart_add': 'enhance_query',
        'cart_remove': 'enhance_query',
        'product_search': 'enhance_query',
        'recipe_search': 'enhance_query',
        'vision_recipe': 'vision_recipe',
        'cart_view': 'enhance_query',
        'checkout': 'enhance_query',
    }

    next_node = target_mapping.get(target, 'enhance_query')
    logger.info(f"determine_search_target: route='{target}' -> next='{next_node}'")
    return next_node

def determine_cs_target(state: ChatState) -> str:
    """cs_hub에서 다음 노드를 결정하는 조건부 함수 - LLM 분류 결과 기반"""
    target = state.route.get("target")
    classification = state.cs.get("classification", "cs_intake")
    
    logger.info(f"CS target decision: route='{target}', classification='{classification}'")
    
    if target == 'handoff' or classification == 'handoff':
        logger.info(f"determine_cs_target: route='{target}', class='{classification}' -> next='handoff'")
        return 'handoff'
    
    # LLM 분류 결과에 따른 분기 (딕셔너리 매핑)
    classification_mapping = {
        'cs_intake': 'cs_intake',
        'faq_policy': 'faq_policy_rag'
    }
    
    next_node = classification_mapping.get(classification, 'cs_intake')
    logger.info(f"determine_cs_target: route='{target}', class='{classification}' -> next='{next_node}'")
    return next_node

def determine_after_enhance_query(state: ChatState) -> str:
    """enhance_query 후 다음 노드를 결정하는 조건부 함수"""
    target = state.route.get("target")
    logger.info(f"After enhance_query decision: '{target}'")

    target_mapping = {
        'cart_add': 'product_search',
        'cart_remove': 'remove_from_cart',
        'product_search': 'product_search',
        'recipe_search': 'recipe_search',
        'cart_view': 'view_cart',
        'checkout': 'view_cart',
    }
    
    next_node = target_mapping.get(target, 'product_search')
    logger.info(f"determine_after_enhance_query: route='{target}' -> next='{next_node}'")
    return next_node

def determine_after_product_search(state: ChatState) -> str:
    """product_search 후 다음 노드를 결정하는 조건부 함수"""
    target = state.route.get("target")
    
    cart_add_mapping = {
        'cart_add': 'cart_manage'
    }
    
    next_node = cart_add_mapping.get(target, 'END')
    logger.info(f"determine_after_product_search: route='{target}' -> next='{next_node}'")
    return next_node

def determine_after_view_cart(state: ChatState) -> str:
    """view_cart 후 다음 노드를 결정하는 조건부 함수"""
    target = state.route.get("target")
    has_items = bool(state.cart.get("items"))
    
    checkout_condition = target == 'checkout' and has_items
    
    next_node = 'checkout' if checkout_condition else 'END'
    logger.info(f"determine_after_view_cart: route='{target}', has_items={has_items} -> next='{next_node}'")
    return next_node

def determine_after_faq_policy_rag(state: ChatState) -> str:
    """faq_policy_rag 후 다음 노드를 결정하는 조건부 함수"""
    should_handoff = state.cs.get("answer", {}).get("should_handoff", False)
    next_node = 'handoff' if should_handoff else 'END'
    logger.info(f"determine_after_faq_policy_rag: should_handoff={should_handoff} -> next='{next_node}'")
    return next_node

def determine_after_vision_recipe(state: ChatState) -> str:
    """vision_recipe 후 다음 노드를 결정하는 조건부 함수"""
    target = state.route.get("target")
    logger.info(f"After vision_recipe decision: target='{target}'")

    if target == 'recipe_search':
        return 'recipe_search'
    else:
        return 'recipe_search'

def determine_route(state: ChatState) -> str:
    """라우터의 결과에 따라 다음 노드를 결정하는 함수"""
    target = state.route.get("target")
    logger.info(f"Routing decision: target = '{target}'")

    if target == 'clarify':
        return 'clarify'
    elif target in ['product_search', 'recipe_search', 'vision_recipe', 'cart_add', 'cart_remove', 'cart_view', 'checkout']:
        return 'search_hub'
    elif target in ['handoff', 'cs_intake', 'faq_policy_rag']:
        return 'cs_hub'
    elif target == 'casual_chat':
        return 'casual_chat'
    else:
        state.meta["final_message"] = "알 수 없는 요청입니다. 다시 시도해주세요."
        return 'clarify'

def create_workflow_graph():
    """LangGraph StateGraph를 사용한 워크플로우 생성"""

    workflow = StateGraph(ChatState)
    
    workflow.add_node("router", router_route)
    workflow.add_node("clarify", clarify)
    workflow.add_node("search_hub", search_hub)
    workflow.add_node("cs_hub", cs_hub)
    
    workflow.add_node("enhance_query", enhance_query)
    workflow.add_node("product_search", product_search_rag_text2sql)
    workflow.add_node("recipe_search", recipe_search)
    workflow.add_node("vision_recipe", vision_recipe)
    workflow.add_node("cart_manage", cart_manage)
    workflow.add_node("view_cart", view_cart)
    workflow.add_node("remove_from_cart", remove_from_cart)
    workflow.add_node("checkout", checkout)
    workflow.add_node("cs_intake", cs_intake)
    workflow.add_node("faq_policy_rag", faq_policy_rag)
    workflow.add_node("handoff", handoff)
    workflow.add_node("casual_chat", casual_chat)
    
    workflow.set_entry_point("router")
    
    workflow.add_conditional_edges(
        "router",
        determine_route,
        {
            "clarify": "clarify",
            "search_hub": "search_hub", 
            "cs_hub": "cs_hub",
            "casual_chat": "casual_chat"
        }
    )
    
    workflow.add_conditional_edges(
        "search_hub",
        determine_search_target,
        {
            "enhance_query": "enhance_query",
            "vision_recipe": "vision_recipe"
        }
    )
    
    workflow.add_conditional_edges(
        "cs_hub",
        determine_cs_target,
        {
            "cs_intake": "cs_intake",
            "faq_policy_rag": "faq_policy_rag",
            "handoff": "handoff"
        }
    )
    
    workflow.add_conditional_edges(
        "enhance_query",
        determine_after_enhance_query,
        {
            "product_search": "product_search",
            "recipe_search": "recipe_search", 
            "view_cart": "view_cart",
            "remove_from_cart": "remove_from_cart",
            "checkout": "checkout",               
        }
    )
    
    workflow.add_conditional_edges(
        "product_search",
        determine_after_product_search,
        {
            "cart_manage": "cart_manage",
            "END": END
        }
    )
    
    workflow.add_conditional_edges(
        "view_cart", 
        determine_after_view_cart,
        {
            "checkout": "checkout",
            "END": END
        }
    )
    
    workflow.add_conditional_edges(
        "faq_policy_rag",
        determine_after_faq_policy_rag,
        {
            "handoff": "handoff",
            "END": END
        }
    )

    workflow.add_conditional_edges(
        "vision_recipe",
        determine_after_vision_recipe,
        {
            "recipe_search": "recipe_search"
        }
    )

    workflow.add_edge("clarify", END)
    workflow.add_edge("recipe_search", END)
    workflow.add_edge("cart_manage", END)
    workflow.add_edge("remove_from_cart", END)
    workflow.add_edge("checkout", END)
    workflow.add_edge("cs_intake", END)
    workflow.add_edge("handoff", END)
    workflow.add_edge("casual_chat", END)
    
    return workflow.compile()

_workflow_graph = None

def get_workflow_graph():
    """워크플로우 그래프 싱글톤 인스턴스 반환"""
    global _workflow_graph
    if _workflow_graph is None:
        _workflow_graph = create_workflow_graph()
        logger.info("StateGraph workflow created successfully")
    return _workflow_graph

def run_workflow(state: ChatState) -> ChatState:
    """StateGraph 기반 워크플로우 실행 (기존 인터페이스 유지)"""
    try:
        workflow_graph = get_workflow_graph()
        result = workflow_graph.invoke(state)
        logger.info("StateGraph workflow execution completed")
        return result
    except Exception as e:
        logger.error(f"StateGraph workflow execution failed: {e}")
        return run_workflow_fallback(state)

def run_workflow_fallback(state: ChatState) -> ChatState:
    """기존 if문 방식 워크플로우 (폴백용)"""
    state.update(router_route(state))
    target = state.route.get("target")
    logger.info(f"Fallback workflow: Routing complete. Target is '{target}'.")
    
    if target == 'clarify':
        state.update(clarify(state))
        return state
    
    elif target in ['product_search', 'recipe_search', 'cart_add', 'cart_remove', 'cart_view', 'checkout']:
        logger.info(f"Fallback routing to search_hub for target: {target}")
        print("search_hub:", search_hub(state))
        return search_hub(state)
        
    elif target in ['cs_intake', 'faq_policy_rag', 'handoff']:
        logger.info(f"Fallback routing to cs_hub for target: {target}")
        return cs_hub(state)
        
    else: 
        state.meta["final_message"] = "알 수 없는 요청입니다. 다시 시도해주세요."

    logger.info("Fallback workflow finished.")
    return state
