"""Tests for the Nautilus Trader integration layer."""

from __future__ import annotations

import textwrap
from datetime import datetime, timezone

import pytest

from app.nautilus_integration.data import make_bar_type, ohlcv_to_bars
from app.nautilus_integration.instrument import build_instrument


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candles(n: int = 20, base_price: float = 50_000.0) -> list[dict]:
    """Generate *n* simple ascending candle dicts."""
    base_ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
    candles = []
    for i in range(n):
        ts = datetime(
            2025, 1, 1, hour=i // 60, minute=i % 60, tzinfo=timezone.utc
        )
        price = base_price + i * 10
        candles.append(
            {
                "timestamp": ts,
                "open": price,
                "high": price + 5,
                "low": price - 5,
                "close": price + 2,
                "volume": 100.0,
            }
        )
    return candles


# ---------------------------------------------------------------------------
# 1. build_instrument
# ---------------------------------------------------------------------------


class TestBuildInstrument:
    def test_btcusdt_binance(self):
        inst = build_instrument("BTCUSDT", "BINANCE")
        assert str(inst.id) == "BTCUSDT.BINANCE"
        assert str(inst.base_currency) == "BTC"
        assert str(inst.quote_currency) == "USDT"
        assert inst.price_precision == 2
        assert inst.size_precision == 8

    def test_ethbtc(self):
        inst = build_instrument("ETHBTC", "BINANCE")
        assert str(inst.base_currency) == "ETH"
        assert str(inst.quote_currency) == "BTC"

    def test_custom_precision(self):
        inst = build_instrument("SOLUSDT", "BINANCE", price_precision=4, size_precision=2)
        assert inst.price_precision == 4
        assert inst.size_precision == 2

    def test_fiat_pair(self):
        inst = build_instrument("EURUSD", "FOREX", price_precision=5, size_precision=0)
        assert str(inst.base_currency) == "EUR"
        assert str(inst.quote_currency) == "USD"


# ---------------------------------------------------------------------------
# 2. ohlcv_to_bars
# ---------------------------------------------------------------------------


class TestOhlcvToBars:
    def test_converts_candle_dicts_to_bars(self):
        candles = _make_candles(5)
        inst = build_instrument("BTCUSDT", "BINANCE")
        bar_type = make_bar_type(inst.id, "1m")
        bars = ohlcv_to_bars(candles, inst.id, bar_type)

        assert len(bars) == 5
        first = bars[0]
        assert float(first.open) == 50_000.0
        assert float(first.high) == 50_005.0
        assert float(first.low) == 49_995.0
        assert float(first.close) == 50_002.0
        assert float(first.volume) == 100.0
        assert first.ts_event > 0

    def test_empty_candles(self):
        inst = build_instrument("BTCUSDT", "BINANCE")
        bar_type = make_bar_type(inst.id, "1m")
        bars = ohlcv_to_bars([], inst.id, bar_type)
        assert bars == []

    def test_unix_timestamp_seconds(self):
        candles = [
            {
                "timestamp": 1_700_000_000,
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 102.0,
                "volume": 50.0,
            }
        ]
        inst = build_instrument("BTCUSDT", "BINANCE")
        bar_type = make_bar_type(inst.id, "1h")
        bars = ohlcv_to_bars(candles, inst.id, bar_type)
        assert len(bars) == 1
        assert bars[0].ts_event == 1_700_000_000_000_000_000


# ---------------------------------------------------------------------------
# 3. NautilusAdapter — on_bar -> on_candle translation
# ---------------------------------------------------------------------------


class TestNautilusAdapter:
    def test_on_bar_calls_on_candle(self):
        """Run a minimal backtest and verify the adapter calls on_candle."""
        from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
        from nautilus_trader.config import LoggingConfig
        from nautilus_trader.model.currencies import Currency
        from nautilus_trader.model.enums import AccountType, OmsType
        from nautilus_trader.model.identifiers import Venue
        from nautilus_trader.model.objects import Money

        from app.nautilus_integration.adapter import NautilusAdapter
        from app.strategy_sdk.base import AlgoMatterStrategy
        from app.strategy_sdk.models import Candle

        # --- user strategy that records candles ---
        class RecorderStrategy(AlgoMatterStrategy):
            def on_init(self):
                self._state["candles_received"] = 0

            def on_candle(self, candle: Candle):
                self._state["candles_received"] += 1

        user = RecorderStrategy()
        inst = build_instrument("BTCUSDT", "BINANCE")
        bar_type = make_bar_type(inst.id, "1m")
        candles = _make_candles(10)
        bars = ohlcv_to_bars(candles, inst.id, bar_type)

        config = BacktestEngineConfig(
            trader_id="TEST-001",
            logging=LoggingConfig(log_level="ERROR"),
        )
        engine = BacktestEngine(config=config)
        engine.add_venue(
            venue=Venue("BINANCE"),
            oms_type=OmsType.NETTING,
            account_type=AccountType.CASH,
            starting_balances=[Money(10_000.0, Currency.from_str("USDT"))],
        )
        engine.add_instrument(inst)
        engine.add_data(bars)

        adapter = NautilusAdapter(user_strategy=user)
        adapter.set_instrument_id(inst.id)
        adapter.set_bar_type(bar_type)
        engine.add_strategy(adapter)

        engine.run()
        engine.dispose()

        assert user.state["candles_received"] == 10
        # History buffer should also have 10 candles.
        assert len(user._history) == 10

    def test_order_submission_and_fill(self):
        """Verify that user buy/sell orders flow through Nautilus and trigger on_order_update."""
        from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
        from nautilus_trader.config import LoggingConfig
        from nautilus_trader.model.currencies import Currency
        from nautilus_trader.model.enums import AccountType, OmsType
        from nautilus_trader.model.identifiers import Venue
        from nautilus_trader.model.objects import Money

        from app.nautilus_integration.adapter import NautilusAdapter
        from app.strategy_sdk.base import AlgoMatterStrategy
        from app.strategy_sdk.models import Candle

        class BuySellStrategy(AlgoMatterStrategy):
            def on_init(self):
                self._state["fills"] = []

            def on_candle(self, candle: Candle):
                count = self._state.get("bar_count", 0)
                self._state["bar_count"] = count + 1
                if count == 2:
                    self.buy(0.01)
                elif count == 5:
                    self.sell(0.01)

            def on_order_update(self, order_id, status, fill_price, fill_quantity):
                self._state["fills"].append(
                    {
                        "order_id": order_id,
                        "status": status,
                        "fill_price": fill_price,
                        "fill_quantity": fill_quantity,
                    }
                )

        user = BuySellStrategy()
        inst = build_instrument("BTCUSDT", "BINANCE")
        bar_type = make_bar_type(inst.id, "1m")
        candles = _make_candles(10)
        bars = ohlcv_to_bars(candles, inst.id, bar_type)

        config = BacktestEngineConfig(
            trader_id="TEST-002",
            logging=LoggingConfig(log_level="ERROR"),
        )
        engine = BacktestEngine(config=config)
        engine.add_venue(
            venue=Venue("BINANCE"),
            oms_type=OmsType.NETTING,
            account_type=AccountType.CASH,
            starting_balances=[Money(100_000.0, Currency.from_str("USDT"))],
        )
        engine.add_instrument(inst)
        engine.add_data(bars)

        adapter = NautilusAdapter(user_strategy=user)
        adapter.set_instrument_id(inst.id)
        adapter.set_bar_type(bar_type)
        engine.add_strategy(adapter)

        engine.run()
        engine.dispose()

        fills = user.state["fills"]
        assert len(fills) == 2
        assert fills[0]["status"] == "filled"
        assert fills[0]["fill_quantity"] == 0.01
        assert fills[1]["status"] == "filled"


# ---------------------------------------------------------------------------
# 4. Full backtest via run_backtest
# ---------------------------------------------------------------------------


class TestRunBacktest:
    @pytest.mark.asyncio
    async def test_sma_crossover_backtest(self):
        """Run a simple SMA crossover strategy through the full pipeline."""
        from app.nautilus_integration.engine import run_backtest

        code = textwrap.dedent("""\
            from app.strategy_sdk.base import AlgoMatterStrategy
            from app.strategy_sdk.models import Candle

            class SmaCrossover(AlgoMatterStrategy):
                def on_init(self):
                    self._state["in_position"] = False

                def on_candle(self, candle: Candle):
                    hist = self.history()
                    if len(hist) < 10:
                        return

                    closes = [c.close for c in hist[-10:]]
                    sma_short = sum(closes[-3:]) / 3
                    sma_long = sum(closes) / 10

                    if sma_short > sma_long and not self._state["in_position"]:
                        self.buy(0.01)
                        self._state["in_position"] = True
                    elif sma_short < sma_long and self._state["in_position"]:
                        self.sell(0.01)
                        self._state["in_position"] = False
        """)

        candles = _make_candles(50)
        results = await run_backtest(
            code=code,
            entrypoint="SmaCrossover",
            candles=candles,
            symbol="BTCUSDT",
            exchange="BINANCE",
            interval="1m",
            initial_capital=100_000.0,
        )

        assert "trade_log" in results
        assert "equity_curve" in results
        assert "metrics" in results
        # The equity curve always starts with the initial capital.
        assert results["equity_curve"][0]["equity"] == 100_000.0
        assert isinstance(results["metrics"], dict)
        assert "total_return" in results["metrics"]
        assert "sharpe_ratio" in results["metrics"]

    @pytest.mark.asyncio
    async def test_empty_candles_returns_empty(self):
        from app.nautilus_integration.engine import run_backtest

        code = textwrap.dedent("""\
            from app.strategy_sdk.base import AlgoMatterStrategy

            class DoNothing(AlgoMatterStrategy):
                pass
        """)

        results = await run_backtest(
            code=code,
            entrypoint="DoNothing",
            candles=[],
            symbol="BTCUSDT",
            exchange="BINANCE",
            interval="1m",
        )
        assert results == {"trade_log": [], "equity_curve": [], "metrics": {}}

    @pytest.mark.asyncio
    async def test_bad_entrypoint_raises(self):
        from app.nautilus_integration.engine import run_backtest

        code = "class Foo: pass"
        with pytest.raises(ValueError, match="Entrypoint class 'Missing'"):
            await run_backtest(
                code=code,
                entrypoint="Missing",
                candles=_make_candles(5),
                symbol="BTCUSDT",
                exchange="BINANCE",
                interval="1m",
            )


# ---------------------------------------------------------------------------
# 5. extract_results
# ---------------------------------------------------------------------------


class TestExtractResults:
    def test_extract_results_from_engine(self):
        """Verify extract_results produces valid trade_log and metrics."""
        from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
        from nautilus_trader.config import LoggingConfig
        from nautilus_trader.model.currencies import Currency
        from nautilus_trader.model.enums import AccountType, OmsType
        from nautilus_trader.model.identifiers import Venue
        from nautilus_trader.model.objects import Money

        from app.nautilus_integration.adapter import NautilusAdapter
        from app.nautilus_integration.results import extract_results
        from app.strategy_sdk.base import AlgoMatterStrategy
        from app.strategy_sdk.models import Candle

        class BuyAndSell(AlgoMatterStrategy):
            def on_candle(self, candle: Candle):
                count = self._state.get("bar_count", 0)
                self._state["bar_count"] = count + 1
                if count == 1:
                    self.buy(0.01)
                elif count == 5:
                    self.sell(0.01)

        user = BuyAndSell()
        inst = build_instrument("BTCUSDT", "BINANCE")
        bar_type = make_bar_type(inst.id, "1m")
        candles = _make_candles(10)
        bars = ohlcv_to_bars(candles, inst.id, bar_type)

        config = BacktestEngineConfig(
            trader_id="TEST-003",
            logging=LoggingConfig(log_level="ERROR"),
        )
        engine = BacktestEngine(config=config)
        engine.add_venue(
            venue=Venue("BINANCE"),
            oms_type=OmsType.NETTING,
            account_type=AccountType.CASH,
            starting_balances=[Money(100_000.0, Currency.from_str("USDT"))],
        )
        engine.add_instrument(inst)
        engine.add_data(bars)

        adapter = NautilusAdapter(user_strategy=user)
        adapter.set_instrument_id(inst.id)
        adapter.set_bar_type(bar_type)
        engine.add_strategy(adapter)

        engine.run()

        results = extract_results(engine, initial_capital=100_000.0)
        engine.dispose()

        assert len(results["trade_log"]) == 1
        trade = results["trade_log"][0]
        assert trade["side"] == "long"
        assert trade["quantity"] == 0.01
        assert trade["pnl"] != 0  # price moved, so there should be PnL
        assert results["metrics"]["total_trades"] == 1
        assert len(results["equity_curve"]) >= 2
