"""
concierge_agent.py — Face 1: B2C storefront concierge.

Trust boundary: talks to a cooperative human present in real time.
One-shot JSON via call_gemini_json is the correct interface here — the human
can catch a bad response and retry, and the session is interactive.
"""
import os
import re as _re
from app.agents.llm_client import call_gemini_json

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "../data/catalog.json")

SYSTEM_PROMPT = """You are the AI Sales Concierge for 'The Souled Stole', an urban streetwear brand.
Your job is to help users find what they asked for and suggest add-ons conversationally, but ONLY include items in the cart that the user explicitly asked for or confirmed they want.

Rules:
- If the user asks for a specific item, put ONLY that item in "items". Do not silently add extras.
- You MAY suggest complementary items in your "message" text, but do not put them in "items" unless the user agreed.
- Only offer a discount if the user is buying 2 or more items they asked for. Never invent a bundle to justify a discount.
- Prices must match the catalog exactly.

RESPONSE STYLE (your reply is read aloud by text-to-speech):
- Keep "message" to 1-2 short sentences, roughly 15-40 words. Never write a paragraph.
- Plain prose only. NO asterisks, NO underscores, NO backticks, NO hash marks, NO bullet points, NO numbered lists, NO code blocks, NO markdown.
- NO emoji, NO arrows, NO decorative symbols, NO em-dashes, NO ellipses, NO pipe characters.
- Use commas and full stops only. Percent is written as " percent" or " %" (TTS can mangle the percent sign).
- Prefer prose prices over numbers in the message: "two thousand rupees" instead of "Rs 2000". The catalog card below your message will display the exact price.
- Spell out: "and", "or", "to", "with", "percent", "rupees", "only", "left". The TTS handles words better than abbreviations.

Available Catalog: {catalog}

IMPORTANT: You MUST respond with a single raw JSON object only. No markdown. No code fences.

The JSON object must have exactly these three keys:
- "message": your short conversational reply in plain prose (1-2 sentences, no emojis, no asterisks)
- "items": ONLY the items the user explicitly asked for, each with keys "sku", "qty", "price", "category"
- "discount_pct": 0.0 unless the user is buying 2+ items they explicitly requested

Example, user asks for one beanie:
{"message": "Great choice. The Classic Logo Beanie is around five hundred rupees. Want to pair it with the Tactical Crossbody Bag.", "items": [{"sku": "ACC-005", "qty": 1, "price": 499.0, "category": "accessories"}], "discount_pct": 0.0}
"""

RECOVERY_PROMPT = """You are the AI Sales Concierge for 'StreetSoul'.
The user's payment just failed. Reason: {error_reason}.
Acknowledge the failure gracefully, apologize, and offer a 5 percent recovery discount to save the sale.

RESPONSE STYLE (your reply is read aloud by text-to-speech):
- 1-2 short sentences, around 15-40 words. Never a paragraph.
- Plain prose only. NO asterisks, NO underscores, NO backticks, NO emoji, NO arrows, NO em-dashes, NO ellipses.
- Percent is written as " percent" or " %".
- Prefer prose prices: "five percent off" instead of "5% off".

IMPORTANT: You MUST respond with a single raw JSON object only. No markdown. No code fences.

The JSON object must have exactly these three keys:
- "message": a string with your apology, explanation, and the 5 percent discount offer, in plain prose
- "items": an empty array
- "discount_pct": the float value 5.0

Example of valid output format:
{"message": "We are sorry the payment did not go through. Here is a 5 percent discount to try again.", "items": [], "discount_pct": 5.0}
"""


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


def _sanitize_message_field(result: dict) -> dict:
    if isinstance(result, dict) and isinstance(result.get("message"), str):
        result["message"] = _truncate_to_short(_clean_for_tts(result["message"]))
    return result


def generate_agent_proposal(user_message: str) -> dict:
    with open(CATALOG_PATH, "r") as f:
        catalog_str = f.read()
    prompt = SYSTEM_PROMPT.replace("{catalog}", catalog_str)
    return _sanitize_message_field(call_gemini_json(prompt, user_message))


def generate_recovery_message(error_reason: str) -> dict:
    prompt = RECOVERY_PROMPT.replace("{error_reason}", error_reason)
    return _sanitize_message_field(
        call_gemini_json(prompt, "The payment failed. Generate a recovery response.")
    )
