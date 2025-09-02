# Qook 신선식품 챗봇 ERD 문서

## 데이터베이스 구조 개요
신선식품 플랫폼의 주문/검색과 CS 응대를 위한 데이터베이스 설계

## 핵심 테이블 구조

### 1. 사용자 관련 테이블

#### userinfo_tbl (사용자 기본 정보)
- `user_id` (VARCHAR(50), PK): 사용자 고유 ID
- `name` (VARCHAR(50)): 사용자 이름
- `birth_date` (DATE): 생년월일
- `created_at` (DATETIME): 계정 생성일
- `email` (VARCHAR(100)): 이메일
- `phone_num` (VARCHAR(20)): 전화번호
- `address` (VARCHAR(200)): 주소
- `post_num` (VARCHAR(10)): 우편번호

#### user_detail_tbl (사용자 상세 정보)
- `user_id` (VARCHAR(45), PK, FK): 사용자 ID
- `gender` (ENUM('M', 'F')): 성별
- `age` (INT): 나이
- `allergy` (VARCHAR(100)): 알러지 정보
- `vegan` (TINYINT(1)): 비건 여부
- `house_hold` (INT): 가구 구성원 수
- `unfavorite` (VARCHAR(100)): 비선호 식품
- `membership` (VARCHAR(45)): 멤버십 등급

### 2. 세션/대화 관리 테이블

#### userlog_tbl (사용자 세션 로그)
- `log_id` (VARCHAR(45), PK): 로그 고유 ID
- `user_id` (VARCHAR(50), FK): 사용자 ID
- `log_time` (DATETIME): 로그인 시간
- `logout_time` (DATETIME): 로그아웃 시간

#### history_tbl (대화 히스토리)
- `history_id` (VARCHAR(45), PK): 히스토리 고유 ID
- `log_id` (VARCHAR(45), FK): 세션 로그 ID
- `message_text` (VARCHAR(1000)): 메시지 내용
- `role` (ENUM('user', 'bot')): 발화자 (사용자/봇)
- `created_time` (DATETIME): 메시지 생성 시간

#### chat_sessions (추가 - 챗봇 세션 관리)
- `session_id` (VARCHAR(50), PK): 채팅 세션 ID
- `user_id` (VARCHAR(50), FK): 사용자 ID
- `created_at` (DATETIME): 세션 시작 시간
- `updated_at` (DATETIME): 세션 갱신 시간
- `status` (ENUM): 세션 상태 (active, completed, timeout)

#### chat_state (추가 - 챗봇 상태 추적)
- `session_id` (VARCHAR(50), PK, FK): 세션 ID
- `current_step` (VARCHAR(50)): 현재 단계
- `route_type` (ENUM): 라우팅 타입 (search_order, cs)
- `query_data` (JSON): 쿼리 관련 데이터
- `cart_data` (JSON): 장바구니 데이터

### 3. 상품 관련 테이블

#### product_tbl (상품 기본 정보)
- `product` (VARCHAR(45), PK): 상품명
- `unit_price` (VARCHAR(45)): 단위 가격
- `origin` (VARCHAR(45)): 원산지

#### category_tbl (상품 카테고리)
- `item` (VARCHAR(45), PK): 아이템명
- `category` (INT): 카테고리 번호

#### item_tbl (상품 아이템)
- `product` (VARCHAR(45), FK): 상품명
- `item` (VARCHAR(45), PK): 아이템명
- `organic` (VARCHAR(45)): 유기농 여부

#### stock_tbl (재고 관리)
- `product` (VARCHAR(45), PK, FK): 상품명
- `stock` (VARCHAR(45)): 재고 수량

### 4. 주문 관련 테이블

#### order_tbl (주문 정보)
- `order_code` (INT, PK, AUTO_INCREMENT): 주문 코드
- `user_id` (VARCHAR(45), FK): 사용자 ID
- `order_date` (VARCHAR(45)): 주문 일자
- `total_price` (VARCHAR(45)): 총 금액
- `order_status` (VARCHAR(20)): 주문 상태

#### order_detail_tbl (주문 상세)
- `order_code` (INT, PK, FK): 주문 코드
- `product` (VARCHAR(45), PK, FK): 상품명
- `quantity` (VARCHAR(45)): 수량
- `price` (VARCHAR(45)): 가격

#### cart_tbl (장바구니)
- `user_id` (VARCHAR(45), PK, FK): 사용자 ID
- `product` (VARCHAR(45), PK, FK): 상품명
- `unit_price` (VARCHAR(45)): 단위 가격
- `total_price` (VARCHAR(45)): 총 가격
- `quantity` (VARCHAR(45)): 수량

### 5. FAQ/CS 테이블

#### faq_tbl (FAQ 관리)
- `faq_id` (INT, PK, AUTO_INCREMENT): FAQ ID
- `question` (VARCHAR(500)): 질문
- `answer` (VARCHAR(1000)): 답변
- `faq_category` (VARCHAR(100)): FAQ 카테고리

## 주요 관계

1. **사용자 중심 관계**
   - userinfo_tbl ↔ user_detail_tbl (1:1)
   - userinfo_tbl ↔ userlog_tbl (1:N)
   - userlog_tbl ↔ history_tbl (1:N)

2. **상품 중심 관계**
   - product_tbl ↔ item_tbl (1:N)
   - product_tbl ↔ stock_tbl (1:1)
   - category_tbl ↔ item_tbl (1:N)

3. **주문 중심 관계**
   - userinfo_tbl ↔ order_tbl (1:N)
   - order_tbl ↔ order_detail_tbl (1:N)
   - product_tbl ↔ order_detail_tbl (N:M)
   - userinfo_tbl ↔ cart_tbl (1:N)

## 인덱스 최적화

- `idx_userlog_user_time`: 사용자별 로그 시간순 조회
- `idx_history_log_time`: 세션별 대화 시간순 조회  
- `idx_order_user_date`: 사용자별 주문 날짜순 조회
- `idx_product_category`: 상품-카테고리 매핑
- `idx_faq_category`: FAQ 카테고리별 조회

## 확장 고려사항

1. **세션 관리 강화**: chat_sessions, chat_state 테이블 추가
2. **이미지/첨부파일**: 향후 이미지 업로드 기능을 위한 파일 테이블
3. **쿠폰/할인**: 프로모션 관리 테이블
4. **리뷰/평가**: 상품 리뷰 시스템