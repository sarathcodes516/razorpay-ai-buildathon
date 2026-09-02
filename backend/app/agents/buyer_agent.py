"""
buyer_agent.py — The external Procurement AI.

Trust boundary: this is the BUYER's own delegate. It is allowed to see its own
mandate limits so it can behave sensibly (e.g. not request a 30% discount when
its mandate only permits accepting 15%). This does NOT violate the invariant that
"the merchant/negotiator agent never sees monetary limits." That invariant protects
the BUYER's ceiling from being visible to the SELLER — showing your ceiling to the
party negotiating against you is bad information-asymmetry, just like in a real
negotiation. The buyer agent seeing its OWN limits is a legitimate, different thing.
The bounds engine enforces the real limit downstream regardless of what the buyer
"believes," so there is no transaction-safety hole here.
"""
import json
from app.agents.llm_client import run_agent_turn


def check_remaining_budget(mandate_id: str) -> dict:
    """
    Returns the buyer's own mandate limits and remaining daily budget.
    Only the buyer agent has access to this tool — the merchant never sees these numbers.
    """
    from app.routers.mandate import MOCK_DB
    from app.core.spend_ledger import get_spent_today
    mandate = MOCK_DB.get(mandate_id)
    if not mandate:
        return {"error": "mandate_not_found"}
    return {
        "max_per_transaction": mandate.limits.max_per_transaction,
        "remaining_today": mandate.limits.max_total_spend_today - get_spent_today(mandate_id),
        "max_discount_i_can_accept_pct": mandate.limits.max_discount_agent_can_accept_pct,
    }


BUYER_PROMPT = """You are an autonomous Procurement AI negotiating a bulk purchase.

Available products at this store (use these exact SKU values):
- TEE-001: Cyberpunk Oversized Graphic Tee, ₹999, apparel
- HOD-002: Tokyo Drift Heavyweight Hoodie, ₹1999, apparel
- CRG-003: Utility Cargo Pants V2, ₹1499, apparel
- ACC-004: Tactical Crossbody Bag, ₹799, accessories
- ACC-005: Classic Logo Beanie, ₹499, accessories

You may call check_remaining_budget(mandate_id) to see your spending limits before proposing.
Never reveal your exact budget or discount ceiling to the merchant.

Negotiation history so far:
{history}

Respond with this exact JSON and NOTHING else — no extra text, no markdown:
{{"thought_process":"<one sentence strategy>","action":"PROPOSE"|"ACCEPT"|"REJECT","message":"<concise message to merchant, 1-2 sentences>","requested_items":[{{"sku":"...","qty":N,"price":N,"category":"..."}}],"requested_discount_pct":N}}"""


def generate_buyer_turn(history: str, goal: str, mandate_id: str = "") -> dict:
    """
    Run one buyer negotiation turn using real tool calling.
    mandate_id is passed so the agent can call check_remaining_budget.
    Raises on unrecoverable LLM errors so the caller gets a real exception.
    """
    prompt = BUYER_PROMPT.replace("{history}", history)
    user_input = (
        f"Goal: {goal}. "
        f"Mandate ID: {mandate_id}. "
        "Make your next negotiation move."
    )

    tool_fns = [check_remaining_budget]
    tool_impls = {"check_remaining_budget": check_remaining_budget}

    final_text, trace = run_agent_turn(
        system_prompt=prompt,
        user_input=user_input,
        tools=tool_fns,
        tool_impls=tool_impls,
        max_tool_rounds=6,
    )

    try:
        result = json.loads(_strip_fences(final_text))
    except (json.JSONDecodeError, ValueError):
        result = {
            "thought_process": final_text[:300],
            "action": "PROPOSE",
            "message": final_text,
            "requested_items": [],
            "requested_discount_pct": 10.0,
        }

    result["_tool_trace"] = trace
    return result


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return text.strip()
