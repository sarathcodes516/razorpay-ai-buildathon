"""
Agent Registry — Ed25519 keypair store for TrustRail agents and principals.

Supports two registration modes:
  - Self-hosted (server generates keypair): for agents that live on this server
    (e.g. the merchant negotiator). Pass no public_key_hex.
  - External (caller supplies public key only): for buyer agents that run in
    their own process and should NEVER share their private key with this server.
    Pass public_key_hex=<DER-encoded hex>. The server stores only the public half.

Private keys (where generated here) are held in-process only, never serialised
to the API. A production implementation would back this with a KMS.
"""
from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_der_public_key,
)

REGISTRY: dict[str, dict] = {}


def register_agent(
    agent_id: str,
    role: str,
    capabilities: list[str],
    public_key_hex: str | None = None,
) -> dict:
    """
    Register an agent. Idempotent — re-registering the same agent_id returns
    the existing entry unchanged (first registration wins).

    Args:
        agent_id:        Unique identifier for this agent.
        role:            e.g. "merchant", "buyer", "principal".
        capabilities:    List of capability strings.
        public_key_hex:  Optional DER-encoded public key hex from an external caller.
                         If omitted, a new Ed25519 keypair is generated server-side.

    Returns public card (no private key).
    """
    if agent_id in REGISTRY:
        return get_agent_card(agent_id)

    if public_key_hex:
        # External agent: store only the public key. No private key on this server.
        REGISTRY[agent_id] = {
            "agent_id": agent_id,
            "role": role,
            "capabilities": capabilities,
            "public_key": public_key_hex,
            "status": "active",
            "_private_key": None,
        }
    else:
        # Self-hosted agent: generate keypair here.
        priv = Ed25519PrivateKey.generate()
        pub_hex = priv.public_key().public_bytes(
            encoding=Encoding.DER,
            format=PublicFormat.SubjectPublicKeyInfo,
        ).hex()
        REGISTRY[agent_id] = {
            "agent_id": agent_id,
            "role": role,
            "capabilities": capabilities,
            "public_key": pub_hex,
            "status": "active",
            "_private_key": priv,
        }

    return get_agent_card(agent_id)


def get_agent_card(agent_id: str) -> dict | None:
    """Return the public agent card (no private key). None if not registered."""
    entry = REGISTRY.get(agent_id)
    if entry is None:
        return None
    return {
        "agent_id": entry["agent_id"],
        "role": entry["role"],
        "capabilities": entry["capabilities"],
        "public_key": entry["public_key"],
        "status": entry.get("status", "active"),
    }


def get_private_key(agent_id: str) -> Ed25519PrivateKey | None:
    """Internal use only — returns the raw private key for signing."""
    entry = REGISTRY.get(agent_id)
    return entry["_private_key"] if entry else None


def get_public_key(agent_id: str) -> Ed25519PublicKey | None:
    """Internal use only — returns the public key object for verification."""
    entry = REGISTRY.get(agent_id)
    if entry is None:
        return None
    # Support both self-hosted (stored as object via _private_key) and
    # external (stored as hex string in public_key)
    priv = entry.get("_private_key")
    if priv is not None:
        return priv.public_key()
    # External agent: reconstruct from stored hex
    try:
        return load_der_public_key(bytes.fromhex(entry["public_key"]))
    except Exception:
        return None
