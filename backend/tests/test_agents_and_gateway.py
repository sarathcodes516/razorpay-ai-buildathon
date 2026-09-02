"""
Tests for CHECK 9, 10, 11, 12:
  - propose_discount cap enforcement (deterministic, no LLM)
  - check_remaining_budget correctness
  - Session/turn protocol (mocked LLM)
  - Agent auth dependency (Ed25519 signed requests)
  - Discovery manifest
"""
import sys
import json
import pytest
from unittest.mock import patch

sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv("../.env")

import app.integrations.razorpay_client as _rzp
import os
_rzp.KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_dummy")
_rzp.KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "dummy")
_rzp.client = __import__("razorpay").Client(auth=(_rzp.KEY_ID, _rzp.KEY_SECRET))

import app.core.spend_ledger as ledger_module
import app.core.pending_approvals as approvals_module
import app.core.negotiation_sessions as sessions_module
import app.core.agent_registry as registry_module


def reset_all():
    ledger_module._LEDGER.clear()
    approvals_module.PENDING_APPROVALS.clear()
    sessions_module.SESSIONS.clear()
    # Keep registry — merchant registered at import time of main.py is fine


# ─────────────────────────────────────────────────────────
# CHECK 9 — propose_discount cap
# ─────────────────────────────────────────────────────────

class TestProposalDiscountCap:

    def test_absurd_input_capped_at_policy_max(self):
        """
        Core deterministic proof: regardless of what the LLM requests,
        propose_discount() enforces the live merchant policy cap in Python.
        """
        from app.agents.negotiator_agent import propose_discount
        from app.core.merchant_state import STORE_STATE

        cap = STORE_STATE["policy"]["max_allowable_discount_pct"]
        result = propose_discount(pct=999.0)

        assert result["approved_pct"] == cap
        assert result["was_capped"] is True
        assert result["requested_pct"] == 999.0

    def test_below_cap_passes_through_unchanged(self):
        from app.agents.negotiator_agent import propose_discount
        from app.core.merchant_state import STORE_STATE

        cap = STORE_STATE["policy"]["max_allowable_discount_pct"]
        small = cap / 2
        result = propose_discount(pct=small)

        assert result["approved_pct"] == small
        assert result["was_capped"] is False

    def test_exact_cap_not_flagged_as_capped(self):
        from app.agents.negotiator_agent import propose_discount
        from app.core.merchant_state import STORE_STATE

        cap = STORE_STATE["policy"]["max_allowable_discount_pct"]
        result = propose_discount(pct=cap)
        assert result["approved_pct"] == cap
        assert result["was_capped"] is False


# ─────────────────────────────────────────────────────────
# CHECK 10 — check_remaining_budget
# ─────────────────────────────────────────────────────────

class TestCheckRemainingBudget:

    def setup_method(self):
        reset_all()

    def test_returns_correct_budget_with_no_prior_spend(self):
        from app.agents.buyer_agent import check_remaining_budget
        from app.core.mandate_service import create_mandate
        from app.routers.mandate import MOCK_DB

        mandate = create_mandate("BudgetTestBuyer", {
            "max_per_transaction": 3000.0,
            "max_total_spend_today": 8000.0,
            "allowed_categories": ["apparel"],
            "auto_approve_below": 1000.0,
            "max_discount_agent_can_accept_pct": 12.0,
        })
        MOCK_DB[mandate.mandate_id] = mandate

        result = check_remaining_budget(mandate.mandate_id)

        assert result["max_per_transaction"] == 3000.0
        assert result["remaining_today"] == 8000.0
        assert result["max_discount_i_can_accept_pct"] == 12.0

    def test_remaining_reflects_prior_spend(self):
        from app.agents.buyer_agent import check_remaining_budget
        from app.core.mandate_service import create_mandate
        from app.core.spend_ledger import record_spend
        from app.routers.mandate import MOCK_DB

        mandate = create_mandate("BudgetSpendBuyer", {
            "max_per_transaction": 3000.0,
            "max_total_spend_today": 8000.0,
            "allowed_categories": ["apparel"],
            "auto_approve_below": 1000.0,
            "max_discount_agent_can_accept_pct": 12.0,
        })
        MOCK_DB[mandate.mandate_id] = mandate
        record_spend(mandate.mandate_id, 2500.0)

        result = check_remaining_budget(mandate.mandate_id)
        assert result["remaining_today"] == 5500.0

    def test_unknown_mandate_returns_error(self):
        from app.agents.buyer_agent import check_remaining_budget
        result = check_remaining_budget("man_does_not_exist")
        assert result == {"error": "mandate_not_found"}


# ─────────────────────────────────────────────────────────
# CHECK 11 — Session/turn protocol
# ─────────────────────────────────────────────────────────

# Deterministic merchant stub: always ACCEPTs on the first turn
MERCHANT_ACCEPT_STUB = {
    "thought_process": "Stock is available, discount within policy.",
    "action": "ACCEPT",
    "message": "Deal! We can do that.",
    "approved_items": [{"sku": "TEE-001", "qty": 5, "price": 999.0, "category": "apparel"}],
    "offered_discount_pct": 10.0,
    "_tool_trace": [],
}

MERCHANT_COUNTER_STUB = {
    "thought_process": "Countering with 10%.",
    "action": "COUNTER",
    "message": "I can offer 10%.",
    "approved_items": [{"sku": "TEE-001", "qty": 5, "price": 999.0, "category": "apparel"}],
    "offered_discount_pct": 10.0,
    "_tool_trace": [],
}


def make_test_mandate(label="man_sess_test", auto_approve=50000.0):
    from app.core.mandate_service import create_mandate
    from app.routers.mandate import MOCK_DB
    m = create_mandate(label, {
        "max_per_transaction": 60000.0,
        "max_total_spend_today": 100000.0,
        "allowed_categories": ["apparel", "accessories"],
        "auto_approve_below": auto_approve,
        "max_discount_agent_can_accept_pct": 15.0,
    })
    MOCK_DB[m.mandate_id] = m
    return m


def make_signed_headers(agent_id: str, private_key, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    sig = private_key.sign(body)
    return {
        "X-TrustRail-Agent-Id": agent_id,
        "X-TrustRail-Signature": sig.hex(),
        "Content-Type": "application/json",
    }


class TestSessionProtocol:

    def setup_method(self):
        reset_all()

    def _register_buyer(self, agent_id="test_buyer_sess"):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        from app.core.agent_registry import register_agent
        priv = Ed25519PrivateKey.generate()
        pub_hex = priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo).hex()
        register_agent(agent_id, "buyer", ["negotiate"], public_key_hex=pub_hex)
        return priv, agent_id

    def test_start_session_unknown_mandate_raises_404(self):
        from app.routers.gateway import start_session, StartSessionRequest
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            start_session(StartSessionRequest(
                mandate_id="man_nonexistent",
                merchant_agent_id="merchant_souledstole_01",
                procurement_goal="buy stuff",
            ))
        assert exc.value.status_code == 404

    def test_start_session_expired_mandate_raises_401(self):
        from app.routers.gateway import start_session, StartSessionRequest
        from app.core.mandate_service import create_mandate
        from app.routers.mandate import MOCK_DB
        from datetime import timedelta
        from fastapi import HTTPException

        m = create_mandate("ExpiredPrincipal", {
            "max_per_transaction": 1000.0, "max_total_spend_today": 5000.0,
            "allowed_categories": ["apparel"], "auto_approve_below": 500.0,
            "max_discount_agent_can_accept_pct": 10.0,
        })
        # Backdate expiry
        from datetime import datetime, timezone
        MOCK_DB[m.mandate_id] = m.model_copy(update={
            "expires_at": datetime.now(timezone.utc) - timedelta(hours=1)
        })
        with pytest.raises(HTTPException) as exc:
            start_session(StartSessionRequest(
                mandate_id=m.mandate_id,
                merchant_agent_id="merchant_souledstole_01",
                procurement_goal="buy stuff",
            ))
        assert exc.value.status_code == 401

    def test_start_session_valid_mandate_returns_session_id(self):
        from app.routers.gateway import start_session, StartSessionRequest
        m = make_test_mandate()
        result = start_session(StartSessionRequest(
            mandate_id=m.mandate_id,
            merchant_agent_id="merchant_souledstole_01",
            procurement_goal="buy 5 tees",
        ))
        assert result["status"] == "open"
        assert result["session_id"].startswith("sess_")

    def test_turn_unknown_session_raises_404(self):
        from app.routers.gateway import gateway_turn, TurnRequest
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            gateway_turn(TurnRequest(
                session_id="sess_doesnotexist",
                buyer_message="hello",
                requested_items=[],
                requested_discount_pct=10.0,
            ))
        assert exc.value.status_code == 404

    def test_turn_limit_raises_409(self):
        from app.routers.gateway import start_session, gateway_turn, StartSessionRequest, TurnRequest, MAX_TURNS
        from fastapi import HTTPException

        m = make_test_mandate()
        sess = start_session(StartSessionRequest(
            mandate_id=m.mandate_id,
            merchant_agent_id="merchant_souledstole_01",
            procurement_goal="buy stuff",
        ))
        session_id = sess["session_id"]
        # Fill up turns manually
        sessions_module.SESSIONS[session_id]["turns"] = [{}] * MAX_TURNS

        with patch("app.routers.gateway.generate_b2b_merchant_turn", return_value=MERCHANT_COUNTER_STUB):
            with pytest.raises(HTTPException) as exc:
                gateway_turn(TurnRequest(
                    session_id=session_id,
                    buyer_message="push",
                    requested_items=[],
                    requested_discount_pct=5.0,
                ))
        assert exc.value.status_code == 409

    def test_turn_merchant_accept_closes_session_and_creates_order(self):
        from app.routers.gateway import start_session, gateway_turn, StartSessionRequest, TurnRequest

        m = make_test_mandate(auto_approve=50000.0)
        sess = start_session(StartSessionRequest(
            mandate_id=m.mandate_id,
            merchant_agent_id="merchant_souledstole_01",
            procurement_goal="buy 5 tees",
        ))
        session_id = sess["session_id"]

        with patch("app.routers.gateway.generate_b2b_merchant_turn", return_value=MERCHANT_ACCEPT_STUB):
            result = gateway_turn(TurnRequest(
                session_id=session_id,
                buyer_message="We want 5 tees, offer 10%",
                requested_items=[{"sku": "TEE-001", "qty": 5, "price": 999.0, "category": "apparel"}],
                requested_discount_pct=10.0,
            ))

        assert result["merchant_response"]["action"] == "ACCEPT"
        assert sessions_module.SESSIONS[session_id]["status"] == "CLOSED_ACCEPTED"
        assert "final_cart" in result
        assert result["bounds_action"] == "EXECUTE"
        assert result["razorpay_order"]["id"].startswith("order_")


# ─────────────────────────────────────────────────────────
# CHECK 12 — Agent auth + discovery
# ─────────────────────────────────────────────────────────

class TestAgentAuth:

    def setup_method(self):
        reset_all()

    def _make_agent(self, agent_id="auth_test_buyer"):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        from app.core.agent_registry import register_agent
        priv = Ed25519PrivateKey.generate()
        pub_hex = priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo).hex()
        register_agent(agent_id, "buyer", ["negotiate"], public_key_hex=pub_hex)
        return priv, agent_id

    def _run_dependency(self, agent_id, sig_hex, body: bytes):
        """Run require_signed_agent synchronously via anyio."""
        import anyio
        from starlette.testclient import TestClient
        from fastapi import FastAPI, Depends
        from app.core.agent_auth import require_signed_agent
        from starlette.requests import Request

        results = {}

        test_app = FastAPI()

        @test_app.post("/test-auth", dependencies=[Depends(require_signed_agent)])
        async def _test_endpoint(request: Request):
            results["agent_id"] = request.state.verified_agent_id
            return {"ok": True}

        client = TestClient(test_app, raise_server_exceptions=True)
        headers = {}
        if agent_id:
            headers["X-TrustRail-Agent-Id"] = agent_id
        if sig_hex:
            headers["X-TrustRail-Signature"] = sig_hex
        headers["Content-Type"] = "application/json"
        return client.post("/test-auth", data=body, headers=headers), results

    def test_missing_headers_returns_401(self):
        resp, _ = self._run_dependency(None, None, b"{}")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "missing_agent_identity_headers"

    def test_unknown_agent_id_returns_401(self):
        resp, _ = self._run_dependency("nobody_registered", "deafbeef", b"{}")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "unknown_agent_id"

    def test_valid_signature_passes(self):
        priv, agent_id = self._make_agent("auth_pass_agent")
        body = json.dumps({"test": "data"}).encode()
        sig_hex = priv.sign(body).hex()
        resp, results = self._run_dependency(agent_id, sig_hex, body)
        assert resp.status_code == 200
        assert results["agent_id"] == agent_id

    def test_tampered_body_after_signing_returns_401(self):
        priv, agent_id = self._make_agent("auth_tamper_agent")
        original_body = json.dumps({"mandate_id": "man_abc"}).encode()
        sig_hex = priv.sign(original_body).hex()
        tampered_body = json.dumps({"mandate_id": "man_evil"}).encode()
        resp, _ = self._run_dependency(agent_id, sig_hex, tampered_body)
        assert resp.status_code == 401
        assert resp.json()["detail"] == "invalid_signature"


class TestDiscoveryManifest:

    def test_manifest_returns_without_auth(self):
        from app.routers.discovery import manifest
        from app.core.agent_registry import register_agent

        # Ensure merchant is registered (main.py does this at startup)
        register_agent("merchant_souledstole_01", "merchant",
                        ["bulk_discount_negotiation", "inventory_check", "test_mode_payment"])

        result = manifest()
        assert result["protocol"] == "TrustRail/UAP-0.1"
        assert result["merchant_agent_id"] == "merchant_souledstole_01"
        assert result["merchant_public_key"] is not None
        assert len(result["merchant_public_key"]) > 0
        assert "session_start" in result["endpoints"]
        assert "required_mandate_schema" in result
