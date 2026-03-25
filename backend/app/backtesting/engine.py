"""Backtesting engine -- replays signals through SimulatedBroker and computes
performance metrics.

The engine is pure async and has no database dependency.
"""

from __future__ import annotations

from decimal import Decimal

from app.analytics.metrics import compute_metrics
from app.brokers.base import OrderRequest
from app.brokers.simulated import SimulatedBroker


async def run_backtest(
    signals: list[dict],
    initial_capital: Decimal,
    slippage_pct: Decimal = Decimal("0"),
    commission_pct: Decimal = Decimal("0"),
) -> dict:
    """Run a backtest by replaying *signals* through a SimulatedBroker.

    Returns
    -------
    dict
        {status, trade_log, equity_curve, metrics, warnings}
    """
    broker = SimulatedBroker(
        initial_capital=initial_capital,
        slippage_pct=slippage_pct,
        commission_pct=commission_pct,
    )

    # Sort signals chronologically
    sorted_signals = sorted(signals, key=lambda s: s["timestamp"])

    trade_log: list[dict] = []
    equity_curve: list[dict] = []
    warnings: list[str] = []

    # Record initial equity
    balance = await broker.get_balance()
    equity_curve.append(
        {
            "timestamp": sorted_signals[0]["timestamp"] if sorted_signals else None,
            "equity": float(balance.available + balance.used_margin),
        }
    )

    for signal in sorted_signals:
        order = OrderRequest(
            symbol=signal["symbol"],
            exchange=signal.get("exchange", "NSE"),
            action=signal["action"],
            quantity=Decimal(str(signal["quantity"])),
            order_type=signal.get("order_type", "MARKET"),
            price=Decimal(str(signal["price"])),
            product_type=signal.get("product_type", "INTRADAY"),
        )

        response = await broker.place_order(order)

        # Compute PnL for this trade entry
        pnl = 0.0
        if signal["action"] == "SELL" and response.status == "filled":
            # Check positions for realized PnL
            positions = await broker.get_positions()
            for pos in positions:
                if pos.symbol == signal["symbol"] and pos.closed_at is not None:
                    pnl = float(pos.pnl)
                    break
            else:
                # Position still open but partially closed -- get pnl from
                # the position that was just reduced
                for pos in positions:
                    if pos.symbol == signal["symbol"]:
                        pnl = float(pos.pnl)
                        break

        trade_entry = {
            "timestamp": signal["timestamp"],
            "symbol": signal["symbol"],
            "action": signal["action"],
            "quantity": float(order.quantity),
            "fill_price": float(response.fill_price) if response.fill_price else None,
            "status": response.status,
            "pnl": pnl,
        }
        trade_log.append(trade_entry)

        if response.status == "rejected":
            warnings.append(
                f"Order rejected at {signal['timestamp']}: {response.message}"
            )

        # Record equity after this trade
        balance = await broker.get_balance()
        positions = await broker.get_positions()
        position_value = sum(
            float(p.current_price or p.entry_price) * float(p.quantity)
            for p in positions
            if p.closed_at is None
        )
        equity = float(balance.available) + position_value

        equity_curve.append(
            {
                "timestamp": signal["timestamp"],
                "equity": equity,
            }
        )

    # Compute metrics using only SELL trades (which have realized PnL)
    sell_trades = [t for t in trade_log if t["action"] == "SELL" and t["status"] == "filled"]
    metrics = compute_metrics(
        trades=sell_trades,
        equity_curve=equity_curve,
        initial_capital=float(initial_capital),
    )

    return {
        "status": "completed",
        "trade_log": trade_log,
        "equity_curve": equity_curve,
        "metrics": metrics,
        "warnings": warnings,
    }
