"""NautilusAdapter — wraps an AlgoMatterStrategy inside a Nautilus Strategy."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.events.order import OrderFilled
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading.strategy import Strategy

from app.strategy_sdk.models import Candle

if TYPE_CHECKING:
    from app.strategy_sdk.base import AlgoMatterStrategy

logger = logging.getLogger(__name__)


class NautilusAdapterConfig(StrategyConfig, frozen=True):
    """Minimal config — the real parameters live on the user strategy."""

    instrument_id: str = ""
    bar_type: str = ""


class NautilusAdapter(Strategy):
    """Nautilus Strategy that delegates to an ``AlgoMatterStrategy``.

    On each bar the adapter:

    1. Converts the Nautilus ``Bar`` to an AlgoMatter ``Candle``.
    2. Appends the candle to the user strategy's history buffer.
    3. Calls ``user_strategy.on_candle(candle)``.
    4. Collects any orders emitted by the user strategy and submits them
       into the Nautilus execution engine.

    On fill events the adapter translates the Nautilus ``OrderFilled`` event
    back into the user strategy's ``on_order_update`` callback.
    """

    def __init__(
        self,
        user_strategy: AlgoMatterStrategy,
        config: NautilusAdapterConfig | None = None,
    ) -> None:
        super().__init__(config=config or NautilusAdapterConfig())
        self.user_strategy = user_strategy
        # Set the escape-hatch so user code can access the Nautilus strategy.
        self.user_strategy.nautilus_strategy = self

        self._instrument_id: InstrumentId | None = None
        self._bar_type: BarType | None = None
        # Map AlgoMatter order-id -> Nautilus ClientOrderId (string).
        self._order_id_map: dict[str, str] = {}
        # Reverse map for fill callbacks.
        self._reverse_order_id_map: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Configuration helpers (call before engine.run)
    # ------------------------------------------------------------------

    def set_instrument_id(self, instrument_id: InstrumentId) -> None:
        self._instrument_id = instrument_id

    def set_bar_type(self, bar_type: BarType) -> None:
        self._bar_type = bar_type

    # ------------------------------------------------------------------
    # Nautilus lifecycle
    # ------------------------------------------------------------------

    def on_start(self) -> None:
        if self._bar_type is not None:
            self.subscribe_bars(self._bar_type)
        self.user_strategy.on_init()

    def on_stop(self) -> None:
        self.user_strategy.on_stop()

    # ------------------------------------------------------------------
    # Bar handling
    # ------------------------------------------------------------------

    def on_bar(self, bar: Bar) -> None:
        candle = _bar_to_candle(bar)
        # Grow the user strategy's history buffer.
        self.user_strategy._history.append(candle)
        self.user_strategy.on_candle(candle)
        self._process_pending_orders()

    # ------------------------------------------------------------------
    # Order translation
    # ------------------------------------------------------------------

    def _process_pending_orders(self) -> None:
        """Read orders from the user strategy and submit them via Nautilus."""
        output = self.user_strategy.collect_output()

        for cancel_id in output["cancelled_orders"]:
            nautilus_id = self._order_id_map.get(cancel_id)
            if nautilus_id is not None:
                from nautilus_trader.model.identifiers import ClientOrderId

                order = self.cache.order(ClientOrderId(nautilus_id))
                if order is not None and order.is_open:
                    self.cancel_order(order)

        for order_spec in output["orders"]:
            self._submit_user_order(order_spec)

        # Reset accumulators so they don't pile up.
        self.user_strategy._pending_orders.clear()
        self.user_strategy._cancelled_orders.clear()
        self.user_strategy._logs.clear()

    def _submit_user_order(self, order_spec: dict) -> None:
        """Translate an AlgoMatter order dict into a Nautilus order."""
        if self._instrument_id is None:
            logger.warning("NautilusAdapter: instrument_id not set, skipping order")
            return

        side = (
            OrderSide.BUY if order_spec["action"] == "buy" else OrderSide.SELL
        )
        qty = Quantity(
            order_spec["quantity"],
            precision=self.cache.instrument(self._instrument_id).size_precision,
        )

        order_type = order_spec.get("order_type", "market")
        user_order_id = order_spec["id"]

        if order_type == "market":
            order = self.order_factory.market(
                instrument_id=self._instrument_id,
                order_side=side,
                quantity=qty,
            )
        elif order_type == "limit":
            from nautilus_trader.model.objects import Price

            price = Price(
                order_spec["price"],
                precision=self.cache.instrument(self._instrument_id).price_precision,
            )
            order = self.order_factory.limit(
                instrument_id=self._instrument_id,
                order_side=side,
                quantity=qty,
                price=price,
                time_in_force=TimeInForce.GTC,
            )
        else:
            # Fallback to market for unsupported types.
            order = self.order_factory.market(
                instrument_id=self._instrument_id,
                order_side=side,
                quantity=qty,
            )

        # Record the mapping.
        client_id_str = str(order.client_order_id)
        self._order_id_map[user_order_id] = client_id_str
        self._reverse_order_id_map[client_id_str] = user_order_id

        self.submit_order(order)

    # ------------------------------------------------------------------
    # Fill event translation
    # ------------------------------------------------------------------

    def on_order_filled(self, event: OrderFilled) -> None:
        client_id_str = str(event.client_order_id)
        user_order_id = self._reverse_order_id_map.get(client_id_str, client_id_str)
        self.user_strategy.on_order_update(
            order_id=user_order_id,
            status="filled",
            fill_price=float(event.last_px),
            fill_quantity=float(event.last_qty),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bar_to_candle(bar: Bar) -> Candle:
    """Convert a Nautilus ``Bar`` to an AlgoMatter ``Candle``."""
    ts_ns = bar.ts_event
    dt = datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=timezone.utc)
    return Candle(
        timestamp=dt,
        open=float(bar.open),
        high=float(bar.high),
        low=float(bar.low),
        close=float(bar.close),
        volume=float(bar.volume),
    )
