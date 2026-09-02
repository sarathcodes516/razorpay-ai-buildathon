"""
agent_auth.py — FastAPI dependency for per-agent Ed25519 request signing.

Every request to /api/gateway/* must include:
  X-TrustRail-Agent-Id:  the agent_id registered in the agent registry
  X-TrustRail-Signature: Ed25519 signature over the raw request body (hex)

The server verifies the signature against the public key on file for that agent.
This is NOT a shared secret — each agent has its own keypair and only shares the
public half. A buyer agent's private key should never leave its own process.
"""
from fastapi import Request, HTTPException, Depends
from cryptography.hazmat.primitives.serialization import load_der_public_key
from cryptography.exceptions import InvalidSignature
from app.core.agent_registry import get_agent_card


async def require_signed_agent(request: Request):
    """FastAPI dependency. Raises 401 on any auth failure."""
    agent_id = request.headers.get("X-TrustRail-Agent-Id")
    sig_hex = request.headers.get("X-TrustRail-Signature")

    if not agent_id or not sig_hex:
        raise HTTPException(401, "missing_agent_identity_headers")

    card = get_agent_card(agent_id)
    if not card:
        raise HTTPException(401, "unknown_agent_id")

    body = await request.body()

    try:
        pubkey = load_der_public_key(bytes.fromhex(card["public_key"]))
        pubkey.verify(bytes.fromhex(sig_hex), body)
    except (InvalidSignature, ValueError, Exception):
        raise HTTPException(401, "invalid_signature")

    request.state.verified_agent_id = agent_id
