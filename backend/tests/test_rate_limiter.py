import pytest


@pytest.mark.asyncio
async def test_non_webhook_not_rate_limited(client):
    """Non-webhook paths should not be rate-limited."""
    for _ in range(100):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
