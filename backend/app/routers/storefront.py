import uuid
from fastapi import APIRouter
from pydantic import BaseModel
from app.agents.merchant_agent import generate_agent_proposal
from app.models.cart import CartMandate, CartItem
from app.core.bounds_engine import check_against_mandate
from app.routers.mandate import MOCK_DB
from app.integrations.razorpay_client import create_order

router = APIRouter()

class ChatRequest(BaseModel):
    mandate_id: str
    user_message: str

@router.post("/api/storefront/chat")
def chat_with_concierge(req: ChatRequest):
    # 1. LLM Proposes (Language & Intent)
    llm_response = generate_agent_proposal(req.user_message)
    
    items = llm_response.get("items", [])
    subtotal = sum(item["price"] * item["qty"] for item in items)
    discount_pct = float(llm_response.get("discount_pct", 0.0))
    final_amount = subtotal * (1 - (discount_pct / 100))

    cart = CartMandate(
        cart_id=f"cart_{uuid.uuid4().hex[:8]}",
        mandate_id=req.mandate_id,
        items=[CartItem(**i) for i in items],
        subtotal=subtotal,
        discount_pct=discount_pct,
        final_amount=final_amount
    )

    # 2. Code Disposes (Deterministic Bounds Check)
    mandate = MOCK_DB.get(req.mandate_id)
    if not mandate:
        return {"error": "Mandate not found. Please setup your Spend Mandate first."}

    is_approved, action, audit = check_against_mandate(cart, mandate)

    response_payload = {
        "agent_message": llm_response.get("message"),
        "cart": cart.model_dump(),
        "action": action,
        "audit_trail": audit
    }

    # 3. Execution Phase
    if action == "EXECUTE":
        rzp_order = create_order(cart.final_amount, cart.cart_id)
        response_payload["razorpay_order"] = rzp_order

    return response_payload
