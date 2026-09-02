"""
Tests for bounds_engine.check_against_mandate.
Covers all 6 rule branches plus the critical two-purchase daily budget scenario.
"""
import pytest
from datetime import datetime, timezone, timedelta

# Reset the spend ledger before each test so state doesn't bleed between runs
import app.core.spend_ledger as ledger_module


def reset_ledger():
    ledger_module._LEDGER.clear()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_mandate(
    mandate_id: str = "man_test",
    max_per_tx: float = 3000.0,
    max_daily: float = 5000.0,
    auto_approve: float = 2000.0,
    max_discount: float = 15.0,
    anomaly_threshold: float | None = None,
    categories: list[str] | None = None,
    expired: bool = False,
):
    from app.models.mandate import SpendMandate, MandateLimits

    now = datetime.now(timezone.utc)
    expires = now - timedelta(hours=1) if expired else now + timedelta(hours=24)

    limits = MandateLimits(
        max_per_transaction=max_per_tx,
        max_total_spend_today=max_daily,
        allowed_categories=categories or ["apparel", "accessories"],
        auto_approve_below=auto_approve,
        max_discount_agent_can_accept_pct=max_discount,
        anomaly_discount_threshold_pct=anomaly_threshold,
    )
    return SpendMandate(
        mandate_id=mandate_id,
        principal="Test Principal",
        issued_at=now,
        expires_at=expires,
        limits=limits,
        signature="dummy",  # bounds_engine no longer calls verify_mandate
    )


def make_cart(
    cart_id: str = "cart_test",
    mandate_id: str = "man_test",
    final_amount: float = 500.0,
    discount_pct: float = 0.0,
    categories: list[str] | None = None,
):
    from app.models.cart import CartMandate, CartItem

    cats = categories or ["apparel"]
    items = [
        CartItem(sku="TEE-001", qty=1, price=final_amount, category=c)
        for c in cats
    ]
    return CartMandate(
        cart_id=cart_id,
        mandate_id=mandate_id,
        items=items,
        subtotal=final_amount,
        discount_pct=discount_pct,
        final_amount=final_amount,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBoundsEngine:

    def setup_method(self):
        reset_ledger()

    # --- Rule 0: Expired mandate ---

    def test_expired_mandate_returns_reject(self):
        from app.core.bounds_engine import check_against_mandate

        mandate = make_mandate(expired=True)
        cart = make_cart()
        ok, action, audit = check_against_mandate(cart, mandate)

        assert ok is False
        assert action == "REJECT"
        assert audit["action_taken"] == "REJECT_EXPIRED_MANDATE"

    # --- Rule 1: Single transaction ceiling ---

    def test_amount_exceeds_max_per_transaction_escalates(self):
        from app.core.bounds_engine import check_against_mandate

        mandate = make_mandate(max_per_tx=1000.0)
        cart = make_cart(final_amount=1500.0)
        ok, action, audit = check_against_mandate(cart, mandate)

        assert ok is False
        assert action == "ESCALATE"
        assert audit["action_taken"] == "ESCALATE_TO_HUMAN_APPROVAL"

    # --- Rule 2: Category allowlist ---

    def test_out_of_bounds_category_returns_reject(self):
        from app.core.bounds_engine import check_against_mandate

        mandate = make_mandate(categories=["apparel"])
        cart = make_cart(categories=["electronics"])
        ok, action, audit = check_against_mandate(cart, mandate)

        assert ok is False
        assert action == "REJECT"
        assert audit["action_taken"] == "REJECT_OUT_OF_BOUNDS"

    # --- Rule 3: Cumulative daily spend limit ---

    def test_two_purchases_exceeding_daily_limit(self):
        """
        The daily budget check uses the ledger. Since bounds_engine no longer calls
        record_spend, the caller must record spend between purchases for Rule 3 to fire.
        This test verifies that WHEN spend is recorded (simulating a prior confirmed
        payment), the second purchase correctly hits REJECT_DAILY_BUDGET_EXCEEDED.
        """
        from app.core.bounds_engine import check_against_mandate
        from app.core.spend_ledger import record_spend

        mandate = make_mandate(
            mandate_id="man_daily",
            max_per_tx=3000.0,
            max_daily=4000.0,
            auto_approve=3000.0,
        )

        # Purchase 1: ₹2500 — EXECUTE (within limits)
        cart1 = make_cart(cart_id="cart_1", mandate_id="man_daily", final_amount=2500.0)
        ok1, action1, _ = check_against_mandate(cart1, mandate)
        assert ok1 is True
        assert action1 == "EXECUTE"

        # Simulate confirmed payment — record spend as /api/payments/verify would
        record_spend("man_daily", 2500.0)

        # Purchase 2: ₹2000 — individually valid (2000 < 3000 per-tx)
        # but 2500 + 2000 = 4500 > daily limit of 4000 → REJECT
        cart2 = make_cart(cart_id="cart_2", mandate_id="man_daily", final_amount=2000.0)
        ok2, action2, audit2 = check_against_mandate(cart2, mandate)

        assert ok2 is False
        assert action2 == "REJECT"
        assert audit2["action_taken"] == "REJECT_DAILY_BUDGET_EXCEEDED"

    def test_first_purchase_does_not_record_spend_in_ledger(self):
        """bounds_engine is a pure decision function — it must not touch the ledger."""
        from app.core.bounds_engine import check_against_mandate
        from app.core.spend_ledger import get_spent_today

        mandate = make_mandate(mandate_id="man_ledger", max_daily=5000.0, auto_approve=2000.0)
        cart = make_cart(mandate_id="man_ledger", final_amount=999.0)
        ok, action, _ = check_against_mandate(cart, mandate)

        assert action == "EXECUTE"
        # Ledger must be untouched — record_spend is the caller's responsibility
        assert get_spent_today("man_ledger") == 0.0

    # --- Rule 4a: Anomaly discount threshold ---

    def test_anomaly_discount_threshold_escalates(self):
        from app.core.bounds_engine import check_against_mandate

        mandate = make_mandate(anomaly_threshold=10.0, max_discount=20.0)
        cart = make_cart(final_amount=500.0, discount_pct=12.0)
        ok, action, audit = check_against_mandate(cart, mandate)

        assert ok is False
        assert action == "ESCALATE"
        assert audit["action_taken"] == "ESCALATE_ANOMALY_REVIEW"

    def test_no_anomaly_threshold_skips_rule(self):
        """When anomaly_discount_threshold_pct is None, Rule 4a must be skipped."""
        from app.core.bounds_engine import check_against_mandate

        mandate = make_mandate(anomaly_threshold=None, max_discount=20.0)
        cart = make_cart(final_amount=500.0, discount_pct=12.0)
        ok, action, audit = check_against_mandate(cart, mandate)

        # Should pass through to EXECUTE (12% < 20% max_discount, 500 < auto_approve)
        assert action == "EXECUTE"

    # --- Rule 4b: Hard discount ceiling ---

    def test_discount_exceeds_max_escalates(self):
        from app.core.bounds_engine import check_against_mandate

        mandate = make_mandate(max_discount=15.0)
        cart = make_cart(final_amount=500.0, discount_pct=20.0)
        ok, action, audit = check_against_mandate(cart, mandate)

        assert ok is False
        assert action == "ESCALATE"
        assert audit["action_taken"] == "ESCALATE_TO_HUMAN_APPROVAL"

    # --- Rule 5: Auto-approve line ---

    def test_amount_above_auto_approve_escalates(self):
        from app.core.bounds_engine import check_against_mandate

        mandate = make_mandate(auto_approve=1000.0, max_per_tx=5000.0)
        cart = make_cart(final_amount=2000.0)
        ok, action, audit = check_against_mandate(cart, mandate)

        assert ok is False
        assert action == "ESCALATE"
        assert audit["action_taken"] == "ESCALATE_TO_HUMAN_APPROVAL"

    def test_happy_path_auto_executes(self):
        from app.core.bounds_engine import check_against_mandate

        mandate = make_mandate()
        cart = make_cart(final_amount=500.0)
        ok, action, audit = check_against_mandate(cart, mandate)

        assert ok is True
        assert action == "EXECUTE"
        assert audit["action_taken"] == "AUTO_APPROVE_TO_RAZORPAY"
