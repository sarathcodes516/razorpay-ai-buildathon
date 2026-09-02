from pydantic import BaseModel, Field
from typing import List
from datetime import datetime, timezone


class MandateLimits(BaseModel):
    max_per_transaction: float
    max_total_spend_today: float
    allowed_categories: List[str]
    auto_approve_below: float
    max_discount_agent_can_accept_pct: float
    anomaly_discount_threshold_pct: float | None = None


class SpendMandate(BaseModel):
    mandate_id: str
    principal: str
    issued_at: datetime
    expires_at: datetime
    limits: MandateLimits
    signature: str | None = None


class PaymentMandate(BaseModel):
    payment_mandate_id: str
    cart_id: str
    mandate_id: str
    authorized_amount: float
    cart_hash: str
    signature: str
