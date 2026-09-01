from pydantic import BaseModel
from typing import List
from datetime import datetime

class MandateLimits(BaseModel):
    max_per_transaction: float
    max_total_spend_today: float
    allowed_categories: List[str]
    auto_approve_below: float
    max_discount_agent_can_accept_pct: float

class SpendMandate(BaseModel):
    mandate_id: str
    principal: str
    issued_at: datetime
    expires_at: datetime
    limits: MandateLimits
    signature: str | None = None
