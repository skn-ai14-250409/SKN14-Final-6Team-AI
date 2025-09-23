import os
import uuid
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import mysql.connector
from mysql.connector import Error

logger = logging.getLogger("DB_AUDIT")


def _conn():
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            user=os.getenv("DB_USER", "qook_user"),
            password=os.getenv("DB_PASSWORD", "qook_pass"),
            database=os.getenv("DB_NAME", "qook_chatbot"),
            port=int(os.getenv("DB_PORT", "3306")),
        )
    except Error as e:
        logger.warning(f"DB 연결 실패(DB_AUDIT): {e}")
        return None


def _short_uuid(n: int = 16) -> str:
    return uuid.uuid4().hex[:n]


def insert_user_session(user_id: str, session_id: str, expires_at: datetime, user_agent: Optional[str], ip: Optional[str]) -> None:
    conn = _conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_sessions (session_id, user_id, created_at, expires_at, is_active, user_agent, ip_address)
                VALUES (%s, %s, NOW(), %s, 1, %s, %s)
                ON DUPLICATE KEY UPDATE user_id=VALUES(user_id), expires_at=VALUES(expires_at), is_active=1, user_agent=VALUES(user_agent), ip_address=VALUES(ip_address)
                """,
                (session_id, user_id, expires_at.strftime("%Y-%m-%d %H:%M:%S"), user_agent or "", ip or ""),
            )
        conn.commit()
    except Error as e:
        logger.warning(f"insert_user_session 실패: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()


def deactivate_user_sessions(user_id: str) -> None:
    conn = _conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE user_sessions SET is_active=0 WHERE user_id=%s AND is_active=1", (user_id,))
        conn.commit()
    except Error as e:
        logger.warning(f"deactivate_user_sessions 실패: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()


def _trim_session_id(session_id: str) -> str:
    try:
        return (session_id or "")[:50]
    except Exception:
        return ""


def ensure_chat_session(user_id: str, session_id: str, status: str = "active") -> None:
    conn = _conn()
    if not conn:
        return
    try:
        sid = _trim_session_id(session_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_sessions (session_id, user_id, status, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                ON DUPLICATE KEY UPDATE user_id=VALUES(user_id), status=%s, updated_at=NOW()
                """,
                (sid, user_id, status, status),
            )
        conn.commit()
    except Error as e:
        logger.warning(f"ensure_chat_session 실패: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()

def timeout_inactive_sessions(minutes: int = 10) -> None:
    conn = _conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
      
            cur.execute(
                """
                SELECT DISTINCT user_id 
                FROM chat_sessions 
                WHERE status='active' AND updated_at < (NOW() - INTERVAL %s MINUTE)
                AND user_id IS NOT NULL
                """,
                (minutes,)
            )
            timeout_user_ids = [row[0] for row in cur.fetchall()]
            
            cur.execute(
                """
                UPDATE chat_sessions
                SET status='timeout', updated_at=NOW()
                WHERE status='active' AND updated_at < (NOW() - INTERVAL %s MINUTE)
                """,
                (minutes,)
            )
            
            for user_id in timeout_user_ids:
                cur.execute(
                    """
                    UPDATE userlog_tbl 
                    SET logout_time = NOW() 
                    WHERE user_id = %s 
                    AND logout_time IS NULL 
                    ORDER BY log_time DESC 
                    LIMIT 1
                    """,
                    (user_id,)
                )
            
            if timeout_user_ids:
                logger.info(f"세션 타임아웃 처리 완료: {len(timeout_user_ids)}명의 사용자 logout_time 업데이트")
        
        conn.commit()
    except Error as e:
        logger.warning(f"timeout_inactive_sessions 실패: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()

def complete_other_sessions(user_id: str, current_session_id: str) -> None:
    conn = _conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chat_sessions
                SET status='completed', updated_at=NOW()
                WHERE user_id=%s AND status='active' AND session_id <> %s
                """,
                (user_id, _trim_session_id(current_session_id))
            )
        conn.commit()
    except Error as e:
        logger.warning(f"complete_other_sessions 실패: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()

def complete_sessions_for_user(user_id: str) -> None:
    conn = _conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chat_sessions
                SET status='completed', updated_at=NOW()
                WHERE user_id=%s AND status='active'
                """,
                (user_id,)
            )
        conn.commit()
    except Error as e:
        logger.warning(f"complete_sessions_for_user 실패: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()


def ensure_userlog_for_session(user_id: str, session_id: str) -> str:
    """log_id를 session_id(최대 45자)에 매핑하여 생성/유지"""
    log_id = session_id[:45]
    conn = _conn()
    if not conn:
        return log_id
    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE userlog_tbl 
                SET logout_time = NOW() 
                WHERE user_id = %s 
                AND logout_time IS NULL 
                AND log_id != %s
                """,
                (user_id, log_id)
            )
            previous_sessions_closed = cur.rowcount

            cur.execute(
                """
                INSERT IGNORE INTO userlog_tbl (log_id, user_id, log_time)
                VALUES (%s, %s, NOW())
                """,
                (log_id, user_id),
            )
            
            if previous_sessions_closed > 0:
                logger.info(f"사용자 {user_id}의 이전 활성 세션 {previous_sessions_closed}개를 자동 마감 처리")
                
        conn.commit()
    except Error as e:
        logger.warning(f"ensure_userlog_for_session 실패: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()
    return log_id


def finish_userlog_for_user(user_id: str) -> None:
    """사용자의 활성 세션에 대한 logout_time 업데이트"""
    conn = _conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE userlog_tbl 
                SET logout_time = NOW() 
                WHERE user_id = %s 
                AND logout_time IS NULL 
                ORDER BY log_time DESC 
                LIMIT 1
                """,
                (user_id,)
            )
        conn.commit()
    except Error as e:
        logger.warning(f"finish_userlog_for_user 실패: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()


def insert_history(session_id: str, role: str, text: str) -> None:
    if not text:
        return
    log_id = session_id[:45]
    conn = _conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO history_tbl (log_id, message_text, role, created_time, history_id)
                VALUES (%s, %s, %s, NOW(), %s)
                """,
                (log_id, text[:1000], role, _short_uuid(24)),
            )
        conn.commit()
    except Error as e:
        logger.warning(f"insert_history 실패: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()

def upsert_chat_state(session_id: str, step: str, route_type: str, query_data: Dict[str, Any], cart_data: Dict[str, Any]) -> None:
    conn = _conn()
    if not conn:
        return
    try:
        sid = _trim_session_id(session_id)
        q_json = json.dumps(query_data or {}, ensure_ascii=False)
        c_json = json.dumps(cart_data or {}, ensure_ascii=False)
        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT IGNORE INTO chat_sessions (session_id, status, created_at, updated_at)
                VALUES (%s, 'active', NOW(), NOW())
                """,
                (sid,)
            )
            cur.execute(
                """
                INSERT INTO chat_state (session_id, current_step, route_type, query_data, cart_data, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                ON DUPLICATE KEY UPDATE current_step=VALUES(current_step), route_type=VALUES(route_type),
                                        query_data=VALUES(query_data), cart_data=VALUES(cart_data), updated_at=NOW()
                """,
                (sid, (step or "")[:50], route_type or "", q_json, c_json),
            )
        conn.commit()
    except Error as e:
        logger.warning(f"upsert_chat_state 실패: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()
