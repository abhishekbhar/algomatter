import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_tenant_session
from app.db.models import Strategy
from app.strategies.schemas import (
    CreateStrategyRequest,
    StrategyResponse,
    UpdateStrategyRequest,
)

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


@router.post(
    "",
    response_model=StrategyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_strategy(
    body: CreateStrategyRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    strategy = Strategy(
        tenant_id=tenant_id,
        name=body.name,
        broker_connection_id=body.broker_connection_id,
        mode=body.mode,
        mapping_template=body.mapping_template,
        rules=body.rules,
    )
    session.add(strategy)
    await session.commit()
    await session.refresh(strategy)

    return StrategyResponse(
        id=strategy.id,
        name=strategy.name,
        broker_connection_id=strategy.broker_connection_id,
        mode=strategy.mode,
        mapping_template=strategy.mapping_template,
        rules=strategy.rules,
        is_active=strategy.is_active,
        created_at=strategy.created_at,
    )


@router.get("", response_model=list[StrategyResponse])
async def list_strategies(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(Strategy).where(Strategy.tenant_id == tenant_id)
    )
    strategies = result.scalars().all()
    return [
        StrategyResponse(
            id=s.id,
            name=s.name,
            broker_connection_id=s.broker_connection_id,
            mode=s.mode,
            mapping_template=s.mapping_template,
            rules=s.rules,
            is_active=s.is_active,
            created_at=s.created_at,
        )
        for s in strategies
    ]


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.tenant_id == tenant_id,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found",
        )
    return StrategyResponse(
        id=strategy.id,
        name=strategy.name,
        broker_connection_id=strategy.broker_connection_id,
        mode=strategy.mode,
        mapping_template=strategy.mapping_template,
        rules=strategy.rules,
        is_active=strategy.is_active,
        created_at=strategy.created_at,
    )


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: uuid.UUID,
    body: UpdateStrategyRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.tenant_id == tenant_id,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(strategy, field, value)

    await session.commit()
    await session.refresh(strategy)

    return StrategyResponse(
        id=strategy.id,
        name=strategy.name,
        broker_connection_id=strategy.broker_connection_id,
        mode=strategy.mode,
        mapping_template=strategy.mapping_template,
        rules=strategy.rules,
        is_active=strategy.is_active,
        created_at=strategy.created_at,
    )


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    strategy_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.tenant_id == tenant_id,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found",
        )
    await session.delete(strategy)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
