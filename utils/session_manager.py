"""
세션별 ChatState 관리 시스템

LangGraph의 State 영속성을 올바르게 활용하기 위한 세션 관리 모듈.
매 요청마다 새로운 State를 생성하는 대신, 세션별로 State를 메모리에 캐시하여
대화 맥락을 자동으로 유지합니다.
"""

from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
import logging
from graph_interfaces import ChatState

logger = logging.getLogger(__name__)

# 세션별 State 캐시 (메모리 기반)
session_states: Dict[str, ChatState] = {}
session_last_access: Dict[str, datetime] = {}

def get_session_key(user_id: str, session_id: str) -> str:
    """세션 키 생성"""
    return f"{user_id}_{session_id}"

def get_or_create_session_state(user_id: str, session_id: str) -> ChatState:
    """
    세션별 State 반환 (없으면 생성)

    Args:
        user_id: 사용자 ID
        session_id: 세션 ID

    Returns:
        ChatState: 해당 세션의 State (기존 또는 새로 생성)
    """
    key = get_session_key(user_id, session_id)

    # 기존 세션이 있으면 반환
    if key in session_states:
        session_last_access[key] = datetime.now()
        logger.info(f"기존 세션 State 반환: {key}, 히스토리 개수: {len(session_states[key].conversation_history)}")
        return session_states[key]

    # 새 세션 생성
    new_state = ChatState(
        user_id=user_id,
        session_id=session_id
    )

    session_states[key] = new_state
    session_last_access[key] = datetime.now()

    logger.info(f"새 세션 State 생성: {key}")
    return new_state

def update_session_access(user_id: str, session_id: str) -> None:
    """세션 마지막 접근 시간 업데이트"""
    key = get_session_key(user_id, session_id)
    if key in session_states:
        session_last_access[key] = datetime.now()

def cleanup_inactive_sessions(max_age_minutes: int = 30) -> int:
    """
    비활성 세션 정리

    Args:
        max_age_minutes: 세션 유지 시간 (분)

    Returns:
        int: 정리된 세션 수
    """
    cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)
    keys_to_remove = []

    for key, last_access in session_last_access.items():
        if last_access < cutoff_time:
            keys_to_remove.append(key)

    cleaned_count = 0
    for key in keys_to_remove:
        if key in session_states:
            del session_states[key]
            cleaned_count += 1
        if key in session_last_access:
            del session_last_access[key]

    if cleaned_count > 0:
        logger.info(f"비활성 세션 {cleaned_count}개 정리 완료")

    return cleaned_count

def get_session_count() -> int:
    """현재 활성 세션 수 반환"""
    return len(session_states)

def get_session_info() -> List[Dict[str, str]]:
    """모든 세션 정보 반환 (디버깅용)"""
    info = []
    for key, state in session_states.items():
        last_access = session_last_access.get(key, datetime.now())
        info.append({
            "session_key": key,
            "user_id": state.user_id,
            "session_id": state.session_id or "None",
            "history_count": len(state.conversation_history),
            "last_access": last_access.strftime("%Y-%m-%d %H:%M:%S")
        })
    return info

def clear_session(user_id: str, session_id: str) -> bool:
    """
    특정 세션 삭제

    Args:
        user_id: 사용자 ID
        session_id: 세션 ID

    Returns:
        bool: 삭제 성공 여부
    """
    key = get_session_key(user_id, session_id)

    removed = False
    if key in session_states:
        del session_states[key]
        removed = True

    if key in session_last_access:
        del session_last_access[key]

    if removed:
        logger.info(f"세션 삭제 완료: {key}")

    return removed

def clear_all_sessions() -> int:
    """모든 세션 삭제 (테스트/디버깅용)"""
    count = len(session_states)
    session_states.clear()
    session_last_access.clear()

    logger.info(f"모든 세션 삭제 완료: {count}개")
    return count

def get_session_statistics() -> Dict[str, int]:
    """세션 통계 정보 반환"""
    total_sessions = len(session_states)
    total_history_items = sum(len(state.conversation_history) for state in session_states.values())

    return {
        "total_sessions": total_sessions,
        "total_history_items": total_history_items,
        "average_history_per_session": total_history_items // total_sessions if total_sessions > 0 else 0
    }

# 주기적 세션 정리를 위한 헬퍼 함수
def schedule_session_cleanup(interval_minutes: int = 10, max_age_minutes: int = 30):
    """
    주기적 세션 정리 스케줄링 (선택적 사용)

    Args:
        interval_minutes: 정리 주기 (분)
        max_age_minutes: 세션 유지 시간 (분)
    """
    import threading
    import time

    def cleanup_worker():
        while True:
            try:
                cleaned = cleanup_inactive_sessions(max_age_minutes)
                if cleaned > 0:
                    stats = get_session_statistics()
                    logger.info(f"세션 정리 완료: {cleaned}개 제거, 현재 활성: {stats['total_sessions']}개")
                time.sleep(interval_minutes * 60)
            except Exception as e:
                logger.error(f"세션 정리 중 오류: {e}")
                time.sleep(60)  # 오류 시 1분 후 재시도

    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    logger.info(f"세션 정리 스케줄러 시작: {interval_minutes}분 주기, {max_age_minutes}분 유지")