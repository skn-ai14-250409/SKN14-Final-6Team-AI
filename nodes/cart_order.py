import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from mysql.connector import Error

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_interfaces import ChatState
from utils.chat_history import summarize_cart_actions_with_history, summarize_product_search_with_history 
from utils.db import get_db_connection

logger = logging.getLogger("D_CART_ORDER_DB")

def view_cart(state: ChatState) -> Dict[str, Any]:
    """DB에서 현재 사용자의 장바구니 정보를 조회합니다."""
    logger.info(f"장바구니 조회 프로세스 시작: User '{state.user_id}'")
    user_id = state.user_id or 'anonymous'
    conn = get_db_connection()
    if not conn:
        return {"meta": {"cart_error": "DB 연결 실패"}}
    
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT product as name, product as sku, quantity as qty, unit_price "
                "FROM cart_tbl WHERE user_id = %s",
                (user_id,)
            )
            cart_items = cursor.fetchall()

        benefits = _get_membership_benefits(user_id)
        current_cart = {"items": cart_items, "membership": benefits.get("meta")}
        _calculate_totals(current_cart, benefits)


        def _fmt_price(v: float) -> str:
            try:
                return f"{int(round(float(v))):,}"
            except Exception:
                try:
                    return f"{int(v):,}"
                except Exception:
                    return str(v)

        items = current_cart.get("items") or []
        if not items:
            cart_message = "현재 장바구니가 비어있습니다."
        else:
            lines = ["🛒 현재 장바구니 내용:\n"]
            for i, it in enumerate(items, 1):
                name = it.get("name") or it.get("sku") or "상품"
                qty = int(it.get("qty") or it.get("quantity") or 0)
                unit = float(it.get("unit_price") or 0)
                lines.append(f"{i}. {name}")
                lines.append(f"   수량: {qty}")
                lines.append(f"   가격: {_fmt_price(unit)}원")
                lines.append(f"   소계: {_fmt_price(unit*qty)}원\n")

            discount_amount = sum(int(d.get('amount', 0)) for d in (current_cart.get('discounts') or []))
            lines.append(f"💰 총 상품금액: {_fmt_price(current_cart.get('subtotal') or 0)}원")
            if discount_amount > 0:
                lines.append(f"💸 할인금액: -{_fmt_price(discount_amount)}원")
            lines.append(f"💳 최종 결제금액: {_fmt_price(current_cart.get('total') or 0)}원")
            cart_message = "\n".join(lines)

        target = (state.route or {}).get("target") if hasattr(state, "route") else None
        if target == "cart_view":
            return {"cart": current_cart, "meta": {"final_message": cart_message}}
        else:
            return {"cart": current_cart}
    
        
    except Error as e:
        logger.error(f"장바구니 조회 실패: {e}")
        return {"meta": {"cart_error": str(e)}}
    finally:
        if conn and conn.is_connected():
            conn.close()

def update_cart_item(user_id: str, product_name: str, quantity: int) -> Dict[str, Any]:
    """장바구니 아이템 수량을 특정 값으로 직접 설정하거나 삭제하는 전용 함수"""
    logger.info(f"장바구니 직접 수정: User '{user_id}', Product '{product_name}', Quantity '{quantity}'")
    
    conn = get_db_connection()
    if not conn:
        return {"error": "DB 연결 실패"}

    try:
        with conn.cursor() as cursor:
            if quantity > 0:

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
            else:  
                sql = "DELETE FROM cart_tbl WHERE user_id = %s AND product = %s"
                cursor.execute(sql, (user_id, product_name))
                logger.info(f"'{product_name}' 상품을 DB에서 삭제.")
            conn.commit()
            
    except Error as e:
        conn.rollback()
        logger.error(f"장바구니 직접 수정 실패: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()

    temp_state = ChatState(user_id=user_id)
    return view_cart(temp_state)

def _get_cart_items_for_products(user_id: str, product_names: List[str]) -> List[Dict[str, Any]]:
    """사용자 장바구니에서 지정한 상품들만 name, qty, unit_price를 가져옵니다."""
    if not product_names:
        return []
    conn = get_db_connection()
    if not conn:
        return []
    try:
        placeholders = ",".join(["%s"] * len(product_names))
        sql = (
            f"SELECT product AS name, quantity AS qty, unit_price "
            f"FROM cart_tbl WHERE user_id = %s AND product IN ({placeholders})"
        )
        params = [user_id] + product_names
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall() or []
            items = []
            for r in rows:
                try:
                    items.append({
                        "name": r.get("name"),
                        "qty": int(r.get("qty") or 0),
                        "unit_price": float(r.get("unit_price") or 0.0)
                    })
                except Exception:
                    continue
            return [i for i in items if i["qty"] > 0]
    except Error:
        return []
    finally:
        if conn and conn.is_connected():
            conn.close()
    
def _get_products_by_names(product_names: List[str]) -> List[Dict[str, Any]]:
    """상품명 목록으로 product_tbl 정보를 조회합니다.""" 
    targets = [name for name in product_names if name]
    if not targets:
        return []

    conn = get_db_connection()
    if not conn:
        return []

    try:
        placeholders = ",".join(["%s"] * len(targets))
        sql = (
            f"SELECT p.product, p.unit_price, p.origin, p.organic, c.category_id "
            f"FROM product_tbl p "
            f"LEFT JOIN category_tbl c ON p.item = c.item "
            f"WHERE p.product IN ({placeholders})"
        )
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql, targets)
            rows = cursor.fetchall() or []
            resolved = []
            for row in rows:
                resolved.append({
                    "name": row.get("product"),
                    "price": float(row.get("unit_price") or 0),
                    "origin": row.get("origin"),
                    "organic": (row.get("organic") == 'Y'),
                    "category_id": row.get("category_id")
                })
            return resolved
    except Error as e:
        logger.warning(f"상품 조회 실패: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            conn.close()

def cart_manage(state: ChatState) -> Dict[str, Any]:
    """
    장바구니 관리(멱등). DB의 cart_tbl을 기준으로 동작합니다.
    - 검색 후보가 있을 경우 첫 번째 후보를 담습니다.
    - ✅ 담기 성공 시 meta['cart']에 last_action/added_items를 채워 app.py가
      "담았습니다" 문구를 만들 수 있게 합니다.
    """
    logger.info("장바구니 관리 프로세스 시작")
    user_id = state.user_id or 'anonymous'
    
    added_meta = None  

    candidates = state.search.get("candidates", [])

    history_context = summarize_cart_actions_with_history(state)  
    if not candidates:
        history_items = history_context.get("last_cart_snapshot", {}).get("last_added_items") or []  
        if not history_items:
            history_items = history_context.get("selected_products") or []

        candidate_names: List[str] = []
        for hint in history_items:
            if isinstance(hint, dict):
                candidate_names.append(hint.get("name") or hint.get("product"))
            else:
                candidate_names.append(hint)

        if not candidate_names:
            product_history = summarize_product_search_with_history(state, state.query or "") 
            fallback_product = product_history.get("last_slots", {}).get("product") or product_history.get("last_slots", {}).get("item")
            if fallback_product:
                candidate_names.append(fallback_product)

        resolved = _get_products_by_names(candidate_names) 
        if resolved:
            candidates = resolved
            state.search["candidates"] = resolved 

    if candidates:

        candidate = candidates[0]
        quantity = int(state.slots.get("quantity", 1))
        result = _add_to_cart(user_id, candidate, quantity)

        if not result["success"]:
            current_cart_state = view_cart(state)
            return {
                "cart": current_cart_state.get('cart'),
                "meta": {"cart_message": result["message"]}
            }
        else:
            
            added_meta = {
                "cart": {
                    "last_action": "add",
                    "added_items": [{
                        "name": candidate.get("name") or candidate.get("sku") or "상품",
                        "quantity": quantity
                    }]},
                "intent": "cart_add"
            }
    else:
        logger.info("추가할 상품 후보를 찾지 못했습니다.")

    final_cart_state = view_cart(state)
    item_count = len(final_cart_state.get('cart', {}).get('items', []))

    meta = {
        "cart_message": f"장바구니에 {item_count}개 상품이 담겨있습니다.",
        "last_action": "cart_updated"
    }
    if added_meta:
        meta.update(added_meta) 

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
            
            cursor.execute("SELECT quantity FROM cart_tbl WHERE user_id = %s AND product = %s", (user_id, product_name))
            cart_item = cursor.fetchone()
            current_qty_in_cart = int(cart_item['quantity']) if cart_item else 0

            if stock < current_qty_in_cart + quantity:
                return {"success": False, "message": f"{product_name}의 재고가 부족합니다. (요청: {quantity}, 현재고: {stock})"}

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
    """
    장바구니 합계 계산 (DB에서 로드된 데이터를 기반으로)
    - 무료배송 기준을 "할인 후 금액"으로 적용 (주문처리 스냅샷과 일치)
    - 멤버십 할인액은 int()로 계산해 스냅샷과 동일한 반올림 규칙 유지
    """
    subtotal = sum(float(item["unit_price"]) * int(item["qty"]) for item in cart.get("items", []))
    cart["subtotal"] = subtotal
    discounts: List[Dict[str, Any]] = []
    rate = 0.0
    free_ship_threshold = 30000.0
    if benefits:
        rate = float(benefits.get("discount_rate", 0.0) or 0.0)
        free_ship_threshold = float(benefits.get("free_shipping_threshold", 30000) or 30000)

    membership_discount = int(subtotal * rate)
    if membership_discount > 0:
        discounts.append({
            "type": "membership_discount",
            "amount": membership_discount,
            "description": f"멤버십 {int(rate*100)}% 할인"
        })

    shipping_fee = 3000
    cart["shipping_fee"] = shipping_fee

    effective_subtotal = subtotal - membership_discount
    if effective_subtotal >= free_ship_threshold:
        discounts.append({"type": "free_shipping", "amount": 3000, "description": "무료배송"})

    cart["discounts"] = discounts
    total_discount = sum(d["amount"] for d in discounts)
    cart["total"] = max(0, subtotal + shipping_fee - total_discount)

def _get_membership_benefits(user_id: str) -> Dict[str, Any]:
    conn = get_db_connection()

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
            name = str(row.get("membership_name") or "basic").lower()
           
            rate = float(row.get("discount_rate") or 0.0)
            thr = float(row.get("free_shipping_threshold"))
            
            return {
                "discount_rate": rate,
                "free_shipping_threshold": thr,
                "meta": {
                    "membership_name": name,
                    "discount_rate": rate,
                    "free_shipping_threshold": thr,
                },
            }
    except Error:
        pass
    finally:
        if conn and conn.is_connected():
            conn.close()

def checkout(state: ChatState) -> Dict[str, Any]:
    """체크아웃 및 주문 처리 (개선된 버전 - 특정 상품 선택 지원)"""
    logger.info("체크아웃 및 주문 처리 시작")
    user_id = state.user_id or 'anonymous'

    selected_names = (state.checkout or {}).get("selected_names") or []
    if selected_names:
        selected_items = _get_cart_items_for_products(user_id, list(dict.fromkeys(selected_names)))
        if not selected_items:
            return {"checkout": {"error": "선택한 상품이 장바구니에 없습니다.", "confirmed": False}}
        logger.info(f"특정 상품 결제 요청(명시): {[item['name'] for item in selected_items]}")
        return _process_selective_checkout(state, selected_items)

    if not state.cart.get("items"):
        return {"checkout": {"error": "장바구니가 비어있습니다.", "confirmed": False}}
    selected_items = _extract_selected_items_for_checkout(state)
    if selected_items:
        logger.info(f"특정 상품 결제 요청: {[item['name'] for item in selected_items]}")
        return _process_selective_checkout(state, selected_items)
    logger.info("전체 장바구니 결제 진행")
    return _process_full_checkout(state)

def _extract_selected_items_for_checkout(state: ChatState) -> List[Dict[str, Any]]:
    """사용자 쿼리에서 특정 상품명을 추출하여 장바구니에서 해당 상품만 반환"""
    query = (state.query or "").lower()
    cart_items = state.cart.get("items", [])
    
    checkout_keywords = ["결제", "주문", "구매", "계산", "할래", "하고싶어", "할게", "하기"]
    clean_query = query
    for keyword in checkout_keywords:
        clean_query = clean_query.replace(keyword, "")
    clean_query = clean_query.strip()
    
    selected_items = []
    for item in cart_items:
        product_name = (item['name'] or "").lower()

        if product_name in clean_query or any(word in product_name for word in clean_query.split()):
            selected_items.append(item)
    
    return selected_items

def _process_selective_checkout(state: ChatState, selected_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """선택된 상품들만 결제 처리"""
    logger.info(f"선택된 {len(selected_items)}개 상품 결제 진행")
    
    temp_cart = {
        "items": selected_items,
        "subtotal": sum(float(item["unit_price"]) * int(item["qty"]) for item in selected_items),
        "discounts": [],
        "total": 0
    }
    _calculate_totals(temp_cart)
    
    temp_state = ChatState(
        user_id=state.user_id,
        cart=temp_cart,
        query=state.query
    )
    
    return _process_full_checkout(temp_state, selected_items)

def _process_full_checkout(state: ChatState, custom_items: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """전체 결제 처리"""

    address = _get_default_address(state)
    if "오류" in address or "없습니다" in address:
        return {"checkout": {"error": f"배송지 오류: {address}", "confirmed": False}}
    
    if custom_items:
        order_result = _process_selective_order(state, custom_items)
    else:
        order_result = order_process(state)
    
    if order_result.get("order", {}).get("status") == "confirmed":

        order_id = order_result["order"]["order_id"]
        total_amount = order_result["order"]["total_amount"]
        ordered_items = order_result.get("order", {}).get("items", [])

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
        
        if custom_items:
            item_names = [item['name'] for item in custom_items]
            message = (
                f"선택하신 상품({', '.join(item_names)})이 주문 완료되었습니다!\n\n"
                f"주문번호: {order_id}\n결제금액: {total_amount:,}원\n배송지: {address}\n배송시간: {_get_default_delivery_slot()}"
            )
        else:
            message = (
                f"주문이 완료되었습니다!\n\n주문번호: {order_id}\n결제금액: {total_amount:,}원\n"
                f"배송지: {address}\n배송시간: {_get_default_delivery_slot()}"
            )
        
        updated_cart = _update_cart_after_selective_checkout(state, custom_items) if custom_items else {"items": [], "total": 0}
        
        return {
            "checkout": checkout_info,
            "order": order_result["order"],
            "cart": updated_cart,
            "meta": {"final_message": message}
        }
    else:

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
        
        order_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        subtotal = sum(float(item['unit_price']) * int(item['qty']) for item in selected_items)

        cursor.execute("""
            SELECT 
                COALESCE(m.membership_name, 'basic')                AS tier_name,
                COALESCE(m.discount_rate, 0)                        AS discount_rate,
                COALESCE(m.free_shipping_threshold, 30000)          AS free_ship_threshold
            FROM user_detail_tbl ud
            LEFT JOIN membership_tbl m
                ON m.membership_name = ud.membership
            WHERE ud.user_id = %s
            LIMIT 1
        """, (user_id,))
        row = cursor.fetchone()

        if row:
            membership_tier, discount_rate, free_ship_threshold = row
        else:
            membership_tier, discount_rate, free_ship_threshold = ('basic', 0.0, 30000)

        discount_amount = int(subtotal * float(discount_rate))           
        BASE_SHIPPING_FEE = 3000
        shipping_fee = 0 if (subtotal - discount_amount) >= float(free_ship_threshold) else BASE_SHIPPING_FEE
        total_price = int(subtotal - discount_amount + shipping_fee)      

        cursor.execute(
            """
            INSERT INTO order_tbl (
                user_id, order_date,
                total_price, order_status, subtotal, discount_amount, shipping_fee, membership_tier_at_checkout
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, order_date, total_price, 'confirmed', subtotal, discount_amount, shipping_fee, membership_tier)
        )
        order_code = cursor.lastrowid

        for item in selected_items:
            cursor.execute(
                "INSERT INTO order_detail_tbl (order_code, product, quantity, price) VALUES (%s, %s, %s, %s)",
                (order_code, item['name'], item['qty'], float(item['unit_price']) * int(item['qty']))
            )
        
        _update_inventory(cursor, selected_items)
        
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
    """선택 결제 후 남은 장바구니를 DB에서 재조회"""  
    refreshed = view_cart(ChatState(user_id=state.user_id))
    cart_payload = refreshed.get("cart") if isinstance(refreshed, dict) else None
    if cart_payload is None:
        logger.warning("선택 결제 후 장바구니를 재조회하지 못했습니다. 빈 장바구니 반환")
        return {"items": [], "subtotal": 0, "discounts": [], "total": 0}

    logger.info(
        "장바구니 재조회 완료: 구매 %d개, 잔여 %d개",
        len(purchased_items),
        len(cart_payload.get("items", []))
    )
    return cart_payload

def _get_default_address(state: ChatState) -> str:
    """DB의 userinfo_tbl에서 기본 배송지를 가져옵니다."""
    user_id = state.user_id or 'anonymous'
    conn = get_db_connection()
    if not conn:
        return "주소 정보를 가져올 수 없습니다."
    
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
    """
    주문 처리. DB에 주문을 기록하고 재고를 차감합니다 (Transaction 사용)
    - FIX: subtotal은 '상품금액 합계'만 사용 (배송비/할인 미포함)
    """
    logger.info("주문 처리 프로세스 시작")
    user_id = state.user_id or 'anonymous'
    conn = get_db_connection()
    if not conn:
        return {"order": {"status": "failed", "error": "DB 연결 실패"}}

    cursor = conn.cursor()
    try:
        conn.start_transaction()
        
        order_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        subtotal = state.cart.get("subtotal")
        if subtotal is None:
            subtotal = sum(float(i["unit_price"]) * int(i["qty"]) for i in state.cart.get("items", []))

        cursor.execute("""
            SELECT 
                COALESCE(m.membership_name, 'basic')                AS tier_name,
                COALESCE(m.discount_rate, 0)                        AS discount_rate,
                COALESCE(m.free_shipping_threshold, 30000)          AS free_ship_threshold
            FROM user_detail_tbl ud
            LEFT JOIN membership_tbl m
                ON m.membership_name = ud.membership
            WHERE ud.user_id = %s
            LIMIT 1
        """, (user_id,))
        row = cursor.fetchone()

        if row:
            membership_tier, discount_rate, free_ship_threshold = row
        else:
            membership_tier, discount_rate, free_ship_threshold = ('basic', 0.0, 30000)

        discount_amount = int(subtotal * float(discount_rate))          
        BASE_SHIPPING_FEE = 3000
        shipping_fee = 0 if (subtotal - discount_amount) >= float(free_ship_threshold) else BASE_SHIPPING_FEE
        total_price = int(subtotal - discount_amount + shipping_fee)   

        cursor.execute(
            """
            INSERT INTO order_tbl (
                user_id, order_date,
                total_price, order_status, subtotal, discount_amount, shipping_fee, membership_tier_at_checkout
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, order_date, total_price, 'confirmed', subtotal, discount_amount, shipping_fee, membership_tier)
        )
        order_code = cursor.lastrowid
        
        order_items = state.cart.get("items", [])
        for item in order_items:
            cursor.execute(
                "INSERT INTO order_detail_tbl (order_code, product, quantity, price) VALUES (%s, %s, %s, %s)",
                (order_code, item['name'], item['qty'], float(item['unit_price']) * int(item['qty']))
            )
        
        _update_inventory(cursor, order_items)
        
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

        sql = "UPDATE stock_tbl SET stock = GREATEST(0, stock - %s) WHERE product = %s"
        cursor.execute(sql, (quantity, product_name))
        logger.info(f"재고 업데이트: {product_name} -{quantity}")

def remove_from_cart(state: ChatState) -> Dict[str, Any]:
    """DB의 cart_tbl에서 특정 상품을 제거하거나 수량을 1 감소시킵니다."""
    logger.info("장바구니 수정/제거 프로세스 시작")
    user_id = state.user_id or 'anonymous'
    query = (state.query or "").lower()

    selected_names = (state.checkout or {}).get("selected_names") or []
    if selected_names:
        conn = get_db_connection()
        if not conn:
            return {"meta": {"cart_error": "DB 연결 실패"}}
        try:
            with conn.cursor() as cursor:
                if selected_names:
                    placeholders = ",".join(["%s"] * len(selected_names))
                    sql_delete = (
                        f"DELETE FROM cart_tbl WHERE user_id = %s AND product IN ({placeholders})"
                    )
                    params = [user_id] + selected_names
                    cursor.execute(sql_delete, params)
                    conn.commit()
                    message = f"선택한 {len(selected_names)}개 상품을 장바구니에서 제거했습니다."
        except Error as e:
            if conn:
                conn.rollback()
            logger.error(f"선택 제거 실패: {e}")
            return {"meta": {"cart_error": f"오류 발생: {e}"}}
        finally:
            if conn and conn.is_connected():
                conn.close()

        final_cart_state = view_cart(state)
        return {
            "cart": final_cart_state.get('cart'),
            "meta": {"cart_message": message}
        }
    
    conn = get_db_connection()
    if not conn:
        return {"meta": {"cart_error": "DB 연결 실패"}}

    try:
        with conn.cursor(dictionary=True) as cursor:

            cursor.execute("SELECT product FROM cart_tbl WHERE user_id = %s", (user_id,))
            cart_products = [row['product'] for row in cursor.fetchall()]

            product_to_modify = None
 
            for product in cart_products:
                if (product or "").lower() in query:
                    product_to_modify = product
                    break
            
            if not product_to_modify:
                history_context = summarize_cart_actions_with_history(state)  
                snapshot_items = history_context.get("last_cart_snapshot", {}).get("items") or [] 
                if snapshot_items:
                    last_item = snapshot_items[-1]
                    if isinstance(last_item, dict):
                        product_to_modify = last_item.get("name") or last_item.get("product")
                if not product_to_modify:
                    selected_history = history_context.get("selected_products") or []  
                    if selected_history:
                        last_selected = selected_history[-1]
                        if isinstance(last_selected, dict):
                            product_to_modify = last_selected.get("name")
                        else:
                            product_to_modify = last_selected

            if not product_to_modify:
                return {"meta": {"cart_message": "장바구니에 없는 상품이거나, 상품 이름을 인식할 수 없습니다."}}

            remove_keywords = ["빼줘", "제거", "삭제", "취소"]
            if any(keyword in query for keyword in remove_keywords):

                sql = "DELETE FROM cart_tbl WHERE user_id = %s AND product = %s"
                cursor.execute(sql, (user_id, product_to_modify))
                message = f"'{product_to_modify}' 상품을 장바구니에서 뺐습니다."
            else:
               
                sql = """
                    UPDATE cart_tbl 
                    SET quantity = quantity - 1, total_price = unit_price * (quantity - 1)
                    WHERE user_id = %s AND product = %s AND quantity > 1
                """
                cursor.execute(sql, (user_id, product_to_modify))
                
                if cursor.rowcount == 0: 
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
                    
                    cursor.execute("SELECT quantity FROM cart_tbl WHERE user_id = %s AND product = %s", (user_id, product_name))
                    cart_item = cursor.fetchone()
                    current_qty_in_cart = int(cart_item['quantity']) if cart_item else 0

                    quantity_to_add = 1
                    if stock < current_qty_in_cart + quantity_to_add:
                        failed_products.append(f"{product_name} (재고 부족)")
                        continue

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
