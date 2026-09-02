"""
Mandate Service — cryptographic signing and verification for TrustRail.

SpendMandate  : signed with the principal's Ed25519 private key (asymmetric).
PaymentMandate: signed with the system HMAC-SHA256 key (symmetric, internal).

The asymmetric SpendMandate signature means any verifier with the principal's
public key can independently confirm the mandate without a shared secret — this
mirrors how NPCI UAP / Google AP2 work with DID-backed credentials.
"""
import hmac as _hmac
import hashlib
import json
from datetime import datetime, timezone, timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat
)
from cryptography.exceptions import InvalidSignature

from app.models.mandate import SpendMandate, PaymentMandate
from app.core.agent_registry import register_agent, get_private_key, get_public_key

# System-level HMAC key — used only for PaymentMandate (internal receipt signing)
_SYSTEM_HMAC_KEY = b"trustrail_system_receipt_key_2026"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _payload_bytes(payload_dict: dict) -> bytes:
    """Canonical JSON serialisation — sort_keys ensures deterministic byte order."""
    return json.dumps(payload_dict, sort_keys=True, default=str).encode("utf-8")


def _hmac_sign(payload_dict: dict) -> str:
    """HMAC-SHA256 over a canonical JSON payload. Used for PaymentMandate."""
    return _hmac.new(_SYSTEM_HMAC_KEY, _payload_bytes(payload_dict), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# SpendMandate — Ed25519 (asymmetric, principal-scoped)
# ---------------------------------------------------------------------------

def _ensure_principal_registered(principal: str) -> None:
    """Auto-register a principal with a fresh Ed25519 keypair if not present."""
    register_agent(
        agent_id=principal,
        role="principal",
        capabilities=["issue_mandate", "approve_payment"],
    )


def _ed25519_sign(principal: str, payload_dict: dict) -> str:
    """Sign payload with the principal's Ed25519 private key. Returns hex signature."""
    private_key: Ed25519PrivateKey = get_private_key(principal)
    if private_key is None:
        raise ValueError(f"Principal '{principal}' is not registered in the agent registry.")
    signature_bytes = private_key.sign(_payload_bytes(payload_dict))
    return signature_bytes.hex()


def _ed25519_verify(principal: str, payload_dict: dict, signature_hex: str) -> bool:
    """Verify an Ed25519 signature against the principal's registered public key."""
    public_key = get_public_key(principal)
    if public_key is None:
        return False
    try:
        public_key.verify(bytes.fromhex(signature_hex), _payload_bytes(payload_dict))
        return True
    except (InvalidSignature, ValueError):
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_mandate(principal: str, limits: dict, valid_hours: int = 24) -> SpendMandate:
    """
    Issue a new SpendMandate signed with the principal's Ed25519 private key.
    Auto-registers the principal in the agent registry if not already present.
    """
    _ensure_principal_registered(principal)

    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=valid_hours)
    mandate_id = f"man_{int(now.timestamp())}"

    # Build the model first so Pydantic coerces all field types (e.g. int → float)
    mandate = SpendMandate(
        mandate_id=mandate_id,
        principal=principal,
        issued_at=now,
        expires_at=expires,
        limits=limits,
        signature=None,
    )

    # Sign the canonical payload — use model_dump so signing and verification
    # always operate on the same Pydantic-coerced values
    payload = {
        "mandate_id": mandate.mandate_id,
        "principal": mandate.principal,
        "issued_at": mandate.issued_at.isoformat(),
        "expires_at": mandate.expires_at.isoformat(),
        "limits": mandate.limits.model_dump(),
    }

    signature = _ed25519_sign(principal, payload)
    return mandate.model_copy(update={"signature": signature})


def verify_mandate(mandate: SpendMandate) -> tuple[bool, str]:
    """
    Verify a SpendMandate — checks expiry then Ed25519 signature.
    Returns (is_valid: bool, reason: str).
    """
    now = datetime.now(timezone.utc)

    # 1. Expiry check
    expiry = (
        mandate.expires_at
        if mandate.expires_at.tzinfo
        else mandate.expires_at.replace(tzinfo=timezone.utc)
    )
    if now > expiry:
        return False, "MANDATE_EXPIRED"

    # 2. Ed25519 signature verification
    if not mandate.signature:
        return False, "MISSING_SIGNATURE"

    payload = {
        "mandate_id": mandate.mandate_id,
        "principal": mandate.principal,
        "issued_at": mandate.issued_at.isoformat(),
        "expires_at": mandate.expires_at.isoformat(),
        "limits": mandate.limits.model_dump(),
    }

    if not _ed25519_verify(mandate.principal, payload, mandate.signature):
        return False, "INVALID_SIGNATURE"

    return True, "VALID"


def create_payment_mandate(cart, mandate_id: str) -> PaymentMandate:
    """
    Close the AP2 mandate chain.

    Hashes the exact approved cart, assembles the PaymentMandate payload,
    signs it with the system HMAC key, and returns the PaymentMandate.
    The payment_mandate_id becomes the Razorpay receipt so every order is
    traceable back to a signed mandate chain entry.
    """
    cart_hash = hashlib.sha256(cart.model_dump_json().encode()).hexdigest()
    payment_mandate_id = f"pm_{int(datetime.now(timezone.utc).timestamp())}_{cart.cart_id}"

    payload = {
        "payment_mandate_id": payment_mandate_id,
        "cart_id": cart.cart_id,
        "mandate_id": mandate_id,
        "authorized_amount": cart.final_amount,
        "cart_hash": cart_hash,
    }

    signature = _hmac_sign(payload)

    return PaymentMandate(
        payment_mandate_id=payment_mandate_id,
        cart_id=cart.cart_id,
        mandate_id=mandate_id,
        authorized_amount=cart.final_amount,
        cart_hash=cart_hash,
        signature=signature,
    )
