from fastapi import APIRouter
from app.core.agent_registry import get_agent_card
from app.models.mandate import SpendMandate

router = APIRouter()


@router.get("/.well-known/trustrail-manifest.json")
def manifest():
    """
    Public discovery manifest. No auth required — a buyer fetches this
    before registering or negotiating to learn endpoints, public keys, and
    the mandate schema it needs to satisfy.
    """
    card = get_agent_card("merchant_souledstole_01")
    return {
        "protocol": "TrustRail/UAP-0.1",
        "merchant_agent_id": "merchant_souledstole_01",
        "merchant_public_key": card["public_key"] if card else None,
        "endpoints": {
            "catalog": "/api/catalog",
            "register_agent": "/api/agents/{agent_id}/register",
            "session_start": "/api/gateway/session/start",
            "turn": "/api/gateway/turn",
        },
        "required_mandate_schema": SpendMandate.model_json_schema(),
        "capabilities": ["bulk_discount_negotiation", "inventory_check", "test_mode_payment"],
    }
