"""Tests for the AlgoMatterStrategy SDK."""

from datetime import datetime, timezone

import pytest

from app.strategy_sdk.base import AlgoMatterStrategy
from app.strategy_sdk.models import Candle, PendingOrder, Portfolio, Position


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_candle(close: float, ts: datetime | None = None) -> Candle:
    """Create a Candle with sensible defaults; only *close* is required."""
    if ts is None:
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return Candle(
        timestamp=ts,
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1000.0,
    )


# ---------------------------------------------------------------------------
# Simple SMA cross-over strategy used in several tests
# ---------------------------------------------------------------------------

class SmaCrossStrategy(AlgoMatterStrategy):
    """Buy when fast SMA crosses above slow SMA, sell when below."""

    def on_init(self) -> None:
        self.state["initialized"] = True

    def on_candle(self, candle: Candle) -> None:
        fast_period = self.params.get("fast", 3)
        slow_period = self.params.get("slow", 5)

        candles = self.history()
        if len(candles) < slow_period:
            return

        fast_sma = sum(c.close for c in candles[-fast_period:]) / fast_period
        slow_sma = sum(c.close for c in candles[-slow_period:]) / slow_period

        if fast_sma > slow_sma and self.position is None:
            self.buy(1.0)
            self.log("BUY signal")
        elif fast_sma < slow_sma and self.position is not None:
            self.sell(self.position.quantity)
            self.log("SELL signal")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInstantiation:
    def test_default_construction(self) -> None:
        strat = AlgoMatterStrategy()
        assert strat.params == {}
        assert strat.state == {}
        assert strat.position is None
        assert strat.portfolio.balance == 0.0
        assert strat.open_orders == []
        assert strat.history() == []

    def test_construction_with_params(self) -> None:
        strat = AlgoMatterStrategy(params={"fast": 5, "slow": 20})
        assert strat.params["fast"] == 5
        assert strat.params["slow"] == 20

    def test_construction_with_state(self) -> None:
        strat = AlgoMatterStrategy(state={"counter": 42})
        assert strat.state["counter"] == 42

    def test_construction_with_position(self) -> None:
        pos = Position(quantity=10.0, avg_entry_price=100.0, unrealized_pnl=50.0)
        strat = AlgoMatterStrategy(position=pos)
        assert strat.position is not None
        assert strat.position.quantity == 10.0

    def test_construction_with_portfolio(self) -> None:
        pf = Portfolio(balance=10_000.0, equity=10_500.0, available_margin=9_000.0)
        strat = AlgoMatterStrategy(portfolio=pf)
        assert strat.portfolio.balance == 10_000.0
        assert strat.portfolio.equity == 10_500.0

    def test_construction_with_open_orders(self) -> None:
        orders = [
            PendingOrder(id="o1", action="buy", quantity=5.0, order_type="limit", price=99.0)
        ]
        strat = AlgoMatterStrategy(open_orders=orders)
        assert len(strat.open_orders) == 1
        assert strat.open_orders[0].id == "o1"

    def test_open_orders_returns_copy(self) -> None:
        """Mutating the returned list must not affect internal state."""
        strat = AlgoMatterStrategy(
            open_orders=[PendingOrder(id="o1", action="buy", quantity=1.0, order_type="market")]
        )
        orders = strat.open_orders
        orders.clear()
        assert len(strat.open_orders) == 1


class TestOnInit:
    def test_on_init_called(self) -> None:
        strat = SmaCrossStrategy(params={"fast": 3, "slow": 5})
        strat.on_init()
        assert strat.state.get("initialized") is True

    def test_base_on_init_is_noop(self) -> None:
        strat = AlgoMatterStrategy()
        strat.on_init()  # should not raise


class TestBuyOrder:
    def test_buy_returns_order_id(self) -> None:
        strat = AlgoMatterStrategy()
        oid = strat.buy(10.0)
        assert isinstance(oid, str)
        assert len(oid) == 16

    def test_buy_adds_to_pending_orders(self) -> None:
        strat = AlgoMatterStrategy()
        oid = strat.buy(5.0)
        assert len(strat._pending_orders) == 1
        order = strat._pending_orders[0]
        assert order["id"] == oid
        assert order["action"] == "buy"
        assert order["quantity"] == 5.0
        assert order["order_type"] == "market"
        assert order["price"] is None
        assert order["trigger_price"] is None

    def test_buy_multiple_orders(self) -> None:
        strat = AlgoMatterStrategy()
        strat.buy(1.0)
        strat.buy(2.0)
        assert len(strat._pending_orders) == 2


class TestSellOrder:
    def test_sell_returns_order_id(self) -> None:
        strat = AlgoMatterStrategy()
        oid = strat.sell(3.0)
        assert isinstance(oid, str)
        assert len(oid) == 16

    def test_sell_adds_to_pending_orders(self) -> None:
        strat = AlgoMatterStrategy()
        oid = strat.sell(7.0)
        order = strat._pending_orders[0]
        assert order["id"] == oid
        assert order["action"] == "sell"
        assert order["quantity"] == 7.0


class TestCancelOrder:
    def test_cancel_order_adds_to_cancelled(self) -> None:
        strat = AlgoMatterStrategy()
        strat.cancel_order("abc123")
        assert "abc123" in strat._cancelled_orders

    def test_cancel_multiple_orders(self) -> None:
        strat = AlgoMatterStrategy()
        strat.cancel_order("o1")
        strat.cancel_order("o2")
        assert strat._cancelled_orders == ["o1", "o2"]


class TestLimitOrder:
    def test_buy_limit_order_with_price(self) -> None:
        strat = AlgoMatterStrategy()
        oid = strat.buy(2.0, order_type="limit", price=150.0)
        order = strat._pending_orders[0]
        assert order["order_type"] == "limit"
        assert order["price"] == 150.0
        assert order["trigger_price"] is None

    def test_sell_limit_order_with_price(self) -> None:
        strat = AlgoMatterStrategy()
        oid = strat.sell(3.0, order_type="limit", price=200.0)
        order = strat._pending_orders[0]
        assert order["order_type"] == "limit"
        assert order["price"] == 200.0


class TestStopOrder:
    def test_buy_stop_order_with_trigger_price(self) -> None:
        strat = AlgoMatterStrategy()
        oid = strat.buy(1.0, order_type="stop", trigger_price=120.0)
        order = strat._pending_orders[0]
        assert order["order_type"] == "stop"
        assert order["trigger_price"] == 120.0
        assert order["price"] is None

    def test_sell_stop_limit_order(self) -> None:
        strat = AlgoMatterStrategy()
        oid = strat.sell(1.0, order_type="stop_limit", price=95.0, trigger_price=100.0)
        order = strat._pending_orders[0]
        assert order["order_type"] == "stop_limit"
        assert order["price"] == 95.0
        assert order["trigger_price"] == 100.0


class TestHistory:
    def test_history_returns_all_candles(self) -> None:
        candles = [make_candle(float(i)) for i in range(10)]
        strat = AlgoMatterStrategy(history=candles)
        assert len(strat.history()) == 10

    def test_history_returns_last_n_candles(self) -> None:
        candles = [make_candle(float(i)) for i in range(10)]
        strat = AlgoMatterStrategy(history=candles)
        result = strat.history(periods=3)
        assert len(result) == 3
        assert result[0].close == 7.0
        assert result[2].close == 9.0

    def test_history_periods_greater_than_available(self) -> None:
        candles = [make_candle(float(i)) for i in range(3)]
        strat = AlgoMatterStrategy(history=candles)
        result = strat.history(periods=100)
        assert len(result) == 3

    def test_history_returns_copy(self) -> None:
        candles = [make_candle(100.0)]
        strat = AlgoMatterStrategy(history=candles)
        h = strat.history()
        h.clear()
        assert len(strat.history()) == 1


class TestLog:
    def test_log_captures_message_with_default_level(self) -> None:
        strat = AlgoMatterStrategy()
        strat.log("hello")
        assert len(strat._logs) == 1
        assert strat._logs[0]["message"] == "hello"
        assert strat._logs[0]["level"] == "info"
        assert "timestamp" in strat._logs[0]

    def test_log_captures_custom_level(self) -> None:
        strat = AlgoMatterStrategy()
        strat.log("oops", level="error")
        assert strat._logs[0]["level"] == "error"

    def test_log_multiple_entries(self) -> None:
        strat = AlgoMatterStrategy()
        strat.log("a")
        strat.log("b", level="warning")
        strat.log("c", level="debug")
        assert len(strat._logs) == 3
        assert [e["level"] for e in strat._logs] == ["info", "warning", "debug"]


class TestOnCandle:
    def test_sma_cross_generates_buy(self) -> None:
        """Feed an up-trending series so fast > slow and expect a buy."""
        candles = [make_candle(float(i + 1)) for i in range(6)]  # 1..6 rising
        strat = SmaCrossStrategy(
            params={"fast": 3, "slow": 5},
            history=candles,
        )
        strat.on_init()
        strat.on_candle(candles[-1])

        assert len(strat._pending_orders) == 1
        assert strat._pending_orders[0]["action"] == "buy"
        assert any("BUY" in log["message"] for log in strat._logs)

    def test_sma_cross_generates_sell_when_position_held(self) -> None:
        """Feed a down-trending series with existing position => sell."""
        candles = [make_candle(float(10 - i)) for i in range(6)]  # 10..5 falling
        pos = Position(quantity=1.0, avg_entry_price=8.0, unrealized_pnl=-2.0)
        strat = SmaCrossStrategy(
            params={"fast": 3, "slow": 5},
            history=candles,
            position=pos,
        )
        strat.on_init()
        strat.on_candle(candles[-1])

        assert len(strat._pending_orders) == 1
        assert strat._pending_orders[0]["action"] == "sell"
        assert any("SELL" in log["message"] for log in strat._logs)

    def test_sma_cross_no_signal_insufficient_data(self) -> None:
        """Not enough candles => no orders."""
        candles = [make_candle(float(i)) for i in range(3)]
        strat = SmaCrossStrategy(params={"fast": 3, "slow": 5}, history=candles)
        strat.on_candle(candles[-1])
        assert len(strat._pending_orders) == 0


class TestOnOrderUpdate:
    def test_base_on_order_update_is_noop(self) -> None:
        strat = AlgoMatterStrategy()
        strat.on_order_update("oid1", "filled", 100.0, 5.0)  # should not raise

    def test_subclass_can_override_on_order_update(self) -> None:
        class TrackingStrategy(AlgoMatterStrategy):
            def on_order_update(self, order_id, status, fill_price, fill_quantity):
                self.state["last_fill"] = {
                    "order_id": order_id,
                    "status": status,
                    "fill_price": fill_price,
                }

        strat = TrackingStrategy()
        strat.on_order_update("o42", "filled", 155.5, 10.0)
        assert strat.state["last_fill"]["order_id"] == "o42"
        assert strat.state["last_fill"]["fill_price"] == 155.5


class TestOnStop:
    def test_base_on_stop_is_noop(self) -> None:
        strat = AlgoMatterStrategy()
        strat.on_stop()  # should not raise


class TestCollectOutput:
    def test_empty_output(self) -> None:
        strat = AlgoMatterStrategy()
        out = strat.collect_output()
        assert out == {
            "orders": [],
            "cancelled_orders": [],
            "state": {},
            "logs": [],
            "error": None,
        }

    def test_output_with_orders_and_logs(self) -> None:
        strat = AlgoMatterStrategy(state={"counter": 1})
        strat.buy(10.0)
        strat.sell(5.0, order_type="limit", price=200.0)
        strat.cancel_order("old_order")
        strat.log("tick processed")
        strat.state["counter"] = 2

        out = strat.collect_output()

        assert len(out["orders"]) == 2
        assert out["orders"][0]["action"] == "buy"
        assert out["orders"][1]["action"] == "sell"
        assert out["cancelled_orders"] == ["old_order"]
        assert out["state"]["counter"] == 2
        assert len(out["logs"]) == 1
        assert out["error"] is None

    def test_output_returns_copies(self) -> None:
        """Mutating the output dict should not affect internal state."""
        strat = AlgoMatterStrategy()
        strat.buy(1.0)
        out = strat.collect_output()
        out["orders"].clear()
        assert len(strat._pending_orders) == 1


class TestNautilusEscapeHatch:
    def test_nautilus_strategy_default_none(self) -> None:
        strat = AlgoMatterStrategy()
        assert strat.nautilus_strategy is None

    def test_nautilus_strategy_can_be_set(self) -> None:
        strat = AlgoMatterStrategy()
        sentinel = object()
        strat.nautilus_strategy = sentinel
        assert strat.nautilus_strategy is sentinel
