import json
import uuid
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio

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
from app.services.b2b_settlement import execute_autonomous_settlement

router = APIRouter()

MAX_TURNS = 10  # Plentiful room for CoT agents to settle

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

def _event(payload: dict) -> str:
    return json.dumps(payload) + "\n"

def _turn_event(role: str, data: dict) -> str:
    return _event({"type": "turn", "role": role, "data": data})

def _status_event(status: str, **extra) -> str:
    return _event({"type": "status", "status": status, **extra})

def _log_event(msg: str) -> str:
    return _event({"type": "log", "message": msg})


@router.post("/api/gateway/negotiate")
async def negotiate(req: NegotiateRequest):
    mandate = MOCK_DB.get(req.mandate_id)
    if not mandate:
        raise HTTPException(404, "mandate_not_found")
    ok, reason = verify_mandate(mandate)
    if not ok:
        raise HTTPException(401, f"mandate_invalid: {reason}")

    async def stream() -> AsyncGenerator[str, None]:
        session_id = create_session(req.mandate_id, "merchant_souledstole_01", req.procurement_goal)
        transcript = []
        history = ""
        final_cart = None
        audit_trail = None
        outcome = "NO_DEAL"
        last_merchant_tools = None
        last_security_override = False

        yield _log_event(f"Session {session_id} opened. Starting negotiation…")

        for turn_num in range(MAX_TURNS):
            session = get_session(session_id)
            if not session or session["status"] != "open":
                break

            # ---------------------------------------------------------
            # BUYER TURN
            # ---------------------------------------------------------
            yield _log_event(f"Turn {turn_num + 1}: buyer agent thinking…")
            loop = asyncio.get_event_loop()

            # UPDATED CALL: Passes turn_num and MAX_TURNS for the new CoT Buyer
            buyer_res = await loop.run_in_executor(
                None,
                generate_buyer_turn,
                history,
                req.procurement_goal,
                req.mandate_id,
                turn_num + 1,
                MAX_TURNS
            )

            buyer_msg = buyer_res.get("message", req.procurement_goal)
            buyer_action = buyer_res.get("action", "PROPOSE")
            try:
                buyer_discount = float(buyer_res.get("requested_discount_pct", 10.0) or 0.0)
            except (TypeError, ValueError):
                buyer_discount = 10.0
            buyer_items = buyer_res.get("requested_items", [])

            buyer_turn_data = {
                "message": buyer_msg,
                "thought_process": buyer_res.get("thought_process", ""),
                "action": buyer_action,
                "requested_discount_pct": buyer_discount,
                "rationale": buyer_res.get("rationale", ""),
            }
            transcript.append({"role": "buyer", "data": buyer_turn_data})
            append_turn(session_id, {"role": "buyer", "message": buyer_msg, "requested_discount_pct": buyer_discount})
            yield _turn_event("buyer", buyer_turn_data)

            if buyer_action in ["ACCEPT", "REJECT"]:
                # Buyer initiated terminal state
                last_merchant = next(
                    (t["data"] for t in reversed((get_session(session_id) or {}).get("turns", []) or []) if t.get("role") == "merchant"),
                    {},
                )
                items = last_merchant.get("approved_items") or buyer_items or [{"sku": "UNKNOWN_SKU", "qty": 1, "price": 0, "category": "all"}]
                merchant_discount = float(last_merchant.get("offered_discount_pct", 0.0) or 0.0)

                # CRITICAL FIX: Always fetch the true base list price from the catalog
                # even when the Buyer initiates the ACCEPT, preventing double-discounting.
                subtotal = 0.0
                for i in items:
                    qty = int(i.get("qty", 1))
                    sku = i.get("sku", "UNKNOWN_SKU")
                    unit = _true_list_price(sku, float(i.get("price", 0.0) or 0.0))
                    subtotal += unit * qty

                final_amount = round(subtotal * (1.0 - merchant_discount / 100.0), 2)

                cart = CartMandate(
                    cart_id=f"cart_b2b_{uuid.uuid4().hex[:8]}", mandate_id=req.mandate_id,
                    items=[CartItem(**i) for i in items] if items else [],
                    subtotal=subtotal, discount_pct=merchant_discount, final_amount=final_amount,
                )
                _, bounds_action, audit = check_against_mandate(cart, mandate)
                final_cart = cart.model_dump()
                audit_trail = audit
                outcome = bounds_action

                if buyer_action == "ACCEPT":
                    primary_item = (items or [{}])[0]
                    true_base_price = _true_list_price(
                        primary_item.get("sku", "UNKNOWN_SKU"),
                        float(primary_item.get("price", 0.0) or 0.0),
                    )

                    max_transaction = float(
                        getattr(getattr(mandate, "limits", None), "max_per_transaction", 0.0) or 0.0
                    )
                    if max_transaction == 0.0:
                        max_transaction = 10000.0

                    mandate_for_settlement = {
                        "mandate_id": mandate.mandate_id if hasattr(mandate, "mandate_id") else req.mandate_id,
                        "principal": getattr(getattr(mandate, "limits", None), "principal_name", "Corporate Buyer"),
                        "max_per_transaction": max_transaction,
                        "anomaly_discount_threshold": 15.0,
                    }

                    settlement_ok, execution_data, settlement_audit = execute_autonomous_settlement(
                        mandate=mandate_for_settlement, session_id=session_id,
                        buyer_agent_id="buyer_agent_ui", merchant_agent_id="merchant_souledstole_01",
                        sku=primary_item.get("sku", "UNKNOWN_SKU"),
                        qty=int(primary_item.get("qty", 1)),
                        unit_price=true_base_price, discount_pct=merchant_discount,
                        total_amount=final_amount,
                    )

                    if settlement_ok:
                        final_cart["execution"] = execution_data
                        audit_trail = {
                            **(audit or {}),
                            "settlement_audit": settlement_audit,
                            "razorpay_order_id": execution_data.get("razorpay_order_id"),
                            "settlement_signature": execution_data.get("settlement_signature"),
                        }
                        yield _log_event(settlement_audit)
                        outcome = "EXECUTE"
                        yield json.dumps({
                            "type": "EXECUTE_COMPLETE", "execution": execution_data,
                            "bounds_action": bounds_action, "action": outcome,
                        }) + "\n"
                    else:
                        yield _log_event(f"[SETTLEMENT FAILED] {settlement_audit}")
                        outcome = "GATED_VIOLATION"
                        yield json.dumps({
                            "type": "EXECUTE_COMPLETE", "execution": None,
                            "action": outcome, "error_details": settlement_audit,
                        }) + "\n"

                close_session(session_id, "CLOSED_ACCEPTED" if outcome == "EXECUTE" else "CLOSED_REJECTED")
                break

            # ---------------------------------------------------------
            # MERCHANT TURN
            # ---------------------------------------------------------
            yield _log_event(f"Turn {turn_num + 1}: merchant agent evaluating…")
            history_str = _render_history((get_session(session_id) or {}).get("turns", []) or [])

            merchant_res = await loop.run_in_executor(
                None, generate_b2b_merchant_turn, history_str, buyer_msg, turn_num
            )
            append_turn(session_id, {"role": "merchant", "data": merchant_res})

            merchant_msg = merchant_res.get("message", "")
            merchant_action = merchant_res.get("action", "COUNTER")
            merchant_discount = float(merchant_res.get("offered_discount_pct", 0.0))

            camp = merchant_res.get("campaign_check") or {}
            disc = merchant_res.get("discount_engine") or {}
            bundle = merchant_res.get("bundle_proposal_payload") or {}
            is_security_override = bool(merchant_res.get("threat_detected"))

            if camp.get("has_campaign"):
                yield _log_event(
                    f"[TOOL: check_active_campaign] Matched '{camp.get('campaign_name')}' "
                    f"-> {camp.get('discount_pct')}% discount authorized."
                )
            if is_security_override:
                yield _log_event(f"[TOOL: propose_discount] [SECURITY BOUND] {disc.get('audit_note')}")
                yield _log_event(
                    f"[GRACEFUL FAILURE HANDLED] Adversarial prompt injection neutralized. "
                    f"Bounds engine hard-capped to policy maximum: {disc.get('max_allowable_pct')}%."
                )
            elif disc.get("was_capped"):
                yield _log_event(f"[TOOL: propose_discount] [POLICY BOUND] {disc.get('audit_note')}")
            if bundle.get("bundle_available"):
                yield _log_event(
                    f"[TOOL: propose_bundle_addon] Stock liquidation: "
                    f"proposing {bundle['addon']['sku']} bundle at ₹{bundle['addon']['bundle_price']}."
                )

            merchant_turn_data = {
                "message": merchant_msg,
                "thought_process": merchant_res.get("thought_process", ""),
                "action": merchant_action,
                "offered_discount_pct": merchant_discount,
                "tools": {"campaign": camp, "discount_engine": disc, "bundle": bundle},
                "bundle_proposal": merchant_res.get("bundle_proposal"),
                "rationale": merchant_res.get("rationale"),
                "is_security_override": is_security_override,
                "turn_number": turn_num + 1,
            }
            transcript.append({"role": "merchant", "data": merchant_turn_data})
            last_merchant_tools = merchant_turn_data["tools"]
            last_security_override = is_security_override
            yield _turn_event("merchant", merchant_turn_data)

            history += (
                f"\nBuyer: {buyer_msg}\n"
                f"Merchant: {merchant_msg} (offering {merchant_discount}% off)\n"
            )

            if merchant_action == "ACCEPT":
                items = merchant_res.get("approved_items", []) or buyer_items
                subtotal = 0.0
                for i in items:
                    qty = int(i.get("qty", 1))
                    sku = i.get("sku")
                    unit = _true_list_price(sku, float(i.get("price", 0.0) or 0.0))
                    subtotal += unit * qty
                final_amount = subtotal * (1 - merchant_discount / 100)

                bundle_proposal = merchant_res.get("bundle_proposal") or {}
                bundle_cost = 0.0
                if _bundle_authorized(merchant_res, buyer_msg):
                    bundle_cost = float(bundle_proposal["addon_price"])
                    final_amount = round(final_amount + bundle_cost, 2)
                    yield _log_event(
                        f"[SETTLEMENT] Bundle add-on {bundle_proposal.get('sku')} "
                        f"included at ₹{bundle_cost}."
                    )
                else:
                    bundle_proposal = {}
                    if merchant_res.get("bundle_proposal"):
                        yield _log_event(
                            "[SETTLEMENT] Bundle proposal dropped: LLM did not set "
                            "included=true, or buyer explicitly refused add-ons."
                        )

                cart = CartMandate(
                    cart_id=f"cart_b2b_{uuid.uuid4().hex[:8]}", mandate_id=req.mandate_id,
                    items=[CartItem(**i) for i in items] if items else [],
                    subtotal=subtotal, discount_pct=merchant_discount, final_amount=final_amount,
                )
                _, bounds_action, audit = check_against_mandate(cart, mandate)
                final_cart = cart.model_dump()
                audit_trail = audit
                outcome = bounds_action

                primary_item = (items or [{}])[0]
                true_base_price = _true_list_price(
                    primary_item.get("sku", "UNKNOWN_SKU"),
                    float(primary_item.get("price", 0.0) or 0.0),
                )

                max_transaction = float(
                    getattr(getattr(mandate, "limits", None), "max_per_transaction", 0.0) or 0.0
                )
                if max_transaction == 0.0:
                    max_transaction = 10000.0

                mandate_for_settlement = {
                    "mandate_id": mandate.mandate_id if hasattr(mandate, "mandate_id") else req.mandate_id,
                    "principal": getattr(getattr(mandate, "limits", None), "principal_name", "Corporate Buyer"),
                    "max_per_transaction": max_transaction,
                    "anomaly_discount_threshold": 15.0,
                }

                settlement_ok, execution_data, settlement_audit = execute_autonomous_settlement(
                    mandate=mandate_for_settlement, session_id=session_id,
                    buyer_agent_id=session.get("buyer_agent_id", "buyer_agent_ui"),
                    merchant_agent_id="merchant_souledstole_01",
                    sku=primary_item.get("sku", "UNKNOWN_SKU"),
                    qty=int(primary_item.get("qty", 1)),
                    unit_price=true_base_price, discount_pct=merchant_discount,
                    total_amount=final_amount,
                )

                if settlement_ok:
                    final_cart["execution"] = execution_data
                    if bundle_cost:
                        final_cart["bundle"] = {"sku": bundle_proposal.get("sku"), "addon_price": bundle_cost}
                    audit_trail = {
                        **(audit or {}),
                        "settlement_audit": settlement_audit,
                        "razorpay_order_id": execution_data.get("razorpay_order_id"),
                        "settlement_signature": execution_data.get("settlement_signature"),
                        "bundle": final_cart.get("bundle"),
                    }
                    yield _log_event(settlement_audit)
                    outcome = "EXECUTE"
                    yield json.dumps({
                        "type": "EXECUTE_COMPLETE", "execution": execution_data,
                        "bounds_action": bounds_action, "action": outcome,
                        "mandate_ceiling": getattr(mandate.limits, "max_per_transaction", None),
                    }) + "\n"
                else:
                    yield _log_event(f"[SETTLEMENT FAILED] {settlement_audit}")
                    outcome = "GATED_VIOLATION"
                    yield json.dumps({
                        "type": "EXECUTE_COMPLETE", "execution": None,
                        "action": outcome, "error_details": settlement_audit,
                    }) + "\n"

                close_session(session_id, "CLOSED_ACCEPTED" if outcome == "EXECUTE" else "CLOSED_REJECTED")
                break

            if merchant_action == "REJECT":
                outcome = "REJECTED"
                close_session(session_id, "CLOSED_REJECTED")
                break

        if outcome == "NO_DEAL":
            yield _log_event("[SYSTEM] Session terminated — turn limit reached without agreement.")
            close_session(session_id, "TIMEOUT")

        yield _status_event(
            "done", action=outcome, mandate_id=req.mandate_id, transcript=transcript,
            final_cart=final_cart, audit_trail=audit_trail, tools=last_merchant_tools,
            is_security_override=last_security_override, loop_status="COMPLETED",
        )

    return StreamingResponse(
        stream(), media_type="application/x-ndjson", headers={"X-Content-Type-Options": "nosniff"},
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

    try:
        req_discount = float(req.requested_discount_pct or 0.0)
    except (TypeError, ValueError):
        req_discount = 0.0
    append_turn(req.session_id, {"role": "buyer", "message": req.buyer_message, "requested_discount_pct": req_discount})
    append_turn(req.session_id, {"role": "merchant", "data": merchant_res})

    result = {"merchant_response": merchant_res, "turn_count": len(session["turns"]), "status": "IN_PROGRESS"}

    if merchant_res.get("action") == "ACCEPT":
        items = merchant_res.get("approved_items", [])
        subtotal = 0.0
        for i in items:
            qty = int(i.get("qty", 1))
            sku = i.get("sku")
            unit = _true_list_price(sku, float(i.get("price", 0.0) or 0.0))
            subtotal += unit * qty
        discount = float(merchant_res.get("offered_discount_pct", 0.0))
        final_amount = subtotal * (1 - discount / 100)

        bundle_proposal = merchant_res.get("bundle_proposal") or {}
        bundle_cost = 0.0
        if _bundle_authorized(merchant_res, req.buyer_message):
            bundle_cost = float(bundle_proposal["addon_price"])
            final_amount = round(final_amount + bundle_cost, 2)
        else:
            bundle_proposal = {}

        cart = CartMandate(
            cart_id=f"cart_b2b_{uuid.uuid4().hex[:8]}", mandate_id=session["mandate_id"],
            items=[CartItem(**i) for i in items], subtotal=subtotal,
            discount_pct=discount, final_amount=final_amount,
        )
        mandate = MOCK_DB[session["mandate_id"]]
        _, action, audit = check_against_mandate(cart, mandate)
        result.update({"final_cart": cart.model_dump(), "bounds_action": action, "audit_trail": audit})

        result["tools"] = {
            "campaign": merchant_res.get("campaign_check"),
            "discount_engine": merchant_res.get("discount_engine"),
            "bundle": merchant_res.get("bundle_proposal_payload"),
        }
        result["is_security_override"] = bool(merchant_res.get("threat_detected"))
        if bundle_cost:
            result["final_cart"]["bundle"] = {"sku": bundle_proposal.get("sku"), "addon_price": bundle_cost}

        primary_item = (items or [{}])[0]
        true_base_price = _true_list_price(
            primary_item.get("sku", "UNKNOWN_SKU"),
            float(primary_item.get("price", 0.0) or 0.0),
        )

        max_transaction = float(
            getattr(getattr(mandate, "limits", None), "max_per_transaction", 0.0) or 0.0
        )
        if max_transaction == 0.0:
            max_transaction = 10000.0

        mandate_for_settlement = {
            "mandate_id": mandate.mandate_id if hasattr(mandate, "mandate_id") else session["mandate_id"],
            "principal": getattr(getattr(mandate, "limits", None), "principal_name", "Corporate Buyer"),
            "max_per_transaction": max_transaction,
            "anomaly_discount_threshold": 15.0,
        }
        settlement_ok, execution_data, settlement_audit = execute_autonomous_settlement(
            mandate=mandate_for_settlement, session_id=req.session_id,
            buyer_agent_id=getattr(req, "buyer_agent_id", "buyer_agent_signed"),
            merchant_agent_id=session.get("merchant_agent_id", "merchant_souledstole_01"),
            sku=primary_item.get("sku", "UNKNOWN_SKU"),
            qty=int(primary_item.get("qty", 1)),
            unit_price=true_base_price, discount_pct=discount,
            total_amount=final_amount,
        )

        if settlement_ok:
            result["execution"] = execution_data
            result["settlement_audit"] = settlement_audit
            action = "EXECUTE"
        else:
            result["execution_error"] = settlement_audit
            action = "GATED_VIOLATION"

        if action == "EXECUTE":
            pm = create_payment_mandate(cart, session["mandate_id"])
            order = create_order(cart.final_amount, pm.payment_mandate_id)
            result["razorpay_order"] = order
            result["payment_mandate"] = pm.model_dump()
            result["status"] = "COMPLETED"
        elif action == "GATED_VIOLATION":
            store_pending(cart.cart_id, cart, session["mandate_id"], audit)
            result["status"] = "COMPLETED"
            result["action"] = "GATED_VIOLATION"
        close_session(req.session_id, "CLOSED_ACCEPTED")

    elif merchant_res.get("action") == "REJECT":
        close_session(req.session_id, "CLOSED_REJECTED")
        result["status"] = "COMPLETED"
        result["action"] = "REJECT"

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

_BUNDLE_REFUSAL_PATTERNS = (
    "no other items", "no add-ons", "no addons", "no extras", "nothing else",
    "only the ", "just the ", "skip the bundle", "without the bundle", "without any extras",
)

def _buyer_refused_bundle(buyer_message: str) -> bool:
    if not buyer_message:
        return False
    return any(p in buyer_message.lower() for p in _BUNDLE_REFUSAL_PATTERNS)

def _bundle_authorized(merchant_res: dict, buyer_message: str) -> bool:
    if merchant_res.get("threat_detected"):
        return False
    proposal = merchant_res.get("bundle_proposal") or {}
    if proposal.get("included") is not True:
        return False
    if not proposal.get("sku") or not proposal.get("addon_price"):
        return False
    if _buyer_refused_bundle(buyer_message):
        return False
    return True

def _true_list_price(sku: str, fallback: float) -> float:
    try:
        from app.core.merchant_state import get_store_state
        state = get_store_state()
        item = next((i for i in state.get("catalog", []) if i.get("sku") == sku), None)
        if item is not None:
            return float(item.get("price", fallback) or fallback)
    except Exception:
        pass
    return float(fallback or 0.0)
