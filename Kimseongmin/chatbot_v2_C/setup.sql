-- Qook 신선식품 챗봇 데이터베이스 설정
-- 데이터베이스 생성 및 사용자 설정

-- 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS qook_chatbot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 사용자 생성 및 권한 부여
CREATE USER IF NOT EXISTS 'qook_user'@'localhost' IDENTIFIED BY 'qook_pass';
CREATE USER IF NOT EXISTS 'qook_user'@'%' IDENTIFIED BY 'qook_pass';

GRANT ALL PRIVILEGES ON qook_chatbot.* TO 'qook_user'@'localhost';
GRANT ALL PRIVILEGES ON qook_chatbot.* TO 'qook_user'@'%';

FLUSH PRIVILEGES;

-- 데이터베이스 사용
USE qook_chatbot;

-- 사용자 정보 테이블
CREATE TABLE userinfo_tbl (
    user_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    birth_date DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    email VARCHAR(100),
    phone_num VARCHAR(20),
    address VARCHAR(200),
    post_num VARCHAR(10)
);

-- 사용자 상세 정보 테이블
CREATE TABLE user_detail_tbl (
    user_id VARCHAR(45) PRIMARY KEY,
    gender ENUM('M', 'F'),
    age INT,
    allergy VARCHAR(100),
    vegan TINYINT(1) DEFAULT 0,
    house_hold INT,
    unfavorite VARCHAR(100),
    membership VARCHAR(45),
    FOREIGN KEY (user_id) REFERENCES userinfo_tbl(user_id) ON DELETE CASCADE
);

-- 사용자 로그 테이블
CREATE TABLE userlog_tbl (
    log_id VARCHAR(45) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    log_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    logout_time DATETIME,
    FOREIGN KEY (user_id) REFERENCES userinfo_tbl(user_id) ON DELETE CASCADE
);

-- 대화 히스토리 테이블
CREATE TABLE history_tbl (
    log_id VARCHAR(45) NOT NULL,
    message_text VARCHAR(1000) NOT NULL,
    role ENUM('user', 'bot') NOT NULL,
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    history_id VARCHAR(45) PRIMARY KEY,
    FOREIGN KEY (log_id) REFERENCES userlog_tbl(log_id) ON DELETE CASCADE
);

-- 상품 카테고리 테이블
CREATE TABLE category_tbl (
    item VARCHAR(45) PRIMARY KEY,
    category INT
);

-- 상품 정보 테이블
CREATE TABLE product_tbl (
    product VARCHAR(45) PRIMARY KEY,
    unit_price VARCHAR(45) NOT NULL,
    origin VARCHAR(45)
);

-- 상품 아이템 테이블
CREATE TABLE item_tbl (
    product VARCHAR(45) NOT NULL,
    item VARCHAR(45) PRIMARY KEY,
    organic VARCHAR(45),
    FOREIGN KEY (product) REFERENCES product_tbl(product) ON DELETE CASCADE
);

-- 재고 테이블
CREATE TABLE stock_tbl (
    product VARCHAR(45) PRIMARY KEY,
    stock VARCHAR(45) NOT NULL,
    FOREIGN KEY (product) REFERENCES product_tbl(product) ON DELETE CASCADE
);

-- 주문 테이블
CREATE TABLE order_tbl (
    order_code INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(45) NOT NULL,
    order_date VARCHAR(45) NOT NULL,
    total_price VARCHAR(45) NOT NULL,
    order_status VARCHAR(20) DEFAULT 'pending',
    FOREIGN KEY (user_id) REFERENCES userinfo_tbl(user_id) ON DELETE CASCADE
);

-- 주문 상세 테이블
CREATE TABLE order_detail_tbl (
    order_code INT NOT NULL,
    product VARCHAR(45) NOT NULL,
    quantity VARCHAR(45) NOT NULL,
    price VARCHAR(45) NOT NULL,
    PRIMARY KEY (order_code, product),
    FOREIGN KEY (order_code) REFERENCES order_tbl(order_code) ON DELETE CASCADE,
    FOREIGN KEY (product) REFERENCES product_tbl(product) ON DELETE CASCADE
);

-- 장바구니 테이블
CREATE TABLE cart_tbl (
    user_id VARCHAR(45) NOT NULL,
    product VARCHAR(45) NOT NULL,
    unit_price VARCHAR(45) NOT NULL,
    total_price VARCHAR(45) NOT NULL,
    quantity VARCHAR(45) NOT NULL,
    PRIMARY KEY (user_id, product),
    FOREIGN KEY (user_id) REFERENCES userinfo_tbl(user_id) ON DELETE CASCADE,
    FOREIGN KEY (product) REFERENCES product_tbl(product) ON DELETE CASCADE
);

-- FAQ 테이블
CREATE TABLE faq_tbl (
    faq_id INT AUTO_INCREMENT PRIMARY KEY,
    question VARCHAR(500) NOT NULL,
    answer VARCHAR(1000) NOT NULL,
    faq_category VARCHAR(100)
);

-- 인덱스 생성
CREATE INDEX idx_userlog_user_time ON userlog_tbl(user_id, log_time);
CREATE INDEX idx_history_log_time ON history_tbl(log_id, created_time);
CREATE INDEX idx_order_user_date ON order_tbl(user_id, order_date);
CREATE INDEX idx_product_category ON item_tbl(product);
CREATE INDEX idx_faq_category ON faq_tbl(faq_category);