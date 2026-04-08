"""Backtesting API router.

Endpoints:
    POST   /api/v1/backtests       Create & run a backtest
    GET    /api/v1/backtests       List backtests for tenant
    GET    /api/v1/backtests/{id}  Get backtest detail
    DELETE /api/v1/backtests/{id}  Delete a backtest
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_tenant_session
from app.backtesting.engine import run_backtest
from app.db.models import Strategy, StrategyCode, StrategyDeployment, StrategyResult
from app.feature_flags import require_backtesting_enabled

router = APIRouter(prefix="/api/v1/backtests", tags=["backtests"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class CreateBacktestRequest(BaseModel):
    strategy_id: str
    start_date: str
    end_date: str
    capital: float
    slippage_pct: float = 0
    commission_pct: float = 0
    signals_csv: str


class BacktestResponse(BaseModel):
    id: str
    strategy_id: str | None
    strategy_name: str | None = None
    status: str
    trade_log: list | None = None
    equity_curve: list | None = None
    metrics: dict | None = None
    config: dict | None = None
    warnings: list | None = None
    error_message: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_signals_csv(csv_text: str) -> list[dict]:
    """Parse a CSV string into a list of signal dicts."""
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    signals = []
    for row in reader:
        signal: dict = {}
        for key, value in row.items():
            key = key.strip()
            value = value.strip() if value else value
            # Try numeric conversion
            if key in ("quantity", "price"):
                try:
                    signal[key] = float(value)
                except (ValueError, TypeError):
                    signal[key] = value
            else:
                signal[key] = value
        signals.append(signal)
    return signals


def _model_to_response(row: StrategyResult, strategy_name: str | None = None) -> BacktestResponse:
    return BacktestResponse(
        id=str(row.id),
        strategy_id=str(row.strategy_id) if row.strategy_id else None,
        strategy_name=strategy_name,
        status=row.status,
        trade_log=row.trade_log,
        equity_curve=row.equity_curve,
        metrics=row.metrics,
        config=row.config,
        warnings=row.warnings,
        error_message=row.error_message,
        created_at=row.created_at.isoformat() if row.created_at else None,
        completed_at=row.completed_at.isoformat() if row.completed_at else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=BacktestResponse,
    dependencies=[Depends(require_backtesting_enabled)],
)
async def create_backtest(
    body: CreateBacktestRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    strategy_id = uuid.UUID(body.strategy_id)

    config = {
        "start_date": body.start_date,
        "end_date": body.end_date,
        "capital": body.capital,
        "slippage_pct": body.slippage_pct,
        "commission_pct": body.commission_pct,
    }

    # Create StrategyResult row (queued)
    result_row = StrategyResult(
        tenant_id=tenant_id,
        strategy_id=strategy_id,
        result_type="backtest",
        status="queued",
        config=config,
    )
    session.add(result_row)
    await session.commit()
    await session.refresh(result_row)

    # Parse signals and run backtest synchronously
    signals = _parse_signals_csv(body.signals_csv)

    try:
        result = await run_backtest(
            signals=signals,
            initial_capital=Decimal(str(body.capital)),
            slippage_pct=Decimal(str(body.slippage_pct)),
            commission_pct=Decimal(str(body.commission_pct)),
        )
        result_row.status = result["status"]
        result_row.trade_log = result["trade_log"]
        result_row.equity_curve = result["equity_curve"]
        result_row.metrics = result["metrics"]
        result_row.warnings = result["warnings"]
        result_row.completed_at = datetime.now(UTC)
    except Exception as exc:
        result_row.status = "failed"
        result_row.error_message = str(exc)

    await session.commit()
    await session.refresh(result_row)

    return _model_to_response(result_row)


@router.get("", response_model=list[BacktestResponse])
async def list_backtests(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyResult).where(
            StrategyResult.tenant_id == tenant_id,
            StrategyResult.result_type == "backtest",
        )
    )
    rows = result.scalars().all()

    # Resolve strategy names from webhook strategies and hosted strategies
    responses = []
    for r in rows:
        name: str | None = None
        if r.strategy_id:
            strat = await session.get(Strategy, r.strategy_id)
            if strat:
                name = strat.name
        elif r.deployment_id:
            dep = await session.get(StrategyDeployment, r.deployment_id)
            if dep:
                code = await session.get(StrategyCode, dep.strategy_code_id)
                if code:
                    name = code.name
        responses.append(_model_to_response(r, strategy_name=name))
    return responses


@router.get("/{backtest_id}", response_model=BacktestResponse)
async def get_backtest(
    backtest_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyResult).where(
            StrategyResult.id == backtest_id,
            StrategyResult.tenant_id == tenant_id,
            StrategyResult.result_type == "backtest",
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest not found",
        )
    return _model_to_response(row)


@router.delete(
    "/{backtest_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_backtesting_enabled)],
)
async def delete_backtest(
    backtest_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyResult).where(
            StrategyResult.id == backtest_id,
            StrategyResult.tenant_id == tenant_id,
            StrategyResult.result_type == "backtest",
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest not found",
        )
    await session.delete(row)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
