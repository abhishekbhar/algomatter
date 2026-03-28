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
    """Extract closed positions as trades."""
    trades: list[dict] = []
    for pos in cache.positions_closed():
        entry_time = datetime.fromtimestamp(
            pos.ts_opened / 1_000_000_000, tz=timezone.utc
        )
        exit_time = datetime.fromtimestamp(
            pos.ts_closed / 1_000_000_000, tz=timezone.utc
        )
        pnl = float(pos.realized_pnl)
        commission = sum(float(c) for c in pos.commissions())
        trades.append(
            {
                "entry_time": entry_time.isoformat(),
                "exit_time": exit_time.isoformat(),
                "side": "long" if pos.entry.name == "BUY" else "short",
                "quantity": float(pos.peak_qty),
                "entry_price": pos.avg_px_open,
                "exit_price": pos.avg_px_close,
                "pnl": pnl,
                "commission": commission,
            }
        )
    # Sort by entry time.
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
