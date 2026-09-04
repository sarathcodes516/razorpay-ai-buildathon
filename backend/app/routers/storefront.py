import uuid
import json
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from app.agents.b2c_orchestrator import run_orchestrator
from app.agents.specialists import run_specialist
from app.agents.concierge_agent import generate_recovery_message
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


@router.post("/api/storefront/chat")
def b2c_chat(req: B2CChatRequest):
    state = get_store_state()
    catalog = state["catalog"]
    catalog_str = json.dumps(catalog)
    cart_str = json.dumps([i.model_dump() for i in req.current_cart])

    active_campaigns = state.get("campaigns", [])
    campaigns_str = json.dumps(active_campaigns) if active_campaigns else "[]"

    orch = run_orchestrator(req.user_message, req.history, catalog_str, cart_str, campaigns_str)

    reply_message = orch.get("message", "I didn't quite catch that.")
    action        = orch.get("suggested_action", "NONE")
    intent        = orch.get("internal_intent", "GENERAL")
    trigger_sku   = orch.get("trigger_sku")

    new_cart_items = []
    razorpay_order = None

    # 2. Strict cart addition — only what the orchestrator explicitly listed
    for item_req in orch.get("items_to_add", []):
        sku = item_req.get("sku")
        try:
            qty = int(item_req.get("qty", 1))
        except (ValueError, TypeError):
            qty = 1

        item = next((i for i in catalog if i["sku"] == sku), None)
        if item:
            new_cart_items.append({
                "sku":   item["sku"],
                "name":  item["name"],
                "price": item["price"],
                "qty":   qty,
            })

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

    # Resolve the plain-English product name so the specialist prompt is unambiguous
    trigger_item_name = trigger_sku or ""
    if trigger_sku:
        target_item_obj = next((i for i in catalog if i["sku"] == trigger_sku), None)
        if target_item_obj:
            trigger_item_name = target_item_obj["name"]

    # 3. Specialists generate persuasive TEXT ONLY — no cart state
    if action in ("CALL_UPSELL", "CALL_CROSS_SELL") and trigger_sku:
        agent_type = "UPSELL" if action == "CALL_UPSELL" else "CROSS_SELL"
        try:
            specialist = run_specialist(agent_type, catalog_str, trigger_item_name, cart_str, campaigns_str)
            reply_message = specialist.get("persuasive_message", reply_message)
        except Exception:
            pass

    # 4. Checkout — lock cart and create Razorpay order
    if intent == "CHECKOUT":
        # Reconstruct the true final cart from current + this-turn deltas
        final_cart = {c.sku: c.qty for c in req.current_cart}
        for item in new_cart_items:
            final_cart[item["sku"]] = final_cart.get(item["sku"], 0) + item["qty"]
        for item in updated_cart_items:
            if item["qty"] <= 0:
                final_cart.pop(item["sku"], None)
            else:
                final_cart[item["sku"]] = item["qty"]

        total = 0.0
        discount = 0.0

        for sku, qty in final_cart.items():
            cat_item = next((i for i in catalog if i["sku"] == sku), None)
            if cat_item:
                # Hard Inventory Gate: cap checkout qty to live stock
                actual_qty = min(qty, cat_item["in_stock"])
                line_total = cat_item["price"] * actual_qty
                total += line_total

                # Pick the best discount across all eligible campaigns
                best_discount_pct = 0.0
                for camp in active_campaigns:
                    target_sku = camp.get("target_sku", "NONE")
                    target_cat = camp.get("target_category", "all")
                    is_eligible = (
                        (target_sku != "NONE" and sku == target_sku)
                        or (target_sku == "NONE" and target_cat in ["all", cat_item["category"]])
                    )
                    if is_eligible and float(camp.get("discount_pct", 0)) > best_discount_pct:
                        best_discount_pct = float(camp["discount_pct"])

                discount += line_total * (best_discount_pct / 100.0)

        final_total = max(0.0, total - discount)

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
        "is_checkout":     intent == "CHECKOUT",
        "active_campaigns": active_campaigns,
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
