"""
agent_catalog.py — Machine-consumable, cryptographically signed catalog.

The UAP / x402 contract: a buyer agent fetches this BEFORE opening a session.
The catalog is enriched with programmatic metadata (negotiable, bulk_eligible)
and signed with the merchant's Ed25519 private key. The buyer verifies the
signature against the merchant's public key (published in the discovery
manifest) before trusting any of the data.
"""
import json
import time
import base64
from fastapi import APIRouter
from app.core.merchant_state import get_store_state
from app.services.b2b_settlement import (
    _MERCHANT_PRIVATE_KEY,
    MERCHANT_PUBKEY_HEX,
    MERCHANT_PUBLIC_DER_HEX,
)

router = APIRouter()


@router.get("/api/catalog/agent")
def get_agent_catalog():
    state = get_store_state()

    agent_items = []
    for item in state.get("catalog", []):
        agent_items.append({
            "sku":           item["sku"],
            "name":          item["name"],
            "list_price":    item["price"],
            "category":      item["category"],
            "in_stock":      item["in_stock"],
            "negotiable":    True,
            "bulk_eligible": item["in_stock"] > 10,
        })

    payload = {
        "merchant_id": "merchant_souledstole_01",
        "timestamp":   int(time.time()),
        "items":       agent_items,
        "active_campaigns": [
            {
                "name":         c["name"],
                "discount_pct": c["discount_pct"],
                "target": (
                    c.get("target_sku")
                    if c.get("target_sku") and c.get("target_sku") != "NONE"
                    else c.get("target_category")
                ),
            }
            for c in state.get("campaigns", [])
        ],
    }

    # Deterministic serialization is strictly required for cryptographic verification
    payload_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)

    # Sign the payload with the merchant's Ed25519 private key
    signature = _MERCHANT_PRIVATE_KEY.sign(payload_str.encode("utf-8"))
    sig_b64 = base64.b64encode(signature).decode("utf-8")

    return {
        "data": payload,
        "metadata": {
            "protocol":   "TrustRail/UAP-0.1",
            "pubkey":     MERCHANT_PUBKEY_HEX,         # raw 32-byte Ed25519 public key
            "pubkey_der": MERCHANT_PUBLIC_DER_HEX,    # same key, DER form (matches manifest)
            "signature":  sig_b64,
        },
    }