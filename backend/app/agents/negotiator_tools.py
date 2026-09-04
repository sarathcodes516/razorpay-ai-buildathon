"""
negotiator_tools.py — Bounded tool functions for the B2B Merchant Negotiator.

Every function here reads live from `STORE_STATE` (the same global state the
MerchantConfigPanel and the Campaign Orchestrator write to). This is the source
of truth for inventory, policy ceilings, and active campaigns.

Hard rule: tools are deterministic and server-authoritative. The LLM may only
READ from these; the LLM's discount request is always clamped inside
`propose_discount` regardless of prompt content.
"""
from typing import Dict, Any, List, Optional
from app.core.merchant_state import get_store_state


def check_inventory(sku: str, requested_qty: int) -> Dict[str, Any]:
    """Live stock + price + high-stock flag for a SKU."""
    state = get_store_state()
    item = next((i for i in state.get("catalog", []) if i["sku"] == sku), None)
    if not item:
        return {
            "available": False,
            "in_stock": 0,
            "reason": f"SKU {sku} not in catalog",
            "sku": sku,
        }

    in_stock = int(item.get("in_stock", 0))
    threshold = int(state.get("policy", {}).get("high_stock_threshold", 20))
    return {
        "available": in_stock >= requested_qty,
        "in_stock": in_stock,
        "is_high_stock": in_stock >= threshold,
        "threshold": threshold,
        "sku": sku,
        "unit_price": float(item.get("price", 0.0)),
    }


def propose_discount(requested_pct: float) -> Dict[str, Any]:
    """
    Pure-math deterministic bounded discount tool.

    Aggressively parses the live merchant policy — the value can arrive as
    int, float, numeric string, or anything else depending on the
    /api/merchant/policy round-trip. If we can't parse it, fall back to the
    documented default of 15.0. NO threat detection lives here — intent
    classification is the merchant LLM's job (see negotiator_agent.py).
    """
    state = get_store_state()
    raw_max = state.get("policy", {}).get("max_allowable_discount_pct", 15.0)
    try:
        max_discount = float(raw_max)
    except (ValueError, TypeError):
        max_discount = 15.0
    # Negative ceilings are nonsensical — clamp to 0 (caller treats 0 as "no discount")
    if max_discount < 0:
        max_discount = 0.0

    try:
        requested = float(requested_pct)
    except (ValueError, TypeError):
        requested = 0.0
    if requested < 0:
        requested = 0.0

    approved_pct = min(requested, max_discount)
    was_capped = requested > max_discount

    if was_capped:
        audit_note = (
            f"Policy ceiling enforced: {approved_pct}% approved "
            f"(requested: {requested}%)"
        )
    else:
        audit_note = f"Discount approved within policy: {approved_pct}%"

    return {
        "requested_pct": requested,
        "approved_pct": approved_pct,
        "max_allowable_pct": max_discount,
        "was_capped": was_capped,
        "audit_note": audit_note,
    }


def check_active_campaign(sku: str, category: Optional[str] = None) -> Dict[str, Any]:
    """Look up any active merchant campaign that targets the SKU or its category."""
    state = get_store_state()
    campaigns = state.get("campaigns", []) or []
    for camp in campaigns:
        target_sku = camp.get("target_sku", "NONE")
        target_cat = camp.get("target_category", "all")
        if not camp.get("active", True):
            continue
        if target_sku != "NONE" and target_sku == sku:
            return _campaign_payload(camp, sku, target_cat)
        if target_sku == "NONE" and (target_cat == "all" or target_cat == category):
            return _campaign_payload(camp, sku, target_cat)
    return {
        "has_campaign": False,
        "discount_pct": 0.0,
        "rationale": "No active campaign targeting this SKU",
    }


def _campaign_payload(camp: dict, sku: str, target_cat: str) -> Dict[str, Any]:
    return {
        "has_campaign": True,
        "campaign_name": camp.get("name"),
        "discount_pct": float(camp.get("discount_pct", 0.0)),
        "budget_limit": float(camp.get("budget_limit", 0.0)),
        "target_category": target_cat,
        "rationale": (
            f"Campaign '{camp.get('name')}' active on target "
            f"{sku or target_cat} ({camp.get('discount_pct')}% off)"
        ),
    }


def propose_bundle_addon(current_skus: List[str]) -> Dict[str, Any]:
    """
    Strictly gated cross-sell engine.

    NEVER invents random clearance discounts. ONLY proposes bundles that have
    been explicitly authorized by the merchant through the Campaign Orchestrator
    (`STORE_STATE["campaigns"]`). If no campaign targets an in-stock SKU the
    buyer isn't already ordering, the tool returns bundle_available=False and
    the LLM is forbidden from improvising.
    """
    state = get_store_state()
    campaigns = state.get("campaigns", []) or []
    catalog = state.get("catalog", [])

    valid_addons = []

    for camp in campaigns:
        if not camp.get("active", True):
            continue
        target_sku = camp.get("target_sku", "NONE")
        target_cat = camp.get("target_category", "all")
        try:
            camp_discount = float(camp.get("discount_pct", 0.0))
        except (TypeError, ValueError):
            camp_discount = 0.0
        if camp_discount <= 0:
            continue

        for item in catalog:
            if item["sku"] in current_skus:
                continue
            if int(item.get("in_stock", 0)) <= 0:
                continue

            is_eligible = False
            if target_sku and target_sku != "NONE" and item["sku"] == target_sku:
                is_eligible = True
            elif target_sku in (None, "", "NONE") and target_cat in ("all", item.get("category")):
                is_eligible = True

            if not is_eligible:
                continue

            regular_price = float(item.get("price", 0.0))
            bundle_price = round(regular_price * (1.0 - camp_discount / 100.0), 2)
            valid_addons.append({
                "sku": item["sku"],
                "name": item["name"],
                "category": item.get("category", "apparel"),
                "regular_price": regular_price,
                "bundle_price": bundle_price,
                "discount_pct": camp_discount,
                "in_stock": int(item.get("in_stock", 0)),
                "campaign_name": camp.get("name"),
                "campaign_id": camp.get("name"),
                "pitch": (
                    f"Authorized Campaign '{camp.get('name')}': "
                    f"add {item['name']} for \u20b9{bundle_price}."
                ),
            })

    if not valid_addons:
        return {"bundle_available": False, "addon": None}

    # Pick the best authorized addon (highest merchant-approved discount)
    best_addon = max(valid_addons, key=lambda x: x["discount_pct"])
    return {
        "bundle_available": True,
        "addon": best_addon,
        "authorized_campaigns": [
            {"name": c.get("name"), "discount_pct": c.get("discount_pct")}
            for c in campaigns if c.get("active", True)
        ],
    }