import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


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

    _validate_label = field_validator("label")(validate_label)


class UpdateBrokerConnectionRequest(BaseModel):
    label: str

    _validate_label = field_validator("label")(validate_label)


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
