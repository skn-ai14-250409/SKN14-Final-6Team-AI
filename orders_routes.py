from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import mysql.connector
from mysql.connector import Error
import os


class HistoryRequest(BaseModel):
    user_id: str
    limit: Optional[int] = 20


orders_router = APIRouter(prefix="/api/orders", tags=["orders"])


def get_db_connection():
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            user=os.getenv("DB_USER", "qook_user"),
            password=os.getenv("DB_PASSWORD", "qook_pass"),
            database=os.getenv("DB_NAME", "qook_chatbot"),
            port=int(os.getenv("DB_PORT", "3306")),
        )
    except Error:
        return None


@orders_router.post("/history")
async def get_order_history(req: HistoryRequest) -> Dict[str, Any]:
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB 연결 실패")
    try:
        with conn.cursor(dictionary=True) as cur:
            sql = (
                "SELECT order_code, user_id, order_date, total_price, order_status "
                "FROM order_tbl "
                "WHERE user_id=%s AND DATE(order_date) >= DATE_SUB(CURDATE(), INTERVAL 5 DAY) "
                "ORDER BY order_date DESC LIMIT %s"
            )
            cur.execute(sql, (req.user_id, int(req.limit or 20)))
            rows = cur.fetchall() or []
            # 정규화
            items: List[Dict[str, Any]] = []
            for r in rows:
                items.append(
                    {
                        "order_code": str(r.get("order_code")),
                        "order_date": str(r.get("order_date")),
                        "order_status": r.get("order_status") or "",
                        "total_price": r.get("total_price"),
                    }
                )
            return {"orders": items, "total": len(items)}
    except Error as e:
        raise HTTPException(status_code=500, detail=f"주문 내역 조회 실패: {e}")
    finally:
        try:
            if conn and conn.is_connected():
                conn.close()
        except Exception:
            pass
