import pytest
from tests.conftest import create_authenticated_user


@pytest.mark.asyncio
async def test_create_broker_connection(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["broker_type"] == "zerodha"
    assert "credentials" not in data  # credentials must not be in response
    assert "id" in data
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_list_broker_connections(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    resp = await client.get("/api/v1/brokers", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_broker_connection(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create_resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    conn_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/brokers/{conn_id}", headers=headers)
    assert resp.status_code == 204

    # Verify it's gone
    list_resp = await client.get("/api/v1/brokers", headers=headers)
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_rls_isolation_broker_connections(client):
    # User A creates a connection
    tokens_a = await create_authenticated_user(client, email="a@test.com")
    headers_a = {"Authorization": f"Bearer {tokens_a['access_token']}"}
    await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers_a,
    )

    # User B should not see it
    tokens_b = await create_authenticated_user(client, email="b@test.com")
    headers_b = {"Authorization": f"Bearer {tokens_b['access_token']}"}
    resp = await client.get("/api/v1/brokers", headers=headers_b)
    assert resp.status_code == 200
    assert len(resp.json()) == 0
