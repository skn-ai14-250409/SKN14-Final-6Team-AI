"""
database.py - 데이터베이스 연결 및 쿼리 헬퍼

MySQL 데이터베이스 연결을 관리하고 기본적인 CRUD 작업을 제공합니다.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
import pymysql
from contextlib import contextmanager
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

logger = logging.getLogger("DATABASE")

# 데이터베이스 설정
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'qook_user',
    'password': 'qook_pass',
    'database': 'qook_chatbot',
    'charset': 'utf8mb4',
    'autocommit': True
}

@contextmanager
def get_db_connection():
    """데이터베이스 연결 컨텍스트 매니저"""
    connection = None
    try:
        connection = pymysql.connect(**DB_CONFIG)
        yield connection
    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"데이터베이스 오류: {e}")
        raise
    finally:
        if connection:
            connection.close()

def execute_query(query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
    """SELECT 쿼리 실행 및 결과 반환"""
    with get_db_connection() as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchall()

def execute_non_query(query: str, params: Optional[Tuple] = None) -> int:
    """INSERT/UPDATE/DELETE 쿼리 실행 및 영향받은 행 수 반환"""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            affected_rows = cursor.execute(query, params or ())
            conn.commit()
            return affected_rows

def get_product_by_name(product_name: str) -> Optional[Dict[str, Any]]:
    """상품명으로 상품 정보 조회"""
    query = """
    SELECT p.product, p.unit_price, p.origin, s.stock
    FROM product_tbl p
    LEFT JOIN stock_tbl s ON p.product = s.product
    WHERE p.product = %s
    """
    results = execute_query(query, (product_name,))
    return results[0] if results else None

def get_products_by_category(category: str) -> List[Dict[str, Any]]:
    """카테고리로 상품 목록 조회"""
    query = """
    SELECT p.product, p.unit_price, p.origin, s.stock
    FROM product_tbl p
    LEFT JOIN stock_tbl s ON p.product = s.product
    LEFT JOIN item_tbl i ON p.product = i.product
    LEFT JOIN category_tbl c ON i.item = c.item
    WHERE c.category = %s AND s.stock > 0
    """
    return execute_query(query, (category,))

def search_products(keyword: str) -> List[Dict[str, Any]]:
    """키워드로 상품 검색"""
    query = """
    SELECT p.product, p.unit_price, p.origin, s.stock
    FROM product_tbl p
    LEFT JOIN stock_tbl s ON p.product = s.product
    WHERE (p.product LIKE %s OR p.origin LIKE %s) 
    AND s.stock > 0
    ORDER BY p.product
    """
    search_term = f"%{keyword}%"
    return execute_query(query, (search_term, search_term))

def get_user_cart(user_id: str) -> List[Dict[str, Any]]:
    """사용자 장바구니 조회"""
    query = """
    SELECT user_id, product, unit_price, total_price, quantity
    FROM cart_tbl
    WHERE user_id = %s
    """
    return execute_query(query, (user_id,))

def add_to_cart(user_id: str, product: str, quantity: int, unit_price: float) -> bool:
    """장바구니에 상품 추가 또는 업데이트"""
    try:
        # 기존 항목 확인
        existing = execute_query(
            "SELECT quantity FROM cart_tbl WHERE user_id = %s AND product = %s",
            (user_id, product)
        )
        
        total_price = unit_price * quantity
        
        if existing:
            # 기존 항목 업데이트
            new_quantity = existing[0]['quantity'] + quantity
            new_total = unit_price * new_quantity
            query = """
            UPDATE cart_tbl 
            SET quantity = %s, total_price = %s
            WHERE user_id = %s AND product = %s
            """
            execute_non_query(query, (new_quantity, new_total, user_id, product))
        else:
            # 새 항목 추가
            query = """
            INSERT INTO cart_tbl (user_id, product, unit_price, total_price, quantity)
            VALUES (%s, %s, %s, %s, %s)
            """
            execute_non_query(query, (user_id, product, unit_price, total_price, quantity))
        
        return True
    except Exception as e:
        logger.error(f"장바구니 추가 실패: {e}")
        return False

def remove_from_cart(user_id: str, product: str) -> bool:
    """장바구니에서 상품 제거"""
    try:
        query = "DELETE FROM cart_tbl WHERE user_id = %s AND product = %s"
        affected = execute_non_query(query, (user_id, product))
        return affected > 0
    except Exception as e:
        logger.error(f"장바구니 제거 실패: {e}")
        return False

def clear_cart(user_id: str) -> bool:
    """사용자 장바구니 비우기"""
    try:
        query = "DELETE FROM cart_tbl WHERE user_id = %s"
        execute_non_query(query, (user_id,))
        return True
    except Exception as e:
        logger.error(f"장바구니 비우기 실패: {e}")
        return False

def create_order(user_id: str, total_price: float, items: List[Dict[str, Any]]) -> Optional[int]:
    """주문 생성"""
    try:
        from datetime import datetime
        order_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 주문 테이블에 삽입
        order_query = """
        INSERT INTO order_tbl (user_id, order_date, total_price, order_status)
        VALUES (%s, %s, %s, 'pending')
        """
        execute_non_query(order_query, (user_id, order_date, str(total_price)))
        
        # 주문 ID 가져오기
        order_id_query = "SELECT LAST_INSERT_ID() as order_id"
        result = execute_query(order_id_query)
        order_id = result[0]['order_id']
        
        # 주문 상세 삽입
        detail_query = """
        INSERT INTO order_detail_tbl (order_code, product, quantity, price)
        VALUES (%s, %s, %s, %s)
        """
        for item in items:
            execute_non_query(detail_query, (
                order_id, 
                item['product'], 
                str(item['quantity']), 
                str(item['total_price'])
            ))
        
        # 장바구니 비우기
        clear_cart(user_id)
        
        return order_id
    except Exception as e:
        logger.error(f"주문 생성 실패: {e}")
        return None

def get_faq_data() -> List[Dict[str, Any]]:
    """FAQ 데이터 조회"""
    query = "SELECT faq_id, question, answer, faq_category FROM faq_tbl"
    return execute_query(query)

def test_connection() -> bool:
    """데이터베이스 연결 테스트"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return result[0] == 1
    except Exception as e:
        logger.error(f"데이터베이스 연결 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    # 연결 테스트
    if test_connection():
        print("✅ 데이터베이스 연결 성공")
        
        # 샘플 쿼리 테스트
        products = search_products("사과")
        print(f"사과 검색 결과: {len(products)}개")
        
        faqs = get_faq_data()
        print(f"FAQ 데이터: {len(faqs)}개")
    else:
        print("❌ 데이터베이스 연결 실패")