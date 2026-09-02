"""
buyer_agent_runner.py — Streaming orchestrator for the Buyer Agent UI.

POST /api/buyer-agent/run drives the full A2A negotiation loop server-side and
streams every HTTP call it makes as a newline-delimited JSON (NDJSON) event.

Stream event types:
  {"type": "chat",   "role": "agent"|"system", "content": "..."}
  {"type": "wire",   "direction": "request"|"response", "method": "POST",
                     "path": "/api/...", "status": 200, "latencyMs": 123,
                     "signed": true, "headers": {...}, "body": {...}}
  {"type": "status", "status": "negotiating"|"closed_accepted"|"closed_rejected"|"error"}

This is the only place in the backend that acts as an HTTP client talking to itself.
The buyer agent is genuinely a separate logical process: it generates its own Ed25519
keypair per session (private key lives only in this coroutine's stack frame), registers
only its public key, and signs every outbound request — the same contract as the
standalone scripts/buyer_agent_driver.py, but driven by the UI.
"""
import json
import time
import uuid
from typing import AsyncGenerator

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.buyer_agent import generate_buyer_turn

router = APIRouter()


class RunRequest(BaseModel):
    merchant_url: str
    task: str
    mandate_id: str


# ---------------------------------------------------------------------------
# Stream helpers
# ---------------------------------------------------------------------------

def _chat(role: str, content: str) -> str:
    return json.dumps({"type": "chat", "role": role, "content": content}) + "\n"


def _status(status: str) -> str:
    return json.dumps({"type": "status", "status": status}) + "\n"


def _wire(
    direction: str,
    method: str,
    path: str,
    signed: bool,
    headers: dict,
    body: object = None,
    status: int | None = None,
    latency_ms: int | None = None,
    note: str | None = None,
) -> str:
    event: dict = {
        "type": "wire",
        "direction": direction,
        "method": method,
        "path": path,
        "signed": signed,
        "headers": headers,
    }
    if body is not None:
        event["body"] = body
    if status is not None:
        event["status"] = status
    if latency_ms is not None:
        event["latencyMs"] = latency_ms
    if note is not None:
        event["note"] = note
    return json.dumps(event) + "\n"


# ---------------------------------------------------------------------------
# Signed HTTP client helpers
# ---------------------------------------------------------------------------

def _sign_body(private_key: Ed25519PrivateKey, body_bytes: bytes) -> str:
    return private_key.sign(body_bytes).hex()


def _signed_headers(
    private_key: Ed25519PrivateKey,
    agent_id: str,
    body_bytes: bytes,
) -> dict:
    return {
        "X-TrustRail-Agent-Id": agent_id,
        "X-TrustRail-Signature": _sign_body(private_key, body_bytes),
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Async generator — the full negotiation loop
# ---------------------------------------------------------------------------

async def _run_session(
    merchant_url: str,
    task: str,
    mandate_id: str,
) -> AsyncGenerator[str, None]:
    """
    Drives the buyer agent negotiation loop, yielding NDJSON events.
    Each outbound HTTP call is emitted as a wire event before AND after.
    """
    # Per-session ephemeral keypair — private key never leaves this coroutine
    private_key = Ed25519PrivateKey.generate()
    public_key_hex = private_key.public_key().public_bytes(
        encoding=Encoding.DER,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).hex()
    agent_id = f"buyer_ui_{uuid.uuid4().hex[:8]}"

    async with httpx.AsyncClient(timeout=60.0) as client:

        # ── Step 0: Fetch the discovery manifest ────────────────────────────
        manifest_path = "/.well-known/trustrail-manifest.json"
        manifest_url = f"{merchant_url}{manifest_path}"

        yield _wire("request", "GET", manifest_path, False, {})
        t0 = time.monotonic()
        try:
            resp = await client.get(manifest_url)
            latency = int((time.monotonic() - t0) * 1000)
            manifest = resp.json()
            yield _wire("response", "GET", manifest_path, False,
                        dict(resp.headers), manifest, resp.status_code, latency)
            yield _chat("system",
                f"Manifest received. Protocol: {manifest.get('protocol', '?')}. "
                f"Merchant: {manifest.get('merchant_agent_id', '?')}.")
        except Exception as exc:
            yield _wire("response", "GET", manifest_path, False, {},
                        note=str(exc), status=0)
            yield _chat("system", f"Could not reach {merchant_url}. Is the backend running?")
            yield _status("error")
            return

        # ── Step 1: Register buyer's public key ─────────────────────────────
        register_path = f"/api/agents/{agent_id}/register"
        register_url = f"{merchant_url}{register_path}"
        reg_payload = {
            "role": "buyer",
            "capabilities": ["negotiate", "check_budget"],
            "public_key_hex": public_key_hex,
        }
        reg_body = json.dumps(reg_payload).encode()

        yield _wire("request", "POST", register_path, False,
                    {"Content-Type": "application/json"}, reg_payload)
        t0 = time.monotonic()
        try:
            resp = await client.post(
                register_url,
                content=reg_body,
                headers={"Content-Type": "application/json"},
            )
            latency = int((time.monotonic() - t0) * 1000)
            yield _wire("response", "POST", register_path, False,
                        dict(resp.headers), resp.json(), resp.status_code, latency)
            yield _chat("system", f"Registered as {agent_id}. Keypair generated (private key stays here).")
        except Exception as exc:
            yield _chat("system", f"Registration failed: {exc}")
            yield _status("error")
            return

        yield _status("negotiating")

        # ── Step 2: Start a negotiation session ─────────────────────────────
        start_path = "/api/gateway/session/start"
        start_url = f"{merchant_url}{start_path}"
        start_payload = {
            "mandate_id": mandate_id,
            "merchant_agent_id": "merchant_souledstole_01",
            "procurement_goal": task,
        }
        start_body = json.dumps(start_payload).encode()
        start_headers = _signed_headers(private_key, agent_id, start_body)

        yield _wire("request", "POST", start_path, True,
                    {k: v for k, v in start_headers.items() if k != "X-TrustRail-Signature"},
                    start_payload)
        t0 = time.monotonic()
        try:
            resp = await client.post(
                start_url, content=start_body, headers=start_headers
            )
            latency = int((time.monotonic() - t0) * 1000)
            start_data = resp.json()
            yield _wire("response", "POST", start_path, True,
                        dict(resp.headers), start_data, resp.status_code, latency)
            if resp.status_code != 200:
                yield _chat("system", f"Session start rejected: {start_data.get('detail', start_data)}")
                yield _status("error")
                return
        except Exception as exc:
            yield _chat("system", f"Session start failed: {exc}")
            yield _status("error")
            return

        session_id = start_data["session_id"]
        yield _chat("system", f"Session {session_id} open. Starting negotiation…")

        # ── Step 3: Negotiation turns ────────────────────────────────────────
        history = ""
        turn_path = "/api/gateway/turn"
        turn_url = f"{merchant_url}{turn_path}"

        for turn_num in range(5):
            # Buyer thinks (LLM call — local, no wire event)
            yield _chat("system", f"Turn {turn_num + 1}: buyer agent thinking…")
            buyer_res = generate_buyer_turn(history, task, mandate_id)

            buyer_msg = buyer_res.get("message", task)
            buyer_action = buyer_res.get("action", "PROPOSE")
            buyer_discount = buyer_res.get("requested_discount_pct", 10.0)

            yield _chat("agent",
                f"[Turn {turn_num + 1}] {buyer_msg}\n"
                f"→ requesting {buyer_discount}% off")

            if buyer_action == "ACCEPT":
                yield _chat("agent", "My agent accepted the deal.")
                yield _status("closed_accepted")
                return

            # Send turn to merchant
            turn_payload = {
                "session_id": session_id,
                "buyer_message": buyer_msg,
                "requested_items": buyer_res.get("requested_items", []),
                "requested_discount_pct": buyer_discount,
            }
            turn_body = json.dumps(turn_payload).encode()
            turn_headers = _signed_headers(private_key, agent_id, turn_body)

            # Emit request wire event (omit the signature value itself for readability)
            display_headers = {
                "X-TrustRail-Agent-Id": agent_id,
                "X-TrustRail-Signature": "«ed25519_sig»",
                "Content-Type": "application/json",
            }
            yield _wire("request", "POST", turn_path, True,
                        display_headers, turn_payload)

            t0 = time.monotonic()
            try:
                resp = await client.post(
                    turn_url, content=turn_body, headers=turn_headers
                )
                latency = int((time.monotonic() - t0) * 1000)
            except Exception as exc:
                yield _chat("system", f"Turn {turn_num + 1} HTTP error: {exc}")
                yield _status("error")
                return

            try:
                turn_data = resp.json()
            except Exception:
                turn_data = {"raw": resp.text}

            yield _wire("response", "POST", turn_path, True,
                        dict(resp.headers), turn_data, resp.status_code, latency)

            if resp.status_code != 200:
                detail = turn_data.get("detail", str(turn_data))
                yield _chat("system", f"Turn rejected by server: {detail}")
                yield _status("error")
                return

            merchant_res = turn_data.get("merchant_response", {})
            merchant_msg = merchant_res.get("message", "")
            merchant_action = merchant_res.get("action", "COUNTER")
            merchant_discount = merchant_res.get("offered_discount_pct", 0.0)

            yield _chat("system",
                f"Merchant [{merchant_action}]: {merchant_msg}\n"
                f"→ offering {merchant_discount}% off")

            # Update history for next buyer turn
            history += (
                f"\nBuyer: {buyer_msg}\n"
                f"Merchant: {merchant_msg} (offering {merchant_discount}% off)\n"
            )

            if merchant_action == "ACCEPT":
                bounds_action = turn_data.get("bounds_action", "")
                audit = turn_data.get("audit_trail", {})
                rzp = turn_data.get("razorpay_order", {})
                yield _chat("agent",
                    f"Deal reached!\n"
                    f"Bounds engine: {bounds_action}\n"
                    f"Rule: {audit.get('evaluated', '')}\n"
                    + (f"Razorpay order: {rzp.get('id', '')}" if rzp else ""))
                yield _status("closed_accepted")
                return

            if merchant_action == "REJECT":
                yield _chat("agent", "Merchant rejected the deal.")
                yield _status("closed_rejected")
                return

        # Ran out of turns
        yield _chat("system", "Reached maximum turns without agreement.")
        yield _status("closed_rejected")


# ---------------------------------------------------------------------------
# FastAPI endpoint
# ---------------------------------------------------------------------------

@router.post("/api/buyer-agent/run")
async def run_buyer_agent(req: RunRequest):
    """
    Stream the buyer agent negotiation as NDJSON.
    Each line is a JSON event: {type: "chat"|"wire"|"status", ...}.
    """
    async def event_stream():
        async for chunk in _run_session(req.merchant_url, req.task, req.mandate_id):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={"X-Content-Type-Options": "nosniff"},
    )
