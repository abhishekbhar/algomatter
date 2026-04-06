"""Simulated broker for backtesting and paper trading.

All state is held in memory — no external dependencies required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.brokers.base import (
    AccountBalance,
    BrokerAdapter,
    Holding,
    OHLCV,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    Position,
    Quote,
)


class SimulatedBroker(BrokerAdapter):
    """In-memory broker that simulates order fills with optional slippage and
    commission.

    Parameters
    ----------
    initial_capital:
        Starting cash balance.
    slippage_pct:
        Percentage slippage applied to market orders (e.g. ``Decimal("0.1")``
        means 0.1 %).
    commission_pct:
        Percentage commission deducted per trade.
    """

    def __init__(
        self,
        initial_capital: Decimal,
        slippage_pct: Decimal = Decimal("0"),
        commission_pct: Decimal = Decimal("0"),
    ) -> None:
        self._initial_capital = initial_capital
        self._balance = initial_capital
        self._used_margin = Decimal("0")
        self._slippage_pct = slippage_pct
        self._commission_pct = commission_pct

        self._positions: list[Position] = []
        self._orders: list[OrderResponse] = []

    # -- Connection ----------------------------------------------------------

    async def authenticate(self, credentials: dict) -> bool:  # noqa: ARG002
        return True

    async def verify_connection(self) -> bool:
        return True

    # -- Orders --------------------------------------------------------------

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        order_id = uuid.uuid4().hex[:12]
        fill_price = self._apply_slippage(order.price, order.action)

        total_cost = fill_price * order.quantity
        commission = total_cost * self._commission_pct / Decimal("100")

        if order.action == "BUY":
            required = total_cost + commission
            if required > self._balance:
                resp = OrderResponse(
                    order_id=order_id,
                    status="rejected",
                    message="Insufficient balance",
                )
                self._orders.append(resp)
                return resp

            self._balance -= required
            self._used_margin += total_cost

            # Check for an existing open position to add to
            existing = self._find_open_position(order.symbol, "BUY")
            if existing is not None:
                # Average up
                total_qty = existing.quantity + order.quantity
                existing.entry_price = (
                    (existing.entry_price * existing.quantity)
                    + (fill_price * order.quantity)
                ) / total_qty
                existing.quantity = total_qty
            else:
                self._positions.append(
                    Position(
                        symbol=order.symbol,
                        exchange=order.exchange,
                        action="BUY",
                        quantity=order.quantity,
                        entry_price=fill_price,
                        current_price=fill_price,
                        product_type=order.product_type,
                    )
                )

        else:  # SELL
            existing = self._find_open_position(order.symbol, "BUY")
            if existing is None:
                # Short sell — open a new SELL position, requires margin
                required = total_cost + commission
                if required > self._balance:
                    resp = OrderResponse(
                        order_id=order_id,
                        status="rejected",
                        message="Insufficient balance for short sell",
                    )
                    self._orders.append(resp)
                    return resp

                self._balance -= required
                self._used_margin += total_cost
                self._positions.append(
                    Position(
                        symbol=order.symbol,
                        exchange=order.exchange,
                        action="SELL",
                        quantity=order.quantity,
                        entry_price=fill_price,
                        current_price=fill_price,
                        product_type=order.product_type,
                    )
                )
                fill_qty = order.quantity
            else:
                fill_qty = min(order.quantity, existing.quantity)
                pnl = (fill_price - existing.entry_price) * fill_qty
                self._balance += (fill_price * fill_qty) - commission
                self._used_margin -= existing.entry_price * fill_qty
                existing.quantity -= fill_qty
                existing.pnl += pnl

                if existing.quantity == Decimal("0"):
                    existing.closed_at = datetime.now(UTC)

        resp = OrderResponse(
            order_id=order_id,
            status="filled",
            fill_price=fill_price,
            fill_quantity=fill_qty if order.action == "SELL" else order.quantity,
        )
        self._orders.append(resp)
        return resp

    async def cancel_order(self, order_id: str) -> bool:
        for o in self._orders:
            if o.order_id == order_id and o.status == "open":
                o.status = "cancelled"
                return True
        return False

    async def get_order_status(self, order_id: str) -> OrderStatus:
        for o in self._orders:
            if o.order_id == order_id:
                return OrderStatus(
                    order_id=o.order_id,
                    status=o.status,
                    fill_price=o.fill_price,
                    fill_quantity=o.fill_quantity,
                )
        return OrderStatus(order_id=order_id, status="not_found")

    # -- Portfolio -----------------------------------------------------------

    async def get_positions(self) -> list[Position]:
        return list(self._positions)

    async def get_holdings(self) -> list[Holding]:
        return [
            Holding(
                symbol=p.symbol,
                exchange=p.exchange,
                quantity=p.quantity,
                average_price=p.entry_price,
                current_price=p.current_price,
                pnl=p.pnl,
            )
            for p in self._positions
            if p.product_type in ("DELIVERY", "CNC") and p.closed_at is None
        ]

    async def get_balance(self, product_type: str | None = None) -> AccountBalance:
        return AccountBalance(
            available=self._balance,
            used_margin=self._used_margin,
            total=self._balance + self._used_margin,
        )

    # -- Market Data ---------------------------------------------------------

    async def get_quotes(self, symbols: list[str]) -> list[Quote]:  # noqa: ARG002
        return []

    async def get_historical(
        self,
        symbol: str,  # noqa: ARG002
        interval: str,  # noqa: ARG002
        start: datetime,  # noqa: ARG002
        end: datetime,  # noqa: ARG002
    ) -> list[OHLCV]:
        return []

    # -- Helpers -------------------------------------------------------------

    def _apply_slippage(self, price: Decimal, action: str) -> Decimal:
        slippage = price * self._slippage_pct / Decimal("100")
        if action == "BUY":
            return price + slippage
        return price - slippage

    def _find_open_position(self, symbol: str, action: str) -> Position | None:
        for p in self._positions:
            if p.symbol == symbol and p.action == action and p.closed_at is None:
                return p
        return None
