import pytest
from app.events.bus import EventBus


@pytest.mark.asyncio
async def test_publish_and_read_event(redis_client):
    bus = EventBus(redis_client)
    await bus.publish("webhook.received", {
        "tenant_id": "abc", "signal_id": "123", "symbol": "RELIANCE"
    })
    events = await bus.read_recent("webhook.received", count=1)
    assert len(events) == 1
    assert events[0]["symbol"] == "RELIANCE"


@pytest.mark.asyncio
async def test_stream_max_length(redis_client):
    bus = EventBus(redis_client, max_length=5)
    for i in range(10):
        await bus.publish("test.stream", {"i": str(i)})
    events = await bus.read_recent("test.stream", count=100)
    assert len(events) <= 6  # approximate trimming
