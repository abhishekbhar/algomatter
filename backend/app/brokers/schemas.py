import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateBrokerConnectionRequest(BaseModel):
    broker_type: str
    credentials: dict


class BrokerConnectionResponse(BaseModel):
    id: uuid.UUID
    broker_type: str
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
