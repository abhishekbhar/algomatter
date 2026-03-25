import pytest
from tests.conftest import create_authenticated_user


@pytest.mark.asyncio
async def test_create_strategy(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.post(
        "/api/v1/strategies",
        json={
            "name": "My NIFTY Strategy",
            "mapping_template": {"action": "$.side", "symbol": "$.ticker"},
            "rules": {"max_position_size": 10, "allowed_symbols": ["NIFTY"]},
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My NIFTY Strategy"
    assert data["mapping_template"] == {"action": "$.side", "symbol": "$.ticker"}
    assert data["rules"] == {"max_position_size": 10, "allowed_symbols": ["NIFTY"]}
    assert data["mode"] == "paper"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_list_strategies(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.post(
        "/api/v1/strategies",
        json={"name": "Strategy A"},
        headers=headers,
    )
    await client.post(
        "/api/v1/strategies",
        json={"name": "Strategy B"},
        headers=headers,
    )
    resp = await client.get("/api/v1/strategies", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_strategy(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create_resp = await client.post(
        "/api/v1/strategies",
        json={"name": "My Strategy"},
        headers=headers,
    )
    strategy_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/strategies/{strategy_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "My Strategy"


@pytest.mark.asyncio
async def test_get_strategy_not_found(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.get(
        "/api/v1/strategies/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_strategy(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create_resp = await client.post(
        "/api/v1/strategies",
        json={
            "name": "Original Name",
            "rules": {"max_position_size": 5},
        },
        headers=headers,
    )
    strategy_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/strategies/{strategy_id}",
        json={
            "name": "Updated Name",
            "rules": {"max_position_size": 20},
            "mapping_template": {"action": "$.action"},
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Name"
    assert data["rules"] == {"max_position_size": 20}
    assert data["mapping_template"] == {"action": "$.action"}
    # mode should remain unchanged
    assert data["mode"] == "paper"


@pytest.mark.asyncio
async def test_update_strategy_partial(client):
    """Only provided fields should be updated."""
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create_resp = await client.post(
        "/api/v1/strategies",
        json={"name": "Original", "mode": "paper"},
        headers=headers,
    )
    strategy_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/strategies/{strategy_id}",
        json={"is_active": False},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is False
    assert data["name"] == "Original"  # unchanged


@pytest.mark.asyncio
async def test_delete_strategy(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create_resp = await client.post(
        "/api/v1/strategies",
        json={"name": "To Delete"},
        headers=headers,
    )
    strategy_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/strategies/{strategy_id}", headers=headers)
    assert resp.status_code == 204

    # Verify it's gone
    list_resp = await client.get("/api/v1/strategies", headers=headers)
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_rls_isolation_strategies(client):
    # User A creates a strategy
    tokens_a = await create_authenticated_user(client, email="a@test.com")
    headers_a = {"Authorization": f"Bearer {tokens_a['access_token']}"}
    create_resp = await client.post(
        "/api/v1/strategies",
        json={"name": "User A Strategy"},
        headers=headers_a,
    )
    strategy_id = create_resp.json()["id"]

    # User B should not see it
    tokens_b = await create_authenticated_user(client, email="b@test.com")
    headers_b = {"Authorization": f"Bearer {tokens_b['access_token']}"}
    resp = await client.get("/api/v1/strategies", headers=headers_b)
    assert resp.status_code == 200
    assert len(resp.json()) == 0

    # User B should not be able to get it by ID
    resp = await client.get(f"/api/v1/strategies/{strategy_id}", headers=headers_b)
    assert resp.status_code == 404

    # User B should not be able to update it
    resp = await client.put(
        f"/api/v1/strategies/{strategy_id}",
        json={"name": "Hacked"},
        headers=headers_b,
    )
    assert resp.status_code == 404

    # User B should not be able to delete it
    resp = await client.delete(f"/api/v1/strategies/{strategy_id}", headers=headers_b)
    assert resp.status_code == 404
