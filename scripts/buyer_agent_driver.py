"""
buyer_agent_driver.py — Standalone external Buyer Agent process.

This is the first genuinely separate agent conversation in TrustRail — no shared
Python call stack with the merchant, only real HTTP. The buyer's private key never
leaves this process. The server receives only the public half.

Tier-1 simplification note: this script imports app.agents.buyer_agent from the
same codebase for convenience, but it runs as its own OS process with its own
private key that never touches the server. The signing contract (Ed25519 over the
request body, X-TrustRail-* headers) is identical to what a fully independent
buyer app would use. Tier 2 replaces the script with a real buyer app but keeps
this exact wire protocol.

Usage:
    python scripts/buyer_agent_driver.py --mandate-id man_xxx --goal "I need 15 graphic tees"
"""
import sys
import os
import json
import argparse
import requests

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

# Add the backend to path so we can import the buyer agent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..","backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.agents.buyer_agent import generate_buyer_turn

API = "http://localhost:8001"
BUYER_AGENT_ID = "buyer_procurement_alpha"

# Generate a fresh keypair for this process — private key never leaves here
BUYER_PRIVATE_KEY = Ed25519PrivateKey.generate()
BUYER_PUBLIC_KEY_HEX = BUYER_PRIVATE_KEY.public_key().public_bytes(
    encoding=Encoding.DER,
    format=PublicFormat.SubjectPublicKeyInfo,
).hex()


def register_self():
    """Register this buyer with the merchant server — public key only."""
    r = requests.post(
        f"{API}/api/agents/{BUYER_AGENT_ID}/register",
        json={
            "role": "buyer",
            "capabilities": ["negotiate", "check_budget"],
            "public_key_hex": BUYER_PUBLIC_KEY_HEX,
        },
    )
    if r.status_code == 200:
        print(f"[BUYER] Registered as {BUYER_AGENT_ID}")
    else:
        print(f"[BUYER] Registration response: {r.status_code} {r.text}")


def signed_post(url: str, payload: dict) -> requests.Response:
    """Sign the request body with this agent's private key and POST."""
    body = json.dumps(payload).encode()
    sig = BUYER_PRIVATE_KEY.sign(body)
    headers = {
        "X-TrustRail-Agent-Id": BUYER_AGENT_ID,
        "X-TrustRail-Signature": sig.hex(),
        "Content-Type": "application/json",
    }
    return requests.post(url, data=body, headers=headers)


def run(mandate_id: str, goal: str, merchant_agent_id: str = "merchant_souledstole_01"):
    register_self()

    # Start a session
    r = signed_post(f"{API}/api/gateway/session/start", {
        "mandate_id": mandate_id,
        "merchant_agent_id": merchant_agent_id,
        "procurement_goal": goal,
    })
    if r.status_code != 200:
        print(f"[BUYER] Failed to start session: {r.status_code} {r.text}")
        return
    session_id = r.json()["session_id"]
    print(f"[BUYER] Session started: {session_id}")

    history = ""
    for turn_num in range(5):
        print(f"\n--- Turn {turn_num + 1} ---")
        buyer_res = generate_buyer_turn(history, goal, mandate_id)
        print(f"[BUYER] {buyer_res.get('message')}")
        print(f"[BUYER] (thought: {buyer_res.get('thought_process', '')[:80]}...)")

        if buyer_res.get("action") == "ACCEPT":
            print("[BUYER] Accepted the deal.")
            break

        tr = signed_post(f"{API}/api/gateway/turn", {
            "session_id": session_id,
            "buyer_message": buyer_res.get("message", ""),
            "requested_items": buyer_res.get("requested_items", []),
            "requested_discount_pct": buyer_res.get("requested_discount_pct", 0.0),
        })

        if tr.status_code != 200:
            print(f"[BUYER] Turn ended: {tr.status_code} {tr.json()}")
            break

        data = tr.json()
        m = data["merchant_response"]
        print(f"[MERCHANT] {m.get('message')}")
        print(f"[MERCHANT] action={m.get('action')}, offering={m.get('offered_discount_pct')}%")

        history += f"\nBuyer: {buyer_res.get('message')}\nMerchant: {m.get('message')}\n"

        if m.get("action") in ("ACCEPT", "REJECT"):
            print(f"\n[OUTCOME] Merchant action: {m.get('action')}")
            if data.get("bounds_action"):
                print(f"[BOUNDS]  {data['bounds_action']}: {data.get('audit_trail', {}).get('evaluated')}")
            if data.get("razorpay_order"):
                print(f"[RAZORPAY] Order: {data['razorpay_order'].get('id')}")
            break
    else:
        print("[BUYER] Max turns reached without agreement.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="TrustRail Buyer Agent Driver")
    p.add_argument("--mandate-id", required=True, help="Mandate ID (man_...)")
    p.add_argument("--goal", required=True, help="Procurement goal description")
    p.add_argument("--merchant-agent-id", default="merchant_souledstole_01")
    a = p.parse_args()
    run(a.mandate_id, a.goal, a.merchant_agent_id)
