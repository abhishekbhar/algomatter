"""Analytics API router.

Endpoints:
    GET /api/v1/analytics/overview                       Portfolio overview
    GET /api/v1/analytics/strategies/{id}/metrics        Strategy metrics
    GET /api/v1/analytics/strategies/{id}/equity-curve   Equity curve
    GET /api/v1/analytics/strategies/{id}/trades         Trade log (JSON or CSV)
"""

from __future__ import annotations

import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.service import (
    get_equity_curve,
    get_overview,
    get_strategy_metrics,
    get_trades,
)
from app.auth.deps import get_current_user, get_tenant_session

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/overview")
async def overview(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    return await get_overview(session, tenant_id)


@router.get("/strategies/{strategy_id}/metrics")
async def strategy_metrics(
    strategy_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    metrics = await get_strategy_metrics(session, strategy_id, tenant_id)
    if metrics is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No metrics found for this strategy",
        )
    return metrics


@router.get("/strategies/{strategy_id}/equity-curve")
async def equity_curve(
    strategy_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    return await get_equity_curve(session, strategy_id, tenant_id)


@router.get("/strategies/{strategy_id}/trades")
async def trades(
    strategy_id: uuid.UUID,
    format: str = Query(default="json"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    trade_list = await get_trades(session, strategy_id, tenant_id)

    if format == "csv":
        return _trades_to_csv_response(trade_list)

    return trade_list


def _trades_to_csv_response(trade_list: list[dict]) -> StreamingResponse:
    """Convert trade list to a streaming CSV response."""
    output = io.StringIO()
    if trade_list:
        writer = csv.DictWriter(output, fieldnames=trade_list[0].keys())
        writer.writeheader()
        writer.writerows(trade_list)
    else:
        output.write("")

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trades.csv"},
    )
