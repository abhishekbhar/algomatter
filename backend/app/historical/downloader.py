"""Standalone CLI client to download Binance historical candles into the DB.

Usage (inside container or with DB access):
    # Download BTCUSDT daily candles for 2024
    python -m app.historical.downloader BTCUSDT 1d 2024-01-01 2024-12-31

    # Download multiple symbols
    python -m app.historical.downloader ETHUSDT,BTCUSDT 1h 2025-01-01 2025-06-01

    # Defaults to BINANCE exchange; override with --exchange
    python -m app.historical.downloader BTCUSDT 1d 2024-01-01 2024-12-31 --exchange BINANCE

The downloader fetches from Binance public klines API (no auth) and upserts
into the historical_ohlcv table. Subsequent runs for the same range are
idempotent — existing rows are skipped via ON CONFLICT DO NOTHING.

Can also be called programmatically:
    from app.historical.downloader import download_candles
    count = await download_candles("BTCUSDT", "1d", start, end)
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import HistoricalOHLCV
from app.db.session import async_session_factory
from app.historical.binance import fetch_binance_klines

logger = logging.getLogger(__name__)


async def download_candles(
    symbol: str,
    interval: str,
    start: datetime,
    end: datetime,
    exchange: str = "BINANCE",
) -> int:
    """Fetch candles from Binance and store in DB. Returns number of rows inserted.

    This is the core function — used by both the CLI and the backtest runner.
    """
    logger.info(f"Downloading {symbol} {interval} from {start.date()} to {end.date()}")

    candles = await fetch_binance_klines(symbol, interval, start, end)
    if not candles:
        logger.warning(f"No candles returned for {symbol} {interval}")
        return 0

    rows = [
        {
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "interval": interval,
            "timestamp": c["timestamp"],
            "open": c["open"],
            "high": c["high"],
            "low": c["low"],
            "close": c["close"],
            "volume": c["volume"],
        }
        for c in candles
    ]

    # Batch inserts to stay under PostgreSQL's 32767 parameter limit.
    # Each row has 9 columns, so ~3000 rows per batch is safe.
    BATCH_SIZE = 3000
    inserted = 0

    async with async_session_factory() as session:
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            stmt = pg_insert(HistoricalOHLCV).values(batch)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["symbol", "exchange", "interval", "timestamp"]
            )
            result = await session.execute(stmt)
            inserted += result.rowcount
        await session.commit()
        logger.info(f"Stored {inserted} new candles ({len(rows)} fetched, {len(rows) - inserted} already cached)")
        return inserted


async def check_coverage(
    symbol: str,
    exchange: str,
    interval: str,
    start: datetime,
    end: datetime,
) -> int:
    """Return the number of cached candles in the given range."""
    async with async_session_factory() as session:
        stmt = (
            select(func.count())
            .select_from(HistoricalOHLCV)
            .where(
                HistoricalOHLCV.symbol == symbol.upper(),
                HistoricalOHLCV.exchange == exchange.upper(),
                HistoricalOHLCV.interval == interval,
                HistoricalOHLCV.timestamp >= start,
                HistoricalOHLCV.timestamp <= end,
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one()


async def ensure_candles(
    symbol: str,
    interval: str,
    start: datetime,
    end: datetime,
    exchange: str = "BINANCE",
) -> list[dict]:
    """Return candles for the range, downloading from Binance if not cached.

    This is what the backtest runner calls. It:
    1. Checks DB for existing data
    2. Downloads from Binance if insufficient
    3. Returns candles as list[dict] ready for the Nautilus engine
    """
    cached = await check_coverage(symbol, exchange, interval, start, end)

    if cached == 0:
        logger.info(f"No cached data for {symbol} {interval}, downloading...")
        await download_candles(symbol, interval, start, end, exchange)
    else:
        logger.info(f"Found {cached} cached candles for {symbol} {interval}")

    # Read from DB (authoritative, ordered)
    async with async_session_factory() as session:
        stmt = (
            select(HistoricalOHLCV)
            .where(
                HistoricalOHLCV.symbol == symbol.upper(),
                HistoricalOHLCV.exchange == exchange.upper(),
                HistoricalOHLCV.interval == interval,
                HistoricalOHLCV.timestamp >= start,
                HistoricalOHLCV.timestamp <= end,
            )
            .order_by(HistoricalOHLCV.timestamp)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

    candles = [
        {
            "timestamp": row.timestamp,
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume),
        }
        for row in rows
    ]
    logger.info(f"Returning {len(candles)} candles for {symbol} {interval}")
    return candles


def _parse_date(s: str) -> datetime:
    """Parse YYYY-MM-DD string to timezone-aware datetime."""
    dt = datetime.strptime(s, "%Y-%m-%d")
    return dt.replace(tzinfo=timezone.utc)


async def _main(args: argparse.Namespace) -> None:
    symbols = [s.strip().upper() for s in args.symbols.split(",")]
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    exchange = args.exchange.upper()

    total = 0
    for symbol in symbols:
        count = await download_candles(symbol, args.interval, start, end, exchange)
        total += count
        cached = await check_coverage(symbol, exchange, args.interval, start, end)
        print(f"  {symbol}: {cached} candles in DB for {args.interval} ({count} newly inserted)")

    print(f"\nDone. {total} new candles inserted across {len(symbols)} symbol(s).")


async def _export(args: argparse.Namespace) -> None:
    """Export cached candles to CSV."""
    import csv as _csv

    symbol = args.symbol.strip().upper()
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    exchange = args.exchange.upper()

    async with async_session_factory() as session:
        stmt = (
            select(HistoricalOHLCV)
            .where(
                HistoricalOHLCV.symbol == symbol,
                HistoricalOHLCV.exchange == exchange,
                HistoricalOHLCV.interval == args.interval,
                HistoricalOHLCV.timestamp >= start,
                HistoricalOHLCV.timestamp <= end,
            )
            .order_by(HistoricalOHLCV.timestamp)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

    if not rows:
        print(f"No data found for {symbol} {args.interval} [{args.start} → {args.end}]")
        return

    output = args.output or f"{symbol}_{args.interval}_{args.start}_{args.end}.csv"
    with open(output, "w", newline="") as f:
        writer = _csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for r in rows:
            writer.writerow([
                r.timestamp.isoformat(),
                float(r.open), float(r.high), float(r.low),
                float(r.close), float(r.volume),
            ])

    print(f"Exported {len(rows)} candles to {output}")


def cli() -> None:
    parser = argparse.ArgumentParser(
        description="Download / export Binance historical candles.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m app.historical.downloader download BTCUSDT 1d 2024-01-01 2024-12-31\n"
            "  python -m app.historical.downloader download ETHUSDT,BTCUSDT 1h 2025-01-01 2025-06-01\n"
            "  python -m app.historical.downloader export BTCUSDT 1m 2024-01-01 2026-01-01\n"
            "  python -m app.historical.downloader export BTCUSDT 1m 2024-01-01 2026-01-01 -o data.csv\n"
        ),
    )
    sub = parser.add_subparsers(dest="command")

    # download sub-command
    dl = sub.add_parser("download", help="Download candles from Binance into the DB")
    dl.add_argument("symbols", help="Comma-separated symbols (e.g. BTCUSDT,ETHUSDT)")
    dl.add_argument("interval", help="Candle interval (1m, 5m, 15m, 1h, 4h, 1d, etc.)")
    dl.add_argument("start", help="Start date (YYYY-MM-DD)")
    dl.add_argument("end", help="End date (YYYY-MM-DD)")
    dl.add_argument("--exchange", default="BINANCE", help="Exchange name (default: BINANCE)")

    # export sub-command
    ex = sub.add_parser("export", help="Export cached candles to CSV")
    ex.add_argument("symbol", help="Symbol (e.g. BTCUSDT)")
    ex.add_argument("interval", help="Candle interval (1m, 5m, 15m, 1h, 4h, 1d, etc.)")
    ex.add_argument("start", help="Start date (YYYY-MM-DD)")
    ex.add_argument("end", help="End date (YYYY-MM-DD)")
    ex.add_argument("--exchange", default="BINANCE", help="Exchange name (default: BINANCE)")
    ex.add_argument("-o", "--output", help="Output file path (default: {symbol}_{interval}_{start}_{end}.csv)")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if args.command == "download":
        asyncio.run(_main(args))
    elif args.command == "export":
        asyncio.run(_export(args))
    else:
        # Backward compatibility: if no subcommand, treat positional args as download
        parser.print_help()


if __name__ == "__main__":
    cli()
