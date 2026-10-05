from pydantic import BaseModel, Field
from typing import Optional, Any
from decimal import Decimal


class TezCheckCreateBillRequest(BaseModel):
    cash_desk_code: str
    external_id: str
    amount: Decimal
    description: str
    return_url: Optional[str] = None


class TezCheckCreateBillResponse(BaseModel):
    status: str
    bill_id: Optional[str] = None
    pay_url: Optional[str] = None
    message: Optional[str] = None
    raw: dict[str, Any] = Field(default_factory=dict)


class TezCheckWebhookPayload(BaseModel):
    event: Optional[str] = None
    bill_id: str
    external_id: str  # maps to our order_id
    amount: Decimal
    currency: str = "UZS"
    status: str  # PAID, COMPLETED, FAILED, CANCELLED
    signature: Optional[str] = None
