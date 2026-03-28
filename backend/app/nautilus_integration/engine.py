"""High-level backtest runner that ties all Nautilus integration pieces together."""

from __future__ import annotations

import logging
from typing import Any

from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.currencies import Currency
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.objects import Money

from app.nautilus_integration.adapter import NautilusAdapter, NautilusAdapterConfig
from app.nautilus_integration.data import make_bar_type, ohlcv_to_bars
from app.nautilus_integration.instrument import build_instrument
from app.nautilus_integration.results import extract_results

logger = logging.getLogger(__name__)


async def run_backtest(
    code: str,
    entrypoint: str,
    candles: list[dict],
    symbol: str,
    exchange: str,
    interval: str,
    initial_capital: float = 10_000.0,
    params: dict[str, Any] | None = None,
) -> dict:
    """Run a full backtest and return the results dict.

    Parameters
    ----------
    code : str
        Python source code containing the user strategy class.
    entrypoint : str
        Name of the strategy class inside *code*.
    candles : list[dict]
        OHLCV candle dicts with keys ``timestamp``, ``open``, ``high``,
        ``low``, ``close``, ``volume``.
    symbol : str
        Trading pair, e.g. ``"BTCUSDT"``.
    exchange : str
        Venue name, e.g. ``"BINANCE"``.
    interval : str
        Bar interval, e.g. ``"1m"``, ``"1h"``, ``"1d"``.
    initial_capital : float
        Starting account balance in quote currency.
    params : dict | None
        Parameters forwarded to the user strategy constructor.

    Returns
    -------
    dict
        ``{"trade_log": [...], "equity_curve": [...], "metrics": {...}}``
    """
    # 1. Parse user code and instantiate the strategy.
    user_strategy = _load_user_strategy(code, entrypoint, params)

    # 2. Build instrument.
    instrument = build_instrument(symbol, exchange)

    # 3. Determine quote currency for the venue balance.
    quote_code = str(instrument.quote_currency)
    quote_currency = Currency.from_str(quote_code)

    # 4. Build bar type and convert candles.
    bar_type = make_bar_type(instrument.id, interval)
    bars = ohlcv_to_bars(
        candles,
        instrument.id,
        bar_type,
        price_precision=instrument.price_precision,
        volume_precision=instrument.size_precision,
    )

    if not bars:
        return {"trade_log": [], "equity_curve": [], "metrics": {}}

    # 5. Create the BacktestEngine.
    engine_config = BacktestEngineConfig(
        trader_id="ALGOMATTER-001",
        logging=LoggingConfig(log_level="ERROR"),
    )
    engine = BacktestEngine(config=engine_config)

    venue = Venue(exchange.upper())

    try:
        # 6. Add venue, instrument, data.
        engine.add_venue(
            venue=venue,
            oms_type=OmsType.NETTING,
            account_type=AccountType.CASH,
            starting_balances=[Money(initial_capital, quote_currency)],
        )
        engine.add_instrument(instrument)
        engine.add_data(bars)

        # 7. Wrap the user strategy in the Nautilus adapter.
        adapter_config = NautilusAdapterConfig(
            instrument_id=str(instrument.id),
            bar_type=str(bar_type),
        )
        adapter = NautilusAdapter(
            user_strategy=user_strategy,
            config=adapter_config,
        )
        adapter.set_instrument_id(instrument.id)
        adapter.set_bar_type(bar_type)
        engine.add_strategy(adapter)

        # 8. Run the backtest.
        engine.run()

        # 9. Extract results.
        results = extract_results(engine, initial_capital)
        return results
    finally:
        engine.dispose()


def _load_user_strategy(code: str, entrypoint: str, params: dict | None):
    """Execute user code in a restricted namespace and return the strategy instance."""
    namespace: dict[str, Any] = {}
    exec(code, namespace)  # noqa: S102 — security boundary is the subprocess sandbox

    strategy_cls = namespace.get(entrypoint)
    if strategy_cls is None:
        raise ValueError(
            f"Entrypoint class '{entrypoint}' not found in user code. "
            f"Available names: {[k for k in namespace if not k.startswith('_')]}"
        )

    return strategy_cls(params=params or {})
