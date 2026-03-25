import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "database" in data
    assert "redis" in data
    assert data["database"] == "ok"
    assert data["redis"] == "ok"


@pytest.mark.asyncio
async def test_health_check_returns_503_on_db_failure(client, monkeypatch):
    """Health endpoint returns 503 when the database is unreachable."""
    import app.main as main_mod

    class _BrokenFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            raise RuntimeError("db down")

        async def __aexit__(self, *a):
            pass

    monkeypatch.setattr(main_mod, "async_session_factory", _BrokenFactory())

    resp = await client.get("/api/v1/health")
    assert resp.status_code == 503
    data = resp.json()
    assert data["database"] == "error"
    assert data["redis"] == "ok"
