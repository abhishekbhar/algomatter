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
async def test_execute_live_mode_enqueues_arq_job():
    broker_id = uuid.uuid4()
    strategy = _make_strategy(mode="live", broker_connection_id=broker_id)
    redis = AsyncMock()
    redis.mget.return_value = [None, None]
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    arq_redis = AsyncMock()

    results = await execute([strategy], _make_payload(), redis, session, arq_redis, tenant_id=uuid.uuid4())

    assert results[0].execution_result == "queued"
    arq_redis.enqueue_job.assert_called_once()
    call_args = arq_redis.enqueue_job.call_args
    assert call_args.args[0] == "execute_live_order_task"


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

    mock_order_response = MagicMock()
    mock_order_response.status = "filled"
    mock_order_response.model_dump.return_value = {"status": "filled", "order_id": "123"}

    with patch("app.webhooks.executor.async_session_factory") as mock_factory, \
         patch("app.webhooks.executor.get_broker", new_callable=AsyncMock) as mock_broker_fn, \
         patch("app.webhooks.executor.decrypt_credentials", return_value={}):

        mock_bc = MagicMock()
        mock_bc.broker_type = "exchange1"
        mock_bc.credentials = b"enc"

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_bc
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_factory.return_value = mock_session

        mock_broker = AsyncMock()
        mock_broker.place_order = AsyncMock(return_value=mock_order_response)
        mock_broker.close = AsyncMock()
        mock_broker_fn.return_value = mock_broker

        from app.webhooks.executor import _place_live_order
        result, detail = await _place_live_order(
            broker_id, tenant_id, strategy_id, signal, redis, update_redis=False
        )

    assert result == "filled"
    redis.incr.assert_not_called()
