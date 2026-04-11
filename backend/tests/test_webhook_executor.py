# backend/tests/test_webhook_executor.py
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.webhooks.executor import SignalResult, execute
from app.webhooks.schemas import StandardSignal


def _make_strategy(
    strategy_id=None,
    mode="paper",
    mapping_template=None,
    rules=None,
    broker_connection_id=None,
):
    return {
        "id": str(strategy_id or uuid.uuid4()),
        "name": "Test Strategy",
        "mode": mode,
        "mapping_template": mapping_template or {
            "symbol": "$.ticker",
            "exchange": "NSE",
            "action": "$.action",
            "quantity": "$.qty",
            "order_type": "MARKET",
            "product_type": "INTRADAY",
        },
        "rules": rules or {},
        "broker_connection_id": str(broker_connection_id) if broker_connection_id else None,
    }


def _make_payload():
    return {"ticker": "RELIANCE", "action": "BUY", "qty": "10"}


@pytest.mark.asyncio
async def test_execute_mapping_error_logs_signal():
    strategy = _make_strategy(mapping_template={"symbol": "$.missing_field", "exchange": "NSE", "action": "$.action", "quantity": "$.qty", "order_type": "MARKET", "product_type": "INTRADAY"})
    redis = AsyncMock()
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    arq_redis = AsyncMock()

    results = await execute([strategy], _make_payload(), redis, session, arq_redis)

    assert len(results) == 1
    assert results[0].rule_result == "mapping_error"


@pytest.mark.asyncio
async def test_execute_rule_blocks_signal():
    strategy = _make_strategy(rules={"symbol_whitelist": ["TCS"]})
    redis = AsyncMock()
    redis.mget.return_value = [None, None]
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    arq_redis = AsyncMock()

    results = await execute([strategy], _make_payload(), redis, session, arq_redis)

    assert results[0].rule_result == "blocked_by_rule"
    assert "not in whitelist" in (results[0].rule_detail or "")


@pytest.mark.asyncio
async def test_execute_paper_mode_calls_paper_engine():
    strategy = _make_strategy(mode="paper")
    redis = AsyncMock()
    redis.mget.return_value = [None, None]
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    arq_redis = AsyncMock()

    with patch("app.webhooks.executor.execute_paper_trade", new_callable=AsyncMock) as mock_paper:
        mock_paper.return_value = "filled"
        with patch("app.webhooks.executor._get_active_paper_session", new_callable=AsyncMock) as mock_session:
            mock_session.return_value = MagicMock(id=uuid.uuid4())
            results = await execute([strategy], _make_payload(), redis, session, arq_redis)

    assert results[0].execution_result == "filled"
    # Verify Redis counters were updated for filled paper trade
    assert redis.incr.call_count >= 1


@pytest.mark.asyncio
async def test_execute_live_mode_places_order_synchronously():
    """Live mode calls _place_live_order directly (no ARQ queue)."""
    broker_id = uuid.uuid4()
    strategy = _make_strategy(mode="live", broker_connection_id=broker_id)
    redis = AsyncMock()
    redis.mget.return_value = [None, None]
    session = AsyncMock()

    with patch("app.webhooks.executor._place_live_order", new_callable=AsyncMock,
               return_value=("filled", {"status": "filled", "order_id": "abc"})) as mock_place:
        results = await execute([strategy], _make_payload(), redis, session, tenant_id=uuid.uuid4())

    assert results[0].execution_result == "filled"
    mock_place.assert_called_once()


@pytest.mark.asyncio
async def test_execute_live_no_broker_connection_skips():
    strategy = _make_strategy(mode="live", broker_connection_id=None)
    redis = AsyncMock()
    redis.mget.return_value = [None, None]
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    arq_redis = AsyncMock()

    results = await execute([strategy], _make_payload(), redis, session, arq_redis)

    assert results[0].execution_result == "no_broker_connection"
    arq_redis.enqueue_job.assert_not_called()


@pytest.mark.asyncio
async def test_place_live_order_skips_redis_update_when_flag_false():
    """When update_redis=False, position count and signals_today are not updated."""
    broker_id = str(uuid.uuid4())
    tenant_id = uuid.uuid4()
    strategy_id = str(uuid.uuid4())
    redis = AsyncMock()

    signal = StandardSignal(
        symbol="BTCUSDT",
        exchange="EXCHANGE1",
        action="BUY",
        quantity="1",
        order_type="MARKET",
        product_type="FUTURES",
    )

    mock_broker = AsyncMock()

    with patch("app.webhooks.executor.broker_pool") as mock_pool, \
         patch("app.webhooks.executor._place_order_with_broker",
               return_value=("filled", {"status": "filled", "order_id": "123"})):

        mock_pool.get = AsyncMock(return_value=mock_broker)
        mock_pool.evict = AsyncMock()

        from app.webhooks.executor import _place_live_order
        result, detail = await _place_live_order(
            broker_id, tenant_id, strategy_id, signal, redis, update_redis=False
        )

    assert result == "filled"
    redis.incr.assert_not_called()


# ---------------------------------------------------------------------------
# Dual-leg tests
# ---------------------------------------------------------------------------

def _make_dual_leg_strategy(max_trades=5, broker_id=None):
    return {
        "id": str(uuid.uuid4()),
        "name": "DL Strategy",
        "mode": "live",
        "mapping_template": {
            "symbol": "$.ticker",
            "exchange": "$.exchange",
            "action": "$.action",
            "quantity": "$.qty",
            "order_type": "MARKET",
            "product_type": "FUTURES",
        },
        "rules": {
            "dual_leg": {"enabled": True, "max_trades": max_trades},
        },
        "broker_connection_id": str(broker_id or uuid.uuid4()),
    }


def _make_futures_signal(action="BUY"):
    return StandardSignal(
        symbol="BTCUSDT",
        exchange="EXCHANGE1",
        action=action,
        quantity="1",
        order_type="MARKET",
        product_type="FUTURES",
    )


def _mock_broker_pool(broker=None):
    """Patch broker_pool.get to return a mock broker."""
    mock_broker = broker or AsyncMock()
    return patch("app.webhooks.executor.broker_pool"), mock_broker


def _mock_place_order_with_broker(result="filled", detail=None):
    """Patch _place_order_with_broker to return a fixed result."""
    return patch(
        "app.webhooks.executor._place_order_with_broker",
        new_callable=AsyncMock,
        return_value=(result, detail or {"status": result, "order_id": "abc"}),
    )


@pytest.mark.asyncio
async def test_dual_leg_first_signal_opens_only():
    """No existing position → only open leg runs."""
    from app.webhooks.executor import _execute_dual_leg

    redis = AsyncMock()
    strategy = _make_dual_leg_strategy(max_trades=5)
    signal = _make_futures_signal(action="BUY")
    mock_broker = AsyncMock()

    with patch("app.webhooks.executor.get_dual_leg_state", new_callable=AsyncMock, return_value=("", 0)), \
         patch("app.webhooks.executor.broker_pool") as mock_pool, \
         _mock_place_order_with_broker("filled") as mock_place, \
         patch("app.webhooks.executor.set_dual_leg_position", new_callable=AsyncMock) as mock_set, \
         patch("app.webhooks.executor.clear_dual_leg_position", new_callable=AsyncMock) as mock_clear, \
         patch("app.webhooks.executor.increment_dual_leg_trade_count", new_callable=AsyncMock) as mock_incr, \
         patch("app.webhooks.executor.increment_signals_today", new_callable=AsyncMock):

        mock_pool.get = AsyncMock(return_value=mock_broker)
        mock_pool.evict = AsyncMock()

        result, detail = await _execute_dual_leg(
            strategy, signal, uuid.uuid4(), redis,
            {"enabled": True, "max_trades": 5},
        )

    assert result == "opened"
    assert detail["close"] is None
    assert detail["open"] is not None
    mock_place.assert_called_once()  # only open leg
    mock_set.assert_called_once()
    mock_incr.assert_called_once()
    mock_clear.assert_not_called()


@pytest.mark.asyncio
async def test_dual_leg_reversal_closes_then_opens():
    """Existing long position + SELL signal → close long, open short."""
    from app.webhooks.executor import _execute_dual_leg

    redis = AsyncMock()
    strategy = _make_dual_leg_strategy(max_trades=5)
    signal = _make_futures_signal(action="SELL")
    mock_broker = AsyncMock()

    with patch("app.webhooks.executor.get_dual_leg_state", new_callable=AsyncMock, return_value=("long", 1)), \
         patch("app.webhooks.executor.broker_pool") as mock_pool, \
         _mock_place_order_with_broker("filled") as mock_place, \
         patch("app.webhooks.executor.clear_dual_leg_position", new_callable=AsyncMock) as mock_clear, \
         patch("app.webhooks.executor.set_dual_leg_position", new_callable=AsyncMock) as mock_set, \
         patch("app.webhooks.executor.increment_dual_leg_trade_count", new_callable=AsyncMock), \
         patch("app.webhooks.executor.increment_signals_today", new_callable=AsyncMock):

        mock_pool.get = AsyncMock(return_value=mock_broker)
        mock_pool.evict = AsyncMock()

        result, detail = await _execute_dual_leg(
            strategy, signal, uuid.uuid4(), redis,
            {"enabled": True, "max_trades": 5},
        )

    assert result == "reversed"
    assert detail["close"] is not None
    assert detail["open"] is not None
    assert mock_place.call_count == 2
    mock_clear.assert_called_once()
    mock_set.assert_called_once()


@pytest.mark.asyncio
async def test_dual_leg_stop_condition_closes_only():
    """Max trades reached + existing position → close only, no open."""
    from app.webhooks.executor import _execute_dual_leg

    redis = AsyncMock()
    strategy = _make_dual_leg_strategy(max_trades=3)
    signal = _make_futures_signal(action="BUY")
    mock_broker = AsyncMock()

    with patch("app.webhooks.executor.get_dual_leg_state", new_callable=AsyncMock, return_value=("short", 3)), \
         patch("app.webhooks.executor.broker_pool") as mock_pool, \
         _mock_place_order_with_broker("filled") as mock_place, \
         patch("app.webhooks.executor.clear_dual_leg_position", new_callable=AsyncMock) as mock_clear, \
         patch("app.webhooks.executor.set_dual_leg_position", new_callable=AsyncMock) as mock_set, \
         patch("app.webhooks.executor.increment_dual_leg_trade_count", new_callable=AsyncMock) as mock_incr, \
         patch("app.webhooks.executor.increment_signals_today", new_callable=AsyncMock):

        mock_pool.get = AsyncMock(return_value=mock_broker)
        mock_pool.evict = AsyncMock()

        result, detail = await _execute_dual_leg(
            strategy, signal, uuid.uuid4(), redis,
            {"enabled": True, "max_trades": 3},
        )

    assert result == "closed"
    assert detail["close"] is not None
    assert detail["open"] is None
    mock_place.assert_called_once()  # only close leg
    mock_clear.assert_called_once()
    mock_set.assert_not_called()
    mock_incr.assert_not_called()


@pytest.mark.asyncio
async def test_dual_leg_no_action_when_stop_and_no_position():
    """Max trades reached + no open position → no-op."""
    from app.webhooks.executor import _execute_dual_leg

    redis = AsyncMock()
    strategy = _make_dual_leg_strategy(max_trades=3)
    signal = _make_futures_signal(action="BUY")

    with patch("app.webhooks.executor.get_dual_leg_state", new_callable=AsyncMock, return_value=("", 3)), \
         _mock_place_order_with_broker("filled") as mock_place:

        result, detail = await _execute_dual_leg(
            strategy, signal, uuid.uuid4(), redis,
            {"enabled": True, "max_trades": 3},
        )

    assert result == "no_action"
    mock_place.assert_not_called()


@pytest.mark.asyncio
async def test_dual_leg_close_fails_aborts_open():
    """Close leg broker error → abort, do not open."""
    from app.webhooks.executor import _execute_dual_leg

    redis = AsyncMock()
    strategy = _make_dual_leg_strategy(max_trades=5)
    signal = _make_futures_signal(action="SELL")
    mock_broker = AsyncMock()

    with patch("app.webhooks.executor.get_dual_leg_state", new_callable=AsyncMock, return_value=("long", 1)), \
         patch("app.webhooks.executor.broker_pool") as mock_pool, \
         patch("app.webhooks.executor._place_order_with_broker", new_callable=AsyncMock,
               return_value=("broker_error", {"error": "connection timeout"})) as mock_place, \
         patch("app.webhooks.executor.clear_dual_leg_position", new_callable=AsyncMock) as mock_clear:

        mock_pool.get = AsyncMock(return_value=mock_broker)
        mock_pool.evict = AsyncMock()

        result, detail = await _execute_dual_leg(
            strategy, signal, uuid.uuid4(), redis,
            {"enabled": True, "max_trades": 5},
        )

    assert result == "close_failed"
    assert detail["open"] is None
    mock_place.assert_called_once()
    mock_clear.assert_not_called()


@pytest.mark.asyncio
async def test_dual_leg_9012_treated_as_already_closed():
    """Close returns 9012 (position not found) → treat as already closed, proceed to open."""
    from app.webhooks.executor import _execute_dual_leg

    redis = AsyncMock()
    strategy = _make_dual_leg_strategy(max_trades=5)
    signal = _make_futures_signal(action="SELL")

    close_detail = {"error": "Exchange1 API error 500: {\"code\":500,\"data\":\"9012 The position was not found\"}"}
    open_detail = {"status": "filled", "order_id": "xyz"}
    mock_broker = AsyncMock()

    with patch("app.webhooks.executor.get_dual_leg_state", new_callable=AsyncMock, return_value=("long", 1)), \
         patch("app.webhooks.executor.broker_pool") as mock_pool, \
         patch("app.webhooks.executor._place_order_with_broker", new_callable=AsyncMock,
               side_effect=[("broker_error", close_detail), ("filled", open_detail)]) as mock_place, \
         patch("app.webhooks.executor.clear_dual_leg_position", new_callable=AsyncMock) as mock_clear, \
         patch("app.webhooks.executor.set_dual_leg_position", new_callable=AsyncMock) as mock_set, \
         patch("app.webhooks.executor.increment_dual_leg_trade_count", new_callable=AsyncMock), \
         patch("app.webhooks.executor.increment_signals_today", new_callable=AsyncMock):

        mock_pool.get = AsyncMock(return_value=mock_broker)
        mock_pool.evict = AsyncMock()

        result, detail = await _execute_dual_leg(
            strategy, signal, uuid.uuid4(), redis,
            {"enabled": True, "max_trades": 5},
        )

    assert result == "reversed"
    assert detail["close"] == {"status": "already_closed"}
    assert detail["open"] == open_detail
    assert mock_place.call_count == 2
    mock_clear.assert_called_once()
    mock_set.assert_called_once()


@pytest.mark.asyncio
async def test_dual_leg_no_action_when_same_side():
    """Already long + BUY signal → no-op (already in correct position)."""
    from app.webhooks.executor import _execute_dual_leg

    redis = AsyncMock()
    strategy = _make_dual_leg_strategy(max_trades=5)
    signal = _make_futures_signal(action="BUY")

    with patch("app.webhooks.executor.get_dual_leg_state", new_callable=AsyncMock, return_value=("long", 1)), \
         _mock_place_order_with_broker("filled") as mock_place:

        result, detail = await _execute_dual_leg(
            strategy, signal, uuid.uuid4(), redis,
            {"enabled": True, "max_trades": 5},
        )

    assert result == "no_action"
    mock_place.assert_not_called()


@pytest.mark.asyncio
async def test_dual_leg_open_failed_after_successful_close():
    """Close succeeds, open fails → open_failed; position cleared, trade_count not incremented."""
    from app.webhooks.executor import _execute_dual_leg

    redis = AsyncMock()
    strategy = _make_dual_leg_strategy(max_trades=5)
    signal = _make_futures_signal(action="SELL")

    close_detail = {"status": "filled", "order_id": "close-1"}
    open_detail = {"error": "insufficient margin"}
    mock_broker = AsyncMock()

    with patch("app.webhooks.executor.get_dual_leg_state", new_callable=AsyncMock, return_value=("long", 1)), \
         patch("app.webhooks.executor.broker_pool") as mock_pool, \
         patch("app.webhooks.executor._place_order_with_broker", new_callable=AsyncMock,
               side_effect=[("filled", close_detail), ("broker_error", open_detail)]) as mock_place, \
         patch("app.webhooks.executor.clear_dual_leg_position", new_callable=AsyncMock) as mock_clear, \
         patch("app.webhooks.executor.set_dual_leg_position", new_callable=AsyncMock) as mock_set, \
         patch("app.webhooks.executor.increment_dual_leg_trade_count", new_callable=AsyncMock) as mock_incr, \
         patch("app.webhooks.executor.increment_signals_today", new_callable=AsyncMock):

        mock_pool.get = AsyncMock(return_value=mock_broker)
        mock_pool.evict = AsyncMock()

        result, detail = await _execute_dual_leg(
            strategy, signal, uuid.uuid4(), redis,
            {"enabled": True, "max_trades": 5},
        )

    assert result == "open_failed"
    assert detail["close"] == close_detail
    assert detail["open"] == open_detail
    assert mock_place.call_count == 2
    mock_clear.assert_called_once()   # close succeeded → position cleared
    mock_set.assert_not_called()      # open failed → position_side not set
    mock_incr.assert_not_called()     # trade_count not incremented


@pytest.mark.asyncio
async def test_execute_live_mode_routes_to_dual_leg_when_enabled():
    """execute() calls _execute_dual_leg when dual_leg.enabled is true."""
    broker_id = uuid.uuid4()
    strategy = _make_strategy(
        mode="live",
        broker_connection_id=broker_id,
        rules={"dual_leg": {"enabled": True, "max_trades": 5}},
    )
    redis = AsyncMock()
    redis.mget.return_value = [None, None]
    session = AsyncMock()

    with patch("app.webhooks.executor._execute_dual_leg", new_callable=AsyncMock,
               return_value=("opened", {"close": None, "open": {"status": "filled"}})) as mock_dual, \
         patch("app.webhooks.executor._place_live_order", new_callable=AsyncMock) as mock_single:

        results = await execute([strategy], _make_payload(), redis, session, tenant_id=uuid.uuid4())

    assert results[0].execution_result == "opened"
    mock_dual.assert_called_once()
    mock_single.assert_not_called()
