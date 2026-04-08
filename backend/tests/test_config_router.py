import pytest

from app.config import settings


@pytest.mark.asyncio
async def test_get_config_returns_flags_default(client):
    resp = await client.get("/api/v1/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "featureFlags": {
            "paperTrading": True,
            "backtesting": True,
        }
    }


@pytest.mark.asyncio
async def test_get_config_reflects_paper_trading_off(client, monkeypatch):
    monkeypatch.setattr(settings, "enable_paper_trading", False)
    resp = await client.get("/api/v1/config")
    assert resp.status_code == 200
    assert resp.json()["featureFlags"]["paperTrading"] is False
    assert resp.json()["featureFlags"]["backtesting"] is True


@pytest.mark.asyncio
async def test_get_config_reflects_backtesting_off(client, monkeypatch):
    monkeypatch.setattr(settings, "enable_backtesting", False)
    resp = await client.get("/api/v1/config")
    assert resp.status_code == 200
    assert resp.json()["featureFlags"]["backtesting"] is False
    assert resp.json()["featureFlags"]["paperTrading"] is True


@pytest.mark.asyncio
async def test_get_config_no_auth_required(client):
    # No Authorization header — should still succeed
    resp = await client.get("/api/v1/config")
    assert resp.status_code == 200
