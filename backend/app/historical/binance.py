"""Fetch historical OHLCV candles from Binance public API (no auth required)."""

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

BINANCE_BASE_URL = "https://api.binance.com"

# Map our interval strings to Binance kline interval params
INTERVAL_MAP = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "6h": "6h",
    "8h": "8h",
    "12h": "12h",
    "1d": "1d",
    "3d": "3d",
    "1w": "1w",
    "1M": "1M",
}


async def fetch_binance_klines(
    symbol: str,
    interval: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Fetch OHLCV candles from Binance public klines API.

    Returns list of dicts with keys: timestamp, open, high, low, close, volume.
    Paginates automatically (1000 candles per request).
    """
    binance_interval = INTERVAL_MAP.get(interval, interval)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    all_candles: list[dict] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        while start_ms < end_ms:
            resp = await client.get(
                f"{BINANCE_BASE_URL}/api/v3/klines",
                params={
                    "symbol": symbol.upper(),
                    "interval": binance_interval,
                    "startTime": start_ms,
                    "endTime": end_ms,
                    "limit": 1000,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            if not data:
                break

            for k in data:
                all_candles.append({
                    "timestamp": datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                })

            if len(data) < 1000:
                break
            # Next page starts after the close time of the last candle
            start_ms = data[-1][6] + 1

    logger.info(
        "binance_klines_fetched",
        extra={
            "symbol": symbol,
            "interval": interval,
            "candles": len(all_candles),
        },
    )
    return all_candles


async def fetch_latest_candles(
    symbol: str,
    interval: str,
    limit: int = 50,
) -> list[dict]:
    """Fetch the most recent candles from Binance (for live/paper tick execution).

    Returns `limit` candles ending at the current time. The last candle
    is the most recent *closed* candle (we drop the still-open candle).
    """
    binance_interval = INTERVAL_MAP.get(interval, interval)

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{BINANCE_BASE_URL}/api/v3/klines",
            params={
                "symbol": symbol.upper(),
                "interval": binance_interval,
                "limit": limit + 1,  # +1 because last candle is still open
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if not data:
        return []

    # Drop the last (still-open) candle
    closed = data[:-1] if len(data) > 1 else data

    candles = []
    for k in closed:
        candles.append({
            "timestamp": datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).isoformat(),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        })

    return candles
