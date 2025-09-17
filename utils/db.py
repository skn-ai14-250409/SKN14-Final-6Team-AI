"""공통 DB 연결 헬퍼"""

import os
import logging
import mysql.connector
from mysql.connector import Error

logger = logging.getLogger(__name__)


def _build_db_config() -> dict:
    """환경 변수를 기반으로 DB 접속 정보를 생성합니다."""  # hjs 수정
    password = os.getenv("DB_PASSWORD") or os.getenv("DB_PASS") or "qook_pass"
    config = {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "user": os.getenv("DB_USER", "qook_user"),
        "password": password,
        "database": os.getenv("DB_NAME", "qook_chatbot"),
        "port": int(os.getenv("DB_PORT", "3306")),
    }
    charset = os.getenv("DB_CHARSET") or "utf8mb4"
    if charset:
        config["charset"] = charset
    collation = os.getenv("DB_COLLATION") or "utf8mb4_unicode_ci"
    if collation:
        config["collation"] = collation
    return config


def get_db_connection():
    """mysql.connector를 사용해 DB 커넥션을 반환합니다."""  # hjs 수정
    config = _build_db_config()
    try:
        return mysql.connector.connect(**config)
    except Error as exc:  # hjs 수정
        logger.error(f"DB 연결 실패: {exc}")
        return None
