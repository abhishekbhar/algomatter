"""Tests for the standalone manual trades API (/api/v1/trades/manual)."""

import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.auth.deps import get_current_user, get_tenant_session

FAKE_USER = {"user_id": str(uuid.uuid4()), "email": "test@example.com"}


@pytest.fixture
def mock_session():
    """Create a mock async session."""
    return AsyncMock()


@pytest.fixture
def override_deps(mock_session):
    """Override FastAPI dependencies for auth and session."""

    async def fake_get_current_user():
        return FAKE_USER

    async def fake_get_tenant_session():
        yield mock_session

    app.dependency_overrides[get_current_user] = fake_get_current_user
    app.dependency_overrides[get_tenant_session] = fake_get_tenant_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client(override_deps):
    """Async test client with auth mocked out."""
    app.state.redis = AsyncMock()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Test 1: GET /api/v1/trades/manual returns empty list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_manual_trades_returns_empty(client, mock_session):
    # Mock the session.execute to return empty results for both count and list queries
    count_result = MagicMock()
    count_result.scalar.return_value = 0

    rows_result = MagicMock()
    rows_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))

    mock_session.execute = AsyncMock(side_effect=[count_result, rows_result])

    resp = await client.get("/api/v1/trades/manual")
    assert resp.status_code == 200
    data = resp.json()
    assert data["trades"] == []
    assert data["total"] == 0


# ---------------------------------------------------------------------------
# Test 2: POST /api/v1/trades/manual returns 404 for unknown broker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_place_manual_trade_unknown_broker(client, mock_session):
    # session.get(BrokerConnection, ...) returns None -> 404
    mock_session.get = AsyncMock(return_value=None)

    resp = await client.post(
        "/api/v1/trades/manual",
        json={
            "broker_connection_id": str(uuid.uuid4()),
            "symbol": "BTCUSDT",
            "exchange": "BINANCE",
            "action": "BUY",
            "quantity": 1.0,
        },
    )
    assert resp.status_code == 404
    assert "Broker connection not found" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Test 3: POST /api/v1/trades/manual rejects LIMIT order with no price
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_place_manual_trade_limit_requires_price(client, mock_session):
    """LIMIT orders without a valid price must be rejected at the API edge.

    Previously the router coerced a missing price to ``Decimal("0")`` and
    forwarded it to the broker, which stripped the ``price`` field from the
    request body and let Exchange1 reject the order with ``9257 null``. We
    should fail loudly with HTTP 400 instead.
    """
    # No LIMIT order should reach the broker, but mock a broker connection
    # so we get past the 404 branch.
    fake_bc = MagicMock()
    fake_bc.tenant_id = uuid.UUID(FAKE_USER["user_id"])
    fake_bc.id = uuid.uuid4()
    fake_bc.broker_type = "exchange1"
    fake_bc.credentials = b"encrypted"
    mock_session.get = AsyncMock(return_value=fake_bc)

    resp = await client.post(
        "/api/v1/trades/manual",
        json={
            "broker_connection_id": str(uuid.uuid4()),
            "symbol": "BTCUSDT",
            "exchange": "EXCHANGE1",
            "product_type": "FUTURES",
            "action": "BUY",
            "quantity": 0.001,
            "order_type": "limit",
            # price intentionally omitted
        },
    )
    assert resp.status_code == 400
    assert "price" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test 4: POST /api/v1/trades/manual/{id}/cancel returns 404 for missing trade
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_manual_trade_not_found(client, mock_session):
    # session.execute returns a result with scalar_one_or_none -> None
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=execute_result)

    trade_id = uuid.uuid4()
    resp = await client.post(f"/api/v1/trades/manual/{trade_id}/cancel")
    assert resp.status_code == 404
    assert "Trade not found" in resp.json()["detail"]
