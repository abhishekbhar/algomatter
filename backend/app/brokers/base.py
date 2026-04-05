"""Broker adapter abstraction layer.

Defines the BrokerAdapter ABC and shared data models used across all broker
implementations (simulated, paper-trading, live).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class OrderRequest(BaseModel):
    """Incoming order to be placed with a broker."""

    symbol: str
    exchange: str
    action: Literal["BUY", "SELL"]
    quantity: Decimal
    order_type: Literal["MARKET", "LIMIT", "SL", "SL-M"]
    price: Decimal
    product_type: Literal["INTRADAY", "DELIVERY", "CNC", "MIS", "FUTURES"]
    trigger_price: Decimal | None = None

    # Futures-specific (ignored by spot adapters)
    leverage: int | None = None          # e.g. 20
    position_model: str | None = None    # "isolated" → "fix", "cross" → "cross"
    take_profit: Decimal | None = None   # TP price
    stop_loss: Decimal | None = None     # SL price


class OrderResponse(BaseModel):
    """Result returned after placing an order."""

    order_id: str
    status: Literal["filled", "open", "rejected", "cancelled"]
    fill_price: Decimal | None = None
    fill_quantity: Decimal | None = None
    message: str = ""
    placed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OrderStatus(BaseModel):
    """Current status of an existing order."""

    order_id: str
    status: Literal["filled", "open", "rejected", "cancelled"]
    fill_price: Decimal | None = None
    fill_quantity: Decimal | None = None
    pending_quantity: Decimal | None = None


class Position(BaseModel):
    """An open or closed trading position."""

    symbol: str
    exchange: str
    action: Literal["BUY", "SELL"]
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal | None = None
    pnl: Decimal = Decimal("0")
    product_type: str = "INTRADAY"
    opened_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    closed_at: datetime | None = None


class Holding(BaseModel):
    """A longer-term holding (delivery / CNC)."""

    symbol: str
    exchange: str
    quantity: Decimal
    average_price: Decimal
    current_price: Decimal | None = None
    pnl: Decimal = Decimal("0")


class AccountBalance(BaseModel):
    """Broker account balance snapshot."""

    available: Decimal
    used_margin: Decimal = Decimal("0")
    total: Decimal = Decimal("0")


class Quote(BaseModel):
    """Real-time quote for a single symbol."""

    symbol: str
    exchange: str
    last_price: Decimal
    bid: Decimal | None = None
    ask: Decimal | None = None
    volume: Decimal | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OHLCV(BaseModel):
    """Single OHLCV candle."""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class BrokerAdapter(ABC):
    """Abstract interface that every broker implementation must satisfy."""

    # -- Connection ----------------------------------------------------------

    @abstractmethod
    async def authenticate(self, credentials: dict) -> bool: ...

    @abstractmethod
    async def verify_connection(self) -> bool: ...

    # -- Orders --------------------------------------------------------------

    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResponse: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderStatus: ...

    # -- Portfolio -----------------------------------------------------------

    @abstractmethod
    async def get_positions(self) -> list[Position]: ...

    @abstractmethod
    async def get_holdings(self) -> list[Holding]: ...

    @abstractmethod
    async def get_balance(self) -> AccountBalance: ...

    # -- Market Data ---------------------------------------------------------

    @abstractmethod
    async def get_quotes(self, symbols: list[str]) -> list[Quote]: ...

    @abstractmethod
    async def get_historical(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> list[OHLCV]: ...
