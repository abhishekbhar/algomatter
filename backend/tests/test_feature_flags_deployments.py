import pytest

from app.config import settings
from tests.conftest import create_authenticated_user

STRATEGY_CODE = "class Strategy:\n    def on_candle(self, candle): pass"


async def _create_strategy(client, headers: dict) -> str:
    resp = await client.post(
        "/api/v1/hosted-strategies",
        json={"name": "flag-test", "code": STRATEGY_CODE},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


async def _create_deployment(client, headers, strategy_id, **overrides):
    payload = {
        "mode": "backtest",
        "symbol": "NIFTY",
        "exchange": "NSE",
        "interval": "1d",
        **overrides,
    }
    return await client.post(
        f"/api/v1/hosted-strategies/{strategy_id}/deployments",
        json=payload,
        headers=headers,
    )


@pytest.mark.asyncio
async def test_create_paper_deployment_blocked_when_paper_flag_off(
    client, monkeypatch
):
    tokens = await create_authenticated_user(client, email="df1@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strategy_id = await _create_strategy(client, headers)

    monkeypatch.setattr(settings, "enable_paper_trading", False)

    resp = await _create_deployment(client, headers, strategy_id, mode="paper")
    assert resp.status_code == 403
    assert "paper trading" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_backtest_deployment_blocked_when_backtest_flag_off(
    client, monkeypatch
):
    tokens = await create_authenticated_user(client, email="df2@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strategy_id = await _create_strategy(client, headers)

    monkeypatch.setattr(settings, "enable_backtesting", False)

    resp = await _create_deployment(client, headers, strategy_id, mode="backtest")
    assert resp.status_code == 403
    assert "backtesting" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_deployments_still_works_when_flags_off(client, monkeypatch):
    tokens = await create_authenticated_user(client, email="df3@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    monkeypatch.setattr(settings, "enable_paper_trading", False)
    monkeypatch.setattr(settings, "enable_backtesting", False)

    resp = await client.get("/api/v1/deployments", headers=headers)
    assert resp.status_code == 200
