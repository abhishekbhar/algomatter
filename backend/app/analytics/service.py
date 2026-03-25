"""Analytics service — queries for overview, metrics, equity curves, and trades."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PaperPosition, Strategy, StrategyResult


async def get_overview(session: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Return a portfolio-level overview for the tenant.

    Keys: total_pnl, active_strategies, open_positions, trades_today
    """
    # Active strategies
    active_q = await session.execute(
        select(func.count())
        .select_from(Strategy)
        .where(Strategy.tenant_id == tenant_id, Strategy.is_active.is_(True))
    )
    active_strategies = active_q.scalar() or 0

    # Sum PnL from completed results (load in Python for DB-engine portability)
    results_q = await session.execute(
        select(StrategyResult.metrics)
        .where(
            StrategyResult.tenant_id == tenant_id,
            StrategyResult.status == "completed",
            StrategyResult.metrics.isnot(None),
        )
    )
    total_pnl = 0.0
    for (metrics,) in results_q.all():
        if metrics and "total_return" in metrics:
            total_pnl += float(metrics["total_return"])

    # Open paper positions
    open_pos_q = await session.execute(
        select(func.count())
        .select_from(PaperPosition)
        .where(
            PaperPosition.tenant_id == tenant_id,
            PaperPosition.closed_at.is_(None),
        )
    )
    open_positions = open_pos_q.scalar() or 0

    # Trades today — count paper trading sessions started today
    # Simplified: just return 0 for now; real implementation would count
    # webhook signals or paper trades executed today.
    trades_today = 0

    return {
        "total_pnl": total_pnl,
        "active_strategies": active_strategies,
        "open_positions": open_positions,
        "trades_today": trades_today,
    }


async def get_strategy_metrics(
    session: AsyncSession, strategy_id: uuid.UUID, tenant_id: uuid.UUID
) -> dict | None:
    """Return metrics from the latest completed StrategyResult for a strategy."""
    result = await session.execute(
        select(StrategyResult)
        .where(
            StrategyResult.strategy_id == strategy_id,
            StrategyResult.tenant_id == tenant_id,
            StrategyResult.status == "completed",
            StrategyResult.metrics.isnot(None),
        )
        .order_by(StrategyResult.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return row.metrics


async def get_equity_curve(
    session: AsyncSession, strategy_id: uuid.UUID, tenant_id: uuid.UUID
) -> list[dict]:
    """Return equity curve from the latest completed StrategyResult."""
    result = await session.execute(
        select(StrategyResult.equity_curve)
        .where(
            StrategyResult.strategy_id == strategy_id,
            StrategyResult.tenant_id == tenant_id,
            StrategyResult.status == "completed",
            StrategyResult.equity_curve.isnot(None),
        )
        .order_by(StrategyResult.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row if row else []


async def get_trades(
    session: AsyncSession, strategy_id: uuid.UUID, tenant_id: uuid.UUID
) -> list[dict]:
    """Return trade log from the latest completed StrategyResult."""
    result = await session.execute(
        select(StrategyResult.trade_log)
        .where(
            StrategyResult.strategy_id == strategy_id,
            StrategyResult.tenant_id == tenant_id,
            StrategyResult.status == "completed",
            StrategyResult.trade_log.isnot(None),
        )
        .order_by(StrategyResult.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row if row else []
