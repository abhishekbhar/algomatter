from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Strategy
from app.db.session import async_session_factory
from app.historical.service import fetch_and_cache_ohlcv


async def daily_data_fetch(ctx: dict) -> None:
    """Fetch daily OHLCV for all symbols that have active strategies.

    Intended to be run as an ARQ background task.
    """
    async with async_session_factory() as session:
        # Query distinct symbols from active strategies
        stmt = (
            select(Strategy.name)
            .where(Strategy.is_active.is_(True))
            .distinct()
        )
        result = await session.execute(stmt)
        strategy_names = result.scalars().all()

        end = datetime.utcnow()
        start = end - timedelta(days=2)

        for name in strategy_names:
            # Each strategy name could encode symbol info;
            # this is a placeholder for real symbol extraction logic.
            try:
                await fetch_and_cache_ohlcv(
                    session,
                    symbol=name,
                    exchange="NSE",
                    interval="1d",
                    start=start,
                    end=end,
                )
            except Exception:
                # Log and continue with the next symbol
                continue
