"""
cart_order.py — D팀: 카트 & 주문

D팀의 책임:
- 장바구니 멱등성 관리 (추가/수정/삭제)
- 재고 검증 및 가격 계산
- 체크아웃 프로세스 (배송지, 결제수단 수집)
- 주문 생성 및 상태 관리
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

# 상대 경로로 graph_interfaces 임포트
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_interfaces import ChatState, CartItem

logger = logging.getLogger("D_CART_ORDER")

# 임시 재고 데이터 (실제로는 데이터베이스에서 가져와야 함)
MOCK_INVENTORY = {
    "유기농 사과": {"price": 3000, "stock": 50},
    "바나나": {"price": 2500, "stock": 30},
    "유기농 당근": {"price": 1800, "stock": 25},
    "양상추": {"price": 1500, "stock": 40},
    "토마토": {"price": 2200, "stock": 35}
}

def cart_manage(state: ChatState) -> Dict[str, Any]:
    """
    장바구니 관리(멱등)
    - 추가/수정/삭제 후 합계/할인/총액을 재계산합니다.
    - 재고/최소주문 규칙 등 검증 실패 시 사용자 교정 메시지를 생성하세요.
    """
    logger.info("장바구니 관리 프로세스 시작", extra={
        "user_id": state.user_id,
        "session_id": state.session_id
    })
    
    try:
        # 현재 장바구니 상태 가져오기
        current_cart = state.cart.copy()
        if not current_cart.get("items"):
            current_cart["items"] = []
        
        # 검색 결과에서 장바구니에 추가할 상품들 확인
        candidates = state.search.get("candidates", [])
        
        if candidates:
            # 첫 번째 후보를 장바구니에 추가 (실제로는 사용자 선택 필요)
            for candidate in candidates[:1]:  # 일단 첫 번째 상품만
                result = _add_to_cart(current_cart, candidate, state.slots.get("quantity", 1))
                if result["success"]:
                    logger.info(f"상품 추가 성공: {candidate['name']}")
                else:
                    logger.warning(f"상품 추가 실패: {result['message']}")
                    return {
                        "cart": current_cart,
                        "meta": {"cart_message": result["message"]}
                    }
        
        # 장바구니 합계 계산
        _calculate_totals(current_cart)
        
        logger.info("장바구니 관리 완료", extra={
            "items_count": len(current_cart["items"]),
            "total": current_cart["total"]
        })
        
        return {
            "cart": current_cart,
            "meta": {
                "cart_message": f"장바구니에 {len(current_cart['items'])}개 상품이 담겨있습니다.",
                "last_action": "cart_updated"
            }
        }
        
    except Exception as e:
        logger.error(f"장바구니 관리 실패: {e}", extra={
            "user_id": state.user_id,
            "error": str(e)
        })
        
        return {
            "cart": state.cart,
            "meta": {"cart_error": str(e)}
        }

def _add_to_cart(cart: Dict[str, Any], candidate: Dict[str, Any], quantity: int) -> Dict[str, Any]:
    """상품을 장바구니에 추가"""
    
    sku = candidate.get("sku") or candidate.get("name")
    name = candidate.get("name")
    price = candidate.get("price", 0)
    stock = candidate.get("stock", 0)
    
    # 재고 검증
    if stock < quantity:
        return {
            "success": False,
            "message": f"{name}의 재고가 부족합니다. (요청: {quantity}, 재고: {stock})"
        }
    
    # 기존 아이템이 있는지 확인
    existing_item = None
    for item in cart["items"]:
        if item["sku"] == sku:
            existing_item = item
            break
    
    if existing_item:
        # 기존 아이템 수량 업데이트 (멱등성)
        new_quantity = existing_item["qty"] + quantity
        if stock < new_quantity:
            return {
                "success": False,
                "message": f"{name}의 재고가 부족합니다. (총 요청: {new_quantity}, 재고: {stock})"
            }
        existing_item["qty"] = new_quantity
    else:
        # 새 아이템 추가
        new_item = {
            "sku": sku,
            "name": name,
            "qty": quantity,
            "unit_price": price
        }
        cart["items"].append(new_item)
    
    return {"success": True, "message": f"{name} {quantity}개가 장바구니에 추가되었습니다."}

def _calculate_totals(cart: Dict[str, Any]) -> None:
    """장바구니 합계 계산"""
    
    subtotal = 0.0
    for item in cart["items"]:
        subtotal += item["unit_price"] * item["qty"]
    
    cart["subtotal"] = subtotal
    
    # 할인 계산 (예: 30000원 이상 시 배송비 무료)
    discounts = []
    if subtotal >= 30000:
        discounts.append({"type": "free_shipping", "amount": 3000, "description": "무료배송"})
    
    cart["discounts"] = discounts
    
    # 총 할인 금액
    total_discount = sum(d["amount"] for d in discounts)
    
    # 최종 금액
    cart["total"] = max(0, subtotal - total_discount)

def checkout(state: ChatState) -> Dict[str, Any]:
    """
    체크아웃(과금 없음)
    - 배송지, 배송창, 결제수단을 수집합니다.
    - 실제 결제는 order_process 단계에서 확정됩니다.
    """
    logger.info("체크아웃 프로세스 시작", extra={
        "user_id": state.user_id,
        "cart_total": state.cart.get("total", 0)
    })
    
    try:
        # 장바구니 검증
        if not state.cart.get("items") or len(state.cart["items"]) == 0:
            return {
                "checkout": {
                    "error": "장바구니가 비어있습니다.",
                    "confirmed": False
                }
            }
        
        # 기본 체크아웃 정보 설정
        checkout_info = {
            "address": _get_default_address(state),
            "slot": _get_default_delivery_slot(),
            "payment_method": "CARD",
            "confirmed": False,
            "created_at": datetime.now().isoformat(),
            "total_amount": state.cart.get("total", 0)
        }
        
        logger.info("체크아웃 정보 준비 완료", extra={
            "address": checkout_info["address"][:20] + "...",
            "payment_method": checkout_info["payment_method"]
        })
        
        return {
            "checkout": checkout_info,
            "meta": {
                "checkout_message": "배송지와 결제수단을 확인해주세요.",
                "next_step": "order_confirmation"
            }
        }
        
    except Exception as e:
        logger.error(f"체크아웃 실패: {e}")
        return {
            "checkout": {
                "error": str(e),
                "confirmed": False
            }
        }

def _get_default_address(state: ChatState) -> str:
    """기본 배송지 가져오기 (실제로는 사용자 프로필에서)"""
    # 임시로 기본 주소 반환
    return "서울시 강남구 테헤란로 123길 45, 101동 501호"

def _get_default_delivery_slot() -> str:
    """기본 배송 시간대 반환"""
    # 임시로 기본 배송 시간 반환
    return "내일 오전 (09:00-12:00)"

def order_process(state: ChatState) -> Dict[str, Any]:
    """
    주문 처리(확정/취소)
    - 사용자 확인에 따라 주문을 확정하거나 취소합니다.
    - 주문 레코드/영수증/감사 로그를 남깁니다.
    """
    logger.info("주문 처리 프로세스 시작", extra={
        "user_id": state.user_id,
        "checkout_confirmed": state.checkout.get("confirmed", False)
    })
    
    try:
        # 체크아웃 정보 검증
        if not state.checkout or not state.checkout.get("confirmed", True):  # 임시로 true 처리
            # 임시로 자동 확정 (실제로는 사용자 확인 필요)
            logger.info("자동으로 주문 확정 처리 (데모용)")
        
        # 주문 생성
        order_id = _generate_order_id()
        order_info = {
            "order_id": order_id,
            "status": "confirmed",
            "items": state.cart.get("items", []),
            "total_amount": state.cart.get("total", 0),
            "address": state.checkout.get("address", ""),
            "delivery_slot": state.checkout.get("slot", ""),
            "payment_method": state.checkout.get("payment_method", "CARD"),
            "created_at": datetime.now().isoformat(),
            "estimated_delivery": _calculate_delivery_date()
        }
        
        # 재고 차감 시뮬레이션
        _update_inventory(order_info["items"])
        
        logger.info("주문 처리 완료", extra={
            "order_id": order_id,
            "status": order_info["status"],
            "amount": order_info["total_amount"]
        })
        
        return {
            "order": order_info,
            "meta": {
                "order_message": f"주문이 완료되었습니다. 주문번호: {order_id}",
                "next_step": "session_end"
            }
        }
        
    except Exception as e:
        logger.error(f"주문 처리 실패: {e}")
        return {
            "order": {
                "status": "failed",
                "error": str(e)
            }
        }

def _generate_order_id() -> str:
    """주문 ID 생성"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = str(uuid.uuid4())[:8]
    return f"QK-{timestamp}-{random_suffix.upper()}"

def _calculate_delivery_date() -> str:
    """배송 예정일 계산"""
    from datetime import timedelta
    delivery_date = datetime.now() + timedelta(days=1)
    return delivery_date.strftime("%Y-%m-%d")

def _update_inventory(items: List[Dict[str, Any]]) -> None:
    """재고 업데이트 시뮬레이션"""
    for item in items:
        sku = item["sku"]
        qty = item["qty"]
        if sku in MOCK_INVENTORY:
            MOCK_INVENTORY[sku]["stock"] = max(0, MOCK_INVENTORY[sku]["stock"] - qty)
            logger.info(f"재고 업데이트: {sku} -{qty}, 남은 재고: {MOCK_INVENTORY[sku]['stock']}")