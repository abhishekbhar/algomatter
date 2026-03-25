import pytest
from tests.conftest import create_authenticated_user


@pytest.mark.asyncio
async def test_create_paper_session(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strat = await client.post(
        "/api/v1/strategies",
        json={
            "name": "paper-strat",
            "mode": "paper",
            "mapping_template": {
                "symbol": "$.ticker",
                "exchange": "NSE",
                "action": "$.action",
                "quantity": "$.qty",
                "order_type": "MARKET",
                "product_type": "INTRADAY",
            },
            "rules": {},
        },
        headers=headers,
    )
    strategy_id = strat.json()["id"]

    resp = await client.post(
        "/api/v1/paper-trading/sessions",
        json={"strategy_id": strategy_id, "capital": 1000000},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "active"
    assert float(resp.json()["current_balance"]) == 1000000


@pytest.mark.asyncio
async def test_webhook_executes_paper_trade(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    config = await client.get("/api/v1/webhooks/config", headers=headers)
    webhook_token = config.json()["webhook_token"]

    strat = await client.post(
        "/api/v1/strategies",
        json={
            "name": "paper-live",
            "mode": "paper",
            "mapping_template": {
                "symbol": "$.ticker",
                "exchange": "NSE",
                "action": "$.action",
                "quantity": "$.qty",
                "order_type": "MARKET",
                "product_type": "INTRADAY",
            },
            "rules": {},
        },
        headers=headers,
    )
    strategy_id = strat.json()["id"]

    session_resp = await client.post(
        "/api/v1/paper-trading/sessions",
        json={"strategy_id": strategy_id, "capital": 1000000},
        headers=headers,
    )
    session_id = session_resp.json()["id"]

    await client.post(
        f"/api/v1/webhook/{webhook_token}",
        json={"ticker": "RELIANCE", "action": "buy", "qty": "10"},
    )

    state = await client.get(
        f"/api/v1/paper-trading/sessions/{session_id}", headers=headers
    )
    data = state.json()
    assert len(data["positions"]) >= 1
    assert data["positions"][0]["symbol"] == "RELIANCE"


@pytest.mark.asyncio
async def test_stop_paper_session(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strat = await client.post(
        "/api/v1/strategies",
        json={
            "name": "stop-test",
            "mode": "paper",
            "mapping_template": {
                "symbol": "$.s",
                "exchange": "NSE",
                "action": "$.a",
                "quantity": "$.q",
                "order_type": "MARKET",
                "product_type": "INTRADAY",
            },
            "rules": {},
        },
        headers=headers,
    )

    session_resp = await client.post(
        "/api/v1/paper-trading/sessions",
        json={"strategy_id": strat.json()["id"], "capital": 500000},
        headers=headers,
    )
    session_id = session_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/paper-trading/sessions/{session_id}/stop", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "stopped"
