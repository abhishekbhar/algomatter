import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DeploymentLog,
    StrategyCodeVersion,
    StrategyDeployment,
)

MAX_PAPER_DEPLOYMENTS = 5
MAX_LIVE_DEPLOYMENTS = 2
MAX_CONCURRENT_BACKTESTS = 3
MIN_PAPER_TICKS_FOR_LIVE = 10
CRON_MIN_INTERVAL_MINUTES = 5


def validate_cron_expression(cron_expr: str) -> None:
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise HTTPException(status_code=400, detail="Invalid cron expression (need 5 fields)")
    minute_field = parts[0]
    if minute_field.startswith("*/"):
        try:
            interval = int(minute_field[2:])
            if interval < CRON_MIN_INTERVAL_MINUTES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Minimum cron interval is {CRON_MIN_INTERVAL_MINUTES} minutes",
                )
        except ValueError:
            pass


async def check_deployment_limits(session: AsyncSession, tenant_id: uuid.UUID, mode: str) -> None:
    if mode == "backtest":
        count = await session.scalar(
            select(func.count(StrategyDeployment.id)).where(
                StrategyDeployment.tenant_id == tenant_id,
                StrategyDeployment.mode == "backtest",
                StrategyDeployment.status.in_(["pending", "running"]),
            )
        )
        if count >= MAX_CONCURRENT_BACKTESTS:
            raise HTTPException(status_code=429, detail=f"Max {MAX_CONCURRENT_BACKTESTS} concurrent backtests")
    elif mode == "paper":
        count = await session.scalar(
            select(func.count(StrategyDeployment.id)).where(
                StrategyDeployment.tenant_id == tenant_id,
                StrategyDeployment.mode == "paper",
                StrategyDeployment.status.in_(["running", "paused"]),
            )
        )
        if count >= MAX_PAPER_DEPLOYMENTS:
            raise HTTPException(status_code=429, detail=f"Max {MAX_PAPER_DEPLOYMENTS} paper deployments")
    elif mode == "live":
        count = await session.scalar(
            select(func.count(StrategyDeployment.id)).where(
                StrategyDeployment.tenant_id == tenant_id,
                StrategyDeployment.mode == "live",
                StrategyDeployment.status.in_(["running", "paused"]),
            )
        )
        if count >= MAX_LIVE_DEPLOYMENTS:
            raise HTTPException(status_code=429, detail=f"Max {MAX_LIVE_DEPLOYMENTS} live deployments")


async def resolve_code_version(
    session: AsyncSession, strategy_code_id: uuid.UUID, version: int | None
) -> StrategyCodeVersion:
    if version is not None:
        result = await session.execute(
            select(StrategyCodeVersion).where(
                StrategyCodeVersion.strategy_code_id == strategy_code_id,
                StrategyCodeVersion.version == version,
            )
        )
    else:
        result = await session.execute(
            select(StrategyCodeVersion)
            .where(StrategyCodeVersion.strategy_code_id == strategy_code_id)
            .order_by(StrategyCodeVersion.version.desc())
            .limit(1)
        )
    cv = result.scalar_one_or_none()
    if not cv:
        raise HTTPException(status_code=404, detail="Strategy code version not found")
    return cv


async def validate_promotion(session: AsyncSession, deployment: StrategyDeployment) -> str:
    if deployment.mode == "backtest" and deployment.status == "completed":
        return "paper"
    elif deployment.mode == "paper" and deployment.status in ("running", "paused"):
        tick_count = await session.scalar(
            select(func.count(DeploymentLog.id)).where(
                DeploymentLog.deployment_id == deployment.id,
                DeploymentLog.level == "info",
            )
        )
        if (tick_count or 0) < MIN_PAPER_TICKS_FOR_LIVE:
            raise HTTPException(
                status_code=422,
                detail=f"Paper deployment needs at least {MIN_PAPER_TICKS_FOR_LIVE} ticks before promotion (has {tick_count})",
            )
        return "live"
    else:
        raise HTTPException(
            status_code=409,
            detail=f"Deployment in mode={deployment.mode} status={deployment.status} cannot be promoted",
        )
