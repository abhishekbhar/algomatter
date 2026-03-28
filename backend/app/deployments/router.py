"""Deployment CRUD, status management, and promotion API.

Endpoints:
    POST   /api/v1/hosted-strategies/{strategy_id}/deployments  Create deployment
    GET    /api/v1/hosted-strategies/{strategy_id}/deployments  List strategy deployments
    GET    /api/v1/deployments                                  List all user deployments
    GET    /api/v1/deployments/{deployment_id}                  Get deployment detail
    POST   /api/v1/deployments/{deployment_id}/pause            Pause deployment
    POST   /api/v1/deployments/{deployment_id}/resume           Resume deployment
    POST   /api/v1/deployments/{deployment_id}/stop             Stop deployment
    POST   /api/v1/deployments/stop-all                         Stop all active deployments
    POST   /api/v1/deployments/{deployment_id}/promote          Promote deployment
    GET    /api/v1/deployments/{deployment_id}/results          Get backtest results
    GET    /api/v1/deployments/{deployment_id}/orders           Get open orders
    GET    /api/v1/deployments/{deployment_id}/logs             Get logs (paginated)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_tenant_session
from app.db.models import (
    DeploymentLog,
    DeploymentState,
    StrategyCode,
    StrategyDeployment,
    StrategyResult,
)
from app.deployments.schemas import (
    CreateDeploymentRequest,
    DeploymentLogEntry,
    DeploymentLogsResponse,
    DeploymentResponse,
    DeploymentResultResponse,
    PromoteRequest,
)
from app.deployments.service import (
    check_deployment_limits,
    resolve_code_version,
    validate_cron_expression,
    validate_promotion,
)

router = APIRouter(tags=["deployments"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _deployment_to_response(dep: StrategyDeployment) -> DeploymentResponse:
    return DeploymentResponse(
        id=str(dep.id),
        strategy_code_id=str(dep.strategy_code_id),
        strategy_code_version_id=str(dep.strategy_code_version_id),
        mode=dep.mode,
        status=dep.status,
        symbol=dep.symbol,
        exchange=dep.exchange,
        product_type=dep.product_type,
        interval=dep.interval,
        broker_connection_id=str(dep.broker_connection_id) if dep.broker_connection_id else None,
        cron_expression=dep.cron_expression,
        config=dep.config or {},
        params=dep.params or {},
        promoted_from_id=str(dep.promoted_from_id) if dep.promoted_from_id else None,
        created_at=dep.created_at.isoformat() if dep.created_at else "",
        started_at=dep.started_at.isoformat() if dep.started_at else None,
        stopped_at=dep.stopped_at.isoformat() if dep.stopped_at else None,
    )


# ---------------------------------------------------------------------------
# Create deployment
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/hosted-strategies/{strategy_id}/deployments",
    response_model=DeploymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_deployment(
    strategy_id: uuid.UUID,
    body: CreateDeploymentRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])

    # Verify strategy ownership
    result = await session.execute(
        select(StrategyCode).where(
            StrategyCode.id == strategy_id,
            StrategyCode.tenant_id == tenant_id,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Validate mode
    if body.mode not in ("backtest", "paper", "live"):
        raise HTTPException(status_code=400, detail="mode must be backtest, paper, or live")

    # Check deployment limits
    await check_deployment_limits(session, tenant_id, body.mode)

    # Validate cron for paper/live
    if body.mode in ("paper", "live") and body.cron_expression:
        validate_cron_expression(body.cron_expression)

    # Require broker_connection_id for live
    if body.mode == "live" and not body.broker_connection_id:
        raise HTTPException(status_code=400, detail="broker_connection_id required for live mode")

    # Resolve code version
    code_version = await resolve_code_version(session, strategy_id, body.strategy_code_version)

    # Create deployment
    deployment = StrategyDeployment(
        tenant_id=tenant_id,
        strategy_code_id=strategy_id,
        strategy_code_version_id=code_version.id,
        mode=body.mode,
        status="pending",
        symbol=body.symbol,
        exchange=body.exchange,
        product_type=body.product_type,
        interval=body.interval,
        broker_connection_id=uuid.UUID(body.broker_connection_id) if body.broker_connection_id else None,
        cron_expression=body.cron_expression,
        config=body.config,
        params=body.params,
    )
    session.add(deployment)
    await session.flush()

    # Create initial DeploymentState for paper/live
    if body.mode in ("paper", "live"):
        state = DeploymentState(
            deployment_id=deployment.id,
            tenant_id=tenant_id,
            position=None,
            open_orders=[],
            portfolio={},
            user_state={},
        )
        session.add(state)

    await session.commit()
    await session.refresh(deployment)

    return _deployment_to_response(deployment)


# ---------------------------------------------------------------------------
# List deployments for strategy
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/hosted-strategies/{strategy_id}/deployments",
    response_model=list[DeploymentResponse],
)
async def list_strategy_deployments(
    strategy_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])

    # Verify strategy ownership
    result = await session.execute(
        select(StrategyCode).where(
            StrategyCode.id == strategy_id,
            StrategyCode.tenant_id == tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Strategy not found")

    result = await session.execute(
        select(StrategyDeployment)
        .where(
            StrategyDeployment.strategy_code_id == strategy_id,
            StrategyDeployment.tenant_id == tenant_id,
        )
        .order_by(StrategyDeployment.created_at.desc())
    )
    deployments = result.scalars().all()
    return [_deployment_to_response(d) for d in deployments]


# ---------------------------------------------------------------------------
# List all user deployments
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/deployments",
    response_model=list[DeploymentResponse],
)
async def list_all_deployments(
    status_filter: str | None = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    query = select(StrategyDeployment).where(
        StrategyDeployment.tenant_id == tenant_id,
    )
    if status_filter:
        query = query.where(StrategyDeployment.status == status_filter)
    query = query.order_by(StrategyDeployment.created_at.desc())
    result = await session.execute(query)
    deployments = result.scalars().all()
    return [_deployment_to_response(d) for d in deployments]


# ---------------------------------------------------------------------------
# Get deployment detail
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/deployments/{deployment_id}",
    response_model=DeploymentResponse,
)
async def get_deployment(
    deployment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment).where(
            StrategyDeployment.id == deployment_id,
            StrategyDeployment.tenant_id == tenant_id,
        )
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return _deployment_to_response(deployment)


# ---------------------------------------------------------------------------
# Pause deployment
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/deployments/{deployment_id}/pause",
    response_model=DeploymentResponse,
)
async def pause_deployment(
    deployment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment).where(
            StrategyDeployment.id == deployment_id,
            StrategyDeployment.tenant_id == tenant_id,
        )
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    if deployment.status != "running":
        raise HTTPException(status_code=409, detail="Only running deployments can be paused")

    deployment.status = "paused"
    await session.commit()
    await session.refresh(deployment)
    return _deployment_to_response(deployment)


# ---------------------------------------------------------------------------
# Resume deployment
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/deployments/{deployment_id}/resume",
    response_model=DeploymentResponse,
)
async def resume_deployment(
    deployment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment).where(
            StrategyDeployment.id == deployment_id,
            StrategyDeployment.tenant_id == tenant_id,
        )
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    if deployment.status != "paused":
        raise HTTPException(status_code=409, detail="Only paused deployments can be resumed")

    deployment.status = "running"
    deployment.started_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(deployment)
    return _deployment_to_response(deployment)


# ---------------------------------------------------------------------------
# Stop deployment
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/deployments/{deployment_id}/stop",
    response_model=DeploymentResponse,
)
async def stop_deployment(
    deployment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment).where(
            StrategyDeployment.id == deployment_id,
            StrategyDeployment.tenant_id == tenant_id,
        )
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    if deployment.status in ("stopped", "completed", "error"):
        raise HTTPException(status_code=409, detail="Deployment is already stopped")

    deployment.status = "stopped"
    deployment.stopped_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(deployment)
    return _deployment_to_response(deployment)


# ---------------------------------------------------------------------------
# Stop all active deployments
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/deployments/stop-all",
    response_model=list[DeploymentResponse],
)
async def stop_all_deployments(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment).where(
            StrategyDeployment.tenant_id == tenant_id,
            StrategyDeployment.status.in_(["pending", "running", "paused"]),
        )
    )
    deployments = result.scalars().all()
    now = datetime.now(UTC)
    for dep in deployments:
        dep.status = "stopped"
        dep.stopped_at = now
    await session.commit()
    # Refresh all
    stopped = []
    for dep in deployments:
        await session.refresh(dep)
        stopped.append(_deployment_to_response(dep))
    return stopped


# ---------------------------------------------------------------------------
# Promote deployment
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/deployments/{deployment_id}/promote",
    response_model=DeploymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def promote_deployment(
    deployment_id: uuid.UUID,
    body: PromoteRequest | None = None,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    if body is None:
        body = PromoteRequest()

    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment).where(
            StrategyDeployment.id == deployment_id,
            StrategyDeployment.tenant_id == tenant_id,
        )
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    # Validate promotion eligibility
    target_mode = await validate_promotion(session, deployment)

    # Check limits for target mode
    await check_deployment_limits(session, tenant_id, target_mode)

    # For live promotion, require broker_connection_id
    broker_id = body.broker_connection_id or (
        str(deployment.broker_connection_id) if deployment.broker_connection_id else None
    )
    if target_mode == "live" and not broker_id:
        raise HTTPException(status_code=400, detail="broker_connection_id required for live mode")

    # Merge config
    merged_config = {**(deployment.config or {}), **body.config_overrides}

    # Create new deployment
    new_deployment = StrategyDeployment(
        tenant_id=tenant_id,
        strategy_code_id=deployment.strategy_code_id,
        strategy_code_version_id=deployment.strategy_code_version_id,
        mode=target_mode,
        status="pending",
        symbol=deployment.symbol,
        exchange=deployment.exchange,
        product_type=deployment.product_type,
        interval=deployment.interval,
        broker_connection_id=uuid.UUID(broker_id) if broker_id else None,
        cron_expression=body.cron_expression or deployment.cron_expression,
        config=merged_config,
        params=deployment.params or {},
        promoted_from_id=deployment.id,
    )
    session.add(new_deployment)
    await session.flush()

    # Create DeploymentState for the new deployment
    state = DeploymentState(
        deployment_id=new_deployment.id,
        tenant_id=tenant_id,
        position=None,
        open_orders=[],
        portfolio={},
        user_state={},
    )
    session.add(state)

    await session.commit()
    await session.refresh(new_deployment)

    return _deployment_to_response(new_deployment)


# ---------------------------------------------------------------------------
# Get deployment results
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/deployments/{deployment_id}/results",
    response_model=list[DeploymentResultResponse],
)
async def get_deployment_results(
    deployment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])

    # Verify deployment ownership
    result = await session.execute(
        select(StrategyDeployment).where(
            StrategyDeployment.id == deployment_id,
            StrategyDeployment.tenant_id == tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Deployment not found")

    result = await session.execute(
        select(StrategyResult).where(
            StrategyResult.deployment_id == deployment_id,
            StrategyResult.tenant_id == tenant_id,
        )
    )
    results = result.scalars().all()
    return [
        DeploymentResultResponse(
            id=str(r.id),
            deployment_id=str(r.deployment_id),
            trade_log=r.trade_log if isinstance(r.trade_log, list) else None,
            equity_curve=r.equity_curve if isinstance(r.equity_curve, list) else None,
            metrics=r.metrics if isinstance(r.metrics, dict) else None,
            status=r.status,
            created_at=r.created_at.isoformat() if r.created_at else "",
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
        )
        for r in results
    ]


# ---------------------------------------------------------------------------
# Get open orders
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/deployments/{deployment_id}/orders",
)
async def get_deployment_orders(
    deployment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(DeploymentState).where(
            DeploymentState.deployment_id == deployment_id,
            DeploymentState.tenant_id == tenant_id,
        )
    )
    state = result.scalar_one_or_none()
    if not state:
        raise HTTPException(status_code=404, detail="Deployment state not found")
    return {"open_orders": state.open_orders or []}


# ---------------------------------------------------------------------------
# Get deployment logs (paginated)
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/deployments/{deployment_id}/logs",
    response_model=DeploymentLogsResponse,
)
async def get_deployment_logs(
    deployment_id: uuid.UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])

    # Verify deployment ownership
    result = await session.execute(
        select(StrategyDeployment).where(
            StrategyDeployment.id == deployment_id,
            StrategyDeployment.tenant_id == tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Deployment not found")

    # Get total count
    total = await session.scalar(
        select(func.count(DeploymentLog.id)).where(
            DeploymentLog.deployment_id == deployment_id,
            DeploymentLog.tenant_id == tenant_id,
        )
    )

    # Get paginated logs
    result = await session.execute(
        select(DeploymentLog)
        .where(
            DeploymentLog.deployment_id == deployment_id,
            DeploymentLog.tenant_id == tenant_id,
        )
        .order_by(DeploymentLog.timestamp.desc())
        .offset(offset)
        .limit(limit)
    )
    logs = result.scalars().all()

    return DeploymentLogsResponse(
        logs=[
            DeploymentLogEntry(
                id=str(log.id),
                timestamp=log.timestamp.isoformat() if log.timestamp else "",
                level=log.level,
                message=log.message,
            )
            for log in logs
        ],
        total=total or 0,
        offset=offset,
        limit=limit,
    )
