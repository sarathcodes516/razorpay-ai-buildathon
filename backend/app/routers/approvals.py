from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from app.core.pending_approvals import pop_pending
from app.core.mandate_service import create_payment_mandate
from app.integrations.razorpay_client import create_order, KEY_ID as RAZORPAY_KEY_ID
from app.routers.mandate import MOCK_DB

router = APIRouter()


@router.post("/api/approvals/{cart_id}/approve")
def approve_pending(cart_id: str):
    entry = pop_pending(cart_id)
    if not entry:
        raise HTTPException(404, "No pending approval for this cart_id")

    mandate = MOCK_DB.get(entry["mandate_id"])
    if not mandate or mandate.expires_at < datetime.now(timezone.utc):
        raise HTTPException(410, "Mandate expired before approval was completed")

    cart = entry["cart"]
    payment_mandate = create_payment_mandate(cart, entry["mandate_id"])
    order = create_order(cart.final_amount, payment_mandate.payment_mandate_id)
    # record_spend removed — ledger is updated only after Razorpay signature verification
    # via POST /api/payments/verify

    audit = dict(entry["audit"])
    audit["action_taken"] = "HUMAN_APPROVED_OVERRIDE"

    return {
        "status": "approved",
        "razorpay_order": order,
        "razorpay_key_id": RAZORPAY_KEY_ID,
        "payment_mandate": payment_mandate.model_dump(),
        "audit_trail": audit,
    }


@router.post("/api/approvals/{cart_id}/deny")
def deny_pending(cart_id: str):
    entry = pop_pending(cart_id)
    if not entry:
        raise HTTPException(404, "No pending approval for this cart_id")

    audit = dict(entry["audit"])
    audit["action_taken"] = "HUMAN_DENIED"
    return {"status": "denied", "audit_trail": audit}
