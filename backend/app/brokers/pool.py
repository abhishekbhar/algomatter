# backend/app/brokers/pool.py
"""Per-process broker connection pool.

Caches authenticated BrokerAdapter instances keyed by broker_connection_id.
Each uvicorn worker has its own pool — no cross-process sharing.

Lifecycle
---------
- get()      : cache hit → return; miss → auth + store + return
- evict()    : remove from cache (does NOT close — in-flight orders stay alive)
- close_all(): close all cached brokers and clear pool (called in lifespan shutdown)
"""
from __future__ import annotations

import asyncio
import uuid

import structlog

from app.brokers.base import BrokerAdapter
from app.brokers.factory import get_broker
from app.crypto.encryption import decrypt_credentials
from app.db.models import BrokerConnection
from app.db.session import async_session_factory
from sqlalchemy import select

logger = structlog.get_logger(__name__)


class BrokerPool:
    def __init__(self) -> None:
        self._pool: dict[str, BrokerAdapter] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, broker_connection_id: str) -> asyncio.Lock:
        if broker_connection_id not in self._locks:
            self._locks[broker_connection_id] = asyncio.Lock()
        return self._locks[broker_connection_id]

    async def _create_broker(self, broker_connection_id: str, tenant_id: uuid.UUID) -> BrokerAdapter:
        """Fetch credentials from DB, decrypt, authenticate, return broker."""
        async with async_session_factory() as session:
            bc_result = await session.execute(
                select(BrokerConnection).where(
                    BrokerConnection.id == uuid.UUID(broker_connection_id),
                    BrokerConnection.tenant_id == tenant_id,
                )
            )
            bc = bc_result.scalar_one_or_none()
            if not bc:
                raise RuntimeError(f"broker_connection_not_found: {broker_connection_id}")
            creds = decrypt_credentials(tenant_id, bc.credentials)
            broker_type = bc.broker_type

        broker = await get_broker(broker_type, creds)
        logger.info("broker_pool_created", broker_connection_id=broker_connection_id)
        return broker

    async def get(self, broker_connection_id: str, tenant_id: uuid.UUID) -> BrokerAdapter:
        """Return cached broker, or authenticate and cache a new one."""
        if broker_connection_id in self._pool:
            return self._pool[broker_connection_id]

        lock = self._get_lock(broker_connection_id)
        async with lock:
            # double-check after acquiring lock
            if broker_connection_id in self._pool:
                return self._pool[broker_connection_id]

            broker = await self._create_broker(broker_connection_id, tenant_id)
            self._pool[broker_connection_id] = broker
            return broker

    async def evict(self, broker_connection_id: str) -> None:
        """Remove broker from pool without closing it (in-flight orders stay alive)."""
        self._pool.pop(broker_connection_id, None)
        logger.info("broker_pool_evicted", broker_connection_id=broker_connection_id)

    async def close_all(self) -> None:
        """Close all cached brokers. Called on app shutdown."""
        for broker in self._pool.values():
            await broker.close()
        self._pool.clear()
        self._locks.clear()
        logger.info("broker_pool_closed_all")


# Module-level singleton — one per uvicorn worker process.
broker_pool = BrokerPool()
