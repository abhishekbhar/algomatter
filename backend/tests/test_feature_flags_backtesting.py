import pytest

from app.config import settings
from tests.conftest import create_authenticated_user


@pytest.mark.asyncio
async def test_create_backtest_blocked_when_flag_off(client, monkeypatch):
    tokens = await create_authenticated_user(client, email="bf1@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    monkeypatch.setattr(settings, "enable_backtesting", False)

    # strategy_id doesn't need to be real — the guard runs before lookup
    resp = await client.post(
        "/api/v1/backtests",
        json={
            "strategy_id": "00000000-0000-0000-0000-000000000000",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "capital": 100000,
            "signals_csv": "timestamp,action,symbol,price,quantity\n",
        },
        headers=headers,
    )
    assert resp.status_code == 403
    assert "backtesting" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_backtest_blocked_when_flag_off(client, monkeypatch):
    tokens = await create_authenticated_user(client, email="bf2@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    monkeypatch.setattr(settings, "enable_backtesting", False)

    resp = await client.delete(
        "/api/v1/backtests/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert resp.status_code == 403
    assert "backtesting" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_backtests_still_works_when_flag_off(client, monkeypatch):
    tokens = await create_authenticated_user(client, email="bf3@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    monkeypatch.setattr(settings, "enable_backtesting", False)

    resp = await client.get("/api/v1/backtests", headers=headers)
    assert resp.status_code == 200
    # New user has no backtests; empty list is fine
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_backtest_still_works_when_flag_off(client, monkeypatch):
    """GET by id for a non-existent row returns 404 (not 403) when flag off."""
    tokens = await create_authenticated_user(client, email="bf4@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    monkeypatch.setattr(settings, "enable_backtesting", False)

    resp = await client.get(
        "/api/v1/backtests/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert resp.status_code == 404
