from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import logging, uuid, uvicorn, os
from typing import List
from fastapi import UploadFile, File, Form
from fastapi.encoders import jsonable_encoder

from config import config
from utils.logging_config import setup_logging
from graph_interfaces import ChatState
from workflow import run_workflow
from nodes import cart_order
from auth_routes import auth_router
from auth_system.kakao_address import kakao_router
from cart_routes import router as cart_router
from upload_routes import router as upload_router
from orders_routes import orders_router
from recipes_routes import router as recipes_router
from profile_routes import router as profile_router

from nodes.cs_orders import get_order_details as get_order_details_fn
from nodes.cs_refund import handle_partial_refund_with_image as handle_partial_refund

import asyncio
from utils import db_audit
from utils.chat_history import add_to_history, manage_history_length
from utils.session_manager import get_or_create_session_state, update_session_access, schedule_session_cleanup, get_session_statistics, cleanup_inactive_sessions
import os
try:
    import mysql.connector
except Exception:
    mysql = None

setup_logging()
logger = logging.getLogger(__name__)
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(auth_router)
app.include_router(kakao_router)
app.include_router(cart_router)
app.include_router(upload_router)
app.include_router(orders_router)
app.include_router(profile_router)
app.include_router(recipes_router)

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 세션 관리 시스템 초기화"""
    logger.info("🚀 FastAPI 서버 시작")

    try:
        schedule_session_cleanup(
            interval_minutes=10,
            max_age_minutes=30
        )
        logger.info("✅ 세션 정리 스케줄러 시작됨: 10분 주기, 30분 유지")
    except Exception as e:
        logger.error(f"❌ 세션 정리 스케줄러 시작 실패: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 세션 통계 로깅"""
    logger.info("🛑 FastAPI 서버 종료 중")

    try:
        stats = get_session_statistics()
        logger.info(f"📊 최종 세션 통계: {stats}")

        cleanup_count = cleanup_inactive_sessions(max_age_minutes=0)
        logger.info(f"🧹 종료 시 세션 정리 완료: {cleanup_count}개 세션 제거")
    except Exception as e:
        logger.error(f"❌ 종료 시 세션 정리 실패: {e}")

@app.get("/api/admin/sessions")
async def get_session_info():
    """세션 관리 상태 조회 (개발/디버깅용)"""
    try:
        from utils.session_manager import get_session_info
        import psutil
        import sys

        stats = get_session_statistics()
        sessions = get_session_info()

        memory_info = {}
        try:
            import psutil
            process = psutil.Process()
            mem_info = process.memory_info()
            memory_percent = process.memory_percent()
            memory_info = {
                "rss_mb": round(mem_info.rss / 1024 / 1024, 2),
                "vms_mb": round(mem_info.vms / 1024 / 1024, 2),
                "percent": round(memory_percent, 2),
                "python_objects": len(list(sys.modules.keys()))
            }
            message_suffix = f", 메모리: {round(memory_percent, 1)}%"
        except ImportError:
            memory_info = {"error": "psutil not installed"}
            message_suffix = ""

        return {
            "statistics": stats,
            "sessions": sessions[:10],
            "memory_usage": memory_info,
            "message": f"총 {len(sessions)}개 활성 세션{message_suffix}"
        }
    except Exception as e:
        logger.error(f"세션 정보 조회 실패: {e}")
        return {"error": str(e)}

@app.post("/api/admin/sessions/cleanup")
async def manual_session_cleanup():
    """수동 세션 정리 (개발/디버깅용)"""
    try:
        before_stats = get_session_statistics()
        cleanup_count = cleanup_inactive_sessions(max_age_minutes=30)
        after_stats = get_session_statistics()

        return {
            "before": before_stats,
            "after": after_stats,
            "cleaned": cleanup_count,
            "message": f"{cleanup_count}개 세션 정리 완료"
        }
    except Exception as e:
        logger.error(f"수동 세션 정리 실패: {e}")
        return {"error": str(e)}

def _josa_eul_reul(word: str) -> str:
    if not word:
        return "을"
    ch = word[-1]
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        jong = (code - 0xAC00) % 28
        return "을" if jong != 0 else "를"
    return "을"

async def get_current_user(request: Request):
    """쿠키의 access_token을 직접 검증하여 현재 사용자 ID를 반환합니다.
    런타임 솔트를 사용하므로 프로세스 재시작 시 기존 토큰은 무효화됩니다.
    """
    try:
        import jwt
        from auth_routes import ALGORITHM as _ALG
        from auth_routes import _runtime_secret as _sec
        token = request.cookies.get("access_token")
        if token and token.startswith("Bearer "):
            raw = token[7:]
            payload = jwt.decode(raw, _sec(), algorithms=[_ALG])
            uid = payload.get("sub")
            if uid:
                return uid
    except Exception:
        pass
    return None

async def require_login_for_page(request: Request):
    """페이지 진입용: 비로그인 시 로그인 페이지로 리다이렉트"""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url=f"/login?next={request.url.path}", status_code=303)
    return user

# (선택) API 전용: 비로그인 시 401
async def require_login_for_api(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


@app.get("/", response_class=HTMLResponse)
async def get_landing_page(request: Request):
    current_user = await get_current_user(request)
    return templates.TemplateResponse("landing.html", {
        "request": request,
        "current_user": current_user
    })

@app.get("/chat", response_class=HTMLResponse)
async def get_chat_page(request: Request):
    current_user = await get_current_user(request)
    
    if not current_user:
        return RedirectResponse(url=f"/login?next=/chat", status_code=303)
    
    display_name = None
    try:
        if current_user:
            display_name = _get_user_display_name(current_user) or str(current_user)
    except Exception:
        display_name = str(current_user) # if current_user else None
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "current_user": current_user,
        "name": display_name
    })

def _get_user_display_name(user_id: str) -> str | None:
    """userinfo_tbl에서 사용자 이름을 조회합니다. 실패 시 None.
    환경변수(DB_HOST, DB_USER, DB_PASSWORD/DB_PASS, DB_NAME)로 접속합니다.
    """
    try:
        host = os.getenv("DB_HOST", "127.0.0.1")
        user = os.getenv("DB_USER", "qook_user")
        password = os.getenv("DB_PASSWORD", os.getenv("DB_PASS", "qook_pass"))
        database = os.getenv("DB_NAME", "qook_chatbot")
        port = int(os.getenv("DB_PORT", "3306"))
        conn = mysql.connector.connect(host=host, user=user, password=password, database=database, port=port)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT name FROM userinfo_tbl WHERE user_id=%s LIMIT 1", (user_id,))
                row = cur.fetchone()
                if row and row[0]:
                    return str(row[0])
        finally:
            if conn and conn.is_connected():
                conn.close()
    except Exception:
        return None
    return None

from time import time

LAST_USER_MSG   = {}
LAST_USER_RESP  = {}
LAST_USER_CS    = {}

REFUND_KEYWORDS = ("환불", "교환", "반품")


@app.post("/api/chat/vision")
async def chat_vision_api(
    message: str = Form(...),
    user_id: str = Form(...),
    session_id: str = Form(""),
    image: UploadFile = File(...)
):
    """비전 AI 기반 레시피 검색 API"""
    try:
        image_content = await image.read()
        import base64
        image_base64 = base64.b64encode(image_content).decode('utf-8')
        image_data = f"data:{image.content_type};base64,{image_base64}"

        state = ChatState(
            user_id=user_id,
            session_id=session_id or str(uuid.uuid4()),
            query=message,
            image=image_data,
            vision_mode=True
        )

        try:
            if state.session_id:
                db_audit.ensure_chat_session(state.user_id, state.session_id, status='active')
                db_audit.timeout_inactive_sessions(10)
                db_audit.complete_other_sessions(state.user_id, state.session_id)
                db_audit.ensure_userlog_for_session(state.user_id, state.session_id)
                if state.query:
                    db_audit.insert_history(state.session_id, 'user', f"{state.query} [이미지 포함]")
        except Exception:
            pass

        final_state = run_workflow(state)

        if isinstance(final_state, dict):
            converted_state = ChatState(user_id=final_state.get('user_id', 'anonymous'))
            for key, value in final_state.items():
                if hasattr(converted_state, key):
                    setattr(converted_state, key, value)
            final_state = converted_state

        latest_cart_state = cart_order.view_cart(final_state)
        final_state.update(latest_cart_state)

        response_text = f"{len(final_state.recipe['results'])}개의 레시피를 찾았습니다."

        if getattr(state, 'quick_analysis', False):
            food_analysis = getattr(final_state, 'food_analysis', {})
            food_name = food_analysis.get('food_name')
            if food_name:
                response_text = food_name

        response_payload = {
            'session_id': final_state.session_id or state.session_id,
            'user_id': final_state.user_id,
            'response': response_text,
            'cart': final_state.cart,
            'search': final_state.search,
            'recipe': final_state.recipe,
            'order': final_state.order,
            'cs': getattr(final_state, 'cs', {}),
            'metadata': {'session_id': final_state.session_id or state.session_id}
        }

        try:
            if state.session_id and response_text:
                db_audit.insert_history(state.session_id, 'bot', response_text)
        except Exception:
            pass

        return JSONResponse(content=jsonable_encoder(response_payload))

    except Exception as e:
        logger.error(f"Vision Chat API Error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "비전 채팅 처리 중 서버 오류 발생"})

@app.post("/api/chat")
async def chat_api(request: Request):
    """메인 챗봇 API 엔드포인트 (메시지 기반 상호작용)"""
    try:
        data = await request.json()

        user_id = data.get('user_id', 'anonymous')
        session_id = data.get('session_id')
        message = data.get('message', '')

        state = get_or_create_session_state(user_id, session_id)
        state.query = message

        if data.get('image'):
            state.image = data.get('image')
        if data.get('type') == 'vision_recipe':
            state.vision_mode = True
        if data.get('quick_analysis'):
            state.quick_analysis = True

        import random
        if random.randint(1, 50) == 1:
            try:
                cleanup_count = cleanup_inactive_sessions(max_age_minutes=30)
                if cleanup_count > 0:
                    logger.info(f"🧹 자동 세션 정리: {cleanup_count}개 세션 제거")
            except Exception as e:
                logger.error(f"자동 세션 정리 실패: {e}")
        
        logger.info(f"Session State: User '{state.user_id}', Session '{state.session_id}', History: {len(state.conversation_history)} messages")

        logger.info(f"Chat API Request: User '{state.user_id}', Query: '{state.query}'")

        try:
            if state.session_id:
                db_audit.ensure_chat_session(state.user_id, state.session_id, status='active')
                db_audit.timeout_inactive_sessions(10)
                db_audit.complete_other_sessions(state.user_id, state.session_id)
                db_audit.ensure_userlog_for_session(state.user_id, state.session_id)
                if state.query:
                    db_audit.insert_history(state.session_id, 'user', state.query)
        except Exception:
            pass

        msg = (state.query or "").strip()
        msg_norm = " ".join(msg.split())
        now = time()
        bypass_dedup = any(k in msg_norm for k in REFUND_KEYWORDS)

        if not bypass_dedup:
            prev = LAST_USER_MSG.get(state.user_id)
            if prev:
                prev_msg, prev_ts = prev
                if msg_norm == prev_msg and (now - prev_ts) < 120:
                    last_resp_text = LAST_USER_RESP.get(state.user_id) or "무엇을 도와드릴까요?"
                    last_cs_payload = LAST_USER_CS.get(state.user_id) or {}
                    return JSONResponse(content={
                        'session_id': state.session_id,
                        'user_id': state.user_id,
                        'response': last_resp_text,
                        'cart': {},
                        'search': {},
                        'recipe': {},
                        'order': {},
                        'cs': last_cs_payload,
                        'metadata': {'session_id': state.session_id}
                    })

        add_to_history(state, 'user', state.query,
                        message_type='text',
                        intent=state.route.get("target", "unknown"),
                        slots=state.slots,
                        rewrite=state.rewrite,
                        search=state.search,
                        cart=state.cart)

        final_state = run_workflow(state)

        if isinstance(final_state, dict):
            converted_state = ChatState(user_id=final_state.get('user_id', 'anonymous'))
            for key, value in final_state.items():
                if hasattr(converted_state, key):
                    setattr(converted_state, key, value)
            final_state = converted_state

        latest_cart_state = cart_order.view_cart(final_state)
        final_state.update(latest_cart_state)

        if not getattr(final_state, 'session_id', None):
            final_state.session_id = state.session_id

        response_text = final_state.meta.get("final_message")

        if not response_text and hasattr(final_state, 'response') and final_state.response:
            response_text = final_state.response
            logger.info(f"Using final_state.response: {response_text}")
        else:
            logger.info(f"final_state.response not ofund or empty. hasattr: {hasattr(final_state, 'response')}, value: {getattr(final_state, 'response', None)}")
        if not response_text:
            cart_meta = (final_state.meta.get("cart")
                            or getattr(final_state, "cart_meta", None))
            if cart_meta and cart_meta.get("last_action") in ("add", "bulk_add"):
                added = cart_meta.get("added_items") or cart_meta.get("items") or []
                if len(added) == 1:
                    p = added[0]
                    name = p.get("name") or p.get("product_name") or "상품"
                    qty  = int(p.get("quantity") or p.get("qty") or 1)
                    response_text = f"{name}{_josa_eul_reul(name)} {qty}개 장바구니에 담았습니다."
                elif len(added) > 1:
                    total_qty = sum(int(x.get("quantity") or x.get("qty") or 1) for x in added)
                    response_text = f"{len(added)}개의 상품(총 {total_qty}개)을 장바구니에 담았습니다."

            if not response_text and final_state.meta.get("intent") in ("cart_add", "cart_bulk_add"):
                name = (final_state.slots.get("product_name")
                        or final_state.slots.get("product")
                        or final_state.meta.get("product_name"))
                qty = int(final_state.slots.get("quantity") or 1)
                if name:
                    response_text = f"{name}{_josa_eul_reul(name)} {qty}개 장바구니에 담았습니다."

        def _as_dict(obj):
            return obj if isinstance(obj, dict) else getattr(obj, "__dict__", {}) or {}

        state_dict = _as_dict(final_state)
        handoff = _as_dict(state_dict.get("handoff"))

        if not response_text and handoff.get("status") == "sent":
            response_text = handoff.get("message")

        if not response_text:
            response_text = state_dict.get("message")

        if not response_text:
            cs_payload = getattr(final_state, "cs", {}) or {}
            ans = cs_payload.get("answer") or {}
            if ans.get("text"):
                response_text = ans["text"]
            elif cs_payload.get("message"):
                response_text = cs_payload["message"]
            elif final_state.meta.get("cs_message"):
                response_text = final_state.meta["cs_message"]

        if not response_text and final_state.meta.get("order_message"):
            response_text = final_state.meta.get("order_message")

        if not response_text and hasattr(final_state, 'search') and final_state.search:
            candidates = final_state.search.get("candidates", [])
            search_error = final_state.search.get("error")

            if len(candidates) > 0:
                response_text = f"{len(candidates)}개의 상품을 찾았습니다."
            elif search_error:
                response_text = search_error
            else:
                response_text = "해당 상품을 찾을 수 없습니다."

        if not response_text and final_state.recipe.get("results"):
            response_text = f"{len(final_state.recipe['results'])}개의 레시피를 찾았습니다."
        if not response_text:
            response_text = "무엇을 도와드릴까요?"

        cs_payload_out = getattr(final_state, 'cs', {}) or {}

        add_to_history(final_state, "assistant", response_text,
                        message_type='response',
                        intent=final_state.route.get("target", "unknown"),
                        slots=final_state.slots,
                        search=final_state.search,
                        cart=final_state.cart,
                        meta=final_state.meta)
        
        manage_history_length(final_state, max_messages=15)

        if final_state.session_id:
            update_session_access(final_state.user_id, final_state.session_id)

        response_payload = {
            'session_id': final_state.session_id or state.session_id,
            'user_id': final_state.user_id,
            'response': response_text,
            'cart': final_state.cart,
            'search': final_state.search,
            'recipe': final_state.recipe,
            'order': final_state.order,
            'cs': cs_payload_out,
            'metadata': {'session_id': final_state.session_id or state.session_id}
        }

        LAST_USER_MSG[state.user_id]  = (msg_norm, now)
        LAST_USER_RESP[state.user_id] = response_text
        LAST_USER_CS[state.user_id]   = cs_payload_out

        if (cs_payload_out.get("orders") and len(cs_payload_out.get("orders")) > 0) \
           or (cs_payload_out.get("ticket") and cs_payload_out["ticket"].get("ticket_id")):
            LAST_USER_MSG.pop(state.user_id, None)
            LAST_USER_RESP.pop(state.user_id, None)
            LAST_USER_CS.pop(state.user_id, None)

        try:
            if state.session_id:
                step = final_state.meta.get('next_step') or 'END'
                route_type = 'cs' if (final_state.route.get('target') in ('cs_intake','faq_policy_rag','handoff')) else 'search_order'
                qd = {"query": final_state.query, "slots": final_state.slots, "rewrite": final_state.rewrite}
                cd = {"items": (final_state.cart or {}).get('items', []), "subtotal": (final_state.cart or {}).get('subtotal'), "total": (final_state.cart or {}).get('total')}
                db_audit.upsert_chat_state(state.session_id, step, route_type, qd, cd)
                if response_text:
                    db_audit.insert_history(state.session_id, 'bot', response_text)
        except Exception:
            pass

        return JSONResponse(content=jsonable_encoder(response_payload))

    except Exception as e:
        logger.error(f"Chat API Error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "서버 내부 오류"})


class CartUpdateRequest(BaseModel):
    user_id: str
    product_name: str
    quantity: int

@app.post("/api/cart/update")
async def update_cart_api(request: CartUpdateRequest):
    """장바구니 수량 변경 및 삭제 전용 API"""
    try:
        updated_cart_state = cart_order.update_cart_item(
            user_id=request.user_id,
            product_name=request.product_name,
            quantity=request.quantity
        )
        if updated_cart_state.get("error"):
            return JSONResponse(status_code=400, content={"detail": updated_cart_state["error"]})
        return JSONResponse(content=updated_cart_state)
    except Exception as e:
        logger.error(f"Cart Update API Error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "장바구니 업데이트 중 서버 오류 발생"})

@app.get("/login", response_class=HTMLResponse)
async def get_login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def get_register_page(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})

@app.get("/membership", response_class=HTMLResponse)
async def get_membership_page(request: Request):
    current_user = await get_current_user(request)
    return templates.TemplateResponse("auth/membership.html", {"request": request, "current_user": current_user})

@app.get("/auth/status")
async def get_auth_status(request: Request):
    try:
        current_user = await get_current_user(request)
        return {
            "authenticated": current_user is not None,
            "user_id": current_user
        }
    except Exception as e:
        logger.error(f"Auth status check error: {e}")
        return {"authenticated": False, "user_id": None}

@app.get("/mypage", response_class=HTMLResponse)
async def get_mypage(request: Request):
    current_user = await get_current_user(request)

    return templates.TemplateResponse("mypage.html", {
        "request": request,
        "current_user": current_user
    })

class BulkCartAddRequest(BaseModel):
    user_id: str
    products: List[dict]

@app.post("/api/cart/bulk-add")
async def bulk_add_to_cart_api(request: BulkCartAddRequest):
    try:
        result = cart_order.bulk_add_to_cart(
            user_id=request.user_id,
            products=request.products
        )
        if result.get("error"):
            return JSONResponse(status_code=400, content={"detail": result["error"]})
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Bulk Cart Add API Error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "일괄 담기 중 서버 오류 발생"})

class OrderDetailsRequest(BaseModel):
    user_id: str
    order_code: str

@app.post("/api/orders/details")
async def get_order_details_api(req: OrderDetailsRequest):
    try:
        details = get_order_details_fn(req.order_code, user_id=req.user_id)
        if not details or not details.get("items"):
            return JSONResponse(status_code=404, content={"detail": "주문 상세 없음"})
        return JSONResponse(content=details)
    except Exception as e:
        logger.error(f"Order details API error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "주문 상세 조회 중 오류"})

@app.post("/api/cs/evidence")
async def cs_evidence_api(
    image: UploadFile = File(...),
    user_id: str = Form(...),
    order_code: str = Form(...),
    product: str = Form(...),
    quantity: int = Form(1)
):
    """
    주문 상세의 특정 상품 행에서 '사진 업로드' → Vision 분석 → 부분 환불 자동 접수
    """
    try:
        save_dir = os.path.join("uploads", "evidence")
        os.makedirs(save_dir, exist_ok=True)
        filename = f"{order_code}_{uuid.uuid4().hex[:8]}_{image.filename}"
        save_path = os.path.join(save_dir, filename)


        with open(save_path, "wb") as f:
            f.write(await image.read())

        state = ChatState(user_id=user_id, query=f"Evidence for {product}", attachments=[save_path])
        result = handle_partial_refund(
            state,
            order_code=order_code,
            product=product,
            request_qty=int(quantity or 1),
        )
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"CS evidence API error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "증빙 이미지 처리 중 오류"})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)
