import os
import uuid
import json
import base64
import time
from typing import Dict, Any, Tuple
import razorpay
from dotenv import load_dotenv
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_dummyKey123")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "dummySecretKey123")

client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

B2B_SETTLEMENT_LEDGER: list[dict] = []

# Single canonical merchant key — also preloaded into the agent registry on
# startup so the discovery manifest advertises the SAME public key that signs
# the agent catalog and the settlement receipt.
_MERCHANT_PRIVATE_KEY = Ed25519PrivateKey.generate()
MERCHANT_PUBLIC_BYTES_RAW = _MERCHANT_PRIVATE_KEY.public_key().public_bytes_raw()
MERCHANT_PUBLIC_DER_HEX = _MERCHANT_PRIVATE_KEY.public_key().public_bytes(
    encoding=Encoding.DER,
    format=PublicFormat.SubjectPublicKeyInfo,
).hex()
MERCHANT_PUBKEY_HEX = MERCHANT_PUBLIC_BYTES_RAW.hex()


def sign_settlement_payload(payload_str: str) -> str:
    """Cryptographically sign the settlement manifest using the merchant's key."""
    signature = _MERCHANT_PRIVATE_KEY.sign(payload_str.encode("utf-8"))
    return base64.b64encode(signature).decode("utf-8")


def execute_autonomous_settlement(
    mandate: Dict[str, Any],
    session_id: str,
    buyer_agent_id: str,
    merchant_agent_id: str,
    sku: str,
    qty: int,
    unit_price: float,
    discount_pct: float,
    total_amount: float,
) -> Tuple[bool, Dict[str, Any], str]:
    """
    Evaluates mandate bounds and creates a Razorpay test order autonomously.
    Returns: (is_success, execution_data, audit_message)
    """
    max_per_txn = float(mandate.get("max_per_transaction", 0.0))
    if total_amount > max_per_txn:
        audit_err = (
            f"EXECUTE REJECTED: Total \u20b9{total_amount:.2f} exceeds "
            f"Mandate Max \u20b9{max_per_txn:.2f}"
        )
        return False, {}, audit_err

    # 2. Bounded & Gated Check: Anomaly Discount Threshold
    anomaly_threshold = float(mandate.get("anomaly_discount_threshold", 15.0))
    if discount_pct > anomaly_threshold:
        audit_err = (
            f"EXECUTE GATED: Discount {discount_pct}% exceeds Anomaly Threshold "
            f"{anomaly_threshold}%. Requires human escalation."
        )
        return False, {}, audit_err

    # 3. Create Autonomous Razorpay Order
    amount_paise = int(round(total_amount * 100))
    receipt_id = f"b2b_{session_id[-8:]}_{uuid.uuid4().hex[:6]}"

    order_payload = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt_id,
        "notes": {
            "protocol": "TrustRail/UAP-0.1",
            "settlement_type": "AUTONOMOUS_ZERO_CLICK",
            "mandate_id": mandate.get("mandate_id", "MANDATE_UNKNOWN"),
            "principal": mandate.get("principal", "Corporate Buyer"),
            "buyer_agent_id": buyer_agent_id,
            "merchant_agent_id": merchant_agent_id,
            "sku": sku,
            "qty": str(qty),
            "discount_pct": str(discount_pct),
        },
    }

    try:
        # STRICT API CALL: No fallbacks, no hardcoded UUIDs.
        # Requires real Razorpay test keys in the .env file. If the live API
        # rejects the call (bad keys, network down, plan limits), the settlement
        # MUST fail and surface a clear error to the gateway.
        rzp_order = razorpay.Order(client).create(data=order_payload)
        rzp_order_id = rzp_order["id"]
    except Exception as exc:
        return False, {}, f"Razorpay Gateway Error: {exc}"

    # 4. Cryptographic Proof of Settlement
    settlement_manifest = {
        "rzp_order_id": rzp_order_id,
        "amount_inr": total_amount,
        "mandate_id": mandate.get("mandate_id"),
        "timestamp": int(time.time()),
        "merchant_agent": merchant_agent_id,
        "buyer_agent": buyer_agent_id,
        "status": "SETTLED",
    }

    signature = sign_settlement_payload(json.dumps(settlement_manifest, sort_keys=True))

    execution_record = {
        "status": "EXECUTED",
        "razorpay_order_id": rzp_order_id,
        "receipt": receipt_id,
        "amount": total_amount,
        "amount_paise": amount_paise,
        "currency": "INR",
        "sku": sku,
        "qty": qty,
        "discount_pct": discount_pct,
        "mandate_id": mandate.get("mandate_id"),
        "merchant_pubkey": MERCHANT_PUBKEY_HEX,
        "settlement_signature": signature,
        "settled_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    }

    B2B_SETTLEMENT_LEDGER.append(execution_record)
    audit_msg = (
        f"Deal reached! Bounds engine: EXECUTE "
        f"Rule: \u20b9{total_amount:.2f} <= \u20b9{max_per_txn:.2f} -> PASS. "
        f"Razorpay Order: {rzp_order_id} generated."
    )

    return True, execution_record, audit_msg


def get_ledger() -> list[dict]:
    return B2B_SETTLEMENT_LEDGER