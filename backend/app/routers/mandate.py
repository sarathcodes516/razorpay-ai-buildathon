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

@router.post("/api/mandate")
def generate_mandate(req: MandateRequest):
    mandate = create_mandate(req.principal, req.limits)
    MOCK_DB[mandate.mandate_id] = mandate
    return mandate

@router.get("/api/mandate/{mandate_id}")
def get_mandate(mandate_id: str):
    if mandate_id in MOCK_DB:
        return MOCK_DB[mandate_id]
    return {"error": "Mandate not found"}
