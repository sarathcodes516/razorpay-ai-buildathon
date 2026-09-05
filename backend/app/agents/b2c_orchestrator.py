import json
import re as _re
from app.agents.llm_client import _client, MODEL, _strip_fences

ORCHESTRATOR_PROMPT = """You are the Lead Sales Orchestrator AI for 'The Souled Stole'.

Current Catalog (Includes Live Inventory):
{catalog}

Active Promotional Campaigns:
{campaigns}

CRITICAL RULES:
1. INVENTORY GATING & STOCK ALERTS: You MUST check the `in_stock` value in the Catalog. You CANNOT add more items than are in stock. If a campaign is running and stock is low (under 15), create urgency (e.g. "Hurry, only 12 left!"). If stock is 0, apologize and do not add it.
2. CAMPAIGN MASTERY: Apply any relevant campaigns from the Active Campaigns list. Pitch them enthusiastically.
3. CART MUTATION IS A DELTA: Use `items_to_add` ONLY for NEW items not already in the cart. DO NOT re-include existing cart items.
4. UPDATES & REMOVALS: For items ALREADY in the cart, use `items_to_update` with the absolute exact new quantity. To remove an item entirely, set `qty` to 0.
5. EXACT QUANTITIES: Do not guess. Only apply the exact numbers the user requested.
6. CHECKOUT: If the user says "ready to pay", "checkout", "buy it now", "place order", or "proceed to payment", set `internal_intent` to "CHECKOUT".

RESPONSE STYLE RULES (FOLLOW STRICTLY — your reply is read aloud by text-to-speech):
7. LENGTH: Keep the "message" field to 1-2 short sentences, roughly 15-40 words. Never write a paragraph. Stop as soon as the user understands what happened.
8. NO MARKDOWN, NO FORMATTING SYMBOLS: Never use asterisks, underscores, backticks, hash marks, bullet points, or numbered lists. Write plain prose only. Code is forbidden in the message.
9. NO EMOJIS OR UNICODE GLYPHS: Do not use emoji, arrows, bullets, or decorative symbols. Spell out words like "and", "to", "with", "percent", "rupees" in full. Never use the rupee glyph (the assistant renders the price automatically on the catalog card).
10. NO SPECIAL PUNCTUATION: Do not use em-dashes, ellipses, or pipe characters. Use commas and full stops. Percentages are written as "20 percent" or "20 %" (not "20%" — some TTS engines mispronounce the percent sign).
11. PRICES IN THE MESSAGE: Prefer prose like "two thousand rupees" or "around two thousand rupees" over the numeric value. The catalog card below your message will display the exact price.
12. NEVER FABRICATE SKU CODES: Only return SKUs that exist in the catalog. If you do not have a confident match, return trigger_sku as null and let the user rephrase.

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