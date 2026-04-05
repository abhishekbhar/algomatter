"""AlgoMatterStrategy — the user-facing base class for writing trading strategies."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.strategy_sdk.models import Candle, PendingOrder, Portfolio, Position


class AlgoMatterStrategy:
    """Base class that every user strategy must subclass.

    The runtime (back-test engine or live runner) constructs the strategy each
    tick with the current market snapshot, calls the lifecycle hooks, and then
    calls ``collect_output()`` to retrieve orders / state / logs produced
    during that tick.
    """

    # Escape-hatch for NautilusTrader adapter — set externally when needed.
    nautilus_strategy: object | None = None

    def __init__(
        self,
        *,
        params: dict | None = None,
        state: dict | None = None,
        position: Position | None = None,
        portfolio: Portfolio | None = None,
        open_orders: list[PendingOrder] | None = None,
        history: list[Candle] | None = None,
    ) -> None:
        # Public read-only properties
        self._params: dict = params or {}
        self._state: dict = state or {}
        self._position: Position | None = position
        self._portfolio: Portfolio = portfolio or Portfolio(
            balance=0.0, equity=0.0, available_margin=0.0
        )
        self._open_orders: list[PendingOrder] = open_orders or []
        self._history: list[Candle] = history or []

        # Internal accumulators for the current tick
        self._pending_orders: list[dict] = []
        self._cancelled_orders: list[str] = []
        self._logs: list[dict] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def position(self) -> Position | None:
        return self._position

    @property
    def portfolio(self) -> Portfolio:
        return self._portfolio

    @property
    def open_orders(self) -> list[PendingOrder]:
        return list(self._open_orders)

    @property
    def params(self) -> dict:
        return self._params

    @property
    def state(self) -> dict:
        return self._state

    # ------------------------------------------------------------------
    # Order methods
    # ------------------------------------------------------------------

    def buy(
        self,
        quantity: float,
        order_type: str = "market",
        price: float | None = None,
        trigger_price: float | None = None,
        symbol: str | None = None,
    ) -> str:
        """Place a buy order. Returns a generated order ID."""
        order_id = uuid.uuid4().hex[:16]
        self._pending_orders.append(
            {
                "id": order_id,
                "action": "buy",
                "quantity": quantity,
                "order_type": order_type,
                "price": price,
                "trigger_price": trigger_price,
            }
        )
        return order_id

    def sell(
        self,
        quantity: float,
        order_type: str = "market",
        price: float | None = None,
        trigger_price: float | None = None,
        symbol: str | None = None,
    ) -> str:
        """Place a sell order. Returns a generated order ID."""
        order_id = uuid.uuid4().hex[:16]
        self._pending_orders.append(
            {
                "id": order_id,
                "action": "sell",
                "quantity": quantity,
                "order_type": order_type,
                "price": price,
                "trigger_price": trigger_price,
            }
        )
        return order_id

    def cancel_order(self, order_id: str) -> None:
        """Request cancellation of an open order."""
        self._cancelled_orders.append(order_id)

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def history(self, periods: int | None = None) -> list[Candle]:
        """Return the last *periods* candles from the pre-loaded buffer.

        If *periods* is ``None`` the full buffer is returned.
        """
        if periods is None:
            return list(self._history)
        return list(self._history[-periods:])

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log(self, message: str, level: str = "info") -> None:
        """Capture a log entry for the current tick."""
        self._logs.append(
            {
                "message": message,
                "level": level,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    # ------------------------------------------------------------------
    # Lifecycle hooks (override in subclass)
    # ------------------------------------------------------------------

    def on_init(self) -> None:
        """Called once when the strategy is first loaded."""

    def on_candle(self, candle: Candle) -> None:
        """Called on every new candle."""

    def on_order_update(
        self,
        order_id: str,
        status: str,
        fill_price: float | None,
        fill_quantity: float | None,
    ) -> None:
        """Called when an order status changes."""

    def on_stop(self) -> None:
        """Called when the strategy is stopped or the back-test ends."""

    # ------------------------------------------------------------------
    # Internal: collect tick output
    # ------------------------------------------------------------------

    def collect_output(self) -> dict:
        """Return all side-effects produced during this tick.

        Format:
        {
            "orders": [...],
            "cancelled_orders": [...],
            "state": { ... },
            "logs": [...],
            "error": None
        }
        """
        return {
            "orders": list(self._pending_orders),
            "cancelled_orders": list(self._cancelled_orders),
            "state": dict(self._state),
            "logs": list(self._logs),
            "error": None,
        }
