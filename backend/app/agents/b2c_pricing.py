"""
b2c_pricing.py — Single source of truth for B2C pricing/campaign math.

Both the orchestrator prompt input and the checkout total use `annotate_catalog`
+ `checkout_totals`, so the chat total the user sees always matches the
Razorpay order amount the server creates. Eligibility uses the same
`evaluate_campaign_eligibility` the B2B negotiator tools use, so B2C and B2B
discount logic cannot drift.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.agents.negotiator_tools import evaluate_campaign_eligibility


def _round2(n: float) -> float:
    return round(float(n), 2)


def _targets(camp: Dict[str, Any], item: Dict[str, Any]) -> bool:
    """True if `camp` is structurally aimed at `item`'s SKU or category."""
    target_sku = (camp.get("target_sku") or "NONE").strip()
    target_cat = (camp.get("target_category") or "all").strip()
    if target_sku and target_sku != "NONE" and target_sku == item.get("sku"):
        return True
    if target_sku in (None, "", "NONE") and target_cat in ("all", item.get("category")):
        return True
    return False


def best_eligible_discount(
    catalog_item: Dict[str, Any],
    campaigns: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], float]:
    """
    Return (best_campaign_dict, discount_pct) currently applicable to
    `catalog_item`, honouring `trigger_rule` and live stock.
    """
    best_pct = 0.0
    best_camp: Dict[str, Any] = {}
    for camp in campaigns or []:
        if not camp.get("active", True):
            continue
        if not _targets(camp, catalog_item):
            continue
        if not evaluate_campaign_eligibility(camp, catalog_item.get("sku", ""), catalog_item):
            continue
        try:
            pct = float(camp.get("discount_pct", 0.0))
        except (TypeError, ValueError):
            continue
        if pct > best_pct:
            best_pct = pct
            best_camp = camp
    return best_camp, best_pct


def annotate_catalog(
    catalog: List[Dict[str, Any]],
    campaigns: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Return a copy of `catalog` enriched with per-item campaign info:
      - list_price           : the raw catalog price (preserved)
      - best_discount_pct    : float (0 if none eligible right now)
      - eligible_campaigns   : list of {name, discount_pct, trigger_rule}
      - effective_price      : list_price * (1 - best_discount_pct/100), floored at 0

    `in_stock` and `category` are kept untouched. This annotated view is what
    feeds the orchestrator prompt AND what `checkout_totals` uses, so the agent
    message and the Razorpay total can never drift apart.
    """
    out: List[Dict[str, Any]] = []
    for item in catalog:
        annotated = dict(item)
        list_price = float(item.get("price", 0.0) or 0.0)

        eligible: List[Dict[str, Any]] = []
        best_pct = 0.0
        for camp in campaigns or []:
            if not camp.get("active", True):
                continue
            if not _targets(camp, item):
                continue
            if not evaluate_campaign_eligibility(camp, item.get("sku", ""), item):
                continue
            try:
                pct = float(camp.get("discount_pct", 0.0))
            except (TypeError, ValueError):
                continue
            if pct <= 0:
                continue
            eligible.append({
                "name": camp.get("name") or "",
                "discount_pct": pct,
                "trigger_rule": camp.get("trigger_rule", "always"),
            })
            if pct > best_pct:
                best_pct = pct

        annotated["list_price"] = list_price
        annotated["best_discount_pct"] = best_pct
        annotated["eligible_campaigns"] = eligible
        annotated["effective_price"] = _round2(max(0.0, list_price * (1.0 - best_pct / 100.0)))
        out.append(annotated)
    return out


def checkout_totals(
    final_cart: Dict[str, float],
    annotated_catalog: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Re-derive subtotal/discount/total from `final_cart` (sku -> qty) and the
    annotated catalog. Capped to `in_stock`. Returns
    {subtotal, discount, final_amount, lines}.
    """
    by_sku = {i["sku"]: i for i in annotated_catalog if "sku" in i}
    subtotal = 0.0
    discount = 0.0
    lines: List[Dict[str, Any]] = []
    for sku, qty in final_cart.items():
        meta = by_sku.get(sku)
        if not meta:
            continue
        stock = int(meta.get("in_stock", 0))
        capped_qty = min(int(qty), stock)
        if capped_qty <= 0:
            continue
        unit = float(meta.get("list_price", meta.get("price", 0.0)) or 0.0)
        pct = float(meta.get("best_discount_pct", 0.0) or 0.0)
        line_sub = unit * capped_qty
        line_disc = line_sub * (pct / 100.0)
        subtotal += line_sub
        discount += line_disc
        applied = (meta.get("eligible_campaigns") or [{}])[-1].get("name") if pct > 0 else None
        lines.append({
            "sku": sku,
            "name": meta.get("name"),
            "qty": capped_qty,
            "unit_price": unit,
            "line_subtotal": _round2(line_sub),
            "discount_pct": pct,
            "line_discount": _round2(line_disc),
            "line_total": _round2(line_sub - line_disc),
            "applied_campaign": applied,
        })
    return {
        "subtotal": _round2(subtotal),
        "discount": _round2(discount),
        "final_amount": _round2(max(0.0, subtotal - discount)),
        "lines": lines,
    }