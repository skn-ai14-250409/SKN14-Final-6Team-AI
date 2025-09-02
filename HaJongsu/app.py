"""
app.py — Qook 신선식품 챗봇 FastAPI 메인 애플리케이션

이 파일은 전체 챗봇 서비스의 진입점으로:
- FastAPI 웹 서버 제공
- LangGraph 워크플로우 통합  
- 웹 UI 및 API 엔드포인트 제공
- 정적 파일 및 템플릿 서빙
"""

import os
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# 프로젝트 모듈 임포트
from graph_interfaces import ChatState
from workflow import get_main_workflow, get_cs_workflow, run_workflow

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("qook_chatbot")

# FastAPI 앱 생성
app = FastAPI(
    title="Qook 신선식품 챗봇",
    description="신선식품 쇼핑몰의 주문/검색과 CS를 처리하는 AI 챗봇",
    version="1.0.0"
)

# 정적 파일 및 템플릿 설정
static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

if os.path.exists(templates_dir):
    templates = Jinja2Templates(directory=templates_dir)
else:
    templates = None

# 요청/응답 모델
class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    turn_id: int
    route_target: Optional[str] = None
    confidence: Optional[float] = None
    artifacts: Optional[list] = None
    error: Optional[str] = None

# 전역 세션 저장소 (실제로는 Redis 등 사용)
SESSIONS: Dict[str, Dict[str, Any]] = {}

@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """랜딩페이지"""
    if templates:
        return templates.TemplateResponse("landing.html", {"request": request})
    else:
        return HTMLResponse("""
        <html>
            <head><title>Qook 신선식품 챗봇</title></head>
            <body>
                <h1>🥬 Qook 신선식품 챗봇에 오신 것을 환영합니다!</h1>
                <p><a href="/chat">챗봇 사용하기</a></p>
                <p><a href="/docs">API 문서</a></p>
            </body>
        </html>
        """)

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """챗봇 페이지"""
    if templates:
        return templates.TemplateResponse("chat.html", {"request": request})
    else:
        return HTMLResponse("""
        <html>
            <head>
                <title>Qook 챗봇</title>
                <style>
                    body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                    .chat-container { border: 1px solid #ddd; height: 400px; overflow-y: scroll; padding: 10px; margin-bottom: 10px; }
                    .message { margin-bottom: 10px; }
                    .user { text-align: right; color: blue; }
                    .bot { text-align: left; color: green; }
                    .input-container { display: flex; }
                    .input-container input { flex: 1; padding: 10px; }
                    .input-container button { padding: 10px 20px; }
                </style>
            </head>
            <body>
                <h1>🥬 Qook 신선식품 챗봇</h1>
                <div id="chat-container" class="chat-container"></div>
                <div class="input-container">
                    <input type="text" id="message-input" placeholder="메시지를 입력하세요..." />
                    <button onclick="sendMessage()">전송</button>
                </div>

                <script>
                    let sessionId = null;
                    
                    function addMessage(content, isUser) {
                        const container = document.getElementById('chat-container');
                        const message = document.createElement('div');
                        message.className = 'message ' + (isUser ? 'user' : 'bot');
                        message.textContent = content;
                        container.appendChild(message);
                        container.scrollTop = container.scrollHeight;
                    }
                    
                    async function sendMessage() {
                        const input = document.getElementById('message-input');
                        const message = input.value.trim();
                        if (!message) return;
                        
                        addMessage(message, true);
                        input.value = '';
                        
                        try {
                            const response = await fetch('/api/chat', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({
                                    message: message,
                                    session_id: sessionId
                                })
                            });
                            
                            const data = await response.json();
                            sessionId = data.session_id;
                            addMessage(data.response, false);
                        } catch (error) {
                            addMessage('오류가 발생했습니다: ' + error.message, false);
                        }
                    }
                    
                    document.getElementById('message-input').addEventListener('keypress', function(e) {
                        if (e.key === 'Enter') {
                            sendMessage();
                        }
                    });
                    
                    // 초기 인사말
                    addMessage('안녕하세요! Qook 신선식품 챗봇입니다. 무엇을 도와드릴까요?', false);
                </script>
            </body>
        </html>
        """)

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """챗봇 대화 API"""
    try:
        # 세션 ID 생성 또는 가져오기
        session_id = request.session_id or str(uuid.uuid4())
        user_id = request.user_id or "anonymous"
        
        # 기존 세션 가져오기 또는 새로 생성
        if session_id in SESSIONS:
            session_data = SESSIONS[session_id]
            turn_id = session_data.get("turn_id", 0) + 1
        else:
            session_data = {"turn_id": 0, "history": []}
            turn_id = 1
        
        # ChatState 생성
        chat_state = ChatState(
            user_id=user_id,
            session_id=session_id,
            turn_id=turn_id,
            query=request.message
        )
        
        # 워크플로우 실행
        logger.info(f"Processing message: {request.message[:50]}...")
        result = await run_workflow(chat_state)
        
        # 결과에서 응답 추출
        response_text = _extract_response_text(result, request.message)
        
        # 세션 업데이트
        session_data["turn_id"] = turn_id
        session_data["history"].append({
            "user": request.message,
            "bot": response_text,
            "timestamp": datetime.now().isoformat()
        })
        session_data["last_result"] = result
        SESSIONS[session_id] = session_data
        
        logger.info(f"Response generated: {response_text[:50]}...")
        
        return ChatResponse(
            response=response_text,
            session_id=session_id,
            turn_id=turn_id,
            route_target=result.get("route", {}).get("target"),
            confidence=result.get("route", {}).get("confidence"),
            artifacts=result.get("end", {}).get("artifacts", [])
        )
        
    except Exception as e:
        logger.error(f"Chat processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _extract_response_text(result: Dict[str, Any], original_message: str) -> str:
    """워크플로우 결과에서 사용자 응답 텍스트 추출"""
    
    # 세션 종료 메시지
    if result.get("end"):
        return result["end"].get("final_message", "대화가 종료되었습니다.")
    
    # 핸드오프 메시지
    if result.get("handoff"):
        if result["handoff"].get("status") == "sent":
            return f"상담사에게 연결되었습니다. 티켓번호: {result['handoff'].get('crm_id')}"
        elif result["handoff"].get("status") == "failed":
            return result["handoff"].get("fallback_message", "상담사 연결에 실패했습니다.")
    
    # CS 답변
    if result.get("cs", {}).get("answer"):
        answer = result["cs"]["answer"]
        response = answer.get("text", "")
        if answer.get("citations"):
            response += f"\n\n참고: {', '.join(answer['citations'])}"
        return response
    
    # 주문 완료
    if result.get("order", {}).get("status") == "confirmed":
        order_id = result["order"].get("order_id")
        return f"주문이 완료되었습니다! 주문번호: {order_id}"
    
    # 검색 결과
    if result.get("search", {}).get("candidates"):
        candidates = result["search"]["candidates"]
        if candidates:
            response = f"{len(candidates)}개의 상품을 찾았습니다:\n"
            for i, product in enumerate(candidates[:3]):  # 상위 3개만
                response += f"{i+1}. {product['name']} - {product['price']:,}원\n"
            response += "\n장바구니에 담아드릴까요?"
            return response
        else:
            return "찾으시는 상품이 없습니다. 다른 검색어로 시도해보세요."
    
    # 명확화 질문
    if result.get("clarify", {}).get("questions"):
        questions = result["clarify"]["questions"]
        return "\n".join(questions)
    
    # 장바구니 업데이트
    if result.get("cart", {}).get("items"):
        items = result["cart"]["items"]
        total = result["cart"].get("total", 0)
        response = f"장바구니에 {len(items)}개 상품이 담겨있습니다.\n"
        response += f"총 금액: {total:,}원\n주문하시겠어요?"
        return response
    
    # 기본 응답
    return "무엇을 도와드릴까요?"

@app.get("/api/health")
async def health_check():
    """헬스체크"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/stats")
async def get_stats():
    """시스템 통계"""
    return {
        "active_sessions": len(SESSIONS),
        "total_conversations": sum(len(s.get("history", [])) for s in SESSIONS.values()),
        "uptime": "running",
        "version": "1.0.0"
    }

@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """세션 정보 조회"""
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = SESSIONS[session_id]
    return {
        "session_id": session_id,
        "turn_count": session.get("turn_id", 0),
        "history_count": len(session.get("history", [])),
        "last_activity": session.get("history", [{}])[-1].get("timestamp") if session.get("history") else None
    }

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting Qook Chatbot Server on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        reload=False  # 운영환경에서는 False
    )