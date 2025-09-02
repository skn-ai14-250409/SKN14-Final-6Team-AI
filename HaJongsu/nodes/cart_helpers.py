"""
cart_helpers.py - 장바구니 관련 헬퍼 함수들
"""

from typing import Dict, Any, List

def _format_cart_response(db_cart_items: List[Dict[str, Any]]) -> Dict[str, Any]:
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

def calculate_cart_summary(items: List[Dict[str, Any]]) -> Dict[str, float]:
    """장바구니 아이템들로부터 합계 계산"""
    subtotal = sum(item["qty"] * item["unit_price"] for item in items)
    shipping = 0.0 if subtotal >= 30000 else 3000.0
    total = subtotal + shipping
    
    return {
        "subtotal": subtotal,
        "shipping": shipping,
        "total": total,
        "discount": 0.0
    }