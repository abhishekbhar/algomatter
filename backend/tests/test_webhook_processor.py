# backend/tests/test_webhook_processor.py
import pytest
from datetime import date
from unittest.mock import AsyncMock

from app.webhooks.processor import (
    get_strategy_counts,
    increment_signals_today,
    update_position_count,
)


@pytest.mark.asyncio
async def test_get_strategy_counts_both_zero_when_keys_missing():
    redis = AsyncMock()
    redis.mget.return_value = [None, None]
    positions, signals = await get_strategy_counts(redis, "strat-123")
    assert positions == 0
    assert signals == 0


@pytest.mark.asyncio
async def test_get_strategy_counts_reads_existing_values():
    redis = AsyncMock()
    redis.mget.return_value = [b"3", b"7"]
    positions, signals = await get_strategy_counts(redis, "strat-123")
    assert positions == 3
    assert signals == 7


@pytest.mark.asyncio
async def test_get_strategy_counts_redis_unavailable_returns_zeros():
    redis = AsyncMock()
    redis.mget.side_effect = Exception("Redis connection failed")
    positions, signals = await get_strategy_counts(redis, "strat-123")
    assert positions == 0
    assert signals == 0


@pytest.mark.asyncio
async def test_increment_signals_today_sets_ttl():
    redis = AsyncMock()
    redis.incr.return_value = 1
    await increment_signals_today(redis, "strat-123")
    redis.incr.assert_called_once()
    redis.expireat.assert_called_once()


@pytest.mark.asyncio
async def test_update_position_count_buy_increments():
    redis = AsyncMock()
    await update_position_count(redis, "strat-123", action="BUY")
    redis.incr.assert_called_once_with("wh:positions:strat-123")


@pytest.mark.asyncio
async def test_update_position_count_sell_decrements_with_floor():
    redis = AsyncMock()
    redis.get.return_value = b"1"
    await update_position_count(redis, "strat-123", action="SELL")
    redis.decr.assert_called_once_with("wh:positions:strat-123")


@pytest.mark.asyncio
async def test_update_position_count_sell_does_not_go_below_zero():
    redis = AsyncMock()
    redis.get.return_value = b"0"
    await update_position_count(redis, "strat-123", action="SELL")
    redis.decr.assert_not_called()
