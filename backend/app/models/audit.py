from pydantic import BaseModel
from datetime import datetime

class AuditEntry(BaseModel):
    step: str
    cart_id: str | None = None
    rule: str | None = None
    evaluated: str | None = None
    action_taken: str
    system_prompt_snapshot: str | None = None
    timestamp: datetime = datetime.utcnow()
