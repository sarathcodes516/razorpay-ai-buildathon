"""
Integration tests for the human approval loop and payment verification.

Invariant enforced here:
  - record_spend is called in EXACTLY ONE place: POST /api/payments/verify
  - It fires only after Razorpay's HMAC signature check passes
  - bounds_engine, approvals.py, and storefront.py must NOT call record_spend
"""
import sys
import hmac
import hashlib
import pytest

sys.path.insert(0, ".")

# Load .env before any app imports so Razorpay/Gemini credentials are available
from dotenv import load_dotenv
load_dotenv("../.env")

# Force re-read of env vars that razorpay_client caches at import time
import app.integrations.razorpay_client as _rzp
import os
_rzp.KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_dummy")
_rzp.KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "dummy")
_rzp.client = __import__("razorpay").Client(auth=(_rzp.KEY_ID, _rzp.KEY_SECRET))

import app.core.spend_ledger as ledger_module
import app.core.pending_approvals as approvals_module


def reset_state():
    ledger_module._LEDGER.clear()
    approvals_module.PENDING_APPROVALS.clear()


def make_mandate(
    mandate_id: str = "man_aptest",
    max_per_tx: float = 5000.0,
    max_daily: float = 10000.0,
    auto_approve: float = 500.0,
):
    from app.core.mandate_service import create_mandate
    return create_mandate(
        principal=mandate_id,
        limits={
            "max_per_transaction": max_per_tx,
            "max_total_spend_today": max_daily,
            "allowed_categories": ["apparel", "accessories"],
            "auto_approve_below": auto_approve,
            "max_discount_agent_can_accept_pct": 15.0,
        },
    )


def make_escalating_cart(mandate_id: str, final_amount: float = 1500.0):
    from app.models.cart import CartMandate, CartItem
    return CartMandate(
        cart_id="cart_aptest_001",
        mandate_id=mandate_id,
        items=[CartItem(sku="HOD-002", qty=1, price=final_amount, category="apparel")],
        subtotal=final_amount,
        discount_pct=0.0,
        final_amount=final_amount,
    )


def make_valid_razorpay_signature(order_id: str, payment_id: str) -> str:
    """Generate a valid Razorpay signature using the test key secret."""
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "dummy")
    msg = f"{order_id}|{payment_id}"
    return hmac.new(key_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()


class TestPendingApprovalFlow:

    def setup_method(self):
        reset_state()

    # ------------------------------------------------------------------
    # Existing approval flow tests (updated for new ledger invariant)
    # ------------------------------------------------------------------

    def test_escalate_stores_in_pending_approvals(self):
        from app.core.bounds_engine import check_against_mandate
        from app.core.pending_approvals import store_pending, PENDING_APPROVALS

        mandate = make_mandate()
        cart = make_escalating_cart(mandate.mandate_id)

        _, action, audit = check_against_mandate(cart, mandate)
        assert action == "ESCALATE"

        store_pending(cart.cart_id, cart, mandate.mandate_id, audit)

        assert cart.cart_id in PENDING_APPROVALS
        assert PENDING_APPROVALS[cart.cart_id]["cart"].final_amount == 1500.0

    def test_approve_creates_razorpay_order_but_does_NOT_record_spend(self):
        """After /approve, ledger must still be 0 — spend recorded only after verify."""
        from app.core.bounds_engine import check_against_mandate
        from app.core.pending_approvals import store_pending
        from app.routers.approvals import approve_pending
        from app.routers.mandate import MOCK_DB
        from app.core.spend_ledger import get_spent_today

        mandate = make_mandate()
        MOCK_DB[mandate.mandate_id] = mandate
        cart = make_escalating_cart(mandate.mandate_id, final_amount=1500.0)

        _, action, audit = check_against_mandate(cart, mandate)
        assert action == "ESCALATE"
        store_pending(cart.cart_id, cart, mandate.mandate_id, audit)

        assert get_spent_today(mandate.mandate_id) == 0.0

        result = approve_pending(cart.cart_id)

        # Razorpay order must be real
        rzp = result["razorpay_order"]
        assert rzp.get("id", "").startswith("order_"), f"Expected order ID, got: {rzp}"
        assert rzp.get("amount") == int(1500.0 * 100)

        # PaymentMandate must be signed
        pm = result["payment_mandate"]
        assert pm["authorized_amount"] == 1500.0
        assert len(pm["signature"]) == 64

        # KEY ASSERTION: ledger must still be 0 — money hasn't moved yet
        assert get_spent_today(mandate.mandate_id) == 0.0, (
            "record_spend must NOT be called in approvals.py — only after Razorpay signature verify"
        )

        assert result["audit_trail"]["action_taken"] == "HUMAN_APPROVED_OVERRIDE"

    def test_deny_does_not_record_spend(self):
        from app.core.bounds_engine import check_against_mandate
        from app.core.pending_approvals import store_pending, PENDING_APPROVALS
        from app.routers.approvals import deny_pending
        from app.core.spend_ledger import get_spent_today

        mandate = make_mandate()
        cart = make_escalating_cart(mandate.mandate_id)

        _, _, audit = check_against_mandate(cart, mandate)
        store_pending(cart.cart_id, cart, mandate.mandate_id, audit)

        result = deny_pending(cart.cart_id)

        assert result["status"] == "denied"
        assert result["audit_trail"]["action_taken"] == "HUMAN_DENIED"
        assert cart.cart_id not in PENDING_APPROVALS
        assert get_spent_today(mandate.mandate_id) == 0.0

    def test_double_approve_raises_404(self):
        from app.core.bounds_engine import check_against_mandate
        from app.core.pending_approvals import store_pending
        from app.routers.approvals import approve_pending
        from app.routers.mandate import MOCK_DB
        from fastapi import HTTPException

        mandate = make_mandate()
        MOCK_DB[mandate.mandate_id] = mandate
        cart = make_escalating_cart(mandate.mandate_id)
        _, _, audit = check_against_mandate(cart, mandate)
        store_pending(cart.cart_id, cart, mandate.mandate_id, audit)

        approve_pending(cart.cart_id)

        with pytest.raises(HTTPException) as exc_info:
            approve_pending(cart.cart_id)
        assert exc_info.value.status_code == 404

    # ------------------------------------------------------------------
    # Payment verification tests (the single record_spend location)
    # ------------------------------------------------------------------

    def test_verify_with_valid_signature_records_spend(self):
        from app.routers.payment_verify import verify_and_record
        from app.core.spend_ledger import get_spent_today
        from app.routers.mandate import MOCK_DB

        mandate = make_mandate(mandate_id="man_verify_test")
        MOCK_DB[mandate.mandate_id] = mandate

        # Create a real Razorpay order so we have a real order_id to sign
        from app.integrations.razorpay_client import create_order
        order = create_order(999.0, "test_receipt_verify")
        order_id = order["id"]
        payment_id = "pay_test_fake_123"

        sig = make_valid_razorpay_signature(order_id, payment_id)

        from pydantic import BaseModel
        class Req:
            mandate_id = mandate.mandate_id
            amount = 999.0
            razorpay_order_id = order_id
            razorpay_payment_id = payment_id
            razorpay_signature = sig

        result = verify_and_record(Req())

        assert result["status"] == "payment_confirmed"
        assert result["spent_today"] == 999.0
        assert get_spent_today(mandate.mandate_id) == 999.0

    def test_verify_with_bad_signature_raises_400_and_does_not_record_spend(self):
        from app.routers.payment_verify import verify_and_record
        from app.core.spend_ledger import get_spent_today
        from fastapi import HTTPException

        class Req:
            mandate_id = "man_bad_sig_test"
            amount = 999.0
            razorpay_order_id = "order_fake"
            razorpay_payment_id = "pay_fake"
            razorpay_signature = "deadbeefdeadbeefdeadbeefdeadbeef"  # garbage

        with pytest.raises(HTTPException) as exc_info:
            verify_and_record(Req())

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "signature_verification_failed"
        assert get_spent_today("man_bad_sig_test") == 0.0

    def test_bounds_engine_execute_does_not_record_spend(self):
        """Regression: EXECUTE from bounds_engine must NOT call record_spend."""
        from app.core.bounds_engine import check_against_mandate
        from app.core.spend_ledger import get_spent_today
        from app.models.cart import CartMandate, CartItem

        mandate = make_mandate(auto_approve=2000.0)
        cart = CartMandate(
            cart_id="cart_execute_test",
            mandate_id=mandate.mandate_id,
            items=[CartItem(sku="ACC-005", qty=1, price=499.0, category="accessories")],
            subtotal=499.0,
            discount_pct=0.0,
            final_amount=499.0,
        )

        _, action, _ = check_against_mandate(cart, mandate)
        assert action == "EXECUTE"

        # Ledger must be untouched — no spend recorded at bounds-check time
        assert get_spent_today(mandate.mandate_id) == 0.0, (
            "bounds_engine must NOT call record_spend — it is a pure decision function"
        )
