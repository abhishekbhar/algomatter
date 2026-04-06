import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user, get_session, get_tenant_session
from app.brokers.schemas import (
    BrokerBalanceResponse,
    BrokerConnectionResponse,
    BrokerOrderResponse,
    BrokerPositionResponse,
    BrokerStatsResponse,
    CreateBrokerConnectionRequest,
)
from app.crypto.encryption import decrypt_credentials
from app.brokers.factory import get_broker
from app.crypto.encryption import encrypt_credentials
from app.db.models import (
    BrokerConnection,
    DeploymentState,
    DeploymentTrade,
    ExchangeInstrument,
    StrategyDeployment,
)
from app.deployments.schemas import DeploymentTradeResponse, TradesResponse
from app.deployments.router import _trade_to_response

router = APIRouter(prefix="/api/v1/brokers", tags=["brokers"])


class InstrumentResponse(BaseModel):
    symbol: str
    base_asset: str
    quote_asset: str
    product_type: str
    exchange: str


@router.post(
    "",
    response_model=BrokerConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_broker_connection(
    body: CreateBrokerConnectionRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    encrypted = encrypt_credentials(tenant_id, body.credentials)

    conn = BrokerConnection(
        tenant_id=tenant_id,
        broker_type=body.broker_type,
        credentials=encrypted,
        is_active=True,
    )
    session.add(conn)
    await session.commit()
    await session.refresh(conn)

    return BrokerConnectionResponse(
        id=conn.id,
        broker_type=conn.broker_type,
        is_active=conn.is_active,
        connected_at=conn.connected_at,
    )


@router.get("", response_model=list[BrokerConnectionResponse])
async def list_broker_connections(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(BrokerConnection).where(BrokerConnection.tenant_id == tenant_id)
    )
    connections = result.scalars().all()
    return [
        BrokerConnectionResponse(
            id=c.id,
            broker_type=c.broker_type,
            is_active=c.is_active,
            connected_at=c.connected_at,
        )
        for c in connections
    ]


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_broker_connection(
    connection_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(BrokerConnection).where(
            BrokerConnection.id == connection_id,
            BrokerConnection.tenant_id == tenant_id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker connection not found",
        )
    await session.delete(conn)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/instruments", response_model=list[InstrumentResponse])
async def list_instruments(
    exchange: str,
    product_type: str | None = None,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    query = select(ExchangeInstrument).where(
        ExchangeInstrument.exchange == exchange.upper(),
        ExchangeInstrument.is_active.is_(True),
    )
    if product_type:
        query = query.where(ExchangeInstrument.product_type == product_type.upper())
    result = await session.execute(query.order_by(ExchangeInstrument.base_asset))
    instruments = result.scalars().all()
    return [
        InstrumentResponse(
            symbol=i.symbol,
            base_asset=i.base_asset,
            quote_asset=i.quote_asset,
            product_type=i.product_type,
            exchange=i.exchange,
        )
        for i in instruments
    ]


@router.get("/market/klines")
async def proxy_binance_klines(
    symbol: str,
    interval: str = "15m",
    limit: int = 500,
    current_user: dict = Depends(get_current_user),
):
    """Proxy Binance klines API to avoid geo-blocking in the browser."""
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": min(limit, 1000)}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Binance API error")
        return resp.json()


def _get_broker_or_404(connection_id, tenant_id):
    """Returns a select() for the broker — call scalar_one_or_none() and raise 404 if None."""
    return (
        select(BrokerConnection)
        .where(
            BrokerConnection.id == connection_id,
            BrokerConnection.tenant_id == tenant_id,
        )
    )


@router.get("/{broker_connection_id}/balance", response_model=BrokerBalanceResponse)
async def get_broker_balance(
    broker_connection_id: uuid.UUID,
    product_type: str | None = None,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    conn = await session.scalar(_get_broker_or_404(broker_connection_id, tenant_id))
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker connection not found",
        )

    credentials = decrypt_credentials(conn.tenant_id, conn.credentials)
    broker = await get_broker(conn.broker_type, credentials)
    try:
        balance = await broker.get_balance(product_type=product_type)
        return BrokerBalanceResponse(
            available=float(balance.available),
            total=float(balance.total),
        )
    finally:
        await broker.close()


@router.get("/{broker_connection_id}/quote")
async def get_broker_quote(
    broker_connection_id: uuid.UUID,
    symbol: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Get a price quote for a symbol from the broker's own market data."""
    tenant_id = uuid.UUID(current_user["user_id"])
    conn = await session.scalar(_get_broker_or_404(broker_connection_id, tenant_id))
    if not conn:
        raise HTTPException(status_code=404, detail="Broker connection not found")

    credentials = decrypt_credentials(conn.tenant_id, conn.credentials)
    broker = await get_broker(conn.broker_type, credentials)
    try:
        quotes = await broker.get_quotes([symbol])
        if not quotes:
            raise HTTPException(status_code=404, detail="No quote available")
        q = quotes[0]
        return {
            "symbol": q.symbol,
            "last_price": float(q.last_price),
            "bid": float(q.bid) if q.bid else None,
            "ask": float(q.ask) if q.ask else None,
        }
    finally:
        await broker.close()


@router.get("/{connection_id}/stats", response_model=BrokerStatsResponse)
async def get_broker_stats(
    connection_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    conn = await session.scalar(_get_broker_or_404(connection_id, tenant_id))
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker connection not found")

    # Active deployments
    active = await session.scalar(
        select(func.count(StrategyDeployment.id)).where(
            StrategyDeployment.broker_connection_id == connection_id,
            StrategyDeployment.tenant_id == tenant_id,
            StrategyDeployment.mode == "live",
            StrategyDeployment.status == "running",
        )
    ) or 0

    # Deployment IDs for this broker
    dep_id_rows = await session.execute(
        select(StrategyDeployment.id).where(
            StrategyDeployment.broker_connection_id == connection_id,
            StrategyDeployment.tenant_id == tenant_id,
        )
    )
    dep_ids = [r[0] for r in dep_id_rows.all()]

    if not dep_ids:
        return BrokerStatsResponse(active_deployments=active, total_realized_pnl=0.0, win_rate=0.0, total_trades=0)

    # Trade stats — only filled trades
    trades_result = await session.execute(
        select(DeploymentTrade.realized_pnl).where(
            DeploymentTrade.deployment_id.in_(dep_ids),
            DeploymentTrade.status == "filled",
        )
    )
    pnl_values = [float(row[0]) for row in trades_result.all() if row[0] is not None]
    total_trades_result = await session.scalar(
        select(func.count(DeploymentTrade.id)).where(
            DeploymentTrade.deployment_id.in_(dep_ids),
            DeploymentTrade.status == "filled",
        )
    ) or 0

    total_pnl = sum(pnl_values)
    winning = sum(1 for p in pnl_values if p > 0)
    win_rate = (winning / len(pnl_values)) if pnl_values else 0.0

    return BrokerStatsResponse(
        active_deployments=active,
        total_realized_pnl=round(total_pnl, 4),
        win_rate=round(win_rate, 4),
        total_trades=total_trades_result,
    )


@router.get("/{connection_id}/positions", response_model=list[BrokerPositionResponse])
async def get_broker_positions(
    connection_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    conn = await session.scalar(_get_broker_or_404(connection_id, tenant_id))
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker connection not found")

    deps_result = await session.execute(
        select(StrategyDeployment)
        .where(
            StrategyDeployment.broker_connection_id == connection_id,
            StrategyDeployment.tenant_id == tenant_id,
            StrategyDeployment.mode == "live",
            StrategyDeployment.status == "running",
        )
        .options(
            selectinload(StrategyDeployment.strategy_code),
            selectinload(StrategyDeployment.state),
        )
    )
    deps = deps_result.scalars().all()

    positions = []
    for dep in deps:
        if dep.state is None or dep.state.position is None:
            continue
        pos = dep.state.position
        qty = float(pos.get("quantity", 0))
        if qty == 0:
            continue
        positions.append(
            BrokerPositionResponse(
                deployment_id=str(dep.id),
                deployment_name=dep.strategy_code.name if dep.strategy_code else "",
                symbol=dep.symbol,
                side="LONG" if qty > 0 else "SHORT",
                quantity=abs(qty),
                avg_entry_price=float(pos.get("avg_entry_price", 0)),
                unrealized_pnl=float(pos.get("unrealized_pnl", 0)),
            )
        )
    return positions


@router.get("/{connection_id}/orders", response_model=list[BrokerOrderResponse])
async def get_broker_orders(
    connection_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    conn = await session.scalar(_get_broker_or_404(connection_id, tenant_id))
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker connection not found")

    deps_result = await session.execute(
        select(StrategyDeployment)
        .where(
            StrategyDeployment.broker_connection_id == connection_id,
            StrategyDeployment.tenant_id == tenant_id,
            StrategyDeployment.mode == "live",
            StrategyDeployment.status == "running",
        )
        .options(
            selectinload(StrategyDeployment.strategy_code),
            selectinload(StrategyDeployment.state),
        )
    )
    deps = deps_result.scalars().all()

    orders = []
    for dep in deps:
        if dep.state is None:
            continue
        dep_name = dep.strategy_code.name if dep.strategy_code else ""
        for order in (dep.state.open_orders or []):
            orders.append(
                BrokerOrderResponse(
                    order_id=str(order.get("id", "")),
                    deployment_id=str(dep.id),
                    deployment_name=dep_name,
                    symbol=dep.symbol,
                    action=str(order.get("action", "")),
                    quantity=float(order.get("quantity", 0)),
                    order_type=str(order.get("order_type", "MARKET")),
                    price=float(order["price"]) if order.get("price") is not None else None,
                    created_at=order.get("created_at"),
                )
            )
    return orders


@router.get("/{connection_id}/trades", response_model=TradesResponse)
async def get_broker_trades(
    connection_id: uuid.UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    conn = await session.scalar(_get_broker_or_404(connection_id, tenant_id))
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker connection not found")

    dep_id_rows = await session.execute(
        select(StrategyDeployment.id).where(
            StrategyDeployment.broker_connection_id == connection_id,
            StrategyDeployment.tenant_id == tenant_id,
        )
    )
    dep_ids = [r[0] for r in dep_id_rows.all()]

    if not dep_ids:
        return TradesResponse(trades=[], total=0, offset=offset, limit=limit)

    base_q = select(DeploymentTrade).where(DeploymentTrade.deployment_id.in_(dep_ids))
    total = await session.scalar(select(func.count()).select_from(base_q.subquery())) or 0

    trades_result = await session.execute(
        base_q
        .order_by(DeploymentTrade.created_at.desc())
        .offset(offset)
        .limit(limit)
        .options(
            selectinload(DeploymentTrade.deployment).selectinload(StrategyDeployment.strategy_code)
        )
    )
    trades = trades_result.scalars().all()

    return TradesResponse(
        trades=[
            _trade_to_response(
                t,
                t.deployment.strategy_code.name if t.deployment and t.deployment.strategy_code else "",
                t.deployment.symbol if t.deployment else "",
            )
            for t in trades
        ],
        total=total,
        offset=offset,
        limit=limit,
    )
