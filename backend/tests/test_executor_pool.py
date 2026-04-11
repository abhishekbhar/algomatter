# backend/tests/test_executor_pool.py
import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

from app.brokers.base import OrderResponse
from app.webhooks.executor import _is_auth_error, _place_with_retry
from app.webhooks.schemas import StandardSignal


def _make_signal():
    return StandardSignal(
        symbol="BTCUSDT",
        exchange="EXCHANGE1",
        action="BUY",
        quantity=1,
        order_type="MARKET",
        product_type="FUTURES",
        leverage=10,
        position_model="cross",
    )


def _filled_response():
    return OrderResponse(
        order_id="futures:market:btc:123",
        status="filled",
        fill_price="0",
        fill_quantity="1",
        message="",
    )


# --- _is_auth_error ---

def test_is_auth_error_401():
    assert _is_auth_error("Exchange1 API error 401: unauthorized") is True


def test_is_auth_error_403():
    assert _is_auth_error("Exchange1 API error 403: forbidden") is True


def test_is_auth_error_ip():
    assert _is_auth_error('{"data": "ip is error"}') is True


def test_is_auth_error_false_for_9012():
    assert _is_auth_error("Exchange1 API error 500: 9012 The position was not found") is False


def test_is_auth_error_false_for_margin():
    assert _is_auth_error("Exchange1 API error 500: 9008 Insufficient margin") is False


# --- _place_with_retry ---

@pytest.mark.asyncio
async def test_place_with_retry_success_no_retry():
    broker = AsyncMock()
    broker.place_order = AsyncMock(return_value=_filled_response())
    signal = _make_signal()
    conn_id = str(uuid.uuid4())
    tenant_id = uuid.uuid4()

    with patch("app.webhooks.executor.broker_pool") as mock_pool:
        with patch("app.webhooks.executor._place_order_with_broker",
                   return_value=("filled", {"order_id": "123"})) as mock_place:
            result, detail, returned_broker = await _place_with_retry(
                conn_id, tenant_id, broker, signal, "strat-1"
            )

    assert result == "filled"
    assert mock_place.call_count == 1  # no retry


@pytest.mark.asyncio
async def test_place_with_retry_auth_error_evicts_and_retries():
    broker1 = AsyncMock()
    broker2 = AsyncMock()
    signal = _make_signal()
    conn_id = str(uuid.uuid4())
    tenant_id = uuid.uuid4()

    call_count = 0

    async def mock_place(broker, sig, strat_id):
        nonlocal call_count
        call_count += 1
        if broker is broker1:
            return "broker_error", {"error": "Exchange1 API error 401: unauthorized"}
        return "filled", {"order_id": "abc"}

    with patch("app.webhooks.executor.broker_pool") as mock_pool:
        mock_pool.evict = AsyncMock()
        mock_pool.get = AsyncMock(return_value=broker2)
        with patch("app.webhooks.executor._place_order_with_broker", side_effect=mock_place):
            result, detail, returned_broker = await _place_with_retry(
                conn_id, tenant_id, broker1, signal, "strat-1"
            )

    assert result == "filled"
    mock_pool.evict.assert_awaited_once_with(conn_id)
    mock_pool.get.assert_awaited_once_with(conn_id, tenant_id)
    assert returned_broker is broker2


@pytest.mark.asyncio
async def test_place_with_retry_non_auth_error_no_retry():
    broker = AsyncMock()
    signal = _make_signal()
    conn_id = str(uuid.uuid4())
    tenant_id = uuid.uuid4()

    async def mock_place(broker, sig, strat_id):
        return "broker_error", {"error": "Exchange1 API error 500: 9012 position not found"}

    with patch("app.webhooks.executor.broker_pool") as mock_pool:
        mock_pool.evict = AsyncMock()
        with patch("app.webhooks.executor._place_order_with_broker", side_effect=mock_place):
            result, detail, returned_broker = await _place_with_retry(
                conn_id, tenant_id, broker, signal, "strat-1"
            )

    assert result == "broker_error"
    mock_pool.evict.assert_not_awaited()  # no evict for non-auth errors
