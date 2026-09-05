import uuid
import json
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from app.agents.b2c_orchestrator import run_orchestrator
from app.agents.specialists import run_specialist
from app.agents.concierge_agent import generate_recovery_message
from app.agents.b2c_pricing import annotate_catalog, checkout_totals as pricing_totals
from app.agents.b2c_intent_gate import (
    is_checkout_intent,
    looks_like_acceptance,
    normalize_intent,
    next_best_pitch_sku,
)
from app.core.merchant_state import get_store_state
from app.integrations.razorpay_client import create_order, KEY_ID as RAZORPAY_KEY_ID

router = APIRouter()


class CartItemInfo(BaseModel):
    sku: str
    qty: int


class B2CChatRequest(BaseModel):
    user_message: str
    history: str = ""
    current_cart: List[CartItemInfo] = []


class PaymentFailedWebhook(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    error_code: str
    error_description: str
    error_reason: str


def _cart_skus(current_cart: List[CartItemInfo]) -> set[str]:
    return {c.sku for c in current_cart}


def _line_breakdown_for_message(totals: dict) -> str:
    """Tiny human-readable summary used for follow-up upsell pitches."""
    if not totals or not totals.get("lines"):
        return ""
    bits = []
    for ln in totals["lines"]:
        if float(ln.get("discount_pct", 0)) > 0:
            bits.append(
                f"{ln['qty']}x {ln['name']} (Rs {ln['line_total']} after "
                f"{ln['discount_pct']:.0f} percent off)"
            )
        else:
            bits.append(f"{ln['qty']}x {ln['name']} (Rs {ln['line_total']})")
    return "; ".join(bits)


def _campaign_blurb_for_items(items: List[dict], annotated: List[dict]) -> str:
    """Return a short sentence mentioning any campaign that applies to the
    items that were just added, so the orchestrator's confirmation message
    always surfaces the discount without relying on the LLM to remember."""
    if not items:
        return ""
    by_sku = {i["sku"]: i for i in annotated}
    campaigns_seen: dict[str, dict] = {}
    for it in items:
        meta = by_sku.get(it["sku"])
        if not meta:
            continue
        for camp in meta.get("eligible_campaigns") or []:
            name = camp.get("name")
            if name and name not in campaigns_seen:
                campaigns_seen[name] = camp
    if not campaigns_seen:
        return ""
    parts = []
    for camp in campaigns_seen.values():
        pct = camp.get("discount_pct", 0)
        name = camp.get("name", "our campaign")
        target = camp.get("target_category") or camp.get("target_sku") or "these items"
        parts.append(f"{name} is active on {target} at {pct:.0f} percent off")
    return " ".join(parts) + "."


@router.post("/api/storefront/chat")
def b2c_chat(req: B2CChatRequest):
    state = get_store_state()
    catalog = state["catalog"]
    active_campaigns = state.get("campaigns", []) or []

    annotated = annotate_catalog(catalog, active_campaigns)
    catalog_str = json.dumps(annotated)
    cart_str = json.dumps([i.model_dump() for i in req.current_cart])
    campaigns_str = json.dumps(active_campaigns) if active_campaigns else "[]"

    # Enrich the user-context with cart so the LLM never loses track.
    cart_skus = _cart_skus(req.current_cart)
    cart_summary = _line_breakdown_for_message(
        pricing_totals({c.sku: c.qty for c in req.current_cart}, annotated)
    ) if cart_skus else ""
    user_context = (
        f"Cart is currently: {cart_str}\n"
        + (f"Cart totals now: {cart_summary}\n" if cart_summary else "")
        + f"Chat History: {req.history}\n"
        + f"User says: {req.user_message}"
    )

    orch = run_orchestrator(req.user_message, req.history, catalog_str, cart_str, campaigns_str)

    reply_message = orch.get("message", "I didn't quite catch that.")
    llm_action    = orch.get("suggested_action", "NONE")
    llm_intent    = orch.get("internal_intent", "GENERAL")
    trigger_sku   = orch.get("trigger_sku")

    # Server-authoritative intent — never trust the LLM for CHECKOUT.
    intent = normalize_intent(
        llm_intent,
        req.user_message,
        cart_is_empty=not cart_skus,
    )

    new_cart_items = []
    razorpay_order = None
    checkout_breakdown = None
    follow_up_pitch: dict | None = None

    # 2. Strict cart addition — only what the orchestrator explicitly listed
    for item_req in orch.get("items_to_add", []):
        sku = item_req.get("sku")
        try:
            qty = int(item_req.get("qty", 1))
        except (ValueError, TypeError):
            qty = 1

        ann_item = next((i for i in annotated if i["sku"] == sku), None)
        if ann_item:
            new_cart_items.append({
                "sku":   ann_item["sku"],
                "name":  ann_item["name"],
                "price": ann_item["price"],
                "qty":   qty,
            })

    # If items were added and any have campaigns, inject a short campaign
    # blurb into the reply so the user sees the promotion immediately even
    # if the LLM forgot to mention it.
    if new_cart_items:
        campaign_blurb = _campaign_blurb_for_items(new_cart_items, annotated)
        if campaign_blurb:
            base_reply = reply_message or ""
            if campaign_blurb not in base_reply:
                reply_message = f"{base_reply} {campaign_blurb}".strip()

    # 2b. Explicit cart updates / removals (absolute qty override)
    updated_cart_items = []
    for item_req in orch.get("items_to_update", []):
        sku = item_req.get("sku")
        try:
            qty = int(item_req.get("qty", 0))
        except (ValueError, TypeError):
            qty = 0
        if sku:
            updated_cart_items.append({"sku": sku, "qty": qty})

    # Guarantee trigger item matches what was actually just added this turn
    if new_cart_items:
        trigger_sku = new_cart_items[-1]["sku"]

    trigger_item_name = trigger_sku or ""
    if trigger_sku:
        target_item_obj = next((i for i in annotated if i["sku"] == trigger_sku), None)
        if target_item_obj:
            trigger_item_name = target_item_obj["name"]

    # 3. Specialist call — only when the orchestrator actually requested one AND
    # the current message wasn't an acceptance of an earlier pitch (in which
    # case we run our deterministic follow-up loop below instead).
    user_was_accepting = looks_like_acceptance(req.user_message)
    used_specialist = False
    if llm_action in ("CALL_UPSELL", "CALL_CROSS_SELL") and trigger_sku and not user_was_accepting:
        agent_type = "UPSELL" if llm_action == "CALL_UPSELL" else "CROSS_SELL"
        try:
            specialist = run_specialist(agent_type, catalog_str, trigger_item_name, cart_str, campaigns_str)
            reply_message = specialist.get("persuasive_message", reply_message)
            used_specialist = True
        except Exception:
            pass

    # 4. Follow-up re-pitch loop — when items were added this turn, run the
    # specialist so the conversation keeps selling. We avoid double-firing when
    # the orchestrator already drove a specialist turn itself.
    if (
        new_cart_items
        and not used_specialist
        and intent != "CHECKOUT"
    ):
        just_added = new_cart_items[-1]["sku"]
        projected_cart = {c.sku: c.qty for c in req.current_cart}
        for item in new_cart_items:
            projected_cart[item["sku"]] = projected_cart.get(item["sku"], 0) + item["qty"]
        next_sku = next_best_pitch_sku(
            annotated,
            current_cart_skus=set(projected_cart.keys()),
            just_added_sku=just_added,
        )
        if next_sku:
            next_meta = next((c for c in annotated if c["sku"] == next_sku), None)
            if next_meta:
                # Pick CROSS_SELL when categories differ, UPSELL when same.
                just_meta = next((c for c in annotated if c["sku"] == just_added), None)
                agent_type = "CROSS_SELL" if (
                    just_meta and next_meta.get("category") != just_meta.get("category")
                ) else "UPSELL"
                try:
                    specialist = run_specialist(
                        agent_type,
                        catalog_str,
                        next_meta["name"],
                        json.dumps([
                            {"sku": k, "qty": v} for k, v in projected_cart.items()
                        ]),
                        campaigns_str,
                    )
                    pitch_msg = specialist.get("persuasive_message") or ""
                    if pitch_msg:
                        follow_up_pitch = {
                            "agent_type": agent_type,
                            "trigger_sku": next_sku,
                            "trigger_name": next_meta["name"],
                            "list_price": float(next_meta.get("list_price", 0.0)),
                            "effective_price": float(next_meta.get("effective_price", 0.0)),
                            "best_discount_pct": float(next_meta.get("best_discount_pct", 0.0)),
                            "eligible_campaigns": next_meta.get("eligible_campaigns") or [],
                            "message": pitch_msg,
                        }
                        reply_message = pitch_msg
                    else:
                        campaign_blurb = ""
                        campaigns = next_meta.get("eligible_campaigns") or []
                        if campaigns:
                            camp = campaigns[0]
                            campaign_blurb = (
                                f" It's {camp.get('discount_pct', 0):.0f} percent off"
                                f" with {camp.get('name', 'our campaign')}."
                            )
                        reply_message = (
                            f"{next_meta['name']} would complete this cart nicely."
                            f"{campaign_blurb} Should I add it for you?"
                        )
                except Exception:
                    campaign_blurb = ""
                    campaigns = next_meta.get("eligible_campaigns") or []
                    if campaigns:
                        camp = campaigns[0]
                        campaign_blurb = (
                            f" It's {camp.get('discount_pct', 0):.0f} percent off"
                            f" with {camp.get('name', 'our campaign')}."
                        )
                    reply_message = (
                        f"{next_meta['name']} would complete this cart nicely."
                        f"{campaign_blurb} Should I add it for you?"
                    )

    # 5. Checkout — only honour when server says it's a checkout phrase AND
    # the cart is non-empty.
    if intent == "CHECKOUT" and cart_skus:
        final_cart = {c.sku: c.qty for c in req.current_cart}
        for item in new_cart_items:
            final_cart[item["sku"]] = final_cart.get(item["sku"], 0) + item["qty"]
        for item in updated_cart_items:
            if item["qty"] <= 0:
                final_cart.pop(item["sku"], None)
            else:
                final_cart[item["sku"]] = item["qty"]

        totals = pricing_totals(final_cart, annotated)
        checkout_breakdown = totals
        final_total = totals["final_amount"]

        if final_total > 0:
            razorpay_order = create_order(final_total, f"b2c_{uuid.uuid4().hex[:8]}")
            reply_message = "I have locked in your cart with the discounts applied! Sending you to secure payment now."
        else:
            reply_message = "Your cart is empty. What would you like to add before checking out?"

    return {
        "agent_message":   reply_message,
        "added_items":     new_cart_items,
        "updated_items":   updated_cart_items,
        "razorpay_order":  razorpay_order,
        "razorpay_key_id": RAZORPAY_KEY_ID,
        "is_checkout":     bool(intent == "CHECKOUT" and razorpay_order),
        "active_campaigns": active_campaigns,
        "annotated_catalog": annotated,
        "checkout_breakdown": checkout_breakdown,
        "follow_up_pitch": follow_up_pitch,
    }


@router.post("/api/storefront/payment-failed")
def handle_payment_failed(req: PaymentFailedWebhook):
    reason = f"{req.error_description} (code: {req.error_code}, reason: {req.error_reason})"
    llm_response = generate_recovery_message(reason)
    return {
        "agent_message":         llm_response.get("message"),
        "recovery_discount_pct": llm_response.get("discount_pct", 5.0),
        "razorpay_payment_id":   req.razorpay_payment_id,
        "razorpay_order_id":     req.razorpay_order_id,
        "error_code":            req.error_code,
        "error_description":     req.error_description,
        "error_reason":          req.error_reason,
    }
