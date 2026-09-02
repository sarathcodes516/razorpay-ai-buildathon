import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.negotiation_sessions import create_session, get_session, append_turn, close_session
from app.core.mandate_service import verify_mandate, create_payment_mandate
from app.core.agent_auth import require_signed_agent
from app.agents.negotiator_agent import generate_b2b_merchant_turn
from app.agents.buyer_agent import generate_buyer_turn
from app.models.cart import CartMandate, CartItem
from app.core.bounds_engine import check_against_mandate
from app.core.pending_approvals import store_pending
from app.routers.mandate import MOCK_DB
from app.integrations.razorpay_client import create_order

router = APIRouter()

MAX_TURNS = 3  # 3 turns = up to 6 LLM calls, ~60-90s total — keeps demo snappy


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class NegotiateRequest(BaseModel):
    mandate_id: str
    procurement_goal: str


class StartSessionRequest(BaseModel):
    mandate_id: str
    merchant_agent_id: str
    procurement_goal: str


class TurnRequest(BaseModel):
    session_id: str
    buyer_message: str
    requested_items: list[dict]
    requested_discount_pct: float


# ---------------------------------------------------------------------------
# NDJSON helpers
# ---------------------------------------------------------------------------

def _event(payload: dict) -> str:
    return json.dumps(payload) + "\n"


def _turn_event(role: str, data: dict) -> str:
    return _event({"type": "turn", "role": role, "data": data})


def _status_event(status: str, **extra) -> str:
    return _event({"type": "status", "status": status, **extra})


def _log_event(msg: str) -> str:
    return _event({"type": "log", "message": msg})


# ---------------------------------------------------------------------------
# Streaming negotiate endpoint
# ---------------------------------------------------------------------------

@router.post("/api/gateway/negotiate")
async def negotiate(req: NegotiateRequest):
    """
    Stream the full agent-to-agent negotiation as NDJSON.
    Each line is a JSON event:
      {"type":"log",    "message":"..."}
      {"type":"turn",   "role":"buyer"|"merchant", "data":{...}}
      {"type":"status", "status":"done"|"error", "action":"...",
                        "transcript":[...], "final_cart":{...}, "audit_trail":{...}}
    """
    mandate = MOCK_DB.get(req.mandate_id)
    if not mandate:
        raise HTTPException(404, "mandate_not_found")
    ok, reason = verify_mandate(mandate)
    if not ok:
        raise HTTPException(401, f"mandate_invalid: {reason}")

    async def stream() -> AsyncGenerator[str, None]:
        import asyncio

        session_id = create_session(
            req.mandate_id, "merchant_souledstole_01", req.procurement_goal
        )
        transcript = []
        history = ""
        final_cart = None
        audit_trail = None
        outcome = "NO_DEAL"

        yield _log_event(f"Session {session_id} opened. Starting negotiation…")

        for turn_num in range(MAX_TURNS):
            session = get_session(session_id)
            if not session or session["status"] != "open":
                break

            # --- Buyer turn (blocking LLM call — run in thread so we can yield) ---
            yield _log_event(f"Turn {turn_num + 1}: buyer agent thinking…")
            loop = asyncio.get_event_loop()
            buyer_res = await loop.run_in_executor(
                None, generate_buyer_turn, history, req.procurement_goal, req.mandate_id
            )

            buyer_msg = buyer_res.get("message", req.procurement_goal)
            buyer_action = buyer_res.get("action", "PROPOSE")
            buyer_discount = float(buyer_res.get("requested_discount_pct", 10.0))
            buyer_items = buyer_res.get("requested_items", [])

            buyer_turn_data = {
                "message": buyer_msg,
                "thought_process": buyer_res.get("thought_process", ""),
                "action": buyer_action,
                "requested_discount_pct": buyer_discount,
            }
            transcript.append({"role": "buyer", "data": buyer_turn_data})
            append_turn(session_id, {
                "role": "buyer",
                "message": buyer_msg,
                "requested_discount_pct": buyer_discount,
            })
            yield _turn_event("buyer", buyer_turn_data)

            if buyer_action == "ACCEPT":
                outcome = "EXECUTE"
                close_session(session_id, "CLOSED_ACCEPTED")
                break

            # --- Merchant turn ---
            yield _log_event(f"Turn {turn_num + 1}: merchant agent evaluating…")
            history_str = _render_history(get_session(session_id)["turns"])
            merchant_res = await loop.run_in_executor(
                None, generate_b2b_merchant_turn, history_str, buyer_msg, turn_num
            )
            append_turn(session_id, {"role": "merchant", "data": merchant_res})

            merchant_msg = merchant_res.get("message", "")
            merchant_action = merchant_res.get("action", "COUNTER")
            merchant_discount = float(merchant_res.get("offered_discount_pct", 0.0))

            merchant_turn_data = {
                "message": merchant_msg,
                "thought_process": merchant_res.get("thought_process", ""),
                "action": merchant_action,
                "offered_discount_pct": merchant_discount,
            }
            transcript.append({"role": "merchant", "data": merchant_turn_data})
            yield _turn_event("merchant", merchant_turn_data)

            history += (
                f"\nBuyer: {buyer_msg}\n"
                f"Merchant: {merchant_msg} (offering {merchant_discount}% off)\n"
            )

            if merchant_action == "ACCEPT":
                items = merchant_res.get("approved_items", []) or buyer_items
                subtotal = sum(float(i.get("price", 0)) * int(i.get("qty", 1)) for i in items)
                final_amount = subtotal * (1 - merchant_discount / 100)
                cart = CartMandate(
                    cart_id=f"cart_b2b_{uuid.uuid4().hex[:8]}",
                    mandate_id=req.mandate_id,
                    items=[CartItem(**i) for i in items] if items else [],
                    subtotal=subtotal,
                    discount_pct=merchant_discount,
                    final_amount=final_amount,
                )
                _, bounds_action, audit = check_against_mandate(cart, mandate)
                final_cart = cart.model_dump()
                audit_trail = audit
                outcome = bounds_action
                close_session(session_id, "CLOSED_ACCEPTED")
                break

            if merchant_action == "REJECT":
                outcome = "REJECTED"
                close_session(session_id, "CLOSED_REJECTED")
                break

        yield _status_event(
            "done",
            action=outcome,
            mandate_id=req.mandate_id,
            transcript=transcript,
            final_cart=final_cart,
            audit_trail=audit_trail,
        )

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"X-Content-Type-Options": "nosniff"},
    )


# ---------------------------------------------------------------------------
# Low-level signed A2A endpoints (unchanged)
# ---------------------------------------------------------------------------

@router.post("/api/gateway/session/start", dependencies=[Depends(require_signed_agent)])
def start_session(req: StartSessionRequest):
    mandate = MOCK_DB.get(req.mandate_id)
    if not mandate:
        raise HTTPException(404, "mandate_not_found")
    ok, reason = verify_mandate(mandate)
    if not ok:
        raise HTTPException(401, f"mandate_invalid: {reason}")
    session_id = create_session(req.mandate_id, req.merchant_agent_id, req.procurement_goal)
    return {"session_id": session_id, "status": "open"}


@router.post("/api/gateway/turn", dependencies=[Depends(require_signed_agent)])
def gateway_turn(req: TurnRequest):
    session = get_session(req.session_id)
    if not session or session["status"] != "open":
        raise HTTPException(404, "session_not_open")
    if len(session["turns"]) >= MAX_TURNS:
        close_session(req.session_id, "TIMEOUT")
        raise HTTPException(409, "negotiation_turn_limit_reached")

    history_str = _render_history(session["turns"])
    merchant_res = generate_b2b_merchant_turn(history_str, req.buyer_message, len(session["turns"]))

    append_turn(req.session_id, {
        "role": "buyer",
        "message": req.buyer_message,
        "requested_discount_pct": req.requested_discount_pct,
    })
    append_turn(req.session_id, {"role": "merchant", "data": merchant_res})

    result = {"merchant_response": merchant_res, "turn_count": len(session["turns"])}

    if merchant_res.get("action") == "ACCEPT":
        items = merchant_res.get("approved_items", [])
        subtotal = sum(i["price"] * i["qty"] for i in items)
        discount = float(merchant_res.get("offered_discount_pct", 0.0))
        final_amount = subtotal * (1 - discount / 100)
        cart = CartMandate(
            cart_id=f"cart_b2b_{uuid.uuid4().hex[:8]}",
            mandate_id=session["mandate_id"],
            items=[CartItem(**i) for i in items],
            subtotal=subtotal,
            discount_pct=discount,
            final_amount=final_amount,
        )
        mandate = MOCK_DB[session["mandate_id"]]
        _, action, audit = check_against_mandate(cart, mandate)
        result.update({"final_cart": cart.model_dump(), "bounds_action": action, "audit_trail": audit})
        if action == "EXECUTE":
            pm = create_payment_mandate(cart, session["mandate_id"])
            order = create_order(cart.final_amount, pm.payment_mandate_id)
            result["razorpay_order"] = order
            result["payment_mandate"] = pm.model_dump()
        elif action == "ESCALATE":
            store_pending(cart.cart_id, cart, session["mandate_id"], audit)
        close_session(req.session_id, "CLOSED_ACCEPTED")
    elif merchant_res.get("action") == "REJECT":
        close_session(req.session_id, "CLOSED_REJECTED")

    return result


def _render_history(turns: list) -> str:
    lines = []
    for t in turns:
        if t["role"] == "buyer":
            lines.append(f"Buyer: {t['message']} (requesting {t['requested_discount_pct']}% off)")
        else:
            d = t["data"]
            lines.append(f"Merchant: {d.get('message')} (offering {d.get('offered_discount_pct')}% off)")
    return "\n".join(lines)
