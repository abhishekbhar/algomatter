from dataclasses import dataclass
from datetime import datetime


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Position:
    quantity: float
    avg_entry_price: float
    unrealized_pnl: float


@dataclass
class Portfolio:
    balance: float
    equity: float
    available_margin: float


@dataclass
class PendingOrder:
    id: str
    action: str
    quantity: float
    order_type: str
    price: float | None = None
    trigger_price: float | None = None
    age_candles: int = 0
