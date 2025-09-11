"""
cart_order.py — D팀: 카트 & 주문 (DB 연동 최종 버전)
"""
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import mysql.connector
from mysql.connector import Error

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_interfaces import ChatState

logger = logging.getLogger("D_CART_ORDER_DB")

DB_CONFIG = {
    'host': '127.0.0.1', 'user': 'qook_user',
    'password': 'qook_pass', 'database': 'qook_chatbot', 'port': 3306
}

def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        logger.error(f"DB 연결 실패: {e}")
        return None

def view_cart(state: ChatState) -> Dict[str, Any]:
    """DB에서 현재 사용자의 장바구니 정보를 조회합니다."""
    logger.info(f"장바구니 조회 프로세스 시작: User '{state.user_id}'")
    user_id = state.user_id or 'anonymous'
    conn = get_db_connection()
    if not conn: return {"meta": {"cart_error": "DB 연결 실패"}}
    
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT product as name, product as sku, quantity as qty, unit_price "
                "FROM cart_tbl WHERE user_id = %s",
                (user_id,)
            )
            cart_items = cursor.fetchall()
        # 멤버십 혜택 조회
        benefits = _get_membership_benefits(user_id)
        current_cart = {"items": cart_items, "membership": benefits.get("meta")}
        _calculate_totals(current_cart, benefits)
        return {"cart": current_cart}
    except Error as e:
        logger.error(f"장바구니 조회 실패: {e}")
        return {"meta": {"cart_error": str(e)}}
    finally:
        if conn and conn.is_connected(): conn.close()

# --- (신설/수정) 장바구니 수량 직접 업데이트 함수 ---
def update_cart_item(user_id: str, product_name: str, quantity: int) -> Dict[str, Any]:
    """장바구니 아이템 수량을 특정 값으로 직접 설정하거나 삭제하는 전용 함수"""
    logger.info(f"장바구니 직접 수정: User '{user_id}', Product '{product_name}', Quantity '{quantity}'")
    
    conn = get_db_connection()
    if not conn: return {"error": "DB 연결 실패"}

    try:
        with conn.cursor() as cursor:
            if quantity > 0:
                # 수량을 특정 값으로 업데이트 (INSERT ... ON DUPLICATE KEY UPDATE 사용)
                sql = """
                    INSERT INTO cart_tbl (user_id, product, quantity, unit_price, total_price)
                    VALUES (
                        %s, %s, %s,
                        (SELECT unit_price FROM product_tbl WHERE product=%s),
                        %s * (SELECT unit_price FROM product_tbl WHERE product=%s)
                    )
                    ON DUPLICATE KEY UPDATE
                        quantity = VALUES(quantity),
                        total_price = VALUES(unit_price) * VALUES(quantity)
                """
                cursor.execute(sql, (user_id, product_name, quantity, product_name, quantity, product_name))
                logger.info(f"'{product_name}' 상품 수량을 {quantity}(으)로 DB에 업데이트.")
            else:  # 수량이 0 이하면 삭제
                sql = "DELETE FROM cart_tbl WHERE user_id = %s AND product = %s"
                cursor.execute(sql, (user_id, product_name))
                logger.info(f"'{product_name}' 상품을 DB에서 삭제.")
            conn.commit()
            
    except Error as e:
        conn.rollback()
        logger.error(f"장바구니 직접 수정 실패: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected(): conn.close()

    # 최종적으로 변경된 장바구니 상태를 다시 조회해서 반환
    temp_state = ChatState(user_id=user_id)
    return view_cart(temp_state)
    
def cart_manage(state: ChatState) -> Dict[str, Any]:
    """
    장바구니 관리(멱등). DB의 cart_tbl을 기준으로 동작합니다.
    - 검색 후보가 있을 경우 첫 번째 후보를 담습니다.
    - ✅ 담기 성공 시 meta['cart']에 last_action/added_items를 채워 app.py가
      "담았습니다" 문구를 만들 수 있게 합니다.
    """
    logger.info("장바구니 관리 프로세스 시작")
    user_id = state.user_id or 'anonymous'
    
    added_meta = None  # ✅ 담기 성공 시 채워질 메타

    # 검색 결과에서 추가할 상품이 있을 때만 DB에 접근
    candidates = state.search.get("candidates", [])
    if candidates:
        # 첫 번째 후보 상품을 장바구니에 추가
        candidate = candidates[0]
        quantity = int(state.slots.get("quantity", 1))
        result = _add_to_cart(user_id, candidate, quantity)
        
        # 추가 실패 시 현재 장바구니 상태와 실패 메시지 반환
        if not result["success"]:
            current_cart_state = view_cart(state)
            return {
                "cart": current_cart_state.get('cart'), 
                "meta": {"cart_message": result["message"]}
            }
        else:
            # ✅ 성공: "무엇을 몇 개 담았는지" 기록
            added_meta = {
                "cart": {
                    "last_action": "add",
                    "added_items": [{
                        "name": candidate.get("name") or candidate.get("sku") or "상품",
                        "quantity": quantity
                    }]
                },
                "intent": "cart_add"
            }
    
    # 모든 작업 후 최종 장바구니 상태 조회 및 반환
    final_cart_state = view_cart(state)
    item_count = len(final_cart_state.get('cart', {}).get('items', []))

    meta = {
        "cart_message": f"장바구니에 {item_count}개 상품이 담겨있습니다.",
        "last_action": "cart_updated"
    }
    if added_meta:
        meta.update(added_meta)  # ✅ 담기 메타 병합

    return {
        "cart": final_cart_state.get('cart'),
        "search": {"candidates": []},
        "meta": meta
    }

def _add_to_cart(user_id: str, candidate: Dict[str, Any], quantity: int) -> Dict[str, Any]:
    """상품을 DB의 cart_tbl에 추가/수정합니다."""
    product_name = candidate.get("name")
    conn = get_db_connection()
    if not conn:
        return {"success": False, "message": "DB 연결에 실패했습니다."}

    try:
        with conn.cursor(dictionary=True) as cursor:
            # 상품 정보 및 재고 조회
            cursor.execute("""
                SELECT p.unit_price, s.stock 
                FROM product_tbl p 
                JOIN stock_tbl s ON p.product = s.product 
                WHERE p.product = %s
            """, (product_name,))
            product_info = cursor.fetchone()

            if not product_info:
                return {"success": False, "message": f"'{product_name}' 상품을 찾을 수 없습니다."}

            price = float(product_info['unit_price'])
            stock = int(product_info['stock'])
            
            # 현재 장바구니 수량 확인
            cursor.execute("SELECT quantity FROM cart_tbl WHERE user_id = %s AND product = %s", (user_id, product_name))
            cart_item = cursor.fetchone()
            current_qty_in_cart = int(cart_item['quantity']) if cart_item else 0

            # 재고 검증
            if stock < current_qty_in_cart + quantity:
                return {"success": False, "message": f"{product_name}의 재고가 부족합니다. (요청: {quantity}, 현재고: {stock})"}

            # ON DUPLICATE KEY UPDATE를 사용하여 멱등성 보장
            new_quantity = current_qty_in_cart + quantity
            sql = """
                INSERT INTO cart_tbl (user_id, product, unit_price, quantity, total_price)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE quantity = %s, total_price = %s
            """
            total_price = price * new_quantity
            cursor.execute(sql, (user_id, product_name, price, new_quantity, total_price, new_quantity, total_price))
            conn.commit()
            
            return {"success": True, "message": f"{product_name} {quantity}개가 추가되었습니다."}
    except Error as e:
        conn.rollback()
        logger.error(f"장바구니 추가 실패: {e}")
        return {"success": False, "message": f"장바구니 추가 중 오류가 발생했습니다."}
    finally:
        if conn and conn.is_connected():
            conn.close()

def _calculate_totals(cart: Dict[str, Any], benefits: Optional[Dict[str, Any]] = None) -> None:
    """장바구니 합계 계산 (DB에서 로드된 데이터를 기반으로)"""
    subtotal = sum(float(item["unit_price"]) * int(item["qty"]) for item in cart.get("items", []))
    cart["subtotal"] = subtotal
    discounts = []
    rate = 0.0
    free_ship_threshold = 30000.0
    if benefits:
        rate = float(benefits.get("discount_rate", 0.0) or 0.0)
        free_ship_threshold = float(benefits.get("free_shipping_threshold", 30000) or 30000)
    # 멤버십 상품할인
    if rate > 0:
        discounts.append({"type": "membership_discount", "amount": round(subtotal * rate), "description": f"멤버십 {int(rate*100)}% 할인"})
    # 기본 배송비(정액 3000원) 표기
    shipping_fee = 3000
    cart["shipping_fee"] = shipping_fee
    # 무료배송(정액 3000원 할인) 적용 기준
    if subtotal >= free_ship_threshold:
        discounts.append({"type": "free_shipping", "amount": 3000, "description": "무료배송"})
    cart["discounts"] = discounts
    total_discount = sum(d["amount"] for d in discounts)
    cart["total"] = max(0, subtotal + shipping_fee - total_discount)

def _get_membership_benefits(user_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    if not conn:
        return {"discount_rate": 0.0, "free_shipping_threshold": 30000, "meta": {"membership_name": "basic"}}
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                SELECT ud.membership AS membership_name,
                       COALESCE(m.discount_rate, 0) AS discount_rate,
                       COALESCE(m.free_shipping_threshold, 30000) AS free_shipping_threshold
                FROM user_detail_tbl ud
                LEFT JOIN membership_tbl m ON ud.membership = m.membership_name
                WHERE ud.user_id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone() or {}
            name = row.get("membership_name") or "basic"
            rate = float(row.get("discount_rate") or 0.0)
            thr = float(row.get("free_shipping_threshold") or 30000)
            return {"discount_rate": rate, "free_shipping_threshold": thr, "meta": {"membership_name": name, "discount_rate": rate, "free_shipping_threshold": thr}}
    except Error:
        return {"discount_rate": 0.0, "free_shipping_threshold": 30000, "meta": {"membership_name": "basic"}}
    finally:
        if conn and conn.is_connected():
            conn.close()

# ===========================
# ✅ 선택 결제/선택 제거 추가
# ===========================
def checkout(state: ChatState) -> Dict[str, Any]:
    """체크아웃 및 주문 처리 (개선된 버전 - 특정 상품 선택 지원)"""
    logger.info("체크아웃 및 주문 처리 시작")
    
    if not state.cart.get("items"):
        return {"checkout": {"error": "장바구니가 비어있습니다.", "confirmed": False}}
    
    # 특정 상품만 결제하고 싶은지 확인
    selected_items = _extract_selected_items_for_checkout(state)
    
    if selected_items:
        logger.info(f"특정 상품 결제 요청: {[item['name'] for item in selected_items]}")
        return _process_selective_checkout(state, selected_items)
    else:
        logger.info("전체 장바구니 결제 진행")
        return _process_full_checkout(state)

def _extract_selected_items_for_checkout(state: ChatState) -> List[Dict[str, Any]]:
    """사용자 쿼리에서 특정 상품명을 추출하여 장바구니에서 해당 상품만 반환"""
    query = state.query.lower()
    cart_items = state.cart.get("items", [])
    
    # 결제 키워드 제거하여 상품명만 추출
    checkout_keywords = ["결제", "주문", "구매", "계산", "할래", "하고싶어", "할게", "하기"]
    clean_query = query
    for keyword in checkout_keywords:
        clean_query = clean_query.replace(keyword, "")
    
    clean_query = clean_query.strip()
    
    # 장바구니에 있는 상품 중에서 쿼리에 언급된 상품 찾기
    selected_items = []
    for item in cart_items:
        product_name = item['name'].lower()
        
        # 완전 일치 또는 부분 일치 확인
        if product_name in clean_query or any(word in product_name for word in clean_query.split()):
            selected_items.append(item)
    
    return selected_items

def _process_selective_checkout(state: ChatState, selected_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """선택된 상품들만 결제 처리"""
    logger.info(f"선택된 {len(selected_items)}개 상품 결제 진행")
    
    # 임시 상태 생성 (선택된 상품만 포함)
    temp_cart = {
        "items": selected_items,
        "subtotal": sum(float(item["unit_price"]) * int(item["qty"]) for item in selected_items),
        "discounts": [],
        "total": 0
    }
    _calculate_totals(temp_cart)
    
    # 임시 상태로 주문 처리
    temp_state = ChatState(
        user_id=state.user_id,
        cart=temp_cart,
        query=state.query
    )
    
    return _process_full_checkout(temp_state, selected_items)

def _process_full_checkout(state: ChatState, custom_items: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """전체 결제 처리 (기존 checkout 로직)"""

    # 1. 배송지 정보 조회
    address = _get_default_address(state)
    if "오류" in address or "없습니다" in address:
        return {"checkout": {"error": f"배송지 오류: {address}", "confirmed": False}}
    
    # 2. 주문 처리 실행 (custom_items가 있으면 선택적 주문 처리)
    if custom_items:
        order_result = _process_selective_order(state, custom_items)
    else:
        order_result = order_process(state)
    
    if order_result.get("order", {}).get("status") == "confirmed":
        # 주문 성공
        order_id = order_result["order"]["order_id"]
        total_amount = order_result["order"]["total_amount"]
        ordered_items = order_result.get("order", {}).get("items", [])

        # 10초 후 자동 배송 완료 처리 예약
        try:
            oc = order_result["order"].get("order_code")
            if not oc:
                oc = int(str(order_id).split("-")[-1])
            _schedule_auto_delivery(int(oc))
        except Exception:
            logger.warning("자동 배송 완료 예약 실패: %s", order_id)
        
        checkout_info = {
            "address": address,
            "slot": _get_default_delivery_slot(),
            "payment_method": "CARD",
            "confirmed": True,
            "order_id": order_id,
            "total_amount": total_amount,
            "created_at": datetime.now().isoformat()
        }
        
        # 선택적 결제인 경우 메시지 수정
        if custom_items:
            item_names = [item['name'] for item in custom_items]
            message = f"선택하신 상품({', '.join(item_names)})이 주문 완료되었습니다!\n\n주문번호: {order_id}\n결제금액: {total_amount:,}원\n배송지: {address}\n배송시간: {_get_default_delivery_slot()}"
        else:
            message = f"주문이 완료되었습니다!\n\n주문번호: {order_id}\n결제금액: {total_amount:,}원\n배송지: {address}\n배송시간: {_get_default_delivery_slot()}"
        
        # 장바구니 업데이트 (선택적 결제인 경우 해당 상품만 제거)
        updated_cart = _update_cart_after_selective_checkout(state, custom_items) if custom_items else {"items": [], "total": 0}
        
        return {
            "checkout": checkout_info,
            "order": order_result["order"],
            "cart": updated_cart,
            "meta": {"final_message": message}
        }
    else:
        # 주문 실패
        error_msg = order_result.get("order", {}).get("error", "알 수 없는 오류")
        return {
            "checkout": {"error": f"주문 처리 실패: {error_msg}", "confirmed": False},
            "meta": {"final_message": f"주문 처리 중 오류가 발생했습니다: {error_msg}"}
        }

def _process_selective_order(state: ChatState, selected_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """선택된 상품들만 주문 처리"""
    logger.info("선택적 상품 주문 처리 시작")
    user_id = state.user_id or 'anonymous'
    conn = get_db_connection()
    if not conn:
        return {"order": {"status": "failed", "error": "DB 연결 실패"}}

    cursor = conn.cursor()
    try:
        conn.start_transaction()
        
        # 1. order_tbl에 주문 추가
        order_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        total_price = sum(float(item['unit_price']) * int(item['qty']) for item in selected_items)
        cursor.execute(
            "INSERT INTO order_tbl (user_id, order_date, total_price, order_status) VALUES (%s, %s, %s, %s)",
            (user_id, order_date, total_price, 'confirmed')
        )
        order_code = cursor.lastrowid
        
        # 2. order_detail_tbl에 주문 상세 추가
        for item in selected_items:
            cursor.execute(
                "INSERT INTO order_detail_tbl (order_code, product, quantity, price) VALUES (%s, %s, %s, %s)",
                (order_code, item['name'], item['qty'], float(item['unit_price']) * int(item['qty']))
            )
        
        # 3. stock_tbl 재고 차감
        _update_inventory(cursor, selected_items)
        
        # 4. cart_tbl에서 선택된 상품들만 제거
        for item in selected_items:
            cursor.execute("DELETE FROM cart_tbl WHERE user_id = %s AND product = %s", 
                          (user_id, item['name']))
        
        conn.commit()
        
        order_id = f"QK-{datetime.now().strftime('%Y%m%d')}-{order_code}"
        logger.info(f"선택적 주문 처리 완료: {order_id}")
        return {
            "order": {"order_id": order_id, "order_code": int(order_code), "status": "confirmed", "total_amount": total_price, "items": selected_items},
            "meta": {"order_message": f"선택 상품 주문이 완료되었습니다. 주문번호: {order_id}"}
        }

    except Error as e:
        conn.rollback()
        logger.error(f"선택적 주문 처리 실패: {e}")
        return {"order": {"status": "failed", "error": str(e)}}
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def _update_cart_after_selective_checkout(state: ChatState, purchased_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """선택적 결제 후 장바구니에서 구매된 상품 제거"""
    purchased_names = {item['name'] for item in purchased_items}
    remaining_items = [item for item in state.cart.get("items", []) 
                      if item['name'] not in purchased_names]
    
    # 남은 상품들로 장바구니 재계산
    benefits = _get_membership_benefits(state.user_id or 'anonymous')
    updated_cart = {"items": remaining_items, "membership": benefits.get("meta")}
    _calculate_totals(updated_cart, benefits)
    
    logger.info(f"장바구니에서 {len(purchased_items)}개 상품 제거, {len(remaining_items)}개 상품 남음")
    return updated_cart

def _get_default_address(state: ChatState) -> str:
    """DB의 userinfo_tbl에서 기본 배송지를 가져옵니다."""
    user_id = state.user_id or 'anonymous'
    conn = get_db_connection()
    if not conn: return "주소 정보를 가져올 수 없습니다."
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT address FROM userinfo_tbl WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else "등록된 주소가 없습니다."
    except Error as e:
        logger.error(f"주소 조회 실패: {e}")
        return "주소 조회 중 오류가 발생했습니다."
    finally:
        if conn and conn.is_connected():
            conn.close()

def _get_default_delivery_slot() -> str:
    """기본 배송 시간대 반환 (기존 로직 유지)"""
    return "내일 오전 (09:00-12:00)"

def order_process(state: ChatState) -> Dict[str, Any]:
    """주문 처리. DB에 주문을 기록하고 재고를 차감합니다 (Transaction 사용)"""
    logger.info("주문 처리 프로세스 시작")
    user_id = state.user_id or 'anonymous'
    conn = get_db_connection()
    if not conn:
        return {"order": {"status": "failed", "error": "DB 연결 실패"}}

    cursor = conn.cursor()
    try:
        conn.start_transaction()
        
        # 1. order_tbl에 주문 추가
        order_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        total_price = state.cart.get("total", 0)
        cursor.execute(
            "INSERT INTO order_tbl (user_id, order_date, total_price, order_status) VALUES (%s, %s, %s, %s)",
            (user_id, order_date, total_price, 'confirmed')
        )
        order_code = cursor.lastrowid
        
        # 2. order_detail_tbl에 주문 상세 추가
        order_items = state.cart.get("items", [])
        for item in order_items:
            cursor.execute(
                "INSERT INTO order_detail_tbl (order_code, product, quantity, price) VALUES (%s, %s, %s, %s)",
                (order_code, item['name'], item['qty'], float(item['unit_price']) * int(item['qty']))
            )
        
        # 3. stock_tbl 재고 차감
        _update_inventory(cursor, order_items)
        
        # 4. cart_tbl에서 장바구니 비우기
        cursor.execute("DELETE FROM cart_tbl WHERE user_id = %s", (user_id,))
        
        conn.commit()
        
        order_id = f"QK-{datetime.now().strftime('%Y%m%d')}-{order_code}"
        logger.info(f"주문 처리 완료: {order_id}")
        return {
            "order": {"order_id": order_id, "order_code": int(order_code), "status": "confirmed", "total_amount": total_price},
            "meta": {"order_message": f"주문이 완료되었습니다. 주문번호: {order_id}"}
        }

    except Error as e:
        conn.rollback()
        logger.error(f"주문 처리 실패: {e}")
        return {"order": {"status": "failed", "error": str(e)}}
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def _update_inventory(cursor, items: List[Dict[str, Any]]) -> None:
    """DB의 stock_tbl 재고를 업데이트합니다."""
    for item in items:
        product_name = item["name"]
        quantity = int(item["qty"])
        # 재고가 음수가 되지 않도록 GREATEST(0, ...) 사용
        sql = "UPDATE stock_tbl SET stock = GREATEST(0, stock - %s) WHERE product = %s"
        cursor.execute(sql, (quantity, product_name))
        logger.info(f"재고 업데이트: {product_name} -{quantity}")

def remove_from_cart(state: ChatState) -> Dict[str, Any]:
    """DB의 cart_tbl에서 특정 상품을 제거하거나 수량을 1 감소시킵니다."""
    logger.info("장바구니 수정/제거 프로세스 시작")
    user_id = state.user_id or 'anonymous'
    query = state.query.lower()
    
    conn = get_db_connection()
    if not conn:
        return {"meta": {"cart_error": "DB 연결 실패"}}

    try:
        with conn.cursor(dictionary=True) as cursor:
            # 현재 사용자의 장바구니에 있는 상품 목록을 먼저 가져옵니다.
            cursor.execute("SELECT product FROM cart_tbl WHERE user_id = %s", (user_id,))
            cart_products = [row['product'] for row in cursor.fetchall()]

            product_to_modify = None
            # 장바구니에 있는 상품 이름이 사용자 쿼리에 포함되어 있는지 확인합니다.
            for product in cart_products:
                if product.lower() in query:
                    product_to_modify = product
                    break
            
            if not product_to_modify:
                return {"meta": {"cart_message": "장바구니에 없는 상품이거나, 상품 이름을 인식할 수 없습니다."}}

            # "빼줘", "제거", "삭제", "취소" 등 전체 삭제 키워드가 있는지 확인
            remove_keywords = ["빼줘", "제거", "삭제", "취소"]
            if any(keyword in query for keyword in remove_keywords):
                # 전체 삭제 로직
                sql = "DELETE FROM cart_tbl WHERE user_id = %s AND product = %s"
                cursor.execute(sql, (user_id, product_to_modify))
                message = f"'{product_to_modify}' 상품을 장바구니에서 뺐습니다."
            else:
                # 수량 1 감소 로직 (UPDATE)
                # 현재 수량이 1보다 클 때만 감소, 1이면 삭제
                sql = """
                    UPDATE cart_tbl 
                    SET quantity = quantity - 1, total_price = unit_price * (quantity - 1)
                    WHERE user_id = %s AND product = %s AND quantity > 1
                """
                cursor.execute(sql, (user_id, product_to_modify))
                
                if cursor.rowcount == 0:  # 수량이 1이어서 업데이트가 안 된 경우 -> 삭제
                    sql_delete = "DELETE FROM cart_tbl WHERE user_id = %s AND product = %s"
                    cursor.execute(sql_delete, (user_id, product_to_modify))
                
                message = f"'{product_to_modify}' 상품의 수량을 1개 줄였습니다."

            conn.commit()
            logger.info(f"'{product_to_modify}' 상품이 수정/제거 되었습니다.")

    except Error as e:
        conn.rollback()
        logger.error(f"장바구니 수정/제거 실패: {e}")
        return {"meta": {"cart_error": f"오류 발생: {e}"}}
    finally:
        if conn and conn.is_connected():
            conn.close()

    # 모든 작업 후, 최종 장바구니 상태를 다시 조회하여 반환
    final_cart_state = view_cart(state)
    return {
        "cart": final_cart_state.get('cart'),
        "meta": {"cart_message": message}
    }

def bulk_add_to_cart(user_id: str, products: List[dict]) -> Dict[str, Any]:
    """여러 상품을 한 번에 장바구니에 추가하는 함수"""
    logger.info(f"일괄 장바구니 추가: User '{user_id}', Products count: {len(products)}")
    
    conn = get_db_connection()
    if not conn:
        return {"error": "DB 연결 실패"}

    added_count = 0
    failed_products = []
    
    try:
        with conn.cursor(dictionary=True) as cursor:
            for product in products:
                product_name = product.get("name")
                if not product_name:
                    continue
                    
                try:
                    # 상품 정보 및 재고 조회
                    cursor.execute("""
                        SELECT p.unit_price, s.stock 
                        FROM product_tbl p 
                        JOIN stock_tbl s ON p.product = s.product 
                        WHERE p.product = %s
                    """, (product_name,))
                    product_info = cursor.fetchone()

                    if not product_info:
                        failed_products.append(f"{product_name} (상품 없음)")
                        continue

                    price = float(product_info['unit_price'])
                    stock = int(product_info['stock'])
                    
                    # 현재 장바구니 수량 확인
                    cursor.execute("SELECT quantity FROM cart_tbl WHERE user_id = %s AND product = %s", (user_id, product_name))
                    cart_item = cursor.fetchone()
                    current_qty_in_cart = int(cart_item['quantity']) if cart_item else 0

                    # 재고 검증 (기본 1개씩 추가)
                    quantity_to_add = 1
                    if stock < current_qty_in_cart + quantity_to_add:
                        failed_products.append(f"{product_name} (재고 부족)")
                        continue

                    # 장바구니에 추가
                    new_quantity = current_qty_in_cart + quantity_to_add
                    sql = """
                        INSERT INTO cart_tbl (user_id, product, unit_price, quantity, total_price)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE quantity = %s, total_price = %s
                    """
                    total_price = price * new_quantity
                    cursor.execute(sql, (user_id, product_name, price, new_quantity, total_price, new_quantity, total_price))
                    added_count += 1
                    
                except Error as e:
                    logger.error(f"개별 상품 추가 실패 {product_name}: {e}")
                    failed_products.append(f"{product_name} (오류)")
                    continue
            
            conn.commit()
            
        # 최종 장바구니 상태 조회
        temp_state = ChatState(user_id=user_id)
        final_cart_state = view_cart(temp_state)
        
        result = {
            "cart": final_cart_state.get('cart'),
            "added_count": added_count,
            "message": f"{added_count}개 상품이 장바구니에 담겼습니다."
        }
        
        if failed_products:
            result["failed_products"] = failed_products
            result["message"] += f" (실패: {len(failed_products)}개)"
            
        return result
        
    except Error as e:
        conn.rollback()
        logger.error(f"일괄 장바구니 추가 실패: {e}")
        return {"error": f"일괄 담기 중 오류가 발생했습니다: {str(e)}"}
    finally:
        if conn and conn.is_connected():
            conn.close()

def _schedule_auto_delivery(order_code: int) -> None:
    """결제 완료 후 10초 뒤 주문 상태를 delivered로 변경"""
    import threading
    def _mark():
        conn = get_db_connection()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE order_tbl SET order_status='delivered' WHERE order_code=%s", (order_code,))
                conn.commit()
                logger.info(f"주문 {order_code} 배송 완료 처리")
        except Error as e:
            logger.error(f"배송 완료 자동 처리 실패: {e}")
        finally:
            if conn and conn.is_connected():
                conn.close()
    threading.Timer(10.0, _mark).start()
