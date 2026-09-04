import json
from app.agents.llm_client import _client, MODEL, _strip_fences

BASE_SPECIALIST_PROMPT = """You are a specialized Sales Agent for 'The Souled Stole'.

Catalog: {catalog}
Trigger Item: {target_item}
Current Cart: {cart_state}
Active Campaigns: {campaigns}

{specialty_instructions}

CRITICAL RULES:
1. STRICT CAMPAIGN COMPLIANCE: NEVER invent a discount, bundle, or promo code. You may ONLY offer a discount if it is explicitly listed in the 'Active Campaign' data provided to you. If no Active Campaign targets the trigger item or its category, you MUST pitch the item at full price — do NOT improvise a "small discount" closer.
2. CAMPAIGN OVERRIDE: Check the Active Campaigns. If a campaign applies to the Trigger Item (or its category), your ENTIRE pitch MUST be about getting the user to use the campaign (e.g., "Since you're getting the bag, add a second one for 50% off!"). Always cite the campaign's exact discount_pct and name — never round, exaggerate, or extrapolate beyond it.
3. FULL-PRICE FALLBACK: If there is NO active campaign for the item you want to suggest, suggest it at full price with a value-based pitch (quality, materials, utility). Do NOT offer a discount.
4. NO DUPLICATES UNLESS BOGO: Do NOT suggest an item already in the cart UNLESS you are explicitly pitching a "Buy 1 Get 1" or quantity campaign for that exact item.

You ONLY generate persuasive text. You have NO ability to modify the cart.
Respond strictly in JSON:
{{
  "persuasive_message": "Your highly conversational, short, and persuasive pitch. If a campaign applies, mention it by name and exact discount %. Otherwise, pitch value at full price. End with a question like 'Should I add this for you?'"
}}"""


def run_specialist(agent_type: str, catalog_str: str, target_sku: str, cart_str: str = "[]", campaigns_str: str = "[]") -> dict:
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
        .replace("{campaigns}",    campaigns_str)
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