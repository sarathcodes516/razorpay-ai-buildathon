from fastapi import APIRouter
from pydantic import BaseModel
from app.models.mandate import SpendMandate
from app.core.mandate_service import create_mandate, verify_mandate

router = APIRouter()

# Simple in-memory DB for hackathon speed
MOCK_DB = {}

class MandateRequest(BaseModel):
    principal: str
    limits: dict

class DynamicMandateRequest(BaseModel):
    principal: str
    max_per_transaction: float
    max_total_spend_today: float
    allowed_categories: list[str]
    auto_approve_below: float
    max_discount_agent_can_accept_pct: float

@router.post("/api/mandate")
def generate_mandate(req: MandateRequest):
    mandate = create_mandate(req.principal, req.limits)
    MOCK_DB[mandate.mandate_id] = mandate
    return mandate

@router.post("/api/mandate/dynamic")
def generate_dynamic_mandate(req: DynamicMandateRequest):
    limits = {
        "max_per_transaction": req.max_per_transaction,
        "max_total_spend_today": req.max_total_spend_today,
        "allowed_categories": req.allowed_categories,
        "auto_approve_below": req.auto_approve_below,
        "max_discount_agent_can_accept_pct": req.max_discount_agent_can_accept_pct
    }
    mandate = create_mandate(req.principal, limits)
    MOCK_DB[mandate.mandate_id] = mandate
    return mandate

@router.get("/api/mandate/{mandate_id}")
def get_mandate(mandate_id: str):
    if mandate_id in MOCK_DB:
        return MOCK_DB[mandate_id]
    return {"error": "Mandate not found"}
