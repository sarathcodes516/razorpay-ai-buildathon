"""
payment_verify.py — Razorpay HMAC verification + (optional) spend recording.

The B2C storefront calls this after a successful Razorpay payment popup, and
the B2B gateway calls it after the autonomous Razorpay settlement. They share
this single endpoint:

  - B2C sends only the three Razorpay fields (no mandate id, no amount).
    The server just verifies the signature and returns payment_confirmed.
  - B2B sends the full payload including the buyer's mandate id + amount
    so the spend ledger is updated. This is the only call site of
    `record_spend` in the entire codebase.
"""
from typing import Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.integrations.razorpay_client import verify_payment
from app.core.spend_ledger import record_spend

router = APIRouter()


class VerifyRequest(BaseModel):
    razorpay_order_id:   str
    razorpay_payment_id: str
    razorpay_signature:  str
    mandate_id:          Optional[str] = None
    amount:              Optional[float] = None


def _detail(payload: Any) -> dict:
    """Normalize any error into the {"detail": "<string>"} shape the front-end
    reads. FastAPI's default 422 returns detail as a list of pydantic errors;
    stringifying them with a JS template would produce `[object Object]`, so we
    collapse them here."""
    if isinstance(payload, str):
        return {"detail": payload}
    if isinstance(payload, list):
        bits = []
        for e in payload:
            if isinstance(e, dict):
                loc = ".".join(str(p) for p in e.get("loc", []))
                msg = e.get("msg", "")
                bits.append(f"{loc}: {msg}" if loc else str(msg))
            else:
                bits.append(str(e))
        return {"detail": "; ".join(bits)}
    return {"detail": str(payload)}


@router.post("/api/payments/verify")
def verify_and_record(req: VerifyRequest):
    ok = verify_payment(req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature)
    if not ok:
        raise HTTPException(status_code=400, detail="signature_verification_failed")

    spent_today = None
    if req.mandate_id and req.amount is not None:
        spent_today = record_spend(req.mandate_id, float(req.amount))

    return {"status": "payment_confirmed", "spent_today": spent_today}
