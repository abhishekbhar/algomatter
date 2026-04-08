from pydantic import BaseModel


class PlaceManualTradeRequest(BaseModel):
    broker_connection_id: str
    symbol: str
    exchange: str
    product_type: str = "SPOT"
    action: str
    quantity: float
    order_type: str = "MARKET"
    price: float | None = None
    trigger_price: float | None = None
    leverage: int | None = None
    position_model: str | None = None
    take_profit: float | None = None
    stop_loss: float | None = None
    position_side: str | None = None


class ManualTradeResponse(BaseModel):
    id: str
    broker_connection_id: str
    symbol: str
    exchange: str
    product_type: str
    action: str
    quantity: float
    order_type: str
    price: float | None
    trigger_price: float | None
    leverage: int | None
    position_model: str | None
    take_profit: float | None
    stop_loss: float | None
    fill_price: float | None
    fill_quantity: float | None
    status: str
    broker_order_id: str | None
    error_message: str | None = None
    created_at: str
    updated_at: str
    filled_at: str | None


class ManualTradesListResponse(BaseModel):
    trades: list[ManualTradeResponse]
    total: int
    offset: int
    limit: int
