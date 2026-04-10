import pytest
from tests.conftest import create_authenticated_user


@pytest.mark.asyncio
async def test_webhook_invalid_token(client):
    resp = await client.post(
        "/api/v1/webhook/invalid-token",
        json={
            "ticker": "RELIANCE",
            "exchange": "NSE",
            "strategy": {"order_action": "buy", "order_contracts": "10"},
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_receives_and_logs_signal(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    config = await client.get("/api/v1/webhooks/config", headers=headers)
    webhook_token = config.json()["token"]

    await client.post(
        "/api/v1/strategies",
        json={
            "name": "test-strategy",
            "mode": "paper",
            "mapping_template": {
                "symbol": "$.ticker",
                "exchange": "$.exchange",
                "action": "$.strategy.order_action",
                "quantity": "$.strategy.order_contracts",
                "order_type": "MARKET",
                "product_type": "INTRADAY",
            },
            "rules": {},
        },
        headers=headers,
    )

    resp = await client.post(
        f"/api/v1/webhook/{webhook_token}",
        json={
            "ticker": "RELIANCE",
            "exchange": "NSE",
            "strategy": {"order_action": "buy", "order_contracts": "10"},
        },
    )
    assert resp.status_code == 200

    signals = await client.get("/api/v1/webhooks/signals", headers=headers)
    assert len(signals.json()) >= 1
    assert signals.json()[0]["parsed_signal"]["symbol"] == "RELIANCE"


@pytest.mark.asyncio
async def test_webhook_blocked_by_rule(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    config = await client.get("/api/v1/webhooks/config", headers=headers)
    webhook_token = config.json()["token"]

    await client.post(
        "/api/v1/strategies",
        json={
            "name": "restricted",
            "mode": "paper",
            "mapping_template": {
                "symbol": "$.ticker",
                "exchange": "NSE",
                "action": "$.action",
                "quantity": "$.qty",
                "order_type": "MARKET",
                "product_type": "INTRADAY",
            },
            "rules": {"symbol_whitelist": ["TCS"]},
        },
        headers=headers,
    )

    resp = await client.post(
        f"/api/v1/webhook/{webhook_token}",
        json={"ticker": "RELIANCE", "action": "buy", "qty": "10"},
    )
    assert resp.status_code == 200

    signals = await client.get("/api/v1/webhooks/signals", headers=headers)
    blocked = [s for s in signals.json() if s["rule_result"] == "blocked_by_rule"]
    assert len(blocked) >= 1


@pytest.mark.asyncio
async def test_webhook_payload_too_large(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    config = await client.get("/api/v1/webhooks/config", headers=headers)
    webhook_token = config.json()["token"]

    big_payload = {"data": "x" * 70000}
    resp = await client.post(
        f"/api/v1/webhook/{webhook_token}", json=big_payload
    )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_webhook_config_regenerate_token(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    config1 = await client.get("/api/v1/webhooks/config", headers=headers)
    old_token = config1.json()["token"]

    await client.post(
        "/api/v1/webhooks/config/regenerate-token", headers=headers
    )
    config2 = await client.get("/api/v1/webhooks/config", headers=headers)
    new_token = config2.json()["token"]

    assert old_token != new_token
    resp = await client.post(
        f"/api/v1/webhook/{old_token}", json={"test": 1}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_slug_targets_single_strategy(client):
    tokens = await create_authenticated_user(client, "slug1@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    config = await client.get("/api/v1/webhooks/config", headers=headers)
    token = config.json()["token"]

    # Create two strategies
    resp1 = await client.post(
        "/api/v1/strategies",
        json={"name": "NIFTY Long", "mode": "log", "mapping_template": {
            "symbol": "$.ticker", "exchange": "NSE", "action": "$.action",
            "quantity": "$.qty", "order_type": "MARKET", "product_type": "INTRADAY",
        }, "rules": {}},
        headers=headers,
    )
    assert resp1.status_code == 201
    slug = resp1.json()["slug"]

    await client.post(
        "/api/v1/strategies",
        json={"name": "NIFTY Short", "mode": "log", "mapping_template": {
            "symbol": "$.ticker", "exchange": "NSE", "action": "$.action",
            "quantity": "$.qty", "order_type": "MARKET", "product_type": "INTRADAY",
        }, "rules": {}},
        headers=headers,
    )

    resp = await client.post(
        f"/api/v1/webhook/{token}/{slug}",
        json={"ticker": "NIFTY", "action": "BUY", "qty": "1"},
    )
    assert resp.status_code == 200
    assert resp.json()["signals_processed"] == 1


@pytest.mark.asyncio
async def test_webhook_slug_404_for_unknown_slug(client):
    tokens = await create_authenticated_user(client, "slug2@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    config = await client.get("/api/v1/webhooks/config", headers=headers)
    token = config.json()["token"]

    resp = await client.post(
        f"/api/v1/webhook/{token}/nonexistent-slug",
        json={"ticker": "NIFTY", "action": "BUY", "qty": "1"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_webhook_broadcast_still_fans_out(client):
    tokens = await create_authenticated_user(client, "slug3@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    config = await client.get("/api/v1/webhooks/config", headers=headers)
    token = config.json()["token"]

    for name in ["Strategy A", "Strategy B"]:
        await client.post(
            "/api/v1/strategies",
            json={"name": name, "mode": "log", "mapping_template": {
                "symbol": "$.ticker", "exchange": "NSE", "action": "$.action",
                "quantity": "$.qty", "order_type": "MARKET", "product_type": "INTRADAY",
            }, "rules": {}},
            headers=headers,
        )

    resp = await client.post(
        f"/api/v1/webhook/{token}",
        json={"ticker": "RELIANCE", "action": "BUY", "qty": "5"},
    )
    assert resp.status_code == 200
    assert resp.json()["signals_processed"] == 2
