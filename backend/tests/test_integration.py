# tests/test_integration.py
import pytest
from tests.conftest import create_authenticated_user


@pytest.mark.asyncio
async def test_full_pipeline(client):
    """
    End-to-end: signup -> create strategy -> start paper session ->
    send webhook -> verify trade -> check analytics
    """
    # 1. Signup
    tokens = (await client.post("/api/v1/auth/signup", json={
        "email": "e2e@test.com", "password": "securepass123"
    })).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # 2. Get webhook token
    config = (await client.get("/api/v1/webhooks/config", headers=headers)).json()
    webhook_token = config["webhook_token"]

    # 3. Create strategy
    strat = (await client.post("/api/v1/strategies", json={
        "name": "e2e-strategy", "mode": "paper",
        "mapping_template": {
            "symbol": "$.ticker", "exchange": "NSE",
            "action": "$.strategy.order_action",
            "quantity": "$.strategy.order_contracts",
            "order_type": "MARKET", "product_type": "INTRADAY",
        },
        "rules": {"symbol_whitelist": ["RELIANCE", "TCS"]},
    }, headers=headers)).json()

    # 4. Start paper trading session
    session = (await client.post("/api/v1/paper-trading/sessions", json={
        "strategy_id": strat["id"], "capital": 1000000
    }, headers=headers)).json()

    # 5. Send webhook (BUY)
    resp = await client.post(f"/api/v1/webhook/{webhook_token}", json={
        "ticker": "RELIANCE", "strategy": {"order_action": "buy", "order_contracts": "10"}
    })
    assert resp.status_code == 200

    # 6. Verify paper position created
    state = (await client.get(
        f"/api/v1/paper-trading/sessions/{session['id']}", headers=headers
    )).json()
    assert len(state["positions"]) == 1
    assert state["positions"][0]["symbol"] == "RELIANCE"

    # 7. Send webhook (SELL)
    await client.post(f"/api/v1/webhook/{webhook_token}", json={
        "ticker": "RELIANCE", "strategy": {"order_action": "sell", "order_contracts": "10"}
    })

    # 8. Verify position closed
    state = (await client.get(
        f"/api/v1/paper-trading/sessions/{session['id']}", headers=headers
    )).json()
    open_positions = [p for p in state["positions"] if p.get("closed_at") is None]
    assert len(open_positions) == 0

    # 9. Check signal log
    signals = (await client.get("/api/v1/webhooks/signals", headers=headers)).json()
    assert len(signals) == 2

    # 10. Check analytics overview
    overview = (await client.get("/api/v1/analytics/overview", headers=headers)).json()
    assert overview["active_strategies"] >= 1

    # 11. Verify RLS — second user sees nothing
    tokens_b = (await client.post("/api/v1/auth/signup", json={
        "email": "other@test.com", "password": "securepass123"
    })).json()
    headers_b = {"Authorization": f"Bearer {tokens_b['access_token']}"}
    strats_b = (await client.get("/api/v1/strategies", headers=headers_b)).json()
    assert len(strats_b) == 0
    signals_b = (await client.get("/api/v1/webhooks/signals", headers=headers_b)).json()
    assert len(signals_b) == 0
