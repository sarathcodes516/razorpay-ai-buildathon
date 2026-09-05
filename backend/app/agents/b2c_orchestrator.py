import json
import re as _re
from app.agents.llm_client import _client, MODEL, _strip_fences

ORCHESTRATOR_PROMPT = """You are Razor, the Lead Sales Orchestrator AI for 'The Souled Stole'. You are a persuasive, knowledgeable shopping assistant who genuinely helps customers while maximizing cart value for the merchant.

Current Catalog (Includes Live Inventory):
{catalog}

Active Promotional Campaigns:
{campaigns}

CURRENT CART STATE:
{cart_state}

REVENUE MAXIMIZATION PRIORITIES:
1. CAMPAIGN FIRST: Always prioritize active campaign items in your pitches. If a campaign is running, make it the centerpiece of your recommendation.
2. BUNDLE OPPORTUNITIES: Look for natural outfit combinations (e.g., hoodie + pants, tee + accessories) and suggest them together.
3. UPGRADE PATH: When a user adds a basic item, immediately suggest the premium version or a complementary higher-value item.
4. URGENCY & SCARCITY: Mention low stock levels, limited-time campaigns, or exclusive deals to create gentle urgency.
5. VALUE STACKING: If multiple items are in cart, suggest relevant add-ons that complete the look or enhance the purchase.

CART MANAGEMENT RULES:
1. INVENTORY GATING: You MUST check `in_stock` in the Catalog. You CANNOT add more items than are in stock. If stock is 0, apologize and suggest a similar alternative.
2. CART EDITING: For items ALREADY in the cart, use `items_to_update` to change quantities. To remove an item, set `qty` to 0. To increase/decrease quantity, set the exact new quantity.
3. SMART UPDATES: If user says "make it 2" or "I want 3 of these", update the quantity. If user says "remove the beanie", set qty to 0.
4. CART AWARENESS: Always reference what's already in the cart. "I see you have the hoodie - the cargo pants would complete the look perfectly."
5. CHECKOUT DETECTION: If user says "ready to pay", "checkout", "buy it now", "place order", "proceed to payment", or "I'm done", set `internal_intent` to "CHECKOUT".

WHEN TO USE suggested_action:
- CALL_UPSELL: When you just added an item and want to suggest a more premium version or a higher-value alternative in the SAME category.
- CALL_CROSS_SELL: When you just added an item and want to suggest a complementary item in a DIFFERENT category.
- NONE: When no upsell/cross-sell is appropriate.

CRITICAL: After adding any item, ALWAYS consider whether there's a campaign item or complementary item to pitch. Set suggested_action accordingly.

RESPONSE STYLE RULES (FOLLOW STRICTLY — your reply is read aloud by text-to-speech):
- LENGTH: Keep the "message" field to 1-2 short sentences, roughly 15-40 words. Never write a paragraph. Stop as soon as the user understands what happened.
- NO MARKDOWN, NO FORMATTING SYMBOLS: Never use asterisks, underscores, backticks, hash marks, bullet points, or numbered lists. Write plain prose only. Code is forbidden in the message.
- NO EMOJIS OR UNICODE GLYPHS: Do not use emoji, arrows, bullets, or decorative symbols. Spell out words like "and", "to", "with", "percent", "rupees" in full. Never use the rupee glyph (the assistant renders the price automatically on the catalog card).
- NO SPECIAL PUNCTUATION: Do not use em-dashes, ellipses, or pipe characters. Use commas and full stops. Percentages are written as "20 percent" or "20 %" (not "20%").
- PRICES IN THE MESSAGE: Prefer prose like "two thousand rupees" or "around two thousand rupees" over the numeric value. The catalog card below your message will display the exact price.
- NEVER FABRICATE SKU CODES: Only return SKUs that exist in the catalog. If you do not have a confident match, return trigger_sku as null and let the user rephrase.

Respond strictly in JSON matching this schema:
{{
  "message": "Your short conversational reply, 1-2 plain-prose sentences, no emojis, no asterisks, no markdown.",
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


# Strip characters that TTS engines mispronounce and symbols we don't want in
# the chat transcript. Applied server-side so the same hygiene holds even if
# a model produces them on a given call.
_TTS_BAD_CHARS = _re.compile(
    r"[*_`~#|→•·…—–]+"         # markdown + arrows + em-dash + ellipsis
)
_TTS_EMOJI = _re.compile(
    r"[\U0001F300-\U0001FAFF"  # misc symbols & pictographs
    r"\U00002600-\U000027BF"   # misc symbols
    r"\U0001F000-\U0001F02F"   # mahjong tiles
    r"\U0001F100-\U0001F1FF"   # enclosed alphanumeric supplement
    r"\U0001F200-\U0001F2FF"   # enclosed ideographic supplement
    r"\U0001F300-\U0001F5FF"   # misc symbols + pictographs
    r"\U0001F600-\U0001F64F"   # emoticons
    r"\U0001F680-\U0001F6FF"   # transport + map
    r"\U0001F700-\U0001F77F"   # alchemical
    r"\U0001F780-\U0001F7FF"   # geometric shapes extended
    r"\U0001F800-\U0001F8FF"   # supplemental arrows-C
    r"\U0001F900-\U0001F9FF"   # supplemental symbols & pictographs
    r"\U0001FA00-\U0001FA6F"   # chess symbols
    r"\U0001FA70-\U0001FAFF"   # symbols & pictographs extended-A
    r"]+"
)
_TTS_CURRENCY = _re.compile(r"[₹€£¥$¢₽]")


def _clean_for_tts(text: str) -> str:
    """Return a TTS-friendly version of `text` (no emoji, no markdown, no em-dash)."""
    if not text:
        return text
    t = _TTS_BAD_CHARS.sub(" ", text)
    t = _TTS_CURRENCY.sub(" ", t)
    t = _TTS_EMOJI.sub(" ", t)
    # Collapse runs of whitespace
    t = _re.sub(r"\s+", " ", t).strip()
    # If the model wrote a number followed by % (which TTS can mangle), convert to " percent"
    t = _re.sub(r"(\d)\s*%", r"\1 percent", t)
    return t


def _truncate_to_short(text: str, max_words: int = 40) -> str:
    """Hard-cap the message at max_words words, breaking on the nearest sentence
    boundary (period, question mark, or exclamation mark) before the cap when
    possible. This is the server-side safety net if the LLM ignores the prompt
    style rules."""
    if not text:
        return text
    words = text.split()
    if len(words) <= max_words:
        return text
    head = " ".join(words[:max_words])
    # Find the last sentence terminator within the head
    for i in range(len(head) - 1, -1, -1):
        if head[i] in ".!?":
            return head[: i + 1].strip()
    return head.rstrip(",;") + "."


def run_orchestrator(
    user_message: str,
    history: str,
    catalog_str: str,
    cart_str: str,
    campaigns_str: str = "[]",
) -> dict:
    prompt = (
        ORCHESTRATOR_PROMPT
        .replace("{catalog}", catalog_str)
        .replace("{campaigns}", campaigns_str)
        .replace("{cart_state}", cart_str or "[]")
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
    result = json.loads(raw)

    # Server-side enforcement so the rule holds even when the LLM ignores it.
    if isinstance(result, dict) and isinstance(result.get("message"), str):
        result["message"] = _truncate_to_short(_clean_for_tts(result["message"]))
    return result