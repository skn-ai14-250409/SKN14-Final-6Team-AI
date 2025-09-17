"""
Common utilities and clients shared across CS modules.
"""
import os
import logging
from decimal import Decimal
from typing import Any
from dotenv import load_dotenv
from datetime import datetime

from mysql.connector import Error
from utils.db import get_db_connection as _get_db_connection  

load_dotenv()

logger = logging.getLogger("E_CS_COMMON")


def get_db_connection():
    """공용 DB 연결 래퍼"""
    conn = _get_db_connection()
    if not conn:
        logger.error('DB 연결 실패')
    return conn

CS_DEFECT_THRESHOLD = float(os.getenv("CS_DEFECT_THRESHOLD", "0.35"))
CS_AUTO_ACCEPT_DEBUG = os.getenv("CS_AUTO_ACCEPT_DEBUG", "false").lower() == "true"
CS_PRODUCT_MATCH_THRESHOLD = float(os.getenv("CS_PRODUCT_MATCH_THRESHOLD", "0.60"))

try:
    import openai

    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_client = openai.OpenAI(api_key=openai_api_key) if openai_api_key else None
    if not openai_api_key:
        logger.warning("OpenAI API key not found. Using mock responses.")
except Exception:
    openai_client = None
    logger.warning("OpenAI package not available.")

try:
    from pinecone import Pinecone

    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    pinecone_index_name = "qook"
    if pinecone_api_key:
        pinecone_client = Pinecone(api_key=pinecone_api_key)
        pinecone_index = pinecone_client.Index(pinecone_index_name)
    else:
        pinecone_client = None
        pinecone_index = None
        logger.warning("Pinecone API key not found. Using mock responses.")
except Exception:
    pinecone_client = None
    pinecone_index = None
    logger.warning("Pinecone package not available.")


def _to_float(val: Any) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).strip().replace(",", "")
        return float(s)
    except Exception:
        try:
            return float(Decimal(str(val)))
        except Exception:
            return 0.0


def _to_int(val: Any) -> int:
    if val is None:
        return 0
    if isinstance(val, int):
        return val
    try:
        s = str(val).strip().replace(",", "")
        return int(float(s))
    except Exception:
        try:
            return int(Decimal(str(val)))
        except Exception:
            return 0


def _fmt_dt(d):
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%d %H:%M")
    return str(d) if d is not None else ""


def _fmt_date(d):
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%d")
    return str(d) if d is not None else ""
