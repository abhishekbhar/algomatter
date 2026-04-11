# backend/tests/test_webhook_processor.py
import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock

from app.webhooks.processor import (
    get_strategy_counts,
    increment_signals_today,
    update_position_count,
    get_dual_leg_state,
    set_dual_leg_position,
    clear_dual_leg_position,
    increment_dual_leg_trade_count,
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

    expected_key = f"wh:signals:strat-123:{datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%Y-%m-%d')}"
    redis.incr.assert_called_once_with(expected_key)
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


@pytest.mark.asyncio
async def test_update_position_count_buy_lowercase_increments():
    redis = AsyncMock()
    await update_position_count(redis, "strat-123", action="buy")
    redis.incr.assert_called_once_with("wh:positions:strat-123")


@pytest.mark.asyncio
async def test_increment_signals_today_redis_failure_does_not_raise():
    redis = AsyncMock()
    redis.incr.side_effect = Exception("Redis down")
    # Should not raise
    await increment_signals_today(redis, "strat-123")


@pytest.mark.asyncio
async def test_get_dual_leg_state_returns_defaults_when_missing():
    redis = AsyncMock()
    redis.mget.return_value = [None, None]
    side, count = await get_dual_leg_state(redis, "strat-1")
    assert side == ""
    assert count == 0


@pytest.mark.asyncio
async def test_get_dual_leg_state_returns_stored_values():
    redis = AsyncMock()
    redis.mget.return_value = [b"long", b"3"]
    side, count = await get_dual_leg_state(redis, "strat-1")
    assert side == "long"
    assert count == 3


@pytest.mark.asyncio
async def test_get_dual_leg_state_returns_defaults_on_redis_error():
    redis = AsyncMock()
    redis.mget.side_effect = Exception("redis down")
    side, count = await get_dual_leg_state(redis, "strat-1")
    assert side == ""
    assert count == 0


@pytest.mark.asyncio
async def test_set_dual_leg_position_sets_key_with_ttl():
    redis = AsyncMock()
    await set_dual_leg_position(redis, "strat-1", "long")
    redis.set.assert_called_once()
    args, kwargs = redis.set.call_args
    assert args[0] == "dual_leg:strat-1:position_side"
    assert args[1] == "long"
    assert "ex" in kwargs


@pytest.mark.asyncio
async def test_clear_dual_leg_position_sets_empty_string():
    redis = AsyncMock()
    await clear_dual_leg_position(redis, "strat-1")
    redis.set.assert_called_once()
    args, kwargs = redis.set.call_args
    assert args[0] == "dual_leg:strat-1:position_side"
    assert args[1] == ""


@pytest.mark.asyncio
async def test_increment_dual_leg_trade_count_increments_with_ttl():
    redis = AsyncMock()
    await increment_dual_leg_trade_count(redis, "strat-1")
    redis.incr.assert_called_once_with("dual_leg:strat-1:trade_count")
    redis.expireat.assert_called_once()
