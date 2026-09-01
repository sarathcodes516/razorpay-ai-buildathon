from pydantic import BaseModel
from typing import List

class CartItem(BaseModel):
    sku: str
    qty: int
    price: float
    category: str

class CartMandate(BaseModel):
    cart_id: str
    mandate_id: str
    items: List[CartItem]
    subtotal: float
    discount_pct: float
    final_amount: float
    negotiation_ref: str | None = None
