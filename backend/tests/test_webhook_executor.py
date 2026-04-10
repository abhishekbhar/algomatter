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
    redis.mget.return_value = [None, None]
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

    results = await execute([strategy], _make_payload(), redis, session, arq_redis)

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
