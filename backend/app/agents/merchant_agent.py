import os
from app.agents.llm_client import call_gemini_json

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "../data/catalog.json")

SYSTEM_PROMPT = """You are the AI Sales Concierge for 'The Souled Stole', an urban streetwear brand.
Your goal is to upsell bundles. The user will tell you what they need.
You can offer a discount up to 15% if they buy 2 or more items.
Available Catalog: {catalog}

You MUST respond strictly in JSON matching this schema:
{
  "message": "Your conversational reply to the user, explaining the bundle and discount.",
  "items": [ {"sku": "...", "qty": 1, "price": 999.0, "category": "apparel"} ],
  "discount_pct": 5.0
}
"""

RECOVERY_PROMPT = """You are the AI Sales Concierge for 'StreetSoul'.
The user's payment just failed. Reason: {error_reason}.
Acknowledge the failure gracefully, apologize, and offer a 5% recovery discount to save the sale.

You MUST respond strictly in JSON matching this schema:
{
  "message": "Apology, explanation, and the 5% discount offer.",
  "items": [],   
  "discount_pct": 5.0
}
"""

def generate_agent_proposal(user_message: str) -> dict:
    with open(CATALOG_PATH, "r") as f:
        catalog_str = f.read()
    prompt = SYSTEM_PROMPT.replace("{catalog}", catalog_str)
    return call_gemini_json(prompt, user_message)

def generate_recovery_message(error_reason: str) -> dict:
    prompt = RECOVERY_PROMPT.replace("{error_reason}", error_reason)
    return call_gemini_json(prompt, "The payment failed. Generate a recovery response.")
