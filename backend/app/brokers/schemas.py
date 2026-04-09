import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator


def validate_label(v: str) -> str:
    """Trim, require non-empty after trim, cap at 40 chars."""
    if not isinstance(v, str):
        raise ValueError("label must be a string")
    stripped = v.strip()
    if not stripped:
        raise ValueError("label cannot be blank")
    if len(stripped) > 40:
        raise ValueError("label cannot exceed 40 characters")
    return stripped


class CreateBrokerConnectionRequest(BaseModel):
    broker_type: str
    label: str
    credentials: dict

    @field_validator("label")
    @classmethod
    def validate_label_field(cls, v: str) -> str:
        return validate_label(v)


class UpdateBrokerConnectionRequest(BaseModel):
    label: str | None = None
    credentials: dict | None = None

    @field_validator("label", mode="before")
    @classmethod
    def validate_label_if_provided(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_label(v)

    @field_validator("credentials", mode="before")
    @classmethod
    def credentials_not_empty(cls, v: dict | None) -> dict | None:
        if v is not None and len(v) == 0:
            raise ValueError("credentials cannot be empty")
        return v

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UpdateBrokerConnectionRequest":
        if self.label is None and self.credentials is None:
            raise ValueError("at least one of label or credentials must be provided")
        return self


class BrokerConnectionResponse(BaseModel):
    id: uuid.UUID
    broker_type: str
    label: str
    is_active: bool
    connected_at: datetime
    # NO credentials in response


class BrokerStatsResponse(BaseModel):
    active_deployments: int
    total_realized_pnl: float
    win_rate: float
    total_trades: int


class BrokerPositionResponse(BaseModel):
    deployment_id: str
    deployment_name: str
    symbol: str
    side: str           # "LONG" or "SHORT"
    quantity: float
    avg_entry_price: float
    unrealized_pnl: float


class BrokerBalanceResponse(BaseModel):
    available: float
    total: float
    used_margin: float


class BrokerOrderResponse(BaseModel):
    order_id: str
    deployment_id: str
    deployment_name: str
    symbol: str
    action: str
    quantity: float
    order_type: str
    price: float | None
    created_at: str | None


class LivePositionResponse(BaseModel):
    symbol: str
    exchange: str
    action: str           # "BUY" (long) or "SELL" (short)
    quantity: float
    entry_price: float
    product_type: str
    origin: str           # "webhook", "deployment", "exchange_direct"
    strategy_name: str | None


class ActivityItemResponse(BaseModel):
    id: str
    source: str           # "webhook" or "deployment"
    symbol: str
    action: str           # "BUY" or "SELL"
    quantity: float
    fill_price: float | None
    status: str
    order_id: str | None
    strategy_name: str | None
    created_at: str       # ISO 8601


class ActivityResponse(BaseModel):
    items: list[ActivityItemResponse]
    total: int
    offset: int
    limit: int
