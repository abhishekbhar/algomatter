"""API endpoints for historical OHLCV data — query, coverage, and CSV export."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_tenant_session
from app.db.models import HistoricalOHLCV

router = APIRouter(prefix="/api/v1/historical", tags=["historical"])


@router.get("/coverage")
async def get_coverage(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    """List all cached symbol/interval combinations with row counts and date ranges."""
    stmt = (
        select(
            HistoricalOHLCV.symbol,
            HistoricalOHLCV.exchange,
            HistoricalOHLCV.interval,
            func.count().label("candles"),
            func.min(HistoricalOHLCV.timestamp).label("earliest"),
            func.max(HistoricalOHLCV.timestamp).label("latest"),
        )
        .group_by(
            HistoricalOHLCV.symbol,
            HistoricalOHLCV.exchange,
            HistoricalOHLCV.interval,
        )
        .order_by(HistoricalOHLCV.symbol, HistoricalOHLCV.interval)
    )
    result = await session.execute(stmt)
    rows = result.all()
    return [
        {
            "symbol": r.symbol,
            "exchange": r.exchange,
            "interval": r.interval,
            "candles": r.candles,
            "earliest": r.earliest.isoformat() if r.earliest else None,
            "latest": r.latest.isoformat() if r.latest else None,
        }
        for r in rows
    ]


@router.get("/ohlcv")
async def get_ohlcv(
    symbol: str = Query(..., description="e.g. BTCUSDT"),
    interval: str = Query(..., description="e.g. 1m, 5m, 1h, 1d"),
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
    exchange: str = Query("BINANCE"),
    limit: int = Query(1000, le=10000),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Query cached OHLCV candles as JSON (paginated)."""
    start_dt = _parse(start)
    end_dt = _parse(end)
    stmt = (
        select(HistoricalOHLCV)
        .where(
            HistoricalOHLCV.symbol == symbol.upper(),
            HistoricalOHLCV.exchange == exchange.upper(),
            HistoricalOHLCV.interval == interval,
            HistoricalOHLCV.timestamp >= start_dt,
            HistoricalOHLCV.timestamp <= end_dt,
        )
        .order_by(HistoricalOHLCV.timestamp)
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "timestamp": r.timestamp.isoformat(),
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": float(r.volume),
        }
        for r in rows
    ]


@router.get("/export")
async def export_csv(
    symbol: str = Query(..., description="e.g. BTCUSDT"),
    interval: str = Query(..., description="e.g. 1m, 5m, 1h, 1d"),
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
    exchange: str = Query("BINANCE"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Export cached OHLCV candles as a downloadable CSV file."""
    start_dt = _parse(start)
    end_dt = _parse(end)
    stmt = (
        select(HistoricalOHLCV)
        .where(
            HistoricalOHLCV.symbol == symbol.upper(),
            HistoricalOHLCV.exchange == exchange.upper(),
            HistoricalOHLCV.interval == interval,
            HistoricalOHLCV.timestamp >= start_dt,
            HistoricalOHLCV.timestamp <= end_dt,
        )
        .order_by(HistoricalOHLCV.timestamp)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
    for r in rows:
        writer.writerow([
            r.timestamp.isoformat(),
            float(r.open),
            float(r.high),
            float(r.low),
            float(r.close),
            float(r.volume),
        ])

    buf.seek(0)
    filename = f"{symbol}_{exchange}_{interval}_{start}_{end}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _parse(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
