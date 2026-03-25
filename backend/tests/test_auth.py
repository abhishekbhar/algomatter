import pytest


@pytest.mark.asyncio
async def test_signup_success(client):
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "securepass123"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_signup_duplicate_email(client):
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "securepass123"},
    )
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "otherpass123"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "securepass123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "securepass123"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "securepass123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "wrongpass"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code in [401, 403]  # HTTPBearer returns 403 when no token


@pytest.mark.asyncio
async def test_me_returns_user(client):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "securepass123"},
    )
    token = signup.json()["access_token"]
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_refresh_token_rotation(client):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "securepass123"},
    )
    refresh = signup.json()["refresh_token"]
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert new_tokens["refresh_token"] != refresh  # rotated


@pytest.mark.asyncio
async def test_rls_isolation(client):
    a = (
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "a@test.com", "password": "securepass123"},
        )
    ).json()
    b = (
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "b@test.com", "password": "securepass123"},
        )
    ).json()
    a_me = (
        await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {a['access_token']}"},
        )
    ).json()
    assert a_me["email"] == "a@test.com"
    b_me = (
        await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {b['access_token']}"},
        )
    ).json()
    assert b_me["email"] == "b@test.com"
