"""Deployment CRUD, status management, and promotion API.

Endpoints:
    POST   /api/v1/hosted-strategies/{strategy_id}/deployments  Create deployment
    GET    /api/v1/hosted-strategies/{strategy_id}/deployments  List strategy deployments
    GET    /api/v1/deployments                                  List all user deployments
    GET    /api/v1/deployments/recent-trades                    Recent trades (cross-deployment)
    GET    /api/v1/deployments/{deployment_id}                  Get deployment detail
    POST   /api/v1/deployments/{deployment_id}/pause            Pause deployment
    POST   /api/v1/deployments/{deployment_id}/resume           Resume deployment
    POST   /api/v1/deployments/{deployment_id}/stop             Stop deployment
    POST   /api/v1/deployments/stop-all                         Stop all active deployments
    POST   /api/v1/deployments/{deployment_id}/promote          Promote deployment
    GET    /api/v1/deployments/{deployment_id}/trades           Get deployment trades
    GET    /api/v1/deployments/{deployment_id}/position         Get deployment position
    GET    /api/v1/deployments/{deployment_id}/results          Get backtest results
    GET    /api/v1/deployments/{deployment_id}/orders           Get open orders
    GET    /api/v1/deployments/{deployment_id}/logs             Get logs (paginated)
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user, get_tenant_session
from app.db.models import (
    DeploymentLog,
    DeploymentState,
    DeploymentTrade,
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
    DeploymentTradeResponse,
    PositionResponse,
    PromoteRequest,
    RecentTradesResponse,
    TradesResponse,
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
        strategy_name=dep.strategy_code.name if dep.strategy_code else "",
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


def _trade_to_response(trade: DeploymentTrade, strategy_name: str, symbol: str) -> DeploymentTradeResponse:
    return DeploymentTradeResponse(
        id=str(trade.id),
        deployment_id=str(trade.deployment_id),
        order_id=trade.order_id,
        broker_order_id=trade.broker_order_id,
        action=trade.action,
        quantity=float(trade.quantity),
        order_type=trade.order_type,
        price=float(trade.price) if trade.price is not None else None,
        trigger_price=float(trade.trigger_price) if trade.trigger_price is not None else None,
        fill_price=float(trade.fill_price) if trade.fill_price is not None else None,
        fill_quantity=float(trade.fill_quantity) if trade.fill_quantity is not None else None,
        status=trade.status,
        is_manual=trade.is_manual,
        realized_pnl=float(trade.realized_pnl) if trade.realized_pnl is not None else None,
        created_at=trade.created_at.isoformat() if trade.created_at else "",
        filled_at=trade.filled_at.isoformat() if trade.filled_at else None,
        strategy_name=strategy_name,
        symbol=symbol,
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
    request: Request,
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

    # Re-fetch with strategy_code eagerly loaded
    result = await session.execute(
        select(StrategyDeployment)
        .options(selectinload(StrategyDeployment.strategy_code))
        .where(StrategyDeployment.id == deployment.id)
    )
    deployment = result.scalar_one()

    # Enqueue for strategy-runner
    redis = request.app.state.redis
    if body.mode == "backtest":
        await redis.lpush(
            "strategy-runner:queue",
            json.dumps({"deployment_id": str(deployment.id), "type": "backtest"}),
        )
    elif body.mode in ("paper", "live"):
        await redis.publish(
            "strategy-runner:deployments",
            json.dumps({
                "action": "register",
                "deployment_id": str(deployment.id),
                "cron_expression": body.cron_expression or "*/5 * * * *",
            }),
        )

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
        .options(selectinload(StrategyDeployment.strategy_code))
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
    query = (
        select(StrategyDeployment)
        .options(selectinload(StrategyDeployment.strategy_code))
        .where(StrategyDeployment.tenant_id == tenant_id)
    )
    if status_filter:
        query = query.where(StrategyDeployment.status == status_filter)
    query = query.order_by(StrategyDeployment.created_at.desc())
    result = await session.execute(query)
    deployments = result.scalars().all()
    return [_deployment_to_response(d) for d in deployments]


# ---------------------------------------------------------------------------
# Recent trades (cross-deployment) — MUST be before /{deployment_id} routes
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/deployments/recent-trades",
    response_model=RecentTradesResponse,
)
async def get_recent_trades(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    count_result = await session.execute(
        select(func.count()).where(DeploymentTrade.tenant_id == tenant_id)
    )
    total = count_result.scalar() or 0

    result = await session.execute(
        select(DeploymentTrade)
        .where(DeploymentTrade.tenant_id == tenant_id)
        .order_by(DeploymentTrade.created_at.desc())
        .limit(limit)
    )
    trades = result.scalars().all()

    # Batch-load deployment info for strategy names
    dep_ids = {t.deployment_id for t in trades}
    if dep_ids:
        dep_result = await session.execute(
            select(StrategyDeployment)
            .where(StrategyDeployment.id.in_(dep_ids))
            .options(selectinload(StrategyDeployment.strategy_code))
        )
        deps = {d.id: d for d in dep_result.scalars().all()}
    else:
        deps = {}

    trade_responses = []
    for t in trades:
        dep = deps.get(t.deployment_id)
        name = dep.strategy_code.name if dep and dep.strategy_code else ""
        symbol = dep.symbol if dep else ""
        trade_responses.append(_trade_to_response(t, name, symbol))

    return RecentTradesResponse(trades=trade_responses, total=total)


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
        select(StrategyDeployment)
        .options(selectinload(StrategyDeployment.strategy_code))
        .where(
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
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment)
        .options(selectinload(StrategyDeployment.strategy_code))
        .where(
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

    redis = request.app.state.redis
    await redis.publish(
        "strategy-runner:deployments",
        json.dumps({"action": "unregister", "deployment_id": str(deployment_id)}),
    )

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
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment)
        .options(selectinload(StrategyDeployment.strategy_code))
        .where(
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

    redis = request.app.state.redis
    await redis.publish(
        "strategy-runner:deployments",
        json.dumps({
            "action": "register",
            "deployment_id": str(deployment_id),
            "cron_expression": deployment.cron_expression or "*/5 * * * *",
        }),
    )

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
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment)
        .options(selectinload(StrategyDeployment.strategy_code))
        .where(
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

    redis = request.app.state.redis
    await redis.publish(
        "strategy-runner:deployments",
        json.dumps({"action": "unregister", "deployment_id": str(deployment_id)}),
    )

    return _deployment_to_response(deployment)


# ---------------------------------------------------------------------------
# Stop all active deployments
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/deployments/stop-all",
    response_model=list[DeploymentResponse],
)
async def stop_all_deployments(
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment)
        .options(selectinload(StrategyDeployment.strategy_code))
        .where(
            StrategyDeployment.tenant_id == tenant_id,
            StrategyDeployment.status.in_(["pending", "running", "paused"]),
        )
    )
    deployments = result.scalars().all()
    now = datetime.now(UTC)
    stopped_ids = []
    for dep in deployments:
        dep.status = "stopped"
        dep.stopped_at = now
        stopped_ids.append(str(dep.id))
    await session.commit()

    redis = request.app.state.redis
    for d_id in stopped_ids:
        await redis.publish(
            "strategy-runner:deployments",
            json.dumps({"action": "unregister", "deployment_id": d_id}),
        )

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
        select(StrategyDeployment)
        .options(selectinload(StrategyDeployment.strategy_code))
        .where(
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

    # Re-fetch with strategy_code eagerly loaded
    result = await session.execute(
        select(StrategyDeployment)
        .options(selectinload(StrategyDeployment.strategy_code))
        .where(StrategyDeployment.id == new_deployment.id)
    )
    new_deployment = result.scalar_one()

    return _deployment_to_response(new_deployment)


# ---------------------------------------------------------------------------
# Get deployment trades (paginated)
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/deployments/{deployment_id}/trades",
    response_model=TradesResponse,
)
async def get_deployment_trades(
    deployment_id: uuid.UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    is_manual: bool | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment)
        .where(StrategyDeployment.id == deployment_id, StrategyDeployment.tenant_id == tenant_id)
        .options(selectinload(StrategyDeployment.strategy_code))
    )
    dep = result.scalar_one_or_none()
    if not dep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

    query = select(DeploymentTrade).where(
        DeploymentTrade.deployment_id == deployment_id,
        DeploymentTrade.tenant_id == tenant_id,
    )
    if is_manual is not None:
        query = query.where(DeploymentTrade.is_manual == is_manual)

    count_result = await session.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    result = await session.execute(
        query.order_by(DeploymentTrade.created_at.desc()).offset(offset).limit(limit)
    )
    trades = result.scalars().all()

    strategy_name = dep.strategy_code.name if dep.strategy_code else ""
    return TradesResponse(
        trades=[_trade_to_response(t, strategy_name, dep.symbol) for t in trades],
        total=total, offset=offset, limit=limit,
    )


# ---------------------------------------------------------------------------
# Get deployment position
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/deployments/{deployment_id}/position",
    response_model=PositionResponse,
)
async def get_deployment_position(
    deployment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment).where(
            StrategyDeployment.id == deployment_id, StrategyDeployment.tenant_id == tenant_id
        )
    )
    dep = result.scalar_one_or_none()
    if not dep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

    state = await session.get(DeploymentState, deployment_id)

    pnl_result = await session.execute(
        select(func.coalesce(func.sum(DeploymentTrade.realized_pnl), 0)).where(
            DeploymentTrade.deployment_id == deployment_id,
            DeploymentTrade.tenant_id == tenant_id,
            DeploymentTrade.realized_pnl.isnot(None),
        )
    )
    total_realized_pnl = float(pnl_result.scalar() or 0)

    open_orders = state.open_orders if state and state.open_orders else []
    return PositionResponse(
        deployment_id=str(deployment_id),
        position=state.position if state else None,
        portfolio=state.portfolio if state else {},
        open_orders=open_orders,
        open_orders_count=len(open_orders),
        total_realized_pnl=total_realized_pnl,
    )


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
