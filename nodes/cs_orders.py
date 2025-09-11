from typing import Dict, Any, List, Optional
from datetime import datetime
from mysql.connector import Error
from .cs_common import get_db_connection, _to_int, _to_float, logger


def get_user_orders_today(user_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor(dictionary=True) as cursor:
            sql = """
            SELECT o.order_code, o.user_id, o.order_date, o.total_price, o.order_status
            FROM order_tbl o
            WHERE o.user_id = %s
              AND o.order_status IN ('completed','delivered')
              AND DATE(o.order_date) = CURDATE()
            ORDER BY o.order_date DESC
            """
            cursor.execute(sql, (user_id,))
            return cursor.fetchall()
    except Error as e:
        logger.error(f"오늘 주문내역 조회 실패: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            conn.close()

def get_user_orders_delivered_last_5_days(user_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor(dictionary=True) as cursor:
            sql = """
            SELECT o.order_code, o.user_id, o.order_date, o.total_price, o.order_status
            FROM order_tbl o
            WHERE o.user_id = %s
              AND o.order_status = 'delivered'
              AND o.order_date > (CURDATE() - INTERVAL 5 DAY)   -- 시작: 오늘-6일 00:00
              AND o.order_date <  (CURDATE() + INTERVAL 1 DAY)   -- 끝: 내일 00:00 (오늘 포함)
            ORDER BY o.order_date DESC
            """
            cursor.execute(sql, (user_id,))
            return cursor.fetchall()
    except Error as e:
        logger.error(f"배송 내역 조회 실패: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            conn.close()


def _get_order_products(order_code: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor(dictionary=True) as cursor:
            sql = """
            SELECT od.product, od.quantity, od.price
            FROM order_detail_tbl od
            WHERE od.order_code = %s
            ORDER BY od.product
            """
            cursor.execute(sql, (order_code,))
            return cursor.fetchall()
    except Error as e:
        logger.error(f"주문 상품 조회 실패: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            conn.close()


def get_order_details(order_code: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        with conn.cursor(dictionary=True) as cursor:
            if user_id:
                cursor.execute(
                    """
                    SELECT order_code, user_id, order_date, total_price, order_status
                    FROM order_tbl
                    WHERE order_code = %s AND user_id = %s
                    """,
                    (order_code, user_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT order_code, user_id, order_date, total_price, order_status
                    FROM order_tbl
                    WHERE order_code = %s
                    """,
                    (order_code,),
                )
            order_row = cursor.fetchone()
        if not order_row:
            return {}
        raw_items = _get_order_products(order_code)
        items: List[Dict[str, Any]] = []
        for r in raw_items:
            items.append({
                "product": r.get("product") or r.get("name") or "",
                "quantity": _to_int(r.get("quantity")),
                "price": _to_float(r.get("price")),
            })
        subtotal = sum(_to_float(it["price"]) * _to_int(it["quantity"]) for it in items)
        discount = 0.0
        total = _to_float(order_row.get("total_price")) or subtotal
        return {
            "order_code": str(order_row["order_code"]),
            "order_date": (order_row["order_date"].strftime("%Y-%m-%d %H:%M:%S")
                           if isinstance(order_row["order_date"], datetime)
                           else str(order_row["order_date"])),
            "order_status": order_row.get("order_status") or "",
            "total_price": total,
            "subtotal": subtotal,
            "discount": discount,
            "total": total,
            "items": items,
        }
    except Error as e:
        logger.error(f"주문 상세 조회 실패: {e}")
        return {}
    finally:
        try:
            if conn and conn.is_connected():
                conn.close()
        except Exception:
            pass

