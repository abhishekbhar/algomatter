# backend/tests/test_broker_pool.py
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
import uuid

from app.brokers.pool import BrokerPool


def _make_broker():
    broker = AsyncMock()
    broker.close = AsyncMock()
    return broker


@pytest.mark.asyncio
async def test_cache_miss_authenticates_and_caches(monkeypatch):
    pool = BrokerPool()
    broker = _make_broker()
    conn_id = str(uuid.uuid4())
    tenant_id = uuid.uuid4()

    async def fake_create(cid, tid):
        return broker

    monkeypatch.setattr(pool, "_create_broker", fake_create)

    result = await pool.get(conn_id, tenant_id)
    assert result is broker
    # second call returns same instance, _create_broker not called again
    result2 = await pool.get(conn_id, tenant_id)
    assert result2 is broker


@pytest.mark.asyncio
async def test_cache_hit_skips_create(monkeypatch):
    pool = BrokerPool()
    broker = _make_broker()
    conn_id = str(uuid.uuid4())
    tenant_id = uuid.uuid4()
    call_count = 0

    async def fake_create(cid, tid):
        nonlocal call_count
        call_count += 1
        return broker

    monkeypatch.setattr(pool, "_create_broker", fake_create)

    await pool.get(conn_id, tenant_id)
    await pool.get(conn_id, tenant_id)
    await pool.get(conn_id, tenant_id)

    assert call_count == 1


@pytest.mark.asyncio
async def test_evict_removes_from_pool_without_closing(monkeypatch):
    pool = BrokerPool()
    broker = _make_broker()
    conn_id = str(uuid.uuid4())
    tenant_id = uuid.uuid4()

    async def fake_create(cid, tid):
        return broker

    monkeypatch.setattr(pool, "_create_broker", fake_create)

    await pool.get(conn_id, tenant_id)
    await pool.evict(conn_id)

    # broker.close NOT called by evict (in-flight orders stay alive)
    broker.close.assert_not_called()
    # pool is empty — next get will call _create_broker again
    assert conn_id not in pool._pool


@pytest.mark.asyncio
async def test_close_all_closes_all_brokers(monkeypatch):
    pool = BrokerPool()
    brokers = [_make_broker(), _make_broker()]
    ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    tenant_id = uuid.uuid4()
    idx = 0

    async def fake_create(cid, tid):
        nonlocal idx
        b = brokers[idx]
        idx += 1
        return b

    monkeypatch.setattr(pool, "_create_broker", fake_create)

    for cid in ids:
        await pool.get(cid, tenant_id)

    await pool.close_all()

    for b in brokers:
        b.close.assert_awaited_once()
    assert pool._pool == {}


@pytest.mark.asyncio
async def test_thundering_herd_only_one_auth(monkeypatch):
    """Two concurrent gets on same key: only one _create_broker call."""
    pool = BrokerPool()
    broker = _make_broker()
    conn_id = str(uuid.uuid4())
    tenant_id = uuid.uuid4()
    call_count = 0

    async def fake_create(cid, tid):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)  # simulate auth latency
        return broker

    monkeypatch.setattr(pool, "_create_broker", fake_create)

    results = await asyncio.gather(
        pool.get(conn_id, tenant_id),
        pool.get(conn_id, tenant_id),
        pool.get(conn_id, tenant_id),
    )

    assert all(r is broker for r in results)
    assert call_count == 1


@pytest.mark.asyncio
async def test_exchange1_authenticate_does_not_call_token_endpoint(monkeypatch):
    """authenticate() must not make any HTTP calls — just load keys and create client."""
    from app.brokers.exchange1 import Exchange1Broker
    import cryptography.hazmat.primitives.serialization as ser
    from cryptography.hazmat.primitives.asymmetric import rsa
    import base64

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    der_bytes = private_key.private_bytes(
        encoding=ser.Encoding.DER,
        format=ser.PrivateFormat.PKCS8,
        encryption_algorithm=ser.NoEncryption(),
    )
    private_key_b64 = base64.b64encode(der_bytes).decode()

    broker = Exchange1Broker()
    post_calls = []

    async def mock_post(path, body=None, signed=False):
        post_calls.append(path)
        return {}

    monkeypatch.setattr(broker, "_post", mock_post)

    result = await broker.authenticate({
        "api_key": "test-key",
        "private_key": private_key_b64,
    })

    assert result is True
    assert "/openapi/v1/token" not in post_calls
    await broker.close()
