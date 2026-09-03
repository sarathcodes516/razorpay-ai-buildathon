import json
from app.agents.llm_client import _client, MODEL, _strip_fences

BASE_SPECIALIST_PROMPT = """You are a specialized Sales Agent for 'The Souled Stole'.

Catalog: {catalog}
Trigger Item: {target_item}
Current Cart: {cart_state}
Active Campaign: {campaign}

{specialty_instructions}

CRITICAL RULES:
1. DO NOT suggest any item that is already in the Current Cart. If your first choice is already there, pick a different relevant item from the catalog.
2. CAMPAIGN LEVERAGE: If there is an Active Campaign, use its exact discount logic and marketing copy as your primary incentive. If there is NO active campaign, offer a small realistic discount (e.g., 5-10% off) to close the deal.

You ONLY generate persuasive text. You have NO ability to modify the cart.
Respond strictly in JSON:
{{
  "persuasive_message": "Your highly conversational, short, and persuasive pitch suggesting the new item. Mention the active deal and end with a question like 'Should I add this for you?'"
}}"""


def run_specialist(agent_type: str, catalog_str: str, target_sku: str, cart_str: str = "[]", campaign_str: str = "None") -> dict:
    if agent_type not in ("UPSELL", "CROSS_SELL"):
        raise ValueError(f"Unknown agent_type: {agent_type!r}. Must be 'UPSELL' or 'CROSS_SELL'.")

    instructions = (
        "Suggest a more premium alternative or a bundle upgrade to the trigger item to UPSELL."
        if agent_type == "UPSELL"
        else "Suggest a complementary accessory to CROSS-SELL."
    )

    prompt = (
        BASE_SPECIALIST_PROMPT
        .replace("{catalog}",      catalog_str)
        .replace("{target_item}",  target_sku)
        .replace("{cart_state}",   cart_str)
        .replace("{campaign}",     campaign_str)
        .replace("{specialty_instructions}", instructions)
    )

    response = _client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user",   "content": "Generate the pitch based on the cart, catalog, and active campaign."},
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
        timeout=30,
    )

    raw = _strip_fences(response.choices[0].message.content or "")
    return json.loads(raw)