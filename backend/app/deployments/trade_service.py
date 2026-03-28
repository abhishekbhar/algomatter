"""Trade business logic for live trading features."""

from __future__ import annotations

from app.analytics.metrics import compute_metrics


def compute_pnl(
    action: str,
    fill_price: float,
    fill_quantity: float,
    avg_entry_price: float | None,
) -> float | None:
    """Compute realized PnL for a position-closing trade.
    Returns None if avg_entry_price is None (opening trade).
    """
    if avg_entry_price is None:
        return None
    if action == "SELL":
        return (fill_price - avg_entry_price) * fill_quantity
    elif action == "BUY":
        return (avg_entry_price - fill_price) * fill_quantity
    return None


def compute_live_metrics(trades: list[dict], initial_capital: float) -> dict:
    """Compute live performance metrics from filled trade PnLs.
    Each trade dict must have a "pnl" key.
    Uses compute_metrics() for base metrics, then adds best/worst trade separately.
    """
    total_trades = len(trades)

    if total_trades == 0:
        return {
            "total_return": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "total_trades": 0,
            "avg_trade_pnl": 0.0,
            "best_trade": None,
            "worst_trade": None,
        }

    equity_curve = build_equity_curve(
        [t["pnl"] for t in trades], initial_capital
    )

    base = compute_metrics(trades, equity_curve, initial_capital)

    pnls = [t["pnl"] for t in trades]
    base["best_trade"] = max(pnls)
    base["worst_trade"] = min(pnls)

    return base


def build_equity_curve(pnls: list[float], initial_capital: float) -> list[dict]:
    """Build equity curve from sequential PnL values."""
    curve = [{"equity": initial_capital}]
    running = initial_capital
    for pnl in pnls:
        running += pnl
        curve.append({"equity": running})
    return curve
