"""Standalone manual trading API — not tied to any deployment.

Endpoints:
    POST  /api/v1/trades/manual                  Place a manual order
    GET   /api/v1/trades/manual                  List manual trades (paginated)
    POST  /api/v1/trades/manual/{trade_id}/cancel  Cancel an open order
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_tenant_session
from app.brokers.base import OrderRequest
from app.brokers.factory import get_broker
from app.crypto.encryption import decrypt_credentials
from app.db.models import BrokerConnection, ManualTrade
from app.manual_trades.schemas import (
    ManualTradeResponse,
    ManualTradesListResponse,
    PlaceManualTradeRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/trades/manual", tags=["manual-trades"])

ORDER_TYPE_MAP = {
    "market": "MARKET",
    "limit": "LIMIT",
    "stop": "SL-M",
    "stop_limit": "SL",
    "sl-m": "SL-M",
    "sl": "SL",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trade_to_response(trade: ManualTrade) -> ManualTradeResponse:
    return ManualTradeResponse(
        id=str(trade.id),
        broker_connection_id=str(trade.broker_connection_id),
        symbol=trade.symbol,
        exchange=trade.exchange,
        product_type=trade.product_type,
        action=trade.action,
        quantity=trade.quantity,
        order_type=trade.order_type,
        price=trade.price,
        trigger_price=trade.trigger_price,
        leverage=trade.leverage,
        position_model=trade.position_model,
        take_profit=trade.take_profit,
        stop_loss=trade.stop_loss,
        position_side=trade.position_side,
        fill_price=trade.fill_price,
        fill_quantity=trade.fill_quantity,
        status=trade.status,
        broker_order_id=trade.broker_order_id,
        error_message=trade.error_message,
        created_at=trade.created_at.isoformat() if trade.created_at else "",
        updated_at=trade.updated_at.isoformat() if trade.updated_at else "",
        filled_at=trade.filled_at.isoformat() if trade.filled_at else None,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/trades/manual — Place a standalone manual order
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ManualTradeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def place_manual_trade(
    body: PlaceManualTradeRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])

    # Validate action
    action = body.action.upper()
    if action not in ("BUY", "SELL"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="action must be BUY or SELL",
        )

    # Look up broker connection
    bc = await session.get(BrokerConnection, uuid.UUID(body.broker_connection_id))
    if not bc or bc.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker connection not found",
        )

    order_type_mapped = ORDER_TYPE_MAP.get(body.order_type.lower(), "MARKET")

    # LIMIT orders must carry a price — otherwise the broker strips the field
    # and the exchange rejects the order with a cryptic error (e.g. Exchange1
    # returns "9257 null"). Fail loudly at the edge instead.
    if order_type_mapped == "LIMIT" and (body.price is None or body.price <= 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="price is required and must be > 0 for LIMIT orders",
        )

    # Create trade record
    trade = ManualTrade(
        tenant_id=tenant_id,
        broker_connection_id=bc.id,
        symbol=body.symbol,
        exchange=body.exchange,
        product_type=body.product_type,
        action=action,
        quantity=body.quantity,
        order_type=order_type_mapped,
        price=body.price,
        trigger_price=body.trigger_price,
        leverage=body.leverage,
        position_model=body.position_model,
        position_side=body.position_side,
        take_profit=body.take_profit,
        stop_loss=body.stop_loss,
        status="submitted",
    )

    # Build OrderRequest directly (NOT via translate_order — it drops TP/SL)
    order_req = OrderRequest(
        symbol=body.symbol,
        exchange=body.exchange,
        action=action,
        quantity=Decimal(str(body.quantity)),
        order_type=order_type_mapped,
        price=Decimal(str(body.price)) if body.price is not None else Decimal("0"),
        product_type=body.product_type,
        trigger_price=Decimal(str(body.trigger_price)) if body.trigger_price is not None else None,
        leverage=body.leverage,
        position_model=body.position_model,
        take_profit=Decimal(str(body.take_profit)) if body.take_profit is not None else None,
        stop_loss=Decimal(str(body.stop_loss)) if body.stop_loss is not None else None,
        position_side=body.position_side,
    )

    try:
        credentials = decrypt_credentials(bc.tenant_id, bc.credentials)
        broker = await get_broker(bc.broker_type, credentials)
        try:
            broker_result = await broker.place_order(order_req)
            trade.fill_price = float(broker_result.fill_price) if broker_result.fill_price is not None else None
            trade.fill_quantity = float(broker_result.fill_quantity) if broker_result.fill_quantity is not None else None
            trade.broker_order_id = broker_result.order_id
            trade.broker_symbol = body.symbol
            if broker_result.status == "filled":
                trade.status = "filled"
                trade.filled_at = datetime.now(UTC)
            elif broker_result.status == "rejected":
                trade.status = "rejected"
                # Persist the broker's rejection reason so the user can see why
                # the order was rejected — otherwise it's silently dropped.
                trade.error_message = (broker_result.message or "rejected by broker")[:512]
            else:
                trade.status = "open"
        finally:
            await broker.close()
    except Exception as e:
        logger.error(f"Failed to place manual trade: {e}")
        trade.status = "failed"
        trade.error_message = str(e)[:512]

    session.add(trade)
    await session.commit()
    await session.refresh(trade)

    return _trade_to_response(trade)


# ---------------------------------------------------------------------------
# GET /api/v1/trades/manual — List manual trades (paginated, filterable)
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=ManualTradesListResponse,
)
async def list_manual_trades(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    symbol: str | None = Query(None),
    exchange: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
):
    tenant_id = uuid.UUID(current_user["user_id"])

    base_q = select(ManualTrade).where(ManualTrade.tenant_id == tenant_id)
    count_q = select(func.count()).select_from(ManualTrade).where(ManualTrade.tenant_id == tenant_id)

    if symbol:
        base_q = base_q.where(ManualTrade.symbol == symbol)
        count_q = count_q.where(ManualTrade.symbol == symbol)
    if exchange:
        base_q = base_q.where(ManualTrade.exchange == exchange)
        count_q = count_q.where(ManualTrade.exchange == exchange)
    if status_filter:
        base_q = base_q.where(ManualTrade.status == status_filter)
        count_q = count_q.where(ManualTrade.status == status_filter)

    total_result = await session.execute(count_q)
    total = total_result.scalar() or 0

    rows_result = await session.execute(
        base_q.order_by(ManualTrade.created_at.desc()).offset(offset).limit(limit)
    )
    trades = rows_result.scalars().all()

    return ManualTradesListResponse(
        trades=[_trade_to_response(t) for t in trades],
        total=total,
        offset=offset,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/trades/manual/{trade_id}/cancel — Cancel an open order
# ---------------------------------------------------------------------------


@router.post(
    "/{trade_id}/cancel",
    response_model=ManualTradeResponse,
)
async def cancel_manual_trade(
    trade_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])

    result = await session.execute(
        select(ManualTrade).where(
            ManualTrade.id == trade_id,
            ManualTrade.tenant_id == tenant_id,
        )
    )
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trade not found",
        )

    if trade.status not in ("submitted", "open"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel trade with status '{trade.status}'",
        )

    # Cancel at broker if we have a broker_order_id
    if trade.broker_order_id:
        try:
            bc = await session.get(BrokerConnection, trade.broker_connection_id)
            if bc:
                credentials = decrypt_credentials(bc.tenant_id, bc.credentials)
                broker = await get_broker(bc.broker_type, credentials)
                try:
                    # Binance Testnet brokers are ephemeral — the in-memory
                    # order_id → symbol map is empty in a fresh instance, so
                    # reseed it before cancelling. Other brokers (e.g.
                    # Exchange1) don't have this attribute and don't need it.
                    if hasattr(broker, "_order_symbols") and trade.broker_symbol:
                        broker._order_symbols[trade.broker_order_id] = trade.broker_symbol
                    await broker.cancel_order(trade.broker_order_id)
                finally:
                    await broker.close()
        except Exception as e:
            logger.error(f"Failed to cancel order at broker: {e}")
            trade.error_message = f"cancel failed: {e}"[:512]

    trade.status = "cancelled"
    await session.commit()
    await session.refresh(trade)

    return _trade_to_response(trade)
