import uuid
from fastapi import APIRouter
from pydantic import BaseModel
from app.agents.merchant_agent import generate_agent_proposal, generate_recovery_message
from app.models.cart import CartMandate, CartItem
from app.core.bounds_engine import check_against_mandate
from app.routers.mandate import MOCK_DB
from app.integrations.razorpay_client import create_order

router = APIRouter()

class ChatRequest(BaseModel):
    mandate_id: str
    user_message: str

class PaymentFailureRequest(BaseModel):
    error_reason: str

@router.post("/api/storefront/chat")
def chat_with_concierge(req: ChatRequest):
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

    mandate = MOCK_DB.get(req.mandate_id)
    if not mandate:
        return {"error": "Mandate not found."}

    is_approved, action, audit = check_against_mandate(cart, mandate)

    response_payload = {
        "agent_message": llm_response.get("message"),
        "cart": cart.model_dump(),
        "action": action,
        "audit_trail": audit
    }

    if action == "EXECUTE":
        response_payload["razorpay_order"] = create_order(cart.final_amount, cart.cart_id)

    return response_payload

@router.post("/api/storefront/recover")
def recover_failed_payment(req: PaymentFailureRequest):
    llm_response = generate_recovery_message(req.error_reason)
    return {
        "agent_message": llm_response.get("message"),
        "recovery_discount_pct": llm_response.get("discount_pct", 5.0)
    }
