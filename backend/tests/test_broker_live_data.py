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


@pytest.mark.asyncio
async def test_activity_empty(client):
    """No signals or trades → empty activity response."""
    tokens = await create_authenticated_user(client, email="activity1@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    create_resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "exchange1",
            "label": "Activity Broker",
            "credentials": {"api_key": "k", "api_secret": "s"},
        },
        headers=headers,
    )
    broker_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/brokers/{broker_id}/activity", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["offset"] == 0
    assert data["limit"] == 50


@pytest.mark.asyncio
async def test_activity_webhook_item(client):
    """A filled webhook signal linked to this broker appears in activity."""
    import uuid
    from app.db.models import Strategy, WebhookSignal
    from tests.conftest import _test_session_factory

    tokens = await create_authenticated_user(client, email="activity2@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Create broker
    create_resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "exchange1",
            "label": "Activity Webhook Broker",
            "credentials": {"api_key": "k", "api_secret": "s"},
        },
        headers=headers,
    )
    broker_id = create_resp.json()["id"]

    # Get the user id from /auth/me
    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    user_id = uuid.UUID(me_resp.json()["id"])
    broker_uuid = uuid.UUID(broker_id)

    # Create a strategy linked to the broker and a filled webhook signal
    async with _test_session_factory() as session:
        strategy = Strategy(
            tenant_id=user_id,
            name="Test Strategy",
            broker_connection_id=broker_uuid,
            mode="live",
        )
        session.add(strategy)
        await session.flush()

        signal = WebhookSignal(
            tenant_id=user_id,
            strategy_id=strategy.id,
            raw_payload={"signal": "buy"},
            parsed_signal={"symbol": "NIFTY", "action": "BUY", "quantity": 10},
            execution_result="filled",
            execution_detail={"broker_order_id": "ORD123"},
        )
        session.add(signal)
        await session.commit()

    resp = await client.get(f"/api/v1/brokers/{broker_id}/activity", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["source"] == "webhook"
    assert item["symbol"] == "NIFTY"
    assert item["action"] == "BUY"
    assert item["quantity"] == 10.0
    assert item["fill_price"] is None
    assert item["strategy_name"] == "Test Strategy"
    assert item["order_id"] == "ORD123"


@pytest.mark.asyncio
async def test_balance_502_on_broker_error(client):
    """When broker raises on get_balance, endpoint returns 502."""
    tokens = await create_authenticated_user(client, email="balance502@test.com")
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
    mock_broker.get_balance = AsyncMock(side_effect=Exception("auth failed"))
    mock_broker.close = AsyncMock()

    with patch("app.brokers.router.get_broker", new=AsyncMock(return_value=mock_broker)):
        resp = await client.get(f"/api/v1/brokers/{broker_id}/balance", headers=headers)

    assert resp.status_code == 502
    assert "Failed to fetch balance from broker" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_live_positions_webhook_origin(client):
    """Position matching a filled webhook signal → webhook origin."""
    from decimal import Decimal
    from app.db.models import Strategy, WebhookSignal
    from tests.conftest import _test_session_factory
    import uuid

    tokens = await create_authenticated_user(client, email="livepos4@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    create_resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "exchange1",
            "label": "Webhook Origin Broker",
            "credentials": {"api_key": "k", "api_secret": "s"},
        },
        headers=headers,
    )
    broker_id = create_resp.json()["id"]
    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    user_id = uuid.UUID(me_resp.json()["id"])
    broker_uuid = uuid.UUID(broker_id)

    # Create a strategy linked to the broker
    async with _test_session_factory() as session:
        strategy = Strategy(
            tenant_id=user_id,
            name="Webhook Strategy",
            broker_connection_id=broker_uuid,
            mode="live",
        )
        session.add(strategy)
        await session.flush()

        # Create a filled BUY signal for NIFTY (net BUY → open long)
        signal = WebhookSignal(
            tenant_id=user_id,
            strategy_id=strategy.id,
            raw_payload={"signal": "buy"},
            parsed_signal={"symbol": "NIFTY", "action": "BUY", "quantity": 50},
            execution_result="filled",
        )
        session.add(signal)
        await session.commit()

    # Mock Exchange1 returning a long NIFTY position
    from app.brokers.base import Position as BrokerPosition
    mock_position = BrokerPosition(
        symbol="NIFTY",
        exchange="NFO",
        action="BUY",
        quantity=Decimal("50"),
        entry_price=Decimal("20000"),
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
    assert data[0]["origin"] == "webhook"
    assert data[0]["strategy_name"] == "Webhook Strategy"
