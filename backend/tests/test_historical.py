import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import patch


@pytest.mark.asyncio
async def test_get_ohlcv_returns_cached_data(db_session):
    """Data already in DB is returned without external fetch."""
    from app.historical.service import get_ohlcv
    from app.db.models import HistoricalOHLCV

    row = HistoricalOHLCV(
        symbol="RELIANCE",
        exchange="NSE",
        interval="1d",
        timestamp=datetime(2025, 1, 2),
        open=Decimal("2500"),
        high=Decimal("2550"),
        low=Decimal("2480"),
        close=Decimal("2530"),
        volume=Decimal("1000000"),
    )
    db_session.add(row)
    await db_session.commit()

    result = await get_ohlcv(
        db_session, "RELIANCE", "NSE", "1d",
        datetime(2025, 1, 1), datetime(2025, 1, 3),
    )
    assert len(result) == 1
    assert result[0].close == Decimal("2530")


@pytest.mark.asyncio
async def test_get_latest_price(db_session):
    from app.historical.service import get_latest_price
    from app.db.models import HistoricalOHLCV

    for i, price in enumerate([2500, 2530, 2510]):
        db_session.add(
            HistoricalOHLCV(
                symbol="TCS",
                exchange="NSE",
                interval="1d",
                timestamp=datetime(2025, 1, i + 1),
                open=Decimal(str(price)),
                high=Decimal(str(price + 50)),
                low=Decimal(str(price - 20)),
                close=Decimal(str(price)),
                volume=Decimal("500000"),
            )
        )
    await db_session.commit()

    price = await get_latest_price(db_session, "TCS", "NSE")
    assert price == Decimal("2510")  # most recent


@pytest.mark.asyncio
async def test_fetch_and_cache_calls_yfinance_for_nse(db_session):
    """Verify yfinance is called when data is missing."""
    from app.historical.service import fetch_and_cache_ohlcv
    import pandas as pd

    mock_df = pd.DataFrame(
        {
            "Open": [2500.0],
            "High": [2550.0],
            "Low": [2480.0],
            "Close": [2530.0],
            "Volume": [1000000],
        },
        index=pd.DatetimeIndex([datetime(2025, 1, 2)]),
    )

    with patch("app.historical.service.yfinance_download", return_value=mock_df):
        result = await fetch_and_cache_ohlcv(
            db_session,
            "RELIANCE",
            "NSE",
            "1d",
            datetime(2025, 1, 1),
            datetime(2025, 1, 3),
        )

    assert len(result) >= 1
    assert result[0].symbol == "RELIANCE"
