"""
logging_config.py — 로깅 설정 유틸리티

애플리케이션 전체의 일관된 로깅 설정을 제공합니다.
"""

import logging
import sys
from typing import Optional
from config import config

def setup_logging(level: Optional[str] = None, format_string: Optional[str] = None) -> None:
    """
    애플리케이션 로깅 설정
    
    Args:
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: 로그 포맷 문자열
    """
    
    # 설정에서 기본값 가져오기
    log_level = level or config.LOG_LEVEL
    log_format = format_string or config.LOG_FORMAT
    
    # 로그 레벨 변환
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # 기본 로깅 설정
    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("./var/qook_chatbot.log", encoding="utf-8")
        ]
    )
    
    # 특정 라이브러리 로그 레벨 조정
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    # 성공 메시지
    logger = logging.getLogger(__name__)
    logger.info(f"로깅이 {log_level} 레벨로 설정되었습니다.")

def get_logger(name: str) -> logging.Logger:
    """
    이름이 지정된 로거 반환
    
    Args:
        name: 로거 이름 (보통 모듈명)
        
    Returns:
        Logger: 설정된 로거 인스턴스
    """
    return logging.getLogger(name)

class StructuredLogger:
    """구조화된 로깅을 위한 헬퍼 클래스"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def log_user_action(self, user_id: str, action: str, details: dict = None):
        """사용자 액션 로깅"""
        self.logger.info(f"USER_ACTION: {action}", extra={
            "user_id": user_id,
            "action": action,
            "details": details or {}
        })
    
    def log_workflow_step(self, step_name: str, state_info: dict = None):
        """워크플로우 단계 로깅"""
        self.logger.info(f"WORKFLOW: {step_name}", extra={
            "step": step_name,
            "state": state_info or {}
        })
    
    def log_api_call(self, api_name: str, duration: float, success: bool):
        """외부 API 호출 로깅"""
        level = logging.INFO if success else logging.WARNING
        self.logger.log(level, f"API_CALL: {api_name}", extra={
            "api": api_name,
            "duration_ms": duration * 1000,
            "success": success
        })
    
    def log_error(self, error: Exception, context: dict = None):
        """에러 로깅"""
        self.logger.error(f"ERROR: {str(error)}", extra={
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {}
        })

if __name__ == "__main__":
    # 테스트
    setup_logging()
    
    logger = get_logger(__name__)
    logger.info("로깅 테스트 메시지")
    
    structured = StructuredLogger("test")
    structured.log_user_action("test_user", "test_action", {"detail": "테스트"})
    
    print("로깅 설정 테스트 완료")