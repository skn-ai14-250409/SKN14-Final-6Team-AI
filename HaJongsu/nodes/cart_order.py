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
from utils.database import (
    get_product_by_name, get_user_cart, add_to_cart, 
    remove_from_cart, clear_cart, create_order
)

def _format_cart_response(db_cart_items):
    """데이터베이스 장바구니 데이터를 ChatState 형식으로 변환"""
    items = []
    total_amount = 0.0
    
    for db_item in db_cart_items:
        cart_item = {
            "sku": db_item['product'],
            "name": db_item['product'], 
            "qty": int(db_item['quantity']),
            "unit_price": float(db_item['unit_price']),
            "variant": None
        }
        items.append(cart_item)
        total_amount += float(db_item['total_price'])
    
    # 배송비 계산 (30,000원 이상 무료배송)
    shipping_fee = 0.0 if total_amount >= 30000 else 3000.0
    final_total = total_amount + shipping_fee
    
    return {
        "items": items,
        "subtotal": total_amount,
        "shipping": shipping_fee, 
        "total": final_total,
        "discount": 0.0,
        "item_count": len(items)
    }

logger = logging.getLogger("D_CART_ORDER")

# 대체 함수: 실제 DB에서 상품 정보 가져오기
def get_product_info_from_db(product_name: str) -> Optional[Dict[str, Any]]:
    """데이터베이스에서 상품 정보 조회"""
    try:
        product_info = get_product_by_name(product_name)
        if product_info:
            return {
                "price": float(product_info.get('unit_price', 0)),
                "stock": int(product_info.get('stock', 0)),
                "origin": product_info.get('origin', '')
            }
        return None
    except Exception as e:
        logger.error(f"상품 정보 조회 실패: {e}")
        return None

def cart_manage(state: ChatState) -> Dict[str, Any]:
    """
    장바구니 관리(멱등) - 실제 데이터베이스 연동
    - 추가/수정/삭제 후 합계/할인/총액을 재계산합니다.
    - 재고/최소주문 규칙 등 검증 실패 시 사용자 교정 메시지를 생성하세요.
    """
    logger.info("장바구니 관리 프로세스 시작", extra={
        "user_id": state.user_id,
        "session_id": state.session_id
    })
    
    try:
        # 데이터베이스에서 현재 장바구니 상태 가져오기
        db_cart_items = get_user_cart(state.user_id)
        
        # 검색 결과에서 장바구니에 추가할 상품들 확인
        candidates = state.search.get("candidates", [])
        
        if candidates:
            # 첫 번째 후보를 장바구니에 추가
            for candidate in candidates[:1]:
                product_name = candidate.get('name') or candidate.get('sku')
                quantity = state.slots.get("quantity", 1)
                unit_price = float(candidate.get('price', 0))
                
                # 실제 데이터베이스에 추가
                success = add_to_cart(state.user_id, product_name, quantity, unit_price)
                
                if success:
                    logger.info(f"상품 추가 성공: {product_name}")
                    # 업데이트된 장바구니 다시 가져오기
                    db_cart_items = get_user_cart(state.user_id)
                else:
                    logger.warning(f"상품 추가 실패: {product_name}")
                    return {
                        "cart": _format_cart_response(db_cart_items),
                        "meta": {"cart_message": f"{product_name} 추가에 실패했습니다."}
                    }
        
        # 장바구니 형식 변환 및 합계 계산
        formatted_cart = _format_cart_response(db_cart_items)
        
        logger.info("장바구니 관리 완료", extra={
            "items_count": len(formatted_cart["items"]),
            "total": formatted_cart["total"]
        })
        
        return {
            "cart": formatted_cart,
            "meta": {
                "cart_message": f"장바구니에 {len(formatted_cart['items'])}개 상품이 담겨있습니다.",
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

def _validate_product_stock(product_name: str, requested_qty: int) -> Dict[str, Any]:
    """상품 재고 검증 (DB 연동)"""
    try:
        # DB에서 실제 상품 정보 가져오기
        product_info = get_product_info_from_db(product_name)
        
        if not product_info:
            return {
                "success": False,
                "message": f"{product_name} 상품을 찾을 수 없습니다.",
                "available_stock": 0
            }
        
        available_stock = product_info.get("stock", 0)
        
        if available_stock < requested_qty:
            return {
                "success": False,
                "message": f"{product_name}의 재고가 부족합니다. (요청: {requested_qty}, 재고: {available_stock})",
                "available_stock": available_stock
            }
        
        return {
            "success": True,
            "message": "재고 충분",
            "available_stock": available_stock,
            "product_info": product_info
        }
        
    except Exception as e:
        logger.error(f"상품 재고 검증 실패: {e}")
        return {
            "success": False,
            "message": "상품 정보 조회 실패",
            "available_stock": 0
        }

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
        
        # 데이터베이스에서 실제 장바구니 가져오기
        db_cart_items = get_user_cart(state.user_id)
        
        if not db_cart_items:
            return {
                "order": {
                    "error": "장바구니가 비어있습니다.",
                    "status": "failed"
                }
            }
        
        # 주문 총액 계산
        total_amount = sum(float(item['total_price']) for item in db_cart_items)
        if total_amount < 30000:
            total_amount += 3000  # 배송비 추가
        
        # 실제 데이터베이스에 주문 생성
        order_id = create_order(state.user_id, total_amount, db_cart_items)
        
        if not order_id:
            return {
                "order": {
                    "error": "주문 생성에 실패했습니다.",
                    "status": "failed"
                }
            }
        
        # 주문 완료 후 실제 재고 차감
        try:
            _update_inventory_in_db([
                {"sku": item['product'], "qty": int(item['quantity'])} 
                for item in db_cart_items
            ])
        except Exception as e:
            logger.warning(f"재고 업데이트 실패 (주문은 성공): {e}")

        order_info = {
            "order_id": order_id,
            "status": "confirmed",
            "items": [{"product": item['product'], "quantity": item['quantity'], "price": item['total_price']} for item in db_cart_items],
            "total_amount": total_amount,
            "address": state.checkout.get("address", "서울시 강남구 테헤란로 123"),
            "delivery_slot": state.checkout.get("slot", "내일 오전 (09:00-12:00)"),
            "payment_method": state.checkout.get("payment_method", "CARD"),
            "created_at": datetime.now().isoformat(),
            "estimated_delivery": _calculate_delivery_date()
        }
        
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

def _update_inventory_in_db(items: List[Dict[str, Any]]) -> None:
    """실제 DB에서 재고 업데이트"""
    try:
        for item in items:
            product_name = item.get("sku") or item.get("name")
            qty = item.get("qty", 0)
            
            if product_name and qty > 0:
                # 실제 DB 재고 업데이트
                update_query = """
                UPDATE stock_tbl 
                SET stock = GREATEST(0, CAST(stock AS SIGNED) - %s)
                WHERE product = %s
                """
                from utils.database import execute_non_query
                affected = execute_non_query(update_query, (qty, product_name))
                
                if affected > 0:
                    logger.info(f"DB 재고 업데이트: {product_name} -{qty}")
                else:
                    logger.warning(f"재고 업데이트 실패: {product_name}")
    except Exception as e:
        logger.error(f"DB 재고 업데이트 실패: {e}")