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

    with patch("app.brokers.router.get_broker", return_value=mock_broker):
        resp = await client.get(f"/api/v1/brokers/{broker_id}/balance", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] == 50000.0
    assert data["total"] == 60000.0
    assert data["used_margin"] == 10000.0
