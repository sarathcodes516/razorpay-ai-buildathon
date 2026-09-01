import uuid
from fastapi import APIRouter
from pydantic import BaseModel
from app.agents.buyer_agent import generate_buyer_turn
from app.agents.merchant_agent import generate_b2b_merchant_turn
from app.models.cart import CartMandate, CartItem
from app.core.bounds_engine import check_against_mandate
from app.routers.mandate import MOCK_DB
from app.integrations.razorpay_client import create_order

router = APIRouter()

class NegotiationRequest(BaseModel):
    mandate_id: str
    procurement_goal: str

@router.post("/api/gateway/negotiate")
def autonomous_negotiation(req: NegotiationRequest):
    mandate = MOCK_DB.get(req.mandate_id)
    if not mandate:
        return {"error": "Mandate not found."}

    history = ""
    transcript = []
    max_turns = 3
    final_cart = None
    
    # The Autonomous Loop
    for turn in range(max_turns):
        # 1. Buyer's Turn
        buyer_res = generate_buyer_turn(history, req.procurement_goal)
        history += f"\nBuyer: {buyer_res.get('message')} (Asking {buyer_res.get('requested_discount_pct')}% off)\n"
        transcript.append({"role": "buyer", "data": buyer_res})
        
        if buyer_res.get("action") == "ACCEPT" and final_cart:
            break # Deal reached in previous turn
            
        # 2. Merchant's Turn
        merchant_res = generate_b2b_merchant_turn(history, buyer_res.get('message'), turn)
        history += f"\nMerchant: {merchant_res.get('message')} (Offering {merchant_res.get('offered_discount_pct')}% off)\n"
        transcript.append({"role": "merchant", "data": merchant_res})
        
        # Calculate current cart state
        items = merchant_res.get("approved_items", [])
        subtotal = sum(item["price"] * item["qty"] for item in items)
        discount_pct = float(merchant_res.get("offered_discount_pct", 0.0))
        final_amount = subtotal * (1 - (discount_pct / 100))
        
        final_cart = CartMandate(
            cart_id=f"cart_b2b_{uuid.uuid4().hex[:8]}",
            mandate_id=req.mandate_id,
            items=[CartItem(**i) for i in items],
            subtotal=subtotal,
            discount_pct=discount_pct,
            final_amount=final_amount
        )
        
        if merchant_res.get("action") == "ACCEPT":
            break
            
    # Loop finished. Now, CODE DISPOSES.
    is_approved, action, audit = check_against_mandate(final_cart, mandate)
    
    response_payload = {
        "transcript": transcript,
        "final_cart": final_cart.model_dump() if final_cart else None,
        "action": action,
        "audit_trail": audit
    }

    if action == "EXECUTE" and final_cart:
        response_payload["razorpay_order"] = create_order(final_cart.final_amount, final_cart.cart_id)

    return response_payload
