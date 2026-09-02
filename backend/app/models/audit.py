from pydantic import BaseModel, Field
from datetime import datetime, timezone


class AuditEntry(BaseModel):
    step: str
    cart_id: str | None = None
    rule: str | None = None
    evaluated: str | None = None
    action_taken: str
    system_prompt_snapshot: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
