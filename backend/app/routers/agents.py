from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.agent_registry import register_agent, get_agent_card

router = APIRouter()


class RegisterAgentRequest(BaseModel):
    role: str
    capabilities: list[str]
    public_key_hex: str | None = None  # supply to register an external agent (buyer-side)


@router.post("/api/agents/{agent_id}/register")
def register(agent_id: str, req: RegisterAgentRequest):
    """
    Register an agent. Idempotent.
    - Omit public_key_hex to have the server generate a keypair (for server-hosted agents).
    - Supply public_key_hex to register an external agent that holds its own private key.
    """
    card = register_agent(agent_id, req.role, req.capabilities, req.public_key_hex)
    return card


@router.get("/api/agents/{agent_id}/card")
def agent_card(agent_id: str):
    """Return the public agent card (public key, role, capabilities). No private key."""
    card = get_agent_card(agent_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not registered.")
    return card
