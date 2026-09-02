"""
payment_verify.py — The single place in the entire codebase that calls record_spend.

record_spend is called here and ONLY here, after Razorpay's HMAC signature check
passes. This ensures the mandate's daily budget is consumed only when money actually
moved, not at order-creation time or bounds-engine evaluation time.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.integrations.razorpay_client import verify_payment
from app.core.spend_ledger import record_spend

router = APIRouter()


class VerifyRequest(BaseModel):
    mandate_id: str
    amount: float
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/api/payments/verify")
def verify_and_record(req: VerifyRequest):
    ok = verify_payment(req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature)
    if not ok:
        raise HTTPException(400, "signature_verification_failed")

    new_total = record_spend(req.mandate_id, req.amount)
    return {"status": "payment_confirmed", "spent_today": new_total}
