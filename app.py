from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import logging, uuid, uvicorn, os
from typing import List
from fastapi import UploadFile, File, Form  # [ADDED]
from fastapi.encoders import jsonable_encoder

from config import config
from utils.logging_config import setup_logging
from graph_interfaces import ChatState
from workflow import run_workflow
from nodes import cart_order
from auth_routes import auth_router, verify_token
from auth_system.kakao_address import kakao_router
from cart_routes import router as cart_router
from upload_routes import router as upload_router
from orders_routes import orders_router

# [ADDED] CS/RAG 유틸 임포트
from nodes.cs_orders import get_order_details as get_order_details_fn
from nodes.cs_refund import handle_partial_refund_with_image as handle_partial_refund

import asyncio
from utils import db_audit

setup_logging()
logger = logging.getLogger(__name__)
app = FastAPI()

# 정적/템플릿
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 인증 라우터 등록
app.include_router(auth_router)
app.include_router(kakao_router)
app.include_router(cart_router)
app.include_router(upload_router)
app.include_router(orders_router)

# ---------------- 조사(을/를) 헬퍼 ----------------
def _josa_eul_reul(word: str) -> str:
    if not word:
        return "을"
    ch = word[-1]
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        jong = (code - 0xAC00) % 28
        return "을" if jong != 0 else "를"
    return "을"

# 인증 상태 확인 유틸
async def get_current_user(request: Request):
    try:
        token = request.cookies.get("access_token")
        if token and token.startswith("Bearer "):
            token = token[7:]
            return verify_token(token)
    except:
        pass
    return None

# 랜딩/채팅 페이지
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
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "current_user": current_user
    })

# # 메인 챗봇 API
# @app.post("/api/chat")
# async def chat_api(request: Request):
#     """메인 챗봇 API 엔드포인트 (메시지 기반 상호작용)"""
#     try:
#         data = await request.json()
#         state = ChatState(
#             user_id=data.get('user_id', 'anonymous'),
#             session_id=data.get('session_id'),
#             query=data.get('message', '')
#         )
#         logger.info(f"Chat API Request: User '{state.user_id}', Query: '{state.query}'")

#         final_state = run_workflow(state)

#         if isinstance(final_state, dict):
#             converted_state = ChatState(user_id=final_state.get('user_id', 'anonymous'))
#             for key, value in final_state.items():
#                 if hasattr(converted_state, key):
#                     setattr(converted_state, key, value)
#             final_state = converted_state

#         latest_cart_state = cart_order.view_cart(final_state)
#         final_state.update(latest_cart_state)

#         response_text = final_state.meta.get("final_message")
#         if not response_text:
#             cart_meta = (final_state.meta.get("cart")
#                          or getattr(final_state, "cart_meta", None))
#             if cart_meta and cart_meta.get("last_action") in ("add", "bulk_add"):
#                 added = cart_meta.get("added_items") or cart_meta.get("items") or []
#                 if len(added) == 1:
#                     p = added[0]
#                     name = p.get("name") or p.get("product_name") or "상품"
#                     qty  = int(p.get("quantity") or p.get("qty") or 1)
#                     response_text = f"{name}{_josa_eul_reul(name)} {qty}개 장바구니에 담았습니다."
#                 elif len(added) > 1:
#                     total_qty = sum(int(x.get("quantity") or x.get("qty") or 1) for x in added)
#                     response_text = f"{len(added)}개의 상품(총 {total_qty}개)을 장바구니에 담았습니다."

#             if not response_text and final_state.meta.get("intent") in ("cart_add", "cart_bulk_add"):
#                 name = (final_state.slots.get("product_name")
#                         or final_state.slots.get("product")
#                         or final_state.meta.get("product_name"))
#                 qty = int(final_state.slots.get("quantity") or 1)
#                 if name:
#                     response_text = f"{name}{_josa_eul_reul(name)} {qty}개 장바구니에 담았습니다."

#         # ✅ CS/RAG 응답 우선 반영
#         if not response_text:
#             cs_payload = getattr(final_state, "cs", {}) or {}
#             ans = cs_payload.get("answer") or {}
#             if ans.get("text"):
#                 response_text = ans["text"]
#             elif cs_payload.get("message"):
#                 response_text = cs_payload["message"]
#             elif final_state.meta.get("cs_message"):
#                 response_text = final_state.meta["cs_message"]

#         if not response_text and final_state.meta.get("order_message"):
#             response_text = final_state.meta.get("order_message")
#         if not response_text and final_state.search.get("candidates"):
#             response_text = f"{len(final_state.search['candidates'])}개의 상품을 찾았습니다."
#         if not response_text and final_state.recipe.get("results"):
#             response_text = f"{len(final_state.recipe['results'])}개의 레시피를 찾았습니다."
#         if not response_text:
#             response_text = "무엇을 도와드릴까요?"

#         response_payload = {
#             'session_id': final_state.session_id,
#             'user_id': final_state.user_id,
#             'response': response_text,
#             'cart': final_state.cart,
#             'search': final_state.search,
#             'recipe': final_state.recipe,
#             'order': final_state.order,
#             'cs': getattr(final_state, 'cs', {}),
#             'metadata': {'session_id': final_state.session_id}
#         }
#         return JSONResponse(content=response_payload)

#     except Exception as e:
#         logger.error(f"Chat API Error: {e}", exc_info=True)
#         return JSONResponse(status_code=500, content={"detail": "서버 내부 오류"})

# --- 파일 상단 어딘가에 전역 캐시 준비 ---
from time import time

LAST_USER_MSG   = {}   # {user_id: (msg_norm, ts)}
LAST_USER_RESP  = {}   # {user_id: last_response_text}
LAST_USER_CS    = {}   # {user_id: last_cs_payload}  # <-- cs 페이로드도 기억

REFUND_KEYWORDS = ("환불", "교환", "반품")  # 중복 억제 우회 키워드


# 메인 챗봇 API
@app.post("/api/chat")
async def chat_api(request: Request):
    """메인 챗봇 API 엔드포인트 (메시지 기반 상호작용)"""
    try:
        data = await request.json()
        state = ChatState(
            user_id=data.get('user_id', 'anonymous'),
            session_id=data.get('session_id'),
            query=data.get('message', '')
        )
        logger.info(f"Chat API Request: User '{state.user_id}', Query: '{state.query}'")
        # 비침투 로깅 훅: 세션/유저로그/유저 메시지 저장
        try:
            if state.session_id:
                asyncio.create_task(_audit_chat_enter(state, request))
                if state.query:
                    asyncio.create_task(db_audit.insert_history(state.session_id, 'user', state.query))
        except Exception:
            pass

        # ---------- 중복 발화 억제(수정본) ----------
        msg = (state.query or "").strip()
        msg_norm = " ".join(msg.split())
        now = time()
        bypass_dedup = any(k in msg_norm for k in REFUND_KEYWORDS)  # 환불 관련은 항상 우회

        if not bypass_dedup:
            prev = LAST_USER_MSG.get(state.user_id)
            if prev:
                prev_msg, prev_ts = prev
                if msg_norm == prev_msg and (now - prev_ts) < 120:  # 2분 안에 완전 동일
                    # 빠른 재전달: 최소한 직전 CS 페이로드도 같이 돌려준다.
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
        # -------------------------------------------

        # 정상 워크플로우 실행
        final_state = run_workflow(state)

        if isinstance(final_state, dict):
            converted_state = ChatState(user_id=final_state.get('user_id', 'anonymous'))
            for key, value in final_state.items():
                if hasattr(converted_state, key):
                    setattr(converted_state, key, value)
            final_state = converted_state

        latest_cart_state = cart_order.view_cart(final_state)
        final_state.update(latest_cart_state)

        # 세션 ID 일관성 보장: 워크플로우가 세션을 세팅하지 않았다면 입력 세션을 유지
        if not getattr(final_state, 'session_id', None):
            final_state.session_id = state.session_id

        # 응답 메시지 구성
        response_text = final_state.meta.get("final_message")
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

        # ✅ CS/RAG 응답 우선 반영
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
        if not response_text and final_state.search.get("candidates"):
            response_text = f"{len(final_state.search['candidates'])}개의 상품을 찾았습니다."
        if not response_text and final_state.recipe.get("results"):
            response_text = f"{len(final_state.recipe['results'])}개의 레시피를 찾았습니다."
        if not response_text:
            response_text = "무엇을 도와드릴까요?"

        # 클라이언트로 보낼 페이로드
        cs_payload_out = getattr(final_state, 'cs', {}) or {}

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

        # ---------- 중복 억제 캐시 갱신/초기화 ----------
        LAST_USER_MSG[state.user_id]  = (msg_norm, now)
        LAST_USER_RESP[state.user_id] = response_text
        LAST_USER_CS[state.user_id]   = cs_payload_out  # 다음 회차 빠른 재전달 대비

        # 환불 플로우가 시작(주문 선택 UI)되거나 완료(티켓 생성)된 경우에는 캐시 즉시 초기화
        if (cs_payload_out.get("orders") and len(cs_payload_out.get("orders")) > 0) \
           or (cs_payload_out.get("ticket") and cs_payload_out["ticket"].get("ticket_id")):
            LAST_USER_MSG.pop(state.user_id, None)
            LAST_USER_RESP.pop(state.user_id, None)
            LAST_USER_CS.pop(state.user_id, None)
        # -----------------------------------------------

        # 비침투 로깅 훅: 최종 상태/봇 메시지 저장
        try:
            if state.session_id:
                step = final_state.meta.get('next_step') or 'END'
                route_type = 'cs' if (final_state.route.get('target') in ('cs','handoff')) else 'search_order'
                qd = {"query": final_state.query, "slots": final_state.slots, "rewrite": final_state.rewrite}
                cd = {"items": (final_state.cart or {}).get('items', []), "subtotal": (final_state.cart or {}).get('subtotal'), "total": (final_state.cart or {}).get('total')}
                asyncio.create_task(db_audit.upsert_chat_state(state.session_id, step, route_type, qd, cd))
                if response_text:
                    asyncio.create_task(db_audit.insert_history(state.session_id, 'bot', response_text))
        except Exception:
            pass

        return JSONResponse(content=jsonable_encoder(response_payload))

    except Exception as e:
        logger.error(f"Chat API Error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "서버 내부 오류"})



# --- 장바구니 수량 변경 API ---
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

# --- 인증/회원 관련 페이지 & API ---
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
    # if not current_user:
    #     return templates.TemplateResponse("auth/login.html", {"request": request})
    return templates.TemplateResponse("mypage.html", {
        "request": request,
        "current_user": current_user
    })

@app.get("/app", response_class=HTMLResponse)
async def get_app_layout(request: Request):
    current_user = await get_current_user(request)
    return templates.TemplateResponse("app-layout.html", {
        "request": request,
        "current_user": current_user,
        "page_title": "통합 앱"
    })

@app.get("/tab", response_class=HTMLResponse)
async def get_tab_layout(request: Request):
    current_user = await get_current_user(request)
    return templates.TemplateResponse("tab-layout.html", {
        "request": request,
        "current_user": current_user,
        "page_title": "Qook 서비스"
    })


# [MERGE] --- 일괄 담기 API ---
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

# [ADDED] --- 주문 상세 조회 API (프런트의 /api/orders/details 호출용)
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

# [UPDATED] --- CS 증빙 이미지 업로드 & 자동 판정 API (부분 환불 대응)
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
        # 저장 경로
        save_dir = os.path.join("uploads", "evidence")
        os.makedirs(save_dir, exist_ok=True)
        filename = f"{order_code}_{uuid.uuid4().hex[:8]}_{image.filename}"
        save_path = os.path.join(save_dir, filename)


        with open(save_path, "wb") as f:
            f.write(await image.read())

        # 분석/접수 (🎯 부분 환불용 새 함수 호출)
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


# --- 내부: 비침투 로깅 도우미 ---
async def _audit_chat_enter(state: ChatState, request: Request):
    try:
        db_audit.ensure_chat_session(state.user_id, state.session_id, status='active')
        # db_audit.ensure_userlog_for_session(state.user_id, state.session_id)
    except Exception as e:
        logger.warning(f"chat audit 실패: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)
