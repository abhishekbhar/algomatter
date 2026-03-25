# tests/test_metrics.py
import pytest
from app.analytics.metrics import compute_metrics


def test_compute_metrics_basic():
    trades = [
        {"pnl": 100, "entry_price": 1000, "exit_price": 1100, "quantity": 1},
        {"pnl": -50, "entry_price": 2000, "exit_price": 1950, "quantity": 1},
        {"pnl": 200, "entry_price": 500, "exit_price": 700, "quantity": 1},
    ]
    equity_curve = [
        {"timestamp": "2025-01-01", "equity": 100000},
        {"timestamp": "2025-01-02", "equity": 100100},
        {"timestamp": "2025-01-03", "equity": 100050},
        {"timestamp": "2025-01-04", "equity": 100250},
    ]
    metrics = compute_metrics(trades, equity_curve, initial_capital=100000)
    assert metrics["total_return"] == pytest.approx(0.25, rel=0.01)  # 250/100000 as %
    assert metrics["win_rate"] == pytest.approx(66.67, rel=0.1)  # 2/3
    assert metrics["profit_factor"] > 1  # winners > losers
    assert "sharpe_ratio" in metrics
    assert "max_drawdown" in metrics


def test_compute_metrics_no_trades():
    metrics = compute_metrics([], [{"timestamp": "2025-01-01", "equity": 100000}], 100000)
    assert metrics["total_return"] == 0
    assert metrics["win_rate"] == 0
    assert metrics["max_drawdown"] == 0


def test_compute_metrics_all_losses():
    trades = [
        {"pnl": -100, "entry_price": 1000, "exit_price": 900, "quantity": 1},
        {"pnl": -200, "entry_price": 2000, "exit_price": 1800, "quantity": 1},
    ]
    equity_curve = [
        {"timestamp": "2025-01-01", "equity": 100000},
        {"timestamp": "2025-01-02", "equity": 99900},
        {"timestamp": "2025-01-03", "equity": 99700},
    ]
    metrics = compute_metrics(trades, equity_curve, initial_capital=100000)
    assert metrics["win_rate"] == 0
    assert metrics["profit_factor"] == 0
    assert metrics["max_drawdown"] > 0
