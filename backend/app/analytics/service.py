"""Analytics service — queries for overview, metrics, equity curves, and trades."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Float, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.metrics import compute_metrics
from app.db.models import (
    PaperTrade,
    PaperTradingSession,
    PaperPosition,
    Strategy,
    StrategyResult,
    WebhookSignal,
)


async def get_overview(session: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Return a portfolio-level overview for the tenant."""
    # Active strategies
    active_q = await session.execute(
        select(func.count())
        .select_from(Strategy)
        .where(Strategy.tenant_id == tenant_id, Strategy.is_active.is_(True))
    )
    active_strategies = active_q.scalar() or 0

    # Sum total_return from completed StrategyResults via SQL — avoids loading all rows into memory
    strategy_pnl_q = await session.execute(
        select(
            func.coalesce(
                func.sum(
                    func.cast(
                        StrategyResult.metrics["total_return"].as_float(),
                        Float,
                    )
                ),
                0.0,
            )
        ).where(
            StrategyResult.tenant_id == tenant_id,
            StrategyResult.status == "completed",
            StrategyResult.metrics.isnot(None),
        )
    )
    total_pnl = float(strategy_pnl_q.scalar() or 0.0)

    # Add realized PnL from paper trades (webhook strategies)
    paper_pnl_q = await session.execute(
        select(func.coalesce(func.sum(PaperTrade.realized_pnl), 0.0)).where(
            PaperTrade.tenant_id == tenant_id,
            PaperTrade.realized_pnl.isnot(None),
        )
    )
    total_pnl += float(paper_pnl_q.scalar() or 0.0)

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

    # Trades today — paper trades + filled webhook signals executed today (UTC)
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    paper_today_q = await session.execute(
        select(func.count())
        .select_from(PaperTrade)
        .where(
            PaperTrade.tenant_id == tenant_id,
            PaperTrade.executed_at >= today_start,
        )
    )
    webhook_today_q = await session.execute(
        select(func.count())
        .select_from(WebhookSignal)
        .where(
            WebhookSignal.tenant_id == tenant_id,
            WebhookSignal.execution_result == "filled",
            WebhookSignal.received_at >= today_start,
        )
    )
    trades_today = (paper_today_q.scalar() or 0) + (webhook_today_q.scalar() or 0)

    return {
        "total_pnl": total_pnl,
        "active_strategies": active_strategies,
        "open_positions": open_positions,
        "trades_today": trades_today,
    }


async def get_strategy_metrics(
    session: AsyncSession, strategy_id: uuid.UUID, tenant_id: uuid.UUID
) -> dict | None:
    """Return metrics from StrategyResult, falling back to PaperTrade data."""
    # Try StrategyResult first
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
    if row:
        return row.metrics

    # Fall back to PaperTrade data
    trades, equity_curve, initial_capital = await _load_paper_trade_data(
        session, strategy_id, tenant_id
    )
    if not trades:
        return None
    return compute_metrics(trades, equity_curve, initial_capital)


async def get_equity_curve(
    session: AsyncSession, strategy_id: uuid.UUID, tenant_id: uuid.UUID
) -> list[dict]:
    """Return equity curve from StrategyResult, falling back to PaperTrade data."""
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
    if row:
        return row

    # Fall back to PaperTrade data
    _, equity_curve, _ = await _load_paper_trade_data(
        session, strategy_id, tenant_id
    )
    return equity_curve


async def get_trades(
    session: AsyncSession, strategy_id: uuid.UUID, tenant_id: uuid.UUID
) -> list[dict]:
    """Return trade log from StrategyResult, falling back to PaperTrade data."""
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
    if row:
        return row

    # Fall back to PaperTrade data
    trades, _, _ = await _load_paper_trade_data(session, strategy_id, tenant_id)
    return trades


async def _load_paper_trade_data(
    session: AsyncSession,
    strategy_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> tuple[list[dict], list[dict], float]:
    """Load paper trade records for a strategy and return (trades, equity_curve, initial_capital).

    Joins PaperTrade → PaperTradingSession to find trades for this strategy.
    Trades are formatted as AnalyticsTrade dicts.
    Equity curve is built cumulatively from initial_capital + realized_pnl.
    """
    # Get the most recent session for this strategy to obtain initial_capital
    session_q = await session.execute(
        select(PaperTradingSession)
        .where(
            PaperTradingSession.strategy_id == strategy_id,
            PaperTradingSession.tenant_id == tenant_id,
        )
        .order_by(PaperTradingSession.started_at.desc())
        .limit(1)
    )
    paper_session = session_q.scalar_one_or_none()
    initial_capital = float(paper_session.initial_capital) if paper_session else 10000.0

    # Fetch all paper trades for sessions belonging to this strategy, ordered by time
    trades_q = await session.execute(
        select(PaperTrade)
        .join(PaperTradingSession, PaperTrade.session_id == PaperTradingSession.id)
        .where(
            PaperTradingSession.strategy_id == strategy_id,
            PaperTrade.tenant_id == tenant_id,
        )
        .order_by(PaperTrade.executed_at.asc())
    )
    paper_trades = trades_q.scalars().all()

    if not paper_trades:
        return [], [], initial_capital

    # Build trade list (AnalyticsTrade format)
    trade_list: list[dict] = []
    for pt in paper_trades:
        trade_list.append({
            "timestamp": pt.executed_at.isoformat() if pt.executed_at else "",
            "symbol": pt.symbol,
            "action": pt.action,
            "quantity": float(pt.quantity),
            "fill_price": float(pt.fill_price),
            "status": "filled",
            "pnl": float(pt.realized_pnl) if pt.realized_pnl is not None else 0.0,
        })

    # Build cumulative equity curve
    equity = initial_capital
    equity_curve: list[dict] = [
        {"timestamp": paper_trades[0].executed_at.isoformat(), "equity": equity}
    ]
    for pt in paper_trades:
        pnl = float(pt.realized_pnl) if pt.realized_pnl is not None else 0.0
        equity += pnl
        equity_curve.append({
            "timestamp": pt.executed_at.isoformat() if pt.executed_at else "",
            "equity": equity,
        })

    return trade_list, equity_curve, initial_capital
