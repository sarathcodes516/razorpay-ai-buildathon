from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.integrations.razorpay_client import create_order

router = APIRouter()

class OrderRequest(BaseModel):
    amount: float
    receipt_id: str

@router.post("/api/payments/create-order")
def generate_razorpay_order(req: OrderRequest):
    order_response = create_order(req.amount, req.receipt_id)
    if "error" in order_response:
        raise HTTPException(status_code=400, detail=order_response["error"])
    return order_response
