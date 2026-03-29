"""Extract backtest results from a completed Nautilus BacktestEngine."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.analytics.metrics import compute_metrics

if TYPE_CHECKING:
    from nautilus_trader.backtest.engine import BacktestEngine


def extract_results(engine: BacktestEngine, initial_capital: float) -> dict:
    """Build a results dict from a completed ``BacktestEngine``.

    Returns
    -------
    dict
        ``{"trade_log": [...], "equity_curve": [...], "metrics": {...}}``

    The ``trade_log`` entries have keys ``entry_time``, ``exit_time``,
    ``side``, ``quantity``, ``entry_price``, ``exit_price``, ``pnl``,
    ``commission``.

    The ``equity_curve`` entries have keys ``timestamp`` and ``equity``.
    """
    cache = engine.cache
    trade_log = _build_trade_log(cache)
    equity_curve = _build_equity_curve(cache, initial_capital, trade_log)
    metrics = compute_metrics(trade_log, equity_curve, initial_capital)
    return {
        "trade_log": trade_log,
        "equity_curve": equity_curve,
        "metrics": metrics,
    }


def _build_trade_log(cache) -> list[dict]:
    """Extract round-trip trades from filled orders.

    In NETTING mode Nautilus tracks a single position per instrument, so
    ``positions_closed()`` returns at most one entry even when many
    buy/sell pairs occurred.  Instead we pair filled buy and sell orders
    chronologically to reconstruct individual round-trip trades.
    """
    from nautilus_trader.model.enums import OrderSide, OrderStatus

    filled = sorted(
        (o for o in cache.orders() if o.status == OrderStatus.FILLED),
        key=lambda o: o.ts_last,
    )

    trades: list[dict] = []
    pending_entry = None

    for order in filled:
        if order.side == OrderSide.BUY:
            # New entry (or replace stale one if consecutive buys)
            pending_entry = order
        elif order.side == OrderSide.SELL and pending_entry is not None:
            entry_time = datetime.fromtimestamp(
                pending_entry.ts_last / 1_000_000_000, tz=timezone.utc
            )
            exit_time = datetime.fromtimestamp(
                order.ts_last / 1_000_000_000, tz=timezone.utc
            )
            entry_price = float(pending_entry.avg_px)
            exit_price = float(order.avg_px)
            qty = float(pending_entry.filled_qty)
            pnl = round((exit_price - entry_price) * qty, 8)
            trades.append(
                {
                    "entry_time": entry_time.isoformat(),
                    "exit_time": exit_time.isoformat(),
                    "side": "long",
                    "quantity": qty,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "commission": 0.0,
                }
            )
            pending_entry = None

    trades.sort(key=lambda t: t["entry_time"])
    return trades


def _build_equity_curve(
    cache,
    initial_capital: float,
    trade_log: list[dict],
) -> list[dict]:
    """Build an equity curve from the trade log.

    Since Nautilus does not natively emit an equity-per-bar series in
    backtest mode, we reconstruct a simplified curve from the trade PnLs.
    Each point represents equity *after* a trade closes.
    """
    equity = initial_capital
    curve: list[dict] = [
        {"timestamp": None, "equity": initial_capital},
    ]
    for trade in trade_log:
        equity += trade["pnl"]
        curve.append(
            {
                "timestamp": trade["exit_time"],
                "equity": equity,
            }
        )
    return curve
