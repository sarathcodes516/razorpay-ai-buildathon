import uuid
from datetime import datetime, timezone

SESSIONS: dict[str, dict] = {}


def create_session(mandate_id: str, merchant_agent_id: str, procurement_goal: str) -> str:
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    SESSIONS[session_id] = {
        "session_id": session_id,
        "mandate_id": mandate_id,
        "merchant_agent_id": merchant_agent_id,
        "procurement_goal": procurement_goal,
        "turns": [],
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return session_id


def get_session(session_id: str) -> dict | None:
    return SESSIONS.get(session_id)


def append_turn(session_id: str, turn: dict):
    SESSIONS[session_id]["turns"].append(turn)


def close_session(session_id: str, status: str):
    SESSIONS[session_id]["status"] = status
