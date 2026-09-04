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


def _der_hex(priv: Ed25519PrivateKey) -> str:
    """Return the public half of `priv` as DER (SubjectPublicKeyInfo) hex."""
    return priv.public_key().public_bytes(
        encoding=Encoding.DER,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).hex()


def register_agent(
    agent_id: str,
    role: str,
    capabilities: list[str],
    public_key_hex: str | None = None,
) -> dict:
    """
    Register an agent. Idempotent — re-registering the same agent_id returns
    the existing entry unchanged (first registration wins).
    """
    if agent_id in REGISTRY:
        return get_agent_card(agent_id)

    if public_key_hex:
        REGISTRY[agent_id] = {
            "agent_id": agent_id,
            "role": role,
            "capabilities": capabilities,
            "public_key": public_key_hex,
            "status": "active",
            "_private_key": None,
        }
    else:
        priv = Ed25519PrivateKey.generate()
        REGISTRY[agent_id] = {
            "agent_id": agent_id,
            "role": role,
            "capabilities": capabilities,
            "public_key": _der_hex(priv),
            "status": "active",
            "_private_key": priv,
        }

    return get_agent_card(agent_id)


def register_agent_with_private_key(
    agent_id: str,
    role: str,
    capabilities: list[str],
    private_key: Ed25519PrivateKey,
) -> dict:
    """Register or replace an agent using a pre-existing Ed25519 private key.

    Used by the b2b_settlement service so the merchant settlement key is the
    same key the agent registry advertises in the discovery manifest. The
    manifest pubkey then verifies the signed agent catalog and settlement
    receipt without a key-format mismatch.
    """
    REGISTRY[agent_id] = {
        "agent_id": agent_id,
        "role": role,
        "capabilities": capabilities,
        "public_key": _der_hex(private_key),
        "status": "active",
        "_private_key": private_key,
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
    """Internal use only — returns the public key object for verification.

    Accepts both DER (SubjectPublicKeyInfo) hex AND raw 32-byte hex, so a
    caller that registered via DER (legacy) and one that registered via raw
    32 bytes both work transparently.
    """
    entry = REGISTRY.get(agent_id)
    if entry is None:
        return None
    priv = entry.get("_private_key")
    if priv is not None:
        return priv.public_key()
    try:
        raw = bytes.fromhex(entry["public_key"])
        if len(raw) == 32:
            # Raw 32-byte Ed25519 public key (UAP convention)
            return Ed25519PublicKey.from_public_bytes(raw)
        # DER-encoded Ed25519 public key
        return load_der_public_key(raw)
    except Exception:
        return None