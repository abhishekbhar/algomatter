import logging
from datetime import datetime
from decimal import Decimal

import pandas as pd
import yfinance
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HistoricalOHLCV
from app.historical.binance import fetch_binance_klines

logger = logging.getLogger(__name__)


async def get_ohlcv(
    session: AsyncSession,
    symbol: str,
    exchange: str,
    interval: str,
    start: datetime,
    end: datetime,
) -> list[HistoricalOHLCV]:
    """Query historical_ohlcv table for a date range."""
    stmt = (
        select(HistoricalOHLCV)
        .where(
            HistoricalOHLCV.symbol == symbol,
            HistoricalOHLCV.exchange == exchange,
            HistoricalOHLCV.interval == interval,
            HistoricalOHLCV.timestamp >= start,
            HistoricalOHLCV.timestamp <= end,
        )
        .order_by(HistoricalOHLCV.timestamp)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_latest_price(
    session: AsyncSession,
    symbol: str,
    exchange: str,
) -> Decimal:
    """Return the most recent close price for a symbol."""
    stmt = (
        select(HistoricalOHLCV.close)
        .where(
            HistoricalOHLCV.symbol == symbol,
            HistoricalOHLCV.exchange == exchange,
        )
        .order_by(HistoricalOHLCV.timestamp.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    price = result.scalar_one()
    return Decimal(str(price))


def yfinance_download(
    symbol: str,
    start: datetime,
    end: datetime,
    interval: str = "1d",
) -> pd.DataFrame:
    """Thin wrapper around yfinance.download() for easy mocking."""
    return yfinance.download(symbol, start=start, end=end, interval=interval)


def _yf_symbol(symbol: str, exchange: str) -> str:
    """Convert symbol + exchange to yfinance ticker format."""
    if exchange.upper() in ("NSE", "BSE"):
        suffix = ".NS" if exchange.upper() == "NSE" else ".BO"
        return f"{symbol}{suffix}"
    return symbol


async def fetch_and_cache_ohlcv(
    session: AsyncSession,
    symbol: str,
    exchange: str,
    interval: str,
    start: datetime,
    end: datetime,
) -> list[HistoricalOHLCV]:
    """Fetch OHLCV data from yfinance and upsert into DB."""
    yf_ticker = _yf_symbol(symbol, exchange)
    df = yfinance_download(yf_ticker, start=start, end=end, interval=interval)

    if df.empty:
        return []

    rows = []
    for ts, row in df.iterrows():
        values = {
            "symbol": symbol,
            "exchange": exchange,
            "interval": interval,
            "timestamp": ts.to_pydatetime(),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row["Volume"]),
        }
        rows.append(values)

    if rows:
        stmt = pg_insert(HistoricalOHLCV).values(rows)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["symbol", "exchange", "interval", "timestamp"]
        )
        await session.execute(stmt)
        await session.commit()

    return await get_ohlcv(session, symbol, exchange, interval, start, end)
