import os
from app.agents.llm_client import call_gemini_json

BUYER_PROMPT = """You are an autonomous Procurement AI for an events company.
Your goal is to negotiate a bulk purchase with a merchant.
You must be firm on getting a good discount.

Context of negotiation so far:
{history}

IMPORTANT: You MUST respond with a single raw JSON object only. No markdown. No code fences.

The JSON object must have exactly these five keys:
- "thought_process": a string briefly explaining your negotiation strategy
- "action": one of the strings "PROPOSE", "ACCEPT", or "REJECT"
- "message": a string with your message to the merchant
- "requested_items": an array of objects, each with keys "sku" (string), "qty" (integer), "price" (float), "category" (string)
- "requested_discount_pct": a float for the discount you are requesting

Example of valid output format:
{"thought_process": "I will open high at 20% to leave room to settle at 15%.", "action": "PROPOSE", "message": "We want 10 hoodies and 10 tees. We need 20% off for this bulk order.", "requested_items": [{"sku": "HOD-002", "qty": 10, "price": 1999.0, "category": "apparel"}], "requested_discount_pct": 20.0}
"""

def generate_buyer_turn(history: str, goal: str) -> dict:
    prompt = BUYER_PROMPT.replace("{history}", history)
    return call_gemini_json(prompt, f"Your goal: {goal}. Make your next move.")
