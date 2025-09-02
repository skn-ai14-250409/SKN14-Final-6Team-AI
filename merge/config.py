"""
config.py — 설정 관리 모듈

환경 변수를 통한 설정 관리 및 기본값 제공
"""

import os
from typing import Optional

class Config:
    """애플리케이션 설정"""
    
    # 서버 설정
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # OpenAI 설정
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    
    # 데이터베이스 설정
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./qook_chatbot.db")
    
    # 벡터 저장소 설정
    VECTOR_STORE_DIR: str = os.getenv("VECTOR_STORE_DIR", "./var/index")
    CHROMA_DIR: str = os.getenv("CHROMA_DIR", "./var/chroma")
    
    # 외부 API 설정
    TAVILY_API_KEY: Optional[str] = os.getenv("TAVILY_API_KEY")
    
    # 로깅 설정
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 보안 설정
    SECRET_KEY: str = os.getenv("SECRET_KEY", "qook-chatbot-secret-key-change-in-production")
    
    # 세션 설정
    SESSION_TIMEOUT: int = int(os.getenv("SESSION_TIMEOUT", "3600"))  # 1시간
    MAX_CLARIFY_ROUNDS: int = int(os.getenv("MAX_CLARIFY_ROUNDS", "3"))
    
    # 검색 설정
    MAX_SEARCH_RESULTS: int = int(os.getenv("MAX_SEARCH_RESULTS", "20"))
    SEARCH_CONFIDENCE_THRESHOLD: float = float(os.getenv("SEARCH_CONFIDENCE_THRESHOLD", "0.3"))
    
    # 장바구니 설정
    MAX_CART_ITEMS: int = int(os.getenv("MAX_CART_ITEMS", "50"))
    FREE_SHIPPING_THRESHOLD: float = float(os.getenv("FREE_SHIPPING_THRESHOLD", "30000"))
    
    @classmethod
    def validate(cls) -> bool:
        """필수 설정값들이 제대로 설정되었는지 검증"""
        
        errors = []
        
        # OpenAI API 키 체크
        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY가 설정되지 않았습니다.")
        
        # 디렉토리 생성
        os.makedirs(cls.VECTOR_STORE_DIR, exist_ok=True)
        os.makedirs(cls.CHROMA_DIR, exist_ok=True)
        os.makedirs("./var", exist_ok=True)
        os.makedirs("./data/faq", exist_ok=True)
        os.makedirs("./data/policy", exist_ok=True)
        
        if errors:
            for error in errors:
                print(f"CONFIG ERROR: {error}")
            return False
        
        return True
    
    @classmethod
    def get_database_config(cls) -> dict:
        """데이터베이스 설정 반환"""
        return {
            "url": cls.DATABASE_URL,
            "echo": cls.DEBUG,  # SQL 쿼리 로깅
            "pool_pre_ping": True,
            "pool_recycle": 3600
        }
    
    @classmethod
    def get_openai_config(cls) -> dict:
        """OpenAI 설정 반환"""
        return {
            "api_key": cls.OPENAI_API_KEY,
            "model": cls.OPENAI_MODEL,
            "temperature": 0.1,
            "max_tokens": 500
        }

# 전역 설정 인스턴스
config = Config()

# 애플리케이션 시작 시 설정 검증
if __name__ == "__main__":
    if config.validate():
        print("✅ 모든 설정이 올바르게 구성되었습니다.")
    else:
        print("❌ 설정 오류가 발견되었습니다.")
        exit(1)