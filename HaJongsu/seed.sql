-- Qook 신선식품 챗봇 더미 데이터
-- 테스트용 샘플 데이터 삽입

USE qook_chatbot;

-- 사용자 정보 더미 데이터
INSERT INTO userinfo_tbl (user_id, name, birth_date, email, phone_num, address, post_num) VALUES
('user001', '김신선', '1990-05-15', 'shinsun@email.com', '010-1234-5678', '서울시 강남구 테헤란로 123', '06142'),
('user002', '박건강', '1985-08-20', 'healthy@email.com', '010-2345-6789', '서울시 서초구 서초대로 456', '06651'),
('user003', '이맛있', '1992-12-03', 'delicious@email.com', '010-3456-7890', '부산시 해운대구 해운대로 789', '48094'),
('user004', '최영양', '1988-03-10', 'nutrition@email.com', '010-4567-8901', '대구시 중구 중앙대로 101', '41911'),
('user005', '정유기', '1995-07-25', 'organic@email.com', '010-5678-9012', '인천시 남동구 인주대로 202', '21556');

-- 사용자 상세 정보 더미 데이터
INSERT INTO user_detail_tbl (user_id, gender, age, allergy, vegan, house_hold, unfavorite, membership) VALUES
('user001', 'F', 34, '견과류', 0, 3, '매운음식', 'premium'),
('user002', 'M', 39, NULL, 1, 2, '생선', 'basic'),
('user003', 'F', 32, '갑각류', 0, 4, NULL, 'premium'),
('user004', 'M', 36, NULL, 0, 1, '버섯', 'basic'),
('user005', 'F', 29, '유제품', 1, 2, '육류', 'gold');

-- 상품 카테고리 더미 데이터
INSERT INTO category_tbl (item, category) VALUES
('사과', 1), ('바나나', 1), ('오렌지', 1), ('딸기', 1), ('포도', 1),
('양상추', 2), ('당근', 2), ('브로콜리', 2), ('양파', 2), ('토마토', 2),
('쌀', 3), ('현미', 3), ('귀리', 3), ('퀴노아', 3),
('연어', 4), ('참치', 4), ('새우', 4), ('닭가슴살', 4), ('소고기', 4),
('우유', 5), ('요거트', 5), ('치즈', 5), ('달걀', 5);

-- 상품 정보 더미 데이터
INSERT INTO product_tbl (product, unit_price, origin) VALUES
('사과', '3000', '경북 안동'),
('바나나', '2500', '필리핀'),
('오렌지', '4000', '미국 캘리포니아'),
('딸기', '8000', '경남 진주'),
('포도', '6000', '경북 영천'),
('양상추', '2000', '경기 평택'),
('당근', '1500', '제주도'),
('브로콜리', '3500', '경북 안동'),
('양파', '1000', '전남 무안'),
('토마토', '5000', '전북 김제'),
('쌀', '45000', '경기 이천'),
('현미', '50000', '전남 해남'),
('귀리', '12000', '캐나다'),
('퀴노아', '18000', '페루'),
('연어', '25000', '노르웨이'),
('참치', '15000', '원양산'),
('새우', '20000', '서해안'),
('닭가슴살', '8000', '국내산'),
('소고기', '35000', '한우'),
('우유', '3000', '강원 평창'),
('요거트', '4000', '덴마크'),
('치즈', '12000', '네덜란드'),
('달걀', '6000', '경기 용인');

-- 상품 아이템 더미 데이터
INSERT INTO item_tbl (product, item, organic) VALUES
('사과', '유기농사과', 'Y'),
('사과', '일반사과', 'N'),
('바나나', '유기농바나나', 'Y'),
('바나나', '일반바나나', 'N'),
('양상추', '유기농양상추', 'Y'),
('양상추', '일반양상추', 'N'),
('당근', '유기농당근', 'Y'),
('당근', '일반당근', 'N'),
('쌀', '유기농쌀', 'Y'),
('쌀', '일반쌀', 'N'),
('달걀', '유기농달걀', 'Y'),
('달걀', '일반달걀', 'N');

-- 재고 더미 데이터
INSERT INTO stock_tbl (product, stock) VALUES
('사과', '150'),
('바나나', '200'),
('오렌지', '80'),
('딸기', '50'),
('포도', '120'),
('양상추', '100'),
('당근', '180'),
('브로콜리', '60'),
('양파', '300'),
('토마토', '90'),
('쌀', '40'),
('현미', '30'),
('귀리', '25'),
('퀴노아', '15'),
('연어', '35'),
('참치', '45'),
('새우', '28'),
('닭가슴살', '85'),
('소고기', '20'),
('우유', '120'),
('요거트', '75'),
('치즈', '40'),
('달걀', '150');

-- 사용자 로그 더미 데이터
INSERT INTO userlog_tbl (log_id, user_id, log_time) VALUES
('log001', 'user001', '2024-01-15 09:30:00'),
('log002', 'user002', '2024-01-15 14:20:00'),
('log003', 'user003', '2024-01-16 11:45:00'),
('log004', 'user001', '2024-01-16 16:10:00'),
('log005', 'user004', '2024-01-17 08:55:00');

-- 대화 히스토리 더미 데이터
INSERT INTO history_tbl (history_id, log_id, message_text, role, created_time) VALUES
('hist001', 'log001', '안녕하세요! 신선한 사과를 찾고 있어요', 'user', '2024-01-15 09:30:15'),
('hist002', 'log001', '안녕하세요! 경북 안동산 신선한 사과를 추천드려요. 1kg당 3,000원입니다.', 'bot', '2024-01-15 09:30:20'),
('hist003', 'log001', '좋네요! 2kg 주문하고 싶어요', 'user', '2024-01-15 09:31:00'),
('hist004', 'log002', '유기농 채소 추천해주세요', 'user', '2024-01-15 14:20:10'),
('hist005', 'log002', '유기농 양상추와 당근을 추천드려요. 신선하고 영양가가 높습니다!', 'bot', '2024-01-15 14:20:15');

-- 주문 더미 데이터
INSERT INTO order_tbl (order_code, user_id, order_date, total_price, order_status) VALUES
(1001, 'user001', '2024-01-15', '6000', 'completed'),
(1002, 'user002', '2024-01-15', '3500', 'pending'),
(1003, 'user003', '2024-01-16', '15000', 'shipped'),
(1004, 'user004', '2024-01-17', '8000', 'completed'),
(1005, 'user005', '2024-01-17', '12000', 'pending');

-- 주문 상세 더미 데이터
INSERT INTO order_detail_tbl (order_code, product, quantity, price) VALUES
(1001, '사과', '2', '6000'),
(1002, '브로콜리', '1', '3500'),
(1003, '연어', '1', '25000'),
(1003, '토마토', '2', '10000'),
(1004, '닭가슴살', '1', '8000'),
(1005, '치즈', '1', '12000');

-- 장바구니 더미 데이터
INSERT INTO cart_tbl (user_id, product, unit_price, total_price, quantity) VALUES
('user001', '바나나', '2500', '5000', '2'),
('user001', '우유', '3000', '6000', '2'),
('user002', '양상추', '2000', '4000', '2'),
('user003', '딸기', '8000', '8000', '1'),
('user004', '귀리', '12000', '12000', '1'),
('user005', '새우', '20000', '40000', '2');

-- FAQ 더미 데이터
INSERT INTO faq_tbl (question, answer, faq_category) VALUES
('배송은 언제 오나요?', '주문 후 1-2일 내에 배송됩니다. 신선식품 특성상 당일배송도 가능합니다.', '배송'),
('유기농 인증은 어떻게 확인하나요?', '모든 유기농 상품은 국가 인증마크가 있으며, 상품 상세페이지에서 인증서를 확인하실 수 있습니다.', '상품'),
('반품/교환은 어떻게 하나요?', '신선식품 특성상 단순변심 반품은 어렵지만, 상품 불량 시 즉시 교환 가능합니다.', '교환/반품'),
('배송비는 얼마인가요?', '3만원 이상 구매 시 무료배송, 미만 시 3,000원의 배송비가 부과됩니다.', '배송'),
('알레르기 정보는 어디서 확인하나요?', '각 상품 상세페이지에 알레르기 유발요소가 명시되어 있습니다.', '상품'),
('신선도는 어떻게 보장하나요?', '수확 후 24시간 내 배송하며, 콜드체인 시스템으로 신선도를 유지합니다.', '상품'),
('주문 취소는 어떻게 하나요?', '배송 전까지는 마이페이지에서 취소 가능하며, 이후에는 고객센터로 문의주세요.', '주문'),
('회원가입 혜택이 있나요?', '신규 회원 10% 할인쿠폰과 등급별 적립금 혜택을 제공합니다.', '회원');

-- 추가 세션/채팅 관련 테이블 (필요시)
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('active', 'completed', 'timeout') DEFAULT 'active',
    FOREIGN KEY (user_id) REFERENCES userinfo_tbl(user_id)
);

-- 채팅 상태 추적 테이블
CREATE TABLE IF NOT EXISTS chat_state (
    session_id VARCHAR(50) PRIMARY KEY,
    current_step VARCHAR(50),
    route_type ENUM('search_order', 'cs') DEFAULT 'search_order',
    query_data JSON,
    cart_data JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
);