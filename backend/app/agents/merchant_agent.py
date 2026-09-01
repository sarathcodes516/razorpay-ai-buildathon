import os
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


B2B_MERCHANT_PROMPT = """You are the B2B AI Sales Agent for 'StreetSoul'.
You are negotiating with an external Procurement AI.
You want to close the deal, but protect your margins. You can offer up to a 15% discount for bulk orders.
Available Catalog: {catalog}

Context of negotiation so far:
{history}

IMPORTANT: You MUST respond with a single raw JSON object only. No markdown. No code fences.

The JSON object must have exactly these five keys:
- "thought_process": a string explaining why you are accepting or countering
- "action": one of the strings "COUNTER", "ACCEPT", or "REJECT"
- "message": a string with your reply to the buyer
- "approved_items": an array of objects, each with keys "sku" (string), "qty" (integer), "price" (float), "category" (string)
- "offered_discount_pct": a float for the discount you are offering (0.0 to 15.0)

Example of valid output format:
{"thought_process": "Buyer wants 20% but I can only go to 15%.", "action": "COUNTER", "message": "I can offer you 12% for this bulk order.", "approved_items": [{"sku": "HOD-002", "qty": 10, "price": 1999.0, "category": "apparel"}], "offered_discount_pct": 12.0}
"""

def generate_b2b_merchant_turn(history: str, buyer_proposal: str) -> dict:
    with open(CATALOG_PATH, "r") as f:
        catalog_str = f.read()
    prompt = B2B_MERCHANT_PROMPT.replace("{catalog}", catalog_str).replace("{history}", history)
    return call_gemini_json(prompt, f"The buyer says: {buyer_proposal}. Make your counter-offer.")
