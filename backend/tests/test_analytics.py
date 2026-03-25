import pytest
from tests.conftest import create_authenticated_user


@pytest.mark.asyncio
async def test_overview_empty(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.get("/api/v1/analytics/overview", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_pnl"] == 0
    assert data["active_strategies"] == 0


@pytest.mark.asyncio
async def test_strategy_metrics_after_backtest(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strat = await client.post("/api/v1/strategies", json={
        "name": "analytics-test", "mode": "backtest",
        "mapping_template": {"symbol": "$.symbol", "exchange": "NSE",
                             "action": "$.action", "quantity": "$.quantity",
                             "order_type": "MARKET", "product_type": "INTRADAY"},
        "rules": {},
    }, headers=headers)
    strategy_id = strat.json()["id"]

    await client.post("/api/v1/backtests", json={
        "strategy_id": strategy_id,
        "start_date": "2025-01-01", "end_date": "2025-01-31",
        "capital": 1000000, "slippage_pct": 0, "commission_pct": 0,
        "signals_csv": "timestamp,symbol,action,quantity,order_type,price\n2025-01-02,RELIANCE,BUY,10,MARKET,2500\n2025-01-03,RELIANCE,SELL,10,MARKET,2600"
    }, headers=headers)

    resp = await client.get(f"/api/v1/analytics/strategies/{strategy_id}/metrics", headers=headers)
    assert resp.status_code == 200
    assert "total_return" in resp.json()


@pytest.mark.asyncio
async def test_trades_csv_export(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strat = await client.post("/api/v1/strategies", json={
        "name": "csv-test", "mode": "backtest",
        "mapping_template": {"symbol": "$.symbol", "exchange": "NSE",
                             "action": "$.action", "quantity": "$.quantity",
                             "order_type": "MARKET", "product_type": "INTRADAY"},
        "rules": {},
    }, headers=headers)
    strategy_id = strat.json()["id"]

    await client.post("/api/v1/backtests", json={
        "strategy_id": strategy_id,
        "start_date": "2025-01-01", "end_date": "2025-01-31",
        "capital": 1000000, "slippage_pct": 0, "commission_pct": 0,
        "signals_csv": "timestamp,symbol,action,quantity,order_type,price\n2025-01-02,RELIANCE,BUY,10,MARKET,2500\n2025-01-03,RELIANCE,SELL,10,MARKET,2600"
    }, headers=headers)

    resp = await client.get(
        f"/api/v1/analytics/strategies/{strategy_id}/trades?format=csv",
        headers=headers
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
