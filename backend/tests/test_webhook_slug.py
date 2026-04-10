import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.webhooks.slug import generate_slug, ensure_unique_slug


def test_generate_slug_lowercases():
    assert generate_slug("NIFTY Momentum") == "nifty-momentum"


def test_generate_slug_strips_special_chars():
    assert generate_slug("BankNifty Short!") == "banknifty-short"


def test_generate_slug_collapses_hyphens():
    assert generate_slug("NIFTY--Long  Strategy") == "nifty-long-strategy"


def test_generate_slug_strips_leading_trailing_hyphens():
    assert generate_slug("!NIFTY!") == "nifty"


def test_generate_slug_handles_numbers():
    assert generate_slug("Strategy v2") == "strategy-v2"


@pytest.mark.asyncio
async def test_ensure_unique_slug_no_collision():
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result

    import uuid
    slug = await ensure_unique_slug(session, uuid.uuid4(), "nifty-momentum")
    assert slug == "nifty-momentum"


@pytest.mark.asyncio
async def test_ensure_unique_slug_one_collision():
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["nifty-momentum"]
    session.execute.return_value = mock_result

    import uuid
    slug = await ensure_unique_slug(session, uuid.uuid4(), "nifty-momentum")
    assert slug == "nifty-momentum-2"


@pytest.mark.asyncio
async def test_ensure_unique_slug_two_collisions():
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        "nifty-momentum", "nifty-momentum-2"
    ]
    session.execute.return_value = mock_result

    import uuid
    slug = await ensure_unique_slug(session, uuid.uuid4(), "nifty-momentum")
    assert slug == "nifty-momentum-3"
