"""
Text2SQL 모듈 - 자연어 질의를 SQL로 변환하여 상품 검색

C 팀 담당: 상품 검색 기능의 Text2SQL 구현
- 스키마 프라이밍으로 SQL 생성
- SQL 검증 및 안전 실행
- 실패 시 RAG 폴백 지원
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import sqlite3
from django.db import connection
from django.conf import settings
import openai

logger = logging.getLogger('chatbot.product_search')

@dataclass
class SQLResult:
    """SQL 실행 결과를 담는 데이터 클래스"""
    success: bool
    data: List[Dict[str, Any]]
    error: Optional[str] = None
    sql_query: Optional[str] = None

class Text2SQLEngine:
    """Text2SQL 엔진 클래스"""
    
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.db_schema = self._load_schema()
        
    def _load_schema(self) -> str:
        """데이터베이스 스키마 정보를 로드"""
        schema = """
        -- Qook 신선식품 데이터베이스 스키마 (Django 모델 기반)
        
        CREATE TABLE product_tbl (
            id INTEGER PRIMARY KEY,           -- 자동 증가 ID
            name VARCHAR(45) NOT NULL,        -- 상품명 (예: '사과', '바나나')
            unit_price DECIMAL NOT NULL,      -- 단위가격 (예: 3000.00)
            origin VARCHAR(45),               -- 원산지 (예: '경북 안동')
            category_id INTEGER NOT NULL      -- 카테고리 ID (FK)
        );
        
        CREATE TABLE category_tbl (
            id INTEGER PRIMARY KEY,           -- 자동 증가 ID
            name VARCHAR(45) NOT NULL,        -- 카테고리명 (과일, 채소 등)
            category_id INTEGER NOT NULL      -- 카테고리 번호 (1:과일, 2:채소, 3:곡물, 4:육류/수산, 5:유제품)
        );
        
        CREATE TABLE stock_tbl (
            id INTEGER PRIMARY KEY,           -- 자동 증가 ID
            quantity INTEGER NOT NULL,        -- 재고수량 (예: 150)
            product_id INTEGER NOT NULL       -- 상품 ID (FK)
        );
        
        CREATE TABLE item_tbl (
            id INTEGER PRIMARY KEY,           -- 자동 증가 ID
            item_name VARCHAR(45) NOT NULL,   -- 아이템명 (유기농사과, 일반사과 등)
            organic BOOLEAN NOT NULL,         -- 유기농 여부 (true/false)
            product_id INTEGER NOT NULL       -- 상품 ID (FK)
        );
        
        -- 카테고리 매핑
        -- 1: 과일 (사과, 바나나, 오렌지, 딸기, 포도)
        -- 2: 채소 (양상추, 당근, 브로콜리, 양파, 토마토)  
        -- 3: 곡물 (쌀, 현미, 귀리, 퀴노아)
        -- 4: 육류/수산 (연어, 참치, 새우, 닭가슴살, 소고기)
        -- 5: 유제품 (우유, 요거트, 치즈, 달걀)
        """
        return schema
    
    def generate_sql(self, query: str, slots: Dict[str, Any]) -> Tuple[str, float]:
        """자연어 쿼리를 SQL로 변환"""
        
        # 슬롯 정보 추출
        category = slots.get('category', '')
        price_cap = slots.get('price_cap', None)
        organic = slots.get('organic', None)
        quantity_needed = slots.get('quantity', 1)
        
        system_prompt = f"""
당신은 신선식품 데이터베이스를 위한 Text2SQL 전문가입니다.
사용자의 자연어 질의를 안전하고 정확한 SQL 쿼리로 변환하세요.

### 데이터베이스 스키마:
{self.db_schema}

### 중요한 규칙:
1. SELECT 쿼리만 생성하세요 (INSERT, UPDATE, DELETE 금지)
2. 항상 LIMIT을 사용하여 결과를 제한하세요 (기본 20개)
3. 가격 비교 시 CAST(unit_price AS INTEGER)를 사용하세요
4. 재고 비교 시 CAST(stock AS INTEGER)를 사용하세요
5. JOIN은 필요한 경우에만 사용하세요
6. 한국어 상품명을 정확히 매칭하세요

### 응답 형식:
SQL 쿼리만 반환하세요. 설명이나 추가 텍스트는 불필요합니다.

### 예시:
사용자: "사과 찾아줘"
응답: SELECT p.name, p.unit_price, p.origin, s.quantity FROM product_tbl p JOIN stock_tbl s ON p.id = s.product_id WHERE p.name LIKE '%사과%' ORDER BY p.unit_price ASC LIMIT 20;

사용자: "5000원 이하 채소"  
응답: SELECT p.name, p.unit_price, p.origin, s.quantity FROM product_tbl p JOIN stock_tbl s ON p.id = s.product_id JOIN category_tbl c ON p.category_id = c.id WHERE c.category_id = 2 AND p.unit_price <= 5000 ORDER BY p.unit_price ASC LIMIT 20;
"""
        
        user_prompt = f"""
사용자 질의: "{query}"

추출된 정보:
- 카테고리: {category}
- 최대 가격: {price_cap}
- 유기농 여부: {organic}
- 필요 수량: {quantity_needed}

위 정보를 참고하여 적절한 SQL 쿼리를 생성하세요.
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            sql_query = response.choices[0].message.content.strip()
            confidence = 0.8  # 기본 신뢰도
            
            # SQL 검증
            if self._validate_sql(sql_query):
                logger.info(f"Generated SQL: {sql_query}")
                return sql_query, confidence
            else:
                logger.warning(f"Generated invalid SQL: {sql_query}")
                return "", 0.0
                
        except Exception as e:
            logger.error(f"SQL generation failed: {e}")
            return "", 0.0
    
    def _validate_sql(self, sql: str) -> bool:
        """SQL 쿼리 안전성 검증"""
        
        # 기본 안전 검사
        sql_lower = sql.lower().strip()
        
        # 위험한 키워드 체크 (대소문자 무시)
        dangerous_keywords = [
            'drop', 'delete', 'insert', 'update', 'alter', 
            'create', 'truncate', 'exec', 'execute', 
            '--', ';--', 'xp_', 'sp_', '/*', '*/', 
            'union', 'script', 'javascript', 'vbscript',
            'onload', 'onerror', 'eval', 'expression'
        ]
        
        for keyword in dangerous_keywords:
            if keyword in sql_lower:
                logger.warning(f"Dangerous keyword detected: {keyword}")
                return False
        
        # SELECT로 시작하는지 확인
        if not sql_lower.startswith('select'):
            logger.warning("Query does not start with SELECT")
            return False
        
        # LIMIT이 있는지 확인
        if 'limit' not in sql_lower:
            logger.warning("Query missing LIMIT clause")
            return False
            
        # 기본 문법 검증 
        # 1. 세미콜론 개수 체크 (최대 1개만 허용, 끝에만)
        semicolon_count = sql.count(';')
        if semicolon_count > 1:
            logger.warning("Multiple semicolons detected")
            return False
        elif semicolon_count == 1 and not sql.strip().endswith(';'):
            logger.warning("Semicolon in middle of query detected")
            return False
        
        # 2. 따옴표 균형 검사
        single_quote_count = sql.count("'")
        if single_quote_count % 2 != 0:
            logger.warning("Unbalanced single quotes detected")
            return False
            
        return True
    
    def execute_sql(self, sql: str) -> SQLResult:
        """SQL 쿼리 실행"""
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                
                # 결과를 딕셔너리 리스트로 변환
                results = []
                for row in rows:
                    result_dict = dict(zip(columns, row))
                    results.append(result_dict)
                
                logger.info(f"SQL executed successfully, returned {len(results)} rows")
                return SQLResult(success=True, data=results, sql_query=sql)
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"SQL execution failed: {error_msg}")
            return SQLResult(success=False, data=[], error=error_msg, sql_query=sql)
    
    def search_products(self, query: str, slots: Dict[str, Any]) -> SQLResult:
        """상품 검색 메인 함수"""
        
        logger.info(f"Text2SQL search started - Query: {query}, Slots: {slots}")
        
        # SQL 생성
        sql_query, confidence = self.generate_sql(query, slots)
        
        if not sql_query or confidence < 0.5:
            logger.warning("SQL generation failed or low confidence, falling back to RAG")
            return SQLResult(success=False, data=[], error="SQL generation failed")
        
        # SQL 실행
        result = self.execute_sql(sql_query)
        
        if result.success:
            logger.info(f"Text2SQL search completed successfully: {len(result.data)} results")
        else:
            logger.warning("Text2SQL search failed, should fallback to RAG")
            
        return result


def create_text2sql_engine() -> Text2SQLEngine:
    """Text2SQL 엔진 팩토리 함수"""
    return Text2SQLEngine()