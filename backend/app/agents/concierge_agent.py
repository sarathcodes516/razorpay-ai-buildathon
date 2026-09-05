"""
concierge_agent.py — Face 1: B2C storefront concierge (payment-recovery variant).

Trust boundary: talks to a cooperative human present in real time. One-shot
JSON via `call_llm_json` is the correct interface here — the human can catch
a bad response and retry, and the session is interactive.

Only the payment-recovery entry point is wired up. The proactive
`generate_agent_proposal` is kept dormant so the file can be reactivated if a
human-facing storefront (Face 1) is ever added on top of the orchestrator.
"""
import re as _re
from app.agents.llm_client import call_llm_json


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


def generate_recovery_message(error_reason: str) -> dict:
    prompt = RECOVERY_PROMPT.replace("{error_reason}", error_reason)
    return _sanitize_message_field(
        call_llm_json(prompt, "The payment failed. Generate a recovery response.")
    )
