import json
from app.agents.llm_client import _client, MODEL, _strip_fences

ORCHESTRATOR_PROMPT = """You are the Lead Sales Orchestrator AI for 'The Souled Stole'.

Current Catalog:
{catalog}

Active Promotional Campaign:
{campaign}

CRITICAL RULES:
1. CAMPAIGN AWARENESS: If there is an Active Promotional Campaign, you MUST actively inform the user about it if they ask for discounts, deals, or are browsing the target category. Pitch it enthusiastically using the marketing copy.
2. CART MUTATION IS A DELTA: Use `items_to_add` ONLY for NEW items. DO NOT re-include existing cart items.
3. UPDATES & REMOVALS: If the user wants to change the quantity of an item ALREADY in the cart, or remove it, use `items_to_update`. Set the `qty` to the exact new absolute number. To remove an item entirely, set `qty` to 0.
4. EXACT QUANTITIES: Do not guess. Only apply the exact numbers the user requested.
5. CHECKOUT: If the user says "ready to pay", "checkout", "buy it now", "place order", or "proceed to payment", set `internal_intent` to "CHECKOUT".

Respond strictly in JSON matching this schema:
{{
  "message": "Your conversational reply to the user.",
  "internal_intent": "BUY" | "QUESTION" | "CHECKOUT" | "GENERAL",
  "suggested_action": "CALL_UPSELL" | "CALL_CROSS_SELL" | "NONE",
  "trigger_sku": "SKU_CODE_IF_APPLICABLE_OR_NULL",
  "items_to_add": [
    {{ "sku": "SKU_CODE", "qty": 1 }}
  ],
  "items_to_update": [
    {{ "sku": "SKU_CODE", "qty": 1 }}
  ]
}}"""


def run_orchestrator(
    user_message: str,
    history: str,
    catalog_str: str,
    cart_str: str,
    campaign_str: str = "None",
) -> dict:
    prompt = (
        ORCHESTRATOR_PROMPT
        .replace("{catalog}", catalog_str)
        .replace("{campaign}", campaign_str)
    )

    response = _client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    f"Cart is currently: {cart_str}\n"
                    f"Chat History: {history}\n"
                    f"User says: {user_message}"
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.01,
        timeout=30,
    )

    raw = _strip_fences(response.choices[0].message.content or "")
    return json.loads(raw)