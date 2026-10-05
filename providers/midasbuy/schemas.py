from pydantic import BaseModel, Field
from typing import Optional, Any
from decimal import Decimal


class MidasbuyPlayerCheckRequest(BaseModel):
    app_id: str
    player_id: str
    timestamp: int
    sign: str


class MidasbuyPlayerCheckResponse(BaseModel):
    return_code: int = 0
    return_msg: str = "SUCCESS"
    player_id: str
    nickname: str
    zone_id: Optional[str] = None


class MidasbuyOrderRequest(BaseModel):
    app_id: str
    player_id: str
    product_id: str
    partner_order_id: str
    amount: int
    timestamp: int
    sign: str


class MidasbuyOrderResponse(BaseModel):
    return_code: int = 0
    return_msg: str = "SUCCESS"
    midasbuy_order_id: Optional[str] = None
    partner_order_id: Optional[str] = None
    status: str = "SUCCESS"
    raw: dict[str, Any] = Field(default_factory=dict)
