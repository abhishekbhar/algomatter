import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from tests.conftest import create_authenticated_user



@pytest.mark.asyncio
async def test_balance_includes_used_margin(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    create_resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "exchange1",
            "label": "Test Broker",
            "credentials": {"api_key": "k", "api_secret": "s"},
        },
        headers=headers,
    )
    broker_id = create_resp.json()["id"]

    mock_balance = AsyncMock()
    mock_balance.available = Decimal("50000")
    mock_balance.total = Decimal("60000")
    mock_balance.used_margin = Decimal("10000")

    mock_broker = AsyncMock()
    mock_broker.get_balance = AsyncMock(return_value=mock_balance)
    mock_broker.close = AsyncMock()

    with patch("app.brokers.router.get_broker", new=AsyncMock(return_value=mock_broker)):
        resp = await client.get(f"/api/v1/brokers/{broker_id}/balance", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] == 50000.0
    assert data["total"] == 60000.0
    assert data["used_margin"] == 10000.0


@pytest.mark.asyncio
async def test_live_positions_empty(client):
    """When Exchange1 returns no positions, endpoint returns []."""
    tokens = await create_authenticated_user(client, email="livepos1@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    create_resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "exchange1",
            "label": "Live Pos Broker",
            "credentials": {"api_key": "k", "api_secret": "s"},
        },
        headers=headers,
    )
    broker_id = create_resp.json()["id"]

    mock_broker = AsyncMock()
    mock_broker.get_positions = AsyncMock(return_value=[])
    mock_broker.close = AsyncMock()

    with patch("app.brokers.router.get_broker", new=AsyncMock(return_value=mock_broker)):
        resp = await client.get(f"/api/v1/brokers/{broker_id}/live-positions", headers=headers)

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_live_positions_exchange_direct(client):
    """Position with no matching deployment or webhook → exchange_direct."""
    tokens = await create_authenticated_user(client, email="livepos2@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    create_resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "exchange1",
            "label": "ExDirect Broker",
            "credentials": {"api_key": "k", "api_secret": "s"},
        },
        headers=headers,
    )
    broker_id = create_resp.json()["id"]

    from app.brokers.base import Position as BrokerPosition
    from decimal import Decimal
    mock_position = BrokerPosition(
        symbol="BANKNIFTY",
        exchange="NFO",
        action="BUY",
        quantity=Decimal("50"),
        entry_price=Decimal("45000"),
        product_type="FUTURES",
    )

    mock_broker = AsyncMock()
    mock_broker.get_positions = AsyncMock(return_value=[mock_position])
    mock_broker.close = AsyncMock()

    with patch("app.brokers.router.get_broker", new=AsyncMock(return_value=mock_broker)):
        resp = await client.get(f"/api/v1/brokers/{broker_id}/live-positions", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "BANKNIFTY"
    assert data[0]["origin"] == "exchange_direct"
    assert data[0]["strategy_name"] is None


@pytest.mark.asyncio
async def test_live_positions_502_on_broker_error(client):
    """When broker raises an exception on get_positions, endpoint returns 502."""
    tokens = await create_authenticated_user(client, email="livepos3@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    create_resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "exchange1",
            "label": "Error Broker",
            "credentials": {"api_key": "k", "api_secret": "s"},
        },
        headers=headers,
    )
    broker_id = create_resp.json()["id"]

    mock_broker = AsyncMock()
    mock_broker.get_positions = AsyncMock(side_effect=Exception("auth failed"))
    mock_broker.close = AsyncMock()

    with patch("app.brokers.router.get_broker", new=AsyncMock(return_value=mock_broker)):
        resp = await client.get(f"/api/v1/brokers/{broker_id}/live-positions", headers=headers)

    assert resp.status_code == 502
    assert "Failed to fetch positions from broker" in resp.json()["detail"]
