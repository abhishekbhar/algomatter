import pytest

from app.config import settings
from tests.conftest import create_authenticated_user


async def _make_strategy(client, headers):
    strat = await client.post(
        "/api/v1/strategies",
        json={
            "name": "flag-test",
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
    assert strat.status_code == 201, strat.text
    return strat.json()["id"]


@pytest.mark.asyncio
async def test_create_paper_session_blocked_when_flag_off(client, monkeypatch):
    tokens = await create_authenticated_user(client, email="pf1@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strategy_id = await _make_strategy(client, headers)

    monkeypatch.setattr(settings, "enable_paper_trading", False)

    resp = await client.post(
        "/api/v1/paper-trading/sessions",
        json={"strategy_id": strategy_id, "capital": 100000},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "paper trading" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stop_paper_session_blocked_when_flag_off(client, monkeypatch):
    tokens = await create_authenticated_user(client, email="pf2@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strategy_id = await _make_strategy(client, headers)

    # Create while flag is on
    created = await client.post(
        "/api/v1/paper-trading/sessions",
        json={"strategy_id": strategy_id, "capital": 100000},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json()["id"]

    # Flip flag off and try to stop
    monkeypatch.setattr(settings, "enable_paper_trading", False)
    resp = await client.post(
        f"/api/v1/paper-trading/sessions/{session_id}/stop",
        headers=headers,
    )
    assert resp.status_code == 403
    assert "paper trading" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_paper_sessions_still_works_when_flag_off(client, monkeypatch):
    tokens = await create_authenticated_user(client, email="pf3@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strategy_id = await _make_strategy(client, headers)

    # Seed a session while flag is on
    await client.post(
        "/api/v1/paper-trading/sessions",
        json={"strategy_id": strategy_id, "capital": 100000},
        headers=headers,
    )

    # Flip off — GETs must still work
    monkeypatch.setattr(settings, "enable_paper_trading", False)
    resp = await client.get("/api/v1/paper-trading/sessions", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
