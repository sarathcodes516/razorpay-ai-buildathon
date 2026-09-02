from pydantic import BaseModel
from typing import List


class B2CCartItem(BaseModel):
    sku: str
    name: str
    price: float
    qty: int


class B2CCartState(BaseModel):
    items: List[B2CCartItem] = []
    subtotal: float = 0.0
    discount_pct: float = 0.0
    final_amount: float = 0.0


def calculate_cart_totals(cart: B2CCartState) -> B2CCartState:
    cart.subtotal = sum(item.price * item.qty for item in cart.items)
    cart.final_amount = cart.subtotal * (1 - (cart.discount_pct / 100))
    return cart
