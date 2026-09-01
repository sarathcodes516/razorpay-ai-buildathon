import os
import json
from app.agents.llm_client import call_gemini_json

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "../data/catalog.json")

SYSTEM_PROMPT = """You are the AI Sales Concierge for 'The Souled Stole', an urban streetwear brand.
Your goal is to upsell bundles. The user will tell you what they need.
You can offer a discount up to 15% if they buy 2 or more items.
Available Catalog: {catalog}

IMPORTANT: You MUST respond with a single raw JSON object only. No markdown. No code fences. No explanation outside the JSON.

The JSON object must have exactly these three keys:
- "message": a string with your conversational reply explaining the bundle and discount
- "items": an array of objects, each with keys "sku" (string), "qty" (integer), "price" (float), "category" (string)
- "discount_pct": a float representing the discount percentage (0.0 to 15.0)

Example of valid output format:
{"message": "Here is a great bundle for you!", "items": [{"sku": "TEE-001", "qty": 1, "price": 999.0, "category": "apparel"}], "discount_pct": 10.0}
"""

RECOVERY_PROMPT = """You are the AI Sales Concierge for 'StreetSoul'.
The user's payment just failed. Reason: {error_reason}.
Acknowledge the failure gracefully, apologize, and offer a 5% recovery discount to save the sale.

IMPORTANT: You MUST respond with a single raw JSON object only. No markdown. No code fences.

The JSON object must have exactly these three keys:
- "message": a string with your apology, explanation, and the 5% discount offer
- "items": an empty array
- "discount_pct": the float value 5.0

Example of valid output format:
{"message": "We are sorry your payment failed. Here is a 5% discount to try again.", "items": [], "discount_pct": 5.0}
"""

def generate_agent_proposal(user_message: str) -> dict:
    with open(CATALOG_PATH, "r") as f:
        catalog_str = f.read()
    prompt = SYSTEM_PROMPT.replace("{catalog}", catalog_str)
    return call_gemini_json(prompt, user_message)

def generate_recovery_message(error_reason: str) -> dict:
    prompt = RECOVERY_PROMPT.replace("{error_reason}", error_reason)
    return call_gemini_json(prompt, "The payment failed. Generate a recovery response.")


B2B_MERCHANT_PROMPT = """You are the dynamic B2B AI Sales Agent for 'The Souled Stole'.
You evaluate inbound buyer intents against real-time live inventory and the merchant's active runtime store policy.

Active Store Policy:
{policy}

Live Catalog & Stock:
{catalog}

Context of negotiation:
{history}

IMPORTANT: You MUST respond with a single raw JSON object only. No markdown. No code fences.

The JSON object must have exactly these five keys:
- "thought_process": a string analyzing live inventory and active store policy limits to decide counter-offer
- "action": one of the strings "COUNTER", "ACCEPT", or "REJECT"
- "message": a string with your professional negotiation message explaining your policy stance
- "approved_items": an array of objects, each with keys "sku" (string), "qty" (integer), "price" (float), "category" (string)
- "offered_discount_pct": a float for the discount you are offering based on live stock and active policy

Example of valid output format:
{"thought_process": "Policy cap is 15%. HOD-002 stock is 12 (low), TEE-001 stock is 50 (high). Offering blended 10%.", "action": "COUNTER", "message": "Based on our current stock levels, I can offer 10% on this order.", "approved_items": [{"sku": "TEE-001", "qty": 10, "price": 999.0, "category": "apparel"}], "offered_discount_pct": 10.0}
"""


def generate_b2b_merchant_turn(history: str, buyer_proposal: str, turn: int = 0) -> dict:
    from app.core.merchant_state import get_store_state
    state = get_store_state()
    prompt = (
        B2B_MERCHANT_PROMPT
        .replace("{policy}", json.dumps(state["policy"], indent=2))
        .replace("{catalog}", json.dumps(state["catalog"], indent=2))
        .replace("{history}", history)
    )
    return call_gemini_json(prompt, f"Buyer proposal: {buyer_proposal}. Evaluate active store policy and respond.")
