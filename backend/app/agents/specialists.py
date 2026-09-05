import json
import re as _re
from app.agents.llm_client import _client, MODEL, _strip_fences

BASE_SPECIALIST_PROMPT = """You are a specialized Sales Agent for 'The Souled Stole'.

Catalog: {catalog}
Trigger Item: {target_item}
Current Cart: {cart_state}
Active Campaigns: {campaigns}

{specialty_instructions}

CRITICAL RULES:
1. STRICT CAMPAIGN COMPLIANCE: NEVER invent a discount, bundle, or promo code. You may ONLY offer a discount if it is explicitly listed in the 'Active Campaign' data provided to you. If no Active Campaign targets the trigger item or its category, you MUST pitch the item at full price, do NOT improvise a small discount closer.
2. CAMPAIGN OVERRIDE: Check the Active Campaigns. If a campaign applies to the Trigger Item (or its category), your ENTIRE pitch MUST be about getting the user to use the campaign. Always cite the campaign's exact discount percent and name, never round, exaggerate, or extrapolate beyond it.
3. FULL-PRICE FALLBACK: If there is NO active campaign for the item you want to suggest, suggest it at full price with a value-based pitch (quality, materials, utility). Do NOT offer a discount.
4. NO DUPLICATES UNLESS BOGO: Do NOT suggest an item already in the cart UNLESS you are explicitly pitching a Buy One Get One or quantity campaign for that exact item.

RESPONSE STYLE (your reply is read aloud by text-to-speech):
- 1-2 short sentences, around 15-40 words. Never a paragraph.
- Plain prose only. NO asterisks, NO underscores, NO backticks, NO hash marks, NO bullet points, NO numbered lists, NO code blocks, NO markdown.
- NO emoji, NO arrows, NO decorative symbols, NO em-dashes, NO ellipses, NO pipe characters.
- Use commas and full stops only. Percent is written as " percent" or " %" (TTS can mangle the percent sign).
- Prefer prose prices over numbers: "two thousand rupees" instead of "Rs 2000". The catalog card below your message will display the exact price.

You ONLY generate persuasive text. You have NO ability to modify the cart.
Respond strictly in JSON:
{{
  "persuasive_message": "Your short, conversational, persuasive pitch in plain prose, 1-2 sentences, no emojis, no asterisks, no markdown. End with a question like 'Should I add this for you?'"
}}"""


# ── TTS-friendly output post-processor (server-side enforcement) ────────────
_TTS_BAD_CHARS = _re.compile(r"[*_`~#|→•·…—–]+")
_TTS_EMOJI = _re.compile(
    r"[\U0001F300-\U0001FAFF"
    r"\U00002600-\U000027BF"
    r"\U0001F000-\U0001F02F"
    r"\U0001F100-\U0001F1FF"
    r"\U0001F200-\U0001F2FF"
    r"\U0001F300-\U0001F5FF"
    r"\U0001F600-\U0001F64F"
    r"\U0001F680-\U0001F6FF"
    r"\U0001F700-\U0001F77F"
    r"\U0001F780-\U0001F7FF"
    r"\U0001F800-\U0001F8FF"
    r"\U0001F900-\U0001F9FF"
    r"\U0001FA00-\U0001FA6F"
    r"\U0001FA70-\U0001FAFF"
    r"]+"
)
_TTS_CURRENCY = _re.compile(r"[₹€£¥$¢₽]")


def _clean_for_tts(text: str) -> str:
    if not text:
        return text
    t = _TTS_BAD_CHARS.sub(" ", text)
    t = _TTS_CURRENCY.sub(" ", t)
    t = _TTS_EMOJI.sub(" ", t)
    t = _re.sub(r"\s+", " ", t).strip()
    t = _re.sub(r"(\d)\s*%", r"\1 percent", t)
    return t


def _truncate_to_short(text: str, max_words: int = 40) -> str:
    if not text:
        return text
    words = text.split()
    if len(words) <= max_words:
        return text
    head = " ".join(words[:max_words])
    for i in range(len(head) - 1, -1, -1):
        if head[i] in ".!?":
            return head[: i + 1].strip()
    return head.rstrip(",;") + "."


def _sanitize_persuasive(result: dict) -> dict:
    if isinstance(result, dict) and isinstance(result.get("persuasive_message"), str):
        result["persuasive_message"] = _truncate_to_short(
            _clean_for_tts(result["persuasive_message"])
        )
    return result


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
    return _sanitize_persuasive(json.loads(raw))