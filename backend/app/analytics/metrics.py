"""Analytics metrics module for computing trading performance statistics."""

from __future__ import annotations

import math


def compute_metrics(
    trades: list[dict],
    equity_curve: list[dict],
    initial_capital: float,
) -> dict:
    """Compute performance metrics from trade log and equity curve.

    Returns dict with keys:
    - total_return: percentage return (e.g., 0.25 for 0.25%)
    - win_rate: percentage of winning trades (e.g., 66.67)
    - profit_factor: gross profit / gross loss (0 if no losses)
    - sharpe_ratio: annualized Sharpe ratio (daily returns assumed)
    - max_drawdown: maximum peak-to-trough drawdown percentage
    - total_trades: number of trades
    - avg_trade_pnl: average PnL per trade
    """
    total_trades = len(trades)

    # --- total_return ---
    if len(equity_curve) >= 2:
        final_equity = equity_curve[-1]["equity"]
        total_return = (final_equity - initial_capital) / initial_capital * 100
    else:
        total_return = 0.0

    # --- win_rate ---
    if total_trades == 0:
        win_rate = 0.0
    else:
        winners = [t for t in trades if t["pnl"] > 0]
        win_rate = len(winners) / total_trades * 100

    # --- profit_factor ---
    gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    if gross_loss == 0:
        profit_factor = 0.0 if gross_profit == 0 else 9999.99
    else:
        profit_factor = gross_profit / gross_loss

    # --- sharpe_ratio (annualized, daily returns) ---
    sharpe_ratio = _compute_sharpe(equity_curve)

    # --- max_drawdown ---
    max_drawdown = _compute_max_drawdown(equity_curve)

    # --- avg_trade_pnl ---
    avg_trade_pnl = sum(t["pnl"] for t in trades) / total_trades if total_trades else 0.0

    return {
        "total_return": total_return,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "total_trades": total_trades,
        "avg_trade_pnl": avg_trade_pnl,
    }


def _compute_sharpe(equity_curve: list[dict]) -> float:
    """Annualized Sharpe ratio from daily equity values."""
    if len(equity_curve) < 2:
        return 0.0

    equities = [p["equity"] for p in equity_curve]
    daily_returns = [
        (equities[i] - equities[i - 1]) / equities[i - 1]
        for i in range(1, len(equities))
    ]

    n = len(daily_returns)
    if n == 0:
        return 0.0

    mean_ret = sum(daily_returns) / n
    variance = sum((r - mean_ret) ** 2 for r in daily_returns) / n
    std_ret = math.sqrt(variance)

    if std_ret == 0:
        return 0.0

    return (mean_ret / std_ret) * math.sqrt(252)


def _compute_max_drawdown(equity_curve: list[dict]) -> float:
    """Maximum peak-to-trough drawdown as a percentage."""
    if len(equity_curve) < 2:
        return 0.0

    peak = equity_curve[0]["equity"]
    max_dd = 0.0

    for point in equity_curve:
        equity = point["equity"]
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak * 100
        if drawdown > max_dd:
            max_dd = drawdown

    return max_dd
