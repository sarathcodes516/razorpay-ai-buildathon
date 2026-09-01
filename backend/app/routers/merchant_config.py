from fastapi import APIRouter
from pydantic import BaseModel
from app.core.merchant_state import get_store_state, update_store_policy, update_inventory

router = APIRouter()


class PolicyUpdate(BaseModel):
    max_allowable_discount_pct: float
    high_stock_threshold: int


class InventoryUpdate(BaseModel):
    sku: str
    in_stock: int


@router.get("/api/merchant/config")
def get_config():
    return get_store_state()


@router.post("/api/merchant/policy")
def set_policy(policy: PolicyUpdate):
    return update_store_policy(policy.model_dump())


@router.post("/api/merchant/inventory")
def set_inventory(inv: InventoryUpdate):
    return update_inventory(inv.sku, inv.in_stock)
