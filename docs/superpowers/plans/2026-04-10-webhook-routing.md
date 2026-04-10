# Webhook Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add slug-based per-strategy webhook targeting (`/api/v1/webhook/{token}/{slug}`), fix broken rule counters using Redis, and move live broker calls to ARQ background jobs.

**Architecture:** New `slug.py` generates + enforces unique slugs per tenant. New `executor.py` owns the execution pipeline (concurrent paper trades, ARQ-enqueued live orders). `router.py` is slimmed to auth + resolution only. `processor.py` gains Redis counter reads.

**Tech Stack:** Python/FastAPI, SQLAlchemy async, Alembic, Redis (arq + asyncio), ARQ, Next.js/Chakra UI, SWR

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/webhooks/slug.py` | Create | Slug generation and uniqueness enforcement |
| `backend/app/webhooks/processor.py` | Modify | Add `get_strategy_counts`, `increment_signals_today`, `update_position_count` |
| `backend/app/webhooks/executor.py` | Create | Execution pipeline: paper (concurrent) + live (ARQ), ARQ task definition |
| `backend/app/webhooks/router.py` | Modify | Slim handler + add `/{slug}` route |
| `backend/app/db/models.py` | Modify | Add `slug` column to `Strategy` |
| `backend/app/db/migrations/versions/a1b2c3d4e5f6_strategy_slug.py` | Create | Migration: add + backfill slug |
| `backend/app/strategies/schemas.py` | Modify | Add `slug` to `StrategyResponse` |
| `backend/app/strategies/router.py` | Modify | Generate slug on create; regenerate on rename |
| `backend/app/main.py` | Modify | Add ARQ pool to app lifespan |
| `backend/worker.py` | Modify | Register `execute_live_order_task` |
| `backend/tests/conftest.py` | Modify | Add `mock_arq_redis` to client fixture |
| `backend/tests/test_webhook_slug.py` | Create | Slug generation + uniqueness tests |
| `backend/tests/test_webhook_processor.py` | Create | Redis counter tests |
| `backend/tests/test_webhook_executor.py` | Create | Executor pipeline tests |
| `backend/tests/test_webhooks.py` | Modify | Add slug route tests |
| `frontend/lib/api/types.ts` | Modify | Add `slug` to `Strategy` interface |
| `frontend/app/(dashboard)/webhooks/page.tsx` | Modify | Add strategy URLs table |
| `frontend/app/(dashboard)/strategies/[id]/page.tsx` | Modify | Add Webhook URL card |

---

## Task 1: `slug.py` — Slug Generation and Uniqueness

**Files:**
- Create: `backend/app/webhooks/slug.py`
- Create: `backend/tests/test_webhook_slug.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_webhook_slug.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.webhooks.slug import generate_slug, ensure_unique_slug


def test_generate_slug_lowercases():
    assert generate_slug("NIFTY Momentum") == "nifty-momentum"


def test_generate_slug_strips_special_chars():
    assert generate_slug("BankNifty Short!") == "banknifty-short"


def test_generate_slug_collapses_hyphens():
    assert generate_slug("NIFTY--Long  Strategy") == "nifty-long-strategy"


def test_generate_slug_strips_leading_trailing_hyphens():
    assert generate_slug("!NIFTY!") == "nifty"


def test_generate_slug_handles_numbers():
    assert generate_slug("Strategy v2") == "strategy-v2"


@pytest.mark.asyncio
async def test_ensure_unique_slug_no_collision():
    session = AsyncMock(spec=AsyncSession)
    # Simulate no existing slugs found
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result

    import uuid
    slug = await ensure_unique_slug(session, uuid.uuid4(), "nifty-momentum")
    assert slug == "nifty-momentum"


@pytest.mark.asyncio
async def test_ensure_unique_slug_one_collision():
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["nifty-momentum"]
    session.execute.return_value = mock_result

    import uuid
    slug = await ensure_unique_slug(session, uuid.uuid4(), "nifty-momentum")
    assert slug == "nifty-momentum-2"


@pytest.mark.asyncio
async def test_ensure_unique_slug_two_collisions():
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        "nifty-momentum", "nifty-momentum-2"
    ]
    session.execute.return_value = mock_result

    import uuid
    slug = await ensure_unique_slug(session, uuid.uuid4(), "nifty-momentum")
    assert slug == "nifty-momentum-3"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && pytest tests/test_webhook_slug.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.webhooks.slug'`

- [ ] **Step 3: Implement `slug.py`**

```python
# backend/app/webhooks/slug.py
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Strategy


def generate_slug(name: str) -> str:
    """Convert a strategy name to a URL-safe slug.

    'NIFTY Momentum' → 'nifty-momentum'
    'BankNifty Short!' → 'banknifty-short'
    """
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


async def ensure_unique_slug(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    base_slug: str,
) -> str:
    """Return base_slug if unique within tenant, else base_slug-2, -3, …"""
    result = await session.execute(
        select(Strategy.slug).where(
            Strategy.tenant_id == tenant_id,
            Strategy.slug.like(f"{base_slug}%"),
        )
    )
    existing = set(result.scalars().all())

    if base_slug not in existing:
        return base_slug

    n = 2
    while True:
        candidate = f"{base_slug}-{n}"
        if candidate not in existing:
            return candidate
        n += 1
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend && pytest tests/test_webhook_slug.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/webhooks/slug.py backend/tests/test_webhook_slug.py
git commit -m "feat(webhooks): add slug generation and uniqueness enforcement"
```

---

## Task 2: DB Model + Migration

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/app/db/migrations/versions/a1b2c3d4e5f6_strategy_slug.py`

- [ ] **Step 1: Add `slug` to the `Strategy` model**

In `backend/app/db/models.py`, find the `Strategy` class and add the `slug` column after `name`:

```python
# After:
name: Mapped[str] = mapped_column(String(255), nullable=False)
# Add:
slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
```

Also update `__table_args__` to add the unique constraint:

```python
__table_args__ = (
    Index("ix_strategies_tenant_id", "tenant_id"),
    UniqueConstraint("tenant_id", "slug", name="uq_strategies_tenant_slug"),
)
```

`UniqueConstraint` is already imported (check top of file; if not, add to the SQLAlchemy imports line).

- [ ] **Step 2: Create the migration**

```python
# backend/app/db/migrations/versions/a1b2c3d4e5f6_strategy_slug.py
"""strategy_slug

Revision ID: a1b2c3d4e5f6
Revises: f2a3b4c5d6e7
Create Date: 2026-04-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add nullable column
    op.add_column("strategies", sa.Column("slug", sa.String(255), nullable=True))

    # 2. Backfill: generate slug from name, resolve collisions with window function
    op.execute("""
        WITH ranked AS (
            SELECT
                id,
                lower(trim(both '-' from regexp_replace(name, '[^a-zA-Z0-9]+', '-', 'g'))) AS base_slug,
                ROW_NUMBER() OVER (
                    PARTITION BY tenant_id,
                    lower(trim(both '-' from regexp_replace(name, '[^a-zA-Z0-9]+', '-', 'g')))
                    ORDER BY created_at
                ) AS rn
            FROM strategies
        )
        UPDATE strategies s
        SET slug = CASE
            WHEN r.rn = 1 THEN r.base_slug
            ELSE r.base_slug || '-' || r.rn::text
        END
        FROM ranked r
        WHERE s.id = r.id
    """)

    # 3. Make NOT NULL and add unique constraint
    op.alter_column("strategies", "slug", nullable=False)
    op.create_unique_constraint(
        "uq_strategies_tenant_slug", "strategies", ["tenant_id", "slug"]
    )
    op.create_index("ix_strategies_slug", "strategies", ["slug"])


def downgrade() -> None:
    op.drop_index("ix_strategies_slug", table_name="strategies")
    op.drop_constraint("uq_strategies_tenant_slug", "strategies", type_="unique")
    op.drop_column("strategies", "slug")
```

- [ ] **Step 3: Run migration**

```bash
cd backend && alembic upgrade head
```

Expected: `Running upgrade f2a3b4c5d6e7 -> a1b2c3d4e5f6, strategy_slug`

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/models.py backend/app/db/migrations/versions/a1b2c3d4e5f6_strategy_slug.py
git commit -m "feat(db): add slug column to strategies with backfill migration"
```

---

## Task 3: Strategies Schema + Router — Slug on Create/Rename

**Files:**
- Modify: `backend/app/strategies/schemas.py`
- Modify: `backend/app/strategies/router.py`
- Modify: `backend/tests/test_strategies.py`

- [ ] **Step 1: Add `slug` to `StrategyResponse`**

In `backend/app/strategies/schemas.py`, add `slug: str` to `StrategyResponse`:

```python
class StrategyResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str                          # ← add this
    broker_connection_id: uuid.UUID | None
    mode: str
    mapping_template: dict | None
    rules: dict
    is_active: bool
    created_at: datetime
```

- [ ] **Step 2: Write failing tests for slug in strategy responses**

In `backend/tests/test_strategies.py`, add to the existing test file:

```python
@pytest.mark.asyncio
async def test_create_strategy_returns_slug(client):
    tokens = await create_authenticated_user(client, "slugtest@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.post(
        "/api/v1/strategies",
        json={
            "name": "NIFTY Momentum",
            "mode": "paper",
            "mapping_template": None,
            "rules": {},
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "nifty-momentum"


@pytest.mark.asyncio
async def test_rename_strategy_regenerates_slug(client):
    tokens = await create_authenticated_user(client, "slugrename@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create = await client.post(
        "/api/v1/strategies",
        json={"name": "Old Name", "mode": "paper", "mapping_template": None, "rules": {}},
        headers=headers,
    )
    strategy_id = create.json()["id"]

    update = await client.put(
        f"/api/v1/strategies/{strategy_id}",
        json={"name": "New Name"},
        headers=headers,
    )
    assert update.json()["slug"] == "new-name"


@pytest.mark.asyncio
async def test_slug_collision_resolved(client):
    tokens = await create_authenticated_user(client, "slugcol@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    await client.post(
        "/api/v1/strategies",
        json={"name": "NIFTY Long", "mode": "paper", "mapping_template": None, "rules": {}},
        headers=headers,
    )
    resp2 = await client.post(
        "/api/v1/strategies",
        json={"name": "NIFTY Long", "mode": "paper", "mapping_template": None, "rules": {}},
        headers=headers,
    )
    assert resp2.json()["slug"] == "nifty-long-2"
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd backend && pytest tests/test_strategies.py::test_create_strategy_returns_slug -v
```

Expected: `KeyError: 'slug'` or validation error

- [ ] **Step 4: Update `create_strategy` handler in `backend/app/strategies/router.py`**

Add import at top of file:
```python
from app.webhooks.slug import generate_slug, ensure_unique_slug
```

In `create_strategy`, generate the slug before creating the `Strategy` object:

```python
async def create_strategy(body, request, current_user, session):
    tenant_id = uuid.UUID(current_user["user_id"])

    base_slug = generate_slug(body.name)
    slug = await ensure_unique_slug(session, tenant_id, base_slug)

    strategy = Strategy(
        tenant_id=tenant_id,
        name=body.name,
        slug=slug,                    # ← add
        broker_connection_id=body.broker_connection_id,
        mode=body.mode,
        mapping_template=body.mapping_template,
        rules=body.rules,
    )
    session.add(strategy)
    await session.commit()
    await session.refresh(strategy)
    # ... rest unchanged
```

And add `slug=strategy.slug` to all `StrategyResponse(...)` calls in this file (there are 4: create, list, get, update).

- [ ] **Step 5: Update `update_strategy` handler to regenerate slug on rename**

In the `update_strategy` handler, after loading the strategy from DB and before applying updates, add:

```python
update_data = body.model_dump(exclude_unset=True)

# Regenerate slug if name is changing
if "name" in update_data and update_data["name"] != strategy.name:
    base_slug = generate_slug(update_data["name"])
    update_data["slug"] = await ensure_unique_slug(session, tenant_id, base_slug)

for field, value in update_data.items():
    setattr(strategy, field, value)
```

- [ ] **Step 6: Run tests**

```bash
cd backend && pytest tests/test_strategies.py -v
```

Expected: all existing tests pass + 3 new slug tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/strategies/schemas.py backend/app/strategies/router.py backend/tests/test_strategies.py
git commit -m "feat(strategies): generate and return slug on create/rename"
```

---

## Task 4: `processor.py` — Redis Counter Functions

**Files:**
- Modify: `backend/app/webhooks/processor.py`
- Create: `backend/tests/test_webhook_processor.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_webhook_processor.py
import pytest
from datetime import date
from unittest.mock import AsyncMock

from app.webhooks.processor import (
    get_strategy_counts,
    increment_signals_today,
    update_position_count,
)


@pytest.mark.asyncio
async def test_get_strategy_counts_both_zero_when_keys_missing():
    redis = AsyncMock()
    redis.mget.return_value = [None, None]
    positions, signals = await get_strategy_counts(redis, "strat-123")
    assert positions == 0
    assert signals == 0


@pytest.mark.asyncio
async def test_get_strategy_counts_reads_existing_values():
    redis = AsyncMock()
    redis.mget.return_value = [b"3", b"7"]
    positions, signals = await get_strategy_counts(redis, "strat-123")
    assert positions == 3
    assert signals == 7


@pytest.mark.asyncio
async def test_get_strategy_counts_redis_unavailable_returns_zeros():
    redis = AsyncMock()
    redis.mget.side_effect = Exception("Redis connection failed")
    positions, signals = await get_strategy_counts(redis, "strat-123")
    assert positions == 0
    assert signals == 0


@pytest.mark.asyncio
async def test_increment_signals_today_sets_ttl():
    redis = AsyncMock()
    redis.incr.return_value = 1
    await increment_signals_today(redis, "strat-123")
    redis.incr.assert_called_once()
    redis.expireat.assert_called_once()


@pytest.mark.asyncio
async def test_update_position_count_buy_increments():
    redis = AsyncMock()
    await update_position_count(redis, "strat-123", action="BUY")
    redis.incr.assert_called_once_with("wh:positions:strat-123")


@pytest.mark.asyncio
async def test_update_position_count_sell_decrements_with_floor():
    redis = AsyncMock()
    redis.get.return_value = b"1"
    await update_position_count(redis, "strat-123", action="SELL")
    redis.decr.assert_called_once_with("wh:positions:strat-123")


@pytest.mark.asyncio
async def test_update_position_count_sell_does_not_go_below_zero():
    redis = AsyncMock()
    redis.get.return_value = b"0"
    await update_position_count(redis, "strat-123", action="SELL")
    redis.decr.assert_not_called()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && pytest tests/test_webhook_processor.py -v
```

Expected: `ImportError` — functions don't exist yet

- [ ] **Step 3: Add counter functions to `processor.py`**

Append to `backend/app/webhooks/processor.py` (keep `evaluate_rules` and `RuleResult` unchanged):

```python
import datetime
from zoneinfo import ZoneInfo


async def get_strategy_counts(redis, strategy_id: str) -> tuple[int, int]:
    """Return (open_positions, signals_today) for a strategy.

    Falls back to (0, 0) if Redis is unavailable.
    """
    try:
        today = datetime.date.today().strftime("%Y-%m-%d")
        positions_key = f"wh:positions:{strategy_id}"
        signals_key = f"wh:signals:{strategy_id}:{today}"
        positions, signals = await redis.mget(positions_key, signals_key)
        return (int(positions or 0), int(signals or 0))
    except Exception:
        return (0, 0)


async def increment_signals_today(redis, strategy_id: str) -> None:
    """Increment signals_today counter; auto-expires at midnight IST."""
    try:
        today = datetime.date.today().strftime("%Y-%m-%d")
        signals_key = f"wh:signals:{strategy_id}:{today}"
        await redis.incr(signals_key)

        # Set TTL to end of day in IST
        tz = ZoneInfo("Asia/Kolkata")
        now = datetime.datetime.now(tz)
        midnight = datetime.datetime.combine(
            now.date() + datetime.timedelta(days=1),
            datetime.time.min,
            tzinfo=tz,
        )
        await redis.expireat(signals_key, int(midnight.timestamp()))
    except Exception:
        pass  # Counter is best-effort; don't fail the webhook


async def update_position_count(redis, strategy_id: str, action: str) -> None:
    """Increment (BUY) or decrement (SELL, floor 0) the open_positions counter."""
    try:
        key = f"wh:positions:{strategy_id}"
        if action.upper() == "BUY":
            await redis.incr(key)
        elif action.upper() == "SELL":
            current = await redis.get(key)
            if current and int(current) > 0:
                await redis.decr(key)
    except Exception:
        pass  # Counter is best-effort; don't fail the webhook
```

- [ ] **Step 4: Run tests**

```bash
cd backend && pytest tests/test_webhook_processor.py -v
```

Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/webhooks/processor.py backend/tests/test_webhook_processor.py
git commit -m "feat(webhooks): add Redis-backed strategy counters for rule evaluation"
```

---

## Task 5: `executor.py` — Execution Pipeline

**Files:**
- Create: `backend/app/webhooks/executor.py`
- Create: `backend/tests/test_webhook_executor.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_webhook_executor.py
import uuid
from dataclasses import dataclass
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.webhooks.executor import SignalResult, execute
from app.webhooks.schemas import StandardSignal


def _make_strategy(
    strategy_id=None,
    mode="paper",
    mapping_template=None,
    rules=None,
    broker_connection_id=None,
):
    return {
        "id": str(strategy_id or uuid.uuid4()),
        "name": "Test Strategy",
        "mode": mode,
        "mapping_template": mapping_template or {
            "symbol": "$.ticker",
            "exchange": "NSE",
            "action": "$.action",
            "quantity": "$.qty",
            "order_type": "MARKET",
            "product_type": "INTRADAY",
        },
        "rules": rules or {},
        "broker_connection_id": str(broker_connection_id) if broker_connection_id else None,
    }


def _make_payload():
    return {"ticker": "RELIANCE", "action": "BUY", "qty": "10"}


@pytest.mark.asyncio
async def test_execute_mapping_error_logs_signal():
    strategy = _make_strategy(mapping_template={"symbol": "$.missing_field", "exchange": "NSE", "action": "$.action", "quantity": "$.qty", "order_type": "MARKET", "product_type": "INTRADAY"})
    redis = AsyncMock()
    redis.mget.return_value = [None, None]
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    arq_redis = AsyncMock()

    results = await execute([strategy], _make_payload(), redis, session, arq_redis)

    assert len(results) == 1
    assert results[0].rule_result == "mapping_error"
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_execute_rule_blocks_signal():
    strategy = _make_strategy(rules={"symbol_whitelist": ["TCS"]})
    redis = AsyncMock()
    redis.mget.return_value = [None, None]
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    arq_redis = AsyncMock()

    results = await execute([strategy], _make_payload(), redis, session, arq_redis)

    assert results[0].rule_result == "blocked_by_rule"
    assert "not in whitelist" in (results[0].rule_detail or "")


@pytest.mark.asyncio
async def test_execute_paper_mode_calls_paper_engine():
    strategy = _make_strategy(mode="paper")
    redis = AsyncMock()
    redis.mget.return_value = [None, None]
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    arq_redis = AsyncMock()

    with patch("app.webhooks.executor.execute_paper_trade", new_callable=AsyncMock) as mock_paper:
        mock_paper.return_value = "filled"
        with patch("app.webhooks.executor._get_active_paper_session", new_callable=AsyncMock) as mock_session:
            mock_session.return_value = MagicMock(id=uuid.uuid4())
            results = await execute([strategy], _make_payload(), redis, session, arq_redis)

    assert results[0].execution_result == "filled"


@pytest.mark.asyncio
async def test_execute_live_mode_enqueues_arq_job():
    broker_id = uuid.uuid4()
    strategy = _make_strategy(mode="live", broker_connection_id=broker_id)
    redis = AsyncMock()
    redis.mget.return_value = [None, None]
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    arq_redis = AsyncMock()

    results = await execute([strategy], _make_payload(), redis, session, arq_redis)

    assert results[0].execution_result == "queued"
    arq_redis.enqueue_job.assert_called_once()
    call_args = arq_redis.enqueue_job.call_args
    assert call_args.args[0] == "execute_live_order_task"


@pytest.mark.asyncio
async def test_execute_live_no_broker_connection_skips():
    strategy = _make_strategy(mode="live", broker_connection_id=None)
    redis = AsyncMock()
    redis.mget.return_value = [None, None]
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    arq_redis = AsyncMock()

    results = await execute([strategy], _make_payload(), redis, session, arq_redis)

    assert results[0].execution_result == "no_broker_connection"
    arq_redis.enqueue_job.assert_not_called()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && pytest tests/test_webhook_executor.py -v
```

Expected: `ImportError: cannot import name 'SignalResult' from 'app.webhooks.executor'`

- [ ] **Step 3: Implement `executor.py`**

```python
# backend/app/webhooks/executor.py
"""Webhook execution pipeline.

execute()                  — public entry point called from router
execute_live_order_task()  — ARQ background task for live broker orders
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.base import OrderRequest as BrokerOrderRequest
from app.brokers.factory import get_broker
from app.crypto.encryption import decrypt_credentials
from app.db.models import BrokerConnection, PaperTradingSession, WebhookSignal
from app.db.session import async_session_factory
from app.paper_trading.engine import execute_paper_trade
from app.webhooks.mapper import apply_mapping
from app.webhooks.processor import (
    evaluate_rules,
    get_strategy_counts,
    increment_signals_today,
    update_position_count,
)
from app.webhooks.schemas import StandardSignal


@dataclass
class SignalResult:
    strategy_id: str
    rule_result: str
    rule_detail: str | None = None
    execution_result: str | None = None
    execution_detail: dict | None = None
    parsed_signal: dict | None = None


async def _get_active_paper_session(session: AsyncSession, strategy_id: uuid.UUID):
    result = await session.execute(
        select(PaperTradingSession).where(
            PaperTradingSession.strategy_id == strategy_id,
            PaperTradingSession.status == "active",
        )
    )
    return result.scalar_one_or_none()


async def _execute_paper(
    session: AsyncSession,
    strategy: dict,
    signal: StandardSignal,
    tenant_id: uuid.UUID,
    signal_id: uuid.UUID,
) -> SignalResult:
    paper_session = await _get_active_paper_session(
        session, uuid.UUID(strategy["id"])
    )
    if not paper_session:
        return SignalResult(
            strategy_id=strategy["id"],
            rule_result="passed",
            parsed_signal=signal.model_dump(mode="json"),
            execution_result="no_active_session",
        )
    result = await execute_paper_trade(
        session, paper_session.id, tenant_id, signal, signal_id
    )
    return SignalResult(
        strategy_id=strategy["id"],
        rule_result="passed",
        parsed_signal=signal.model_dump(mode="json"),
        execution_result=result,
    )


async def execute(
    strategies: list[dict],
    payload: dict,
    redis,
    session: AsyncSession,
    arq_redis,
    tenant_id: uuid.UUID | None = None,
) -> list[SignalResult]:
    """Process a webhook payload against a list of strategies.

    Paper trades are executed concurrently.
    Live orders are enqueued as ARQ background jobs.
    All results are written as WebhookSignal records via the caller's session.
    """
    results: list[SignalResult] = []
    paper_tasks: list[asyncio.Task] = []
    paper_task_indices: list[int] = []

    # Phase 1: map, evaluate rules, enqueue live jobs
    for strategy in strategies:
        if not strategy.get("mapping_template"):
            continue

        # --- Mapping ---
        try:
            signal = apply_mapping(payload, strategy["mapping_template"])
        except Exception as exc:
            results.append(SignalResult(
                strategy_id=strategy["id"],
                rule_result="mapping_error",
                rule_detail=str(exc),
            ))
            continue

        # --- Rule evaluation ---
        open_positions, signals_today = await get_strategy_counts(
            redis, strategy["id"]
        )
        rule_out = evaluate_rules(
            signal,
            strategy["rules"] or {},
            open_positions=open_positions,
            signals_today=signals_today,
        )

        if not rule_out.passed:
            results.append(SignalResult(
                strategy_id=strategy["id"],
                rule_result="blocked_by_rule",
                rule_detail=rule_out.reason,
                parsed_signal=signal.model_dump(mode="json"),
            ))
            continue

        # --- Execution ---
        mode = strategy.get("mode", "log")

        if mode == "paper":
            signal_id = uuid.uuid4()
            idx = len(results)
            results.append(SignalResult(
                strategy_id=strategy["id"],
                rule_result="passed",
                parsed_signal=signal.model_dump(mode="json"),
            ))
            t = asyncio.ensure_future(
                _execute_paper(
                    session,
                    strategy,
                    signal,
                    tenant_id or uuid.uuid4(),
                    signal_id,
                )
            )
            paper_tasks.append(t)
            paper_task_indices.append(idx)

        elif mode == "live":
            if not strategy.get("broker_connection_id"):
                results.append(SignalResult(
                    strategy_id=strategy["id"],
                    rule_result="passed",
                    parsed_signal=signal.model_dump(mode="json"),
                    execution_result="no_broker_connection",
                ))
                continue

            signal_id = uuid.uuid4()
            job_payload = {
                "strategy_id": strategy["id"],
                "broker_connection_id": strategy["broker_connection_id"],
                "tenant_id": str(tenant_id),
                "signal": signal.model_dump(mode="json"),
                "webhook_signal_id": str(signal_id),
            }
            await arq_redis.enqueue_job(
                "execute_live_order_task",
                job_payload,
                _job_id=f"live-order:{signal_id}",
            )
            await increment_signals_today(redis, strategy["id"])
            results.append(SignalResult(
                strategy_id=strategy["id"],
                rule_result="passed",
                parsed_signal=signal.model_dump(mode="json"),
                execution_result="queued",
                execution_detail={"job_id": f"live-order:{signal_id}"},
            ))

        else:
            # "log" mode — signal recorded, no execution
            results.append(SignalResult(
                strategy_id=strategy["id"],
                rule_result="passed",
                parsed_signal=signal.model_dump(mode="json"),
                execution_result=None,
            ))

    # Phase 2: run paper trades concurrently
    if paper_tasks:
        paper_results = await asyncio.gather(*paper_tasks, return_exceptions=True)
        for idx, paper_result in zip(paper_task_indices, paper_results):
            if isinstance(paper_result, Exception):
                results[idx].execution_result = "error"
                results[idx].execution_detail = {"error": str(paper_result)}
            else:
                results[idx].execution_result = paper_result.execution_result
                results[idx].execution_detail = paper_result.execution_detail
                # Update Redis position counter for successful paper trades
                if paper_result.execution_result == "filled":
                    signal_data = results[idx].parsed_signal or {}
                    await update_position_count(
                        redis,
                        results[idx].strategy_id,
                        signal_data.get("action", ""),
                    )
                    await increment_signals_today(redis, results[idx].strategy_id)

    return results


# ---------------------------------------------------------------------------
# ARQ background task — live broker order execution
# ---------------------------------------------------------------------------

async def execute_live_order_task(ctx: dict, job_payload: dict) -> dict:
    """ARQ task: place a live broker order and update the WebhookSignal log."""
    strategy_id = job_payload["strategy_id"]
    broker_connection_id = job_payload["broker_connection_id"]
    tenant_id = uuid.UUID(job_payload["tenant_id"])
    signal_data = job_payload["signal"]
    webhook_signal_id = uuid.UUID(job_payload["webhook_signal_id"])

    signal = StandardSignal(**{
        k: (Decimal(str(v)) if k in ("quantity", "price", "trigger_price", "take_profit", "stop_loss") and v is not None else v)
        for k, v in signal_data.items()
    })

    async with async_session_factory() as session:
        # Fetch broker connection
        bc_result = await session.execute(
            select(BrokerConnection).where(
                BrokerConnection.id == uuid.UUID(broker_connection_id),
                BrokerConnection.tenant_id == tenant_id,
            )
        )
        bc = bc_result.scalar_one_or_none()
        if not bc:
            return {"error": "broker_connection_not_found"}

        creds = decrypt_credentials(tenant_id, bc.credentials)
        broker = await get_broker(bc.broker_type, creds)

        execution_result = "broker_error"
        execution_detail: dict = {}

        try:
            order_req = BrokerOrderRequest(
                symbol=signal.symbol,
                exchange=signal.exchange,
                action=signal.action,
                quantity=signal.quantity,
                order_type=signal.order_type or "MARKET",
                price=signal.price or Decimal("0"),
                product_type=signal.product_type or "DELIVERY",
                trigger_price=signal.trigger_price,
                leverage=signal.leverage,
                position_model=signal.position_model,
                position_side=signal.position_side,
                take_profit=signal.take_profit,
                stop_loss=signal.stop_loss,
            )
            order_response = await broker.place_order(order_req)
            execution_result = order_response.status
            execution_detail = order_response.model_dump(mode="json")
        except Exception as exc:
            execution_result = "broker_error"
            execution_detail = {"error": str(exc)}
        finally:
            await broker.close()

        # Update WebhookSignal log record
        ws_result = await session.execute(
            select(WebhookSignal).where(WebhookSignal.id == webhook_signal_id)
        )
        ws = ws_result.scalar_one_or_none()
        if ws:
            ws.execution_result = execution_result
            ws.execution_detail = execution_detail
            await session.commit()

        # Update Redis position counter
        redis = ctx.get("redis")
        if redis and execution_result in ("filled", "accepted"):
            await update_position_count(redis, strategy_id, signal.action)
            today_str = __import__("datetime").date.today().strftime("%Y-%m-%d")
            await increment_signals_today(redis, strategy_id)

    return {"execution_result": execution_result}
```

- [ ] **Step 4: Run tests**

```bash
cd backend && pytest tests/test_webhook_executor.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/webhooks/executor.py backend/tests/test_webhook_executor.py
git commit -m "feat(webhooks): add execution pipeline with concurrent paper and ARQ live orders"
```

---

## Task 6: `router.py` — Slim Handlers + Slug Route

**Files:**
- Modify: `backend/app/webhooks/router.py`
- Modify: `backend/tests/test_webhooks.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Update `conftest.py` to mock `arq_redis`**

In the `client` fixture in `backend/tests/conftest.py`, add the arq mock alongside the existing redis mock:

```python
@pytest_asyncio.fixture
async def client():
    """Async test client for FastAPI."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    mock_redis = AsyncMock()
    mock_redis.mget.return_value = [None, None]   # ← add default for counter reads
    mock_arq_redis = AsyncMock()                   # ← add
    app.state.redis = mock_redis
    app.state.arq_redis = mock_arq_redis           # ← add
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

- [ ] **Step 2: Add slug route tests to `test_webhooks.py`**

```python
@pytest.mark.asyncio
async def test_webhook_slug_targets_single_strategy(client):
    tokens = await create_authenticated_user(client, "slug1@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    config = await client.get("/api/v1/webhooks/config", headers=headers)
    token = config.json()["token"]

    # Create two strategies
    await client.post(
        "/api/v1/strategies",
        json={"name": "NIFTY Long", "mode": "log", "mapping_template": {
            "symbol": "$.ticker", "exchange": "NSE", "action": "$.action",
            "quantity": "$.qty", "order_type": "MARKET", "product_type": "INTRADAY",
        }, "rules": {}},
        headers=headers,
    )
    await client.post(
        "/api/v1/strategies",
        json={"name": "NIFTY Short", "mode": "log", "mapping_template": {
            "symbol": "$.ticker", "exchange": "NSE", "action": "$.action",
            "quantity": "$.qty", "order_type": "MARKET", "product_type": "INTRADAY",
        }, "rules": {}},
        headers=headers,
    )

    resp = await client.post(
        f"/api/v1/webhook/{token}/nifty-long",
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
```

- [ ] **Step 3: Run new tests to confirm they fail**

```bash
cd backend && pytest tests/test_webhooks.py::test_webhook_slug_targets_single_strategy -v
```

Expected: `404` because the route doesn't exist yet

- [ ] **Step 4: Rewrite `router.py`**

Replace the contents of `backend/app/webhooks/router.py` with:

```python
import json
import secrets
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_session, get_tenant_session
from app.db.models import Strategy, User, WebhookSignal
from app.webhooks.executor import SignalResult, execute

# ---------------------------------------------------------------------------
# Public router – webhook ingestion (token-based auth, no JWT)
# ---------------------------------------------------------------------------
webhook_public_router = APIRouter(tags=["webhooks"])

_STRATEGY_CACHE_TTL = 60  # seconds


async def _resolve_user(token: str, session: AsyncSession) -> User:
    result = await session.execute(select(User).where(User.webhook_token == token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user


async def _get_active_strategies(redis, session: AsyncSession, tenant_id: uuid.UUID) -> list[dict]:
    """Return all active strategies for tenant, Redis-cached (60 s TTL)."""
    cache_key = f"strategies:active:{tenant_id}"
    try:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    result = await session.execute(
        select(Strategy).where(
            Strategy.tenant_id == tenant_id,
            Strategy.is_active.is_(True),
        )
    )
    strategies = result.scalars().all()
    payload = [
        {
            "id": str(s.id),
            "mapping_template": s.mapping_template,
            "mode": s.mode,
            "broker_connection_id": str(s.broker_connection_id) if s.broker_connection_id else None,
            "rules": s.rules,
            "name": s.name,
        }
        for s in strategies
    ]
    try:
        await redis.set(cache_key, json.dumps(payload), ex=_STRATEGY_CACHE_TTL)
    except Exception:
        pass
    return payload


async def _write_signal_logs(
    session: AsyncSession,
    results: list[SignalResult],
    tenant_id: uuid.UUID,
    raw_payload: dict,
    start_time: float,
) -> None:
    for r in results:
        ws = WebhookSignal(
            tenant_id=tenant_id,
            strategy_id=uuid.UUID(r.strategy_id),
            raw_payload=raw_payload,
            parsed_signal=r.parsed_signal,
            rule_result=r.rule_result,
            rule_detail=r.rule_detail,
            execution_result=r.execution_result,
            execution_detail=r.execution_detail,
            processing_ms=int((time.perf_counter() - start_time) * 1000),
        )
        session.add(ws)
    await session.commit()


@webhook_public_router.post("/api/v1/webhook/{token}")
async def receive_webhook(
    token: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    user = await _resolve_user(token, session)

    body = await request.body()
    from app.config import settings
    if len(body) > settings.max_webhook_payload_bytes:
        raise HTTPException(status_code=413, detail="Payload too large")
    payload: dict = json.loads(body)

    start_time = time.perf_counter()
    redis = request.app.state.redis
    arq_redis = request.app.state.arq_redis
    strategies = await _get_active_strategies(redis, session, user.id)

    results = await execute(strategies, payload, redis, session, arq_redis, tenant_id=user.id)
    await _write_signal_logs(session, results, user.id, payload, start_time)

    return {"received": True, "signals_processed": len(results)}


@webhook_public_router.post("/api/v1/webhook/{token}/{slug}")
async def receive_webhook_targeted(
    token: str,
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    user = await _resolve_user(token, session)

    body = await request.body()
    from app.config import settings
    if len(body) > settings.max_webhook_payload_bytes:
        raise HTTPException(status_code=413, detail="Payload too large")
    payload: dict = json.loads(body)

    # Resolve single strategy by slug
    result = await session.execute(
        select(Strategy).where(
            Strategy.tenant_id == user.id,
            Strategy.slug == slug,
            Strategy.is_active.is_(True),
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    strategy_dict = {
        "id": str(strategy.id),
        "mapping_template": strategy.mapping_template,
        "mode": strategy.mode,
        "broker_connection_id": str(strategy.broker_connection_id) if strategy.broker_connection_id else None,
        "rules": strategy.rules,
        "name": strategy.name,
    }

    start_time = time.perf_counter()
    redis = request.app.state.redis
    arq_redis = request.app.state.arq_redis

    results = await execute([strategy_dict], payload, redis, session, arq_redis, tenant_id=user.id)
    await _write_signal_logs(session, results, user.id, payload, start_time)

    return {"received": True, "signals_processed": len(results)}


# ---------------------------------------------------------------------------
# Authenticated router – config & signal listing (unchanged)
# ---------------------------------------------------------------------------
webhook_config_router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@webhook_config_router.get("/config")
async def get_webhook_config(
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/api/v1/webhook/{user.webhook_token}"
    return {"webhook_url": webhook_url, "token": user.webhook_token}


@webhook_config_router.post("/config/regenerate-token")
async def regenerate_webhook_token(
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.webhook_token = secrets.token_urlsafe(32)
    await session.commit()
    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/api/v1/webhook/{user.webhook_token}"
    return {"webhook_url": webhook_url, "token": user.webhook_token}


@webhook_config_router.get("/signals")
async def list_signals(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    strat_result = await session.execute(
        select(Strategy).where(Strategy.tenant_id == tenant_id)
    )
    strat_map = {s.id: s.name for s in strat_result.scalars().all()}

    total_q = await session.execute(
        select(func.count()).select_from(WebhookSignal).where(WebhookSignal.tenant_id == tenant_id)
    )
    total = total_q.scalar() or 0

    result = await session.execute(
        select(WebhookSignal)
        .where(WebhookSignal.tenant_id == tenant_id)
        .order_by(WebhookSignal.received_at.desc())
        .offset(offset)
        .limit(limit)
    )
    signals = result.scalars().all()
    return {
        "signals": [_signal_to_dict(s, strat_map) for s in signals],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@webhook_config_router.get("/signals/strategy/{strategy_id}")
async def list_strategy_signals(
    strategy_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    strat_result = await session.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.tenant_id == tenant_id,
        )
    )
    strategy = strat_result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    strat_map = {strategy.id: strategy.name}
    result = await session.execute(
        select(WebhookSignal)
        .where(
            WebhookSignal.tenant_id == tenant_id,
            WebhookSignal.strategy_id == strategy_id,
        )
        .order_by(WebhookSignal.received_at.desc())
    )
    signals = result.scalars().all()
    return [_signal_to_dict(s, strat_map) for s in signals]


def _signal_to_dict(s: WebhookSignal, strat_map: dict) -> dict:
    return {
        "id": str(s.id),
        "strategy_id": str(s.strategy_id) if s.strategy_id else None,
        "strategy_name": strat_map.get(s.strategy_id, "Unknown"),
        "received_at": s.received_at.isoformat() if s.received_at else None,
        "raw_payload": s.raw_payload,
        "parsed_signal": s.parsed_signal,
        "status": s.rule_result,
        "error_message": s.rule_detail,
        "execution_result": s.execution_result,
        "execution_detail": s.execution_detail,
        "processing_ms": s.processing_ms,
    }
```

- [ ] **Step 5: Run full webhook test suite**

```bash
cd backend && pytest tests/test_webhooks.py tests/test_webhook_live_dispatch.py -v
```

Expected: all existing tests pass + 3 new slug tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/webhooks/router.py backend/tests/test_webhooks.py backend/tests/conftest.py
git commit -m "feat(webhooks): add slug-targeted route and refactor router to delegate to executor"
```

---

## Task 7: `main.py` + `worker.py` — ARQ Pool and Task Registration

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/worker.py`

- [ ] **Step 1: Add ARQ pool to `main.py` lifespan**

In `backend/app/main.py`, update the imports and lifespan:

```python
from arq.connections import create_pool, RedisSettings  # ← add

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    app.state.redis = redis_pool
    arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))  # ← add
    app.state.arq_redis = arq_pool                                             # ← add
    yield
    # shutdown
    await redis_pool.aclose()
    await arq_pool.aclose()                                                    # ← add
```

- [ ] **Step 2: Register the ARQ task in `worker.py`**

```python
# backend/worker.py
from arq import cron
from arq.connections import RedisSettings

from app.backtesting.tasks import run_backtest_task
from app.config import settings
from app.historical.tasks import daily_data_fetch
from app.webhooks.executor import execute_live_order_task   # ← add


class WorkerSettings:
    functions = [run_backtest_task, execute_live_order_task]  # ← add
    cron_jobs = [cron(daily_data_fetch, hour=6, minute=0)]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 100
    job_timeout = 3600
    keep_result_forever = False
    result_ttl = 86400
```

- [ ] **Step 3: Verify the app starts without errors**

```bash
cd backend && ALGOMATTER_SKIP_SECRET_CHECK=1 python -c "
import asyncio
from app.main import app
print('App imports OK')
from app.webhooks.executor import execute_live_order_task
print('execute_live_order_task importable:', execute_live_order_task.__name__)
"
```

Expected:
```
App imports OK
execute_live_order_task importable: execute_live_order_task
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py backend/worker.py
git commit -m "feat(worker): register execute_live_order_task and add ARQ pool to app lifespan"
```

---

## Task 8: Frontend — Types and Webhooks Page Strategy URLs Table

**Files:**
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/app/(dashboard)/webhooks/page.tsx`

- [ ] **Step 1: Add `slug` to the `Strategy` type**

In `frontend/lib/api/types.ts`, update the `Strategy` interface:

```typescript
export interface Strategy {
  id: string;
  name: string;
  slug: string;           // ← add
  broker_connection_id: string | null;
  mode: string;
  mapping_template: Record<string, unknown> | null;
  rules: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
}
```

- [ ] **Step 2: Add the strategy URLs table to the webhooks page**

In `frontend/app/(dashboard)/webhooks/page.tsx`, add the following imports at the top (alongside existing ones):

```typescript
import { useStrategies } from "@/lib/hooks/useApi";
import { Table, Thead, Tbody, Tr, Th, Td, TableContainer } from "@chakra-ui/react";
```

Then inside `WebhooksPage`, add after the existing `useWebhookConfig` and `useWebhookSignals` hooks:

```typescript
const { data: strategies } = useStrategies();
```

Update the `webhookUrl` section to label it "Broadcast URL":

```typescript
// Replace the existing Card that shows the webhook URL with:
<Card mb={6}>
  <CardHeader>
    <Heading size="sm">Broadcast URL</Heading>
    <Text fontSize="sm" color="gray.500" mt={1}>
      Triggers all active strategies simultaneously
    </Text>
  </CardHeader>
  <CardBody>
    <HStack>
      <Code fontSize="sm" flex={1} p={2} borderRadius="md" overflowX="auto">
        {webhookUrl}
      </Code>
      <IconButton
        aria-label="Copy broadcast URL"
        icon={hasCopied ? <span>✓</span> : <span>⎘</span>}
        onClick={onCopy}
        size="sm"
      />
    </HStack>
    <Button size="sm" mt={3} colorScheme="red" variant="outline" onClick={onOpen}>
      Rotate Token
    </Button>
  </CardBody>
</Card>
```

Then add the strategy URLs table below the broadcast card, before the signal log:

```typescript
{strategies && strategies.length > 0 && (
  <Card mb={6}>
    <CardHeader>
      <Heading size="sm">Strategy URLs</Heading>
      <Text fontSize="sm" color="gray.500" mt={1}>
        Target a single strategy by appending its slug to the broadcast URL
      </Text>
    </CardHeader>
    <CardBody p={0}>
      <TableContainer>
        <Table size="sm">
          <Thead>
            <Tr>
              <Th>Strategy</Th>
              <Th>Slug</Th>
              <Th>URL</Th>
              <Th />
            </Tr>
          </Thead>
          <Tbody>
            {strategies.map((s) => {
              const stratUrl = config
                ? `${window.location.origin}/api/v1/webhook/${config.token}/${s.slug}`
                : "";
              return (
                <StrategyUrlRow key={s.id} strategy={s} url={stratUrl} />
              );
            })}
          </Tbody>
        </Table>
      </TableContainer>
    </CardBody>
  </Card>
)}
```

Add the `StrategyUrlRow` component above the `WebhooksPage` default export:

```typescript
function StrategyUrlRow({ strategy, url }: { strategy: { name: string; slug: string }; url: string }) {
  const { onCopy, hasCopied } = useClipboard(url);
  return (
    <Tr>
      <Td fontWeight="medium">{strategy.name}</Td>
      <Td><Code fontSize="xs">{strategy.slug}</Code></Td>
      <Td>
        <Code fontSize="xs" maxW="320px" display="block" isTruncated>
          {url}
        </Code>
      </Td>
      <Td>
        <IconButton
          aria-label="Copy strategy URL"
          icon={hasCopied ? <span>✓</span> : <span>⎘</span>}
          onClick={onCopy}
          size="xs"
          variant="ghost"
        />
      </Td>
    </Tr>
  );
}
```

- [ ] **Step 3: Verify the frontend builds**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: no TypeScript errors, build completes successfully

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api/types.ts frontend/app/\(dashboard\)/webhooks/page.tsx
git commit -m "feat(frontend): add strategy URLs table to webhooks page"
```

---

## Task 9: Frontend — Strategy Detail Page Webhook URL Card

**Files:**
- Modify: `frontend/app/(dashboard)/strategies/[id]/page.tsx`

- [ ] **Step 1: Add `useWebhookConfig` import to strategy detail page**

In `frontend/app/(dashboard)/strategies/[id]/page.tsx`, add `useWebhookConfig` to the existing import from `@/lib/hooks/useApi`:

```typescript
import {
  useStrategy,
  useStrategySignals,
  usePaperSessions,
  useStrategyMetrics,
  useStrategyEquityCurve,
  useWebhookConfig,      // ← add
} from "@/lib/hooks/useApi";
```

Also add `useClipboard` to the Chakra UI imports:

```typescript
import {
  Box, Heading, Text, Flex, Button, Tabs, TabList, TabPanels, Tab, TabPanel,
  Badge, useColorModeValue, Spinner, Center,
  Card, CardHeader, CardBody, Code, HStack, IconButton, useClipboard,  // ← add Card, CardHeader, CardBody, Code, HStack, IconButton, useClipboard
} from "@chakra-ui/react";
```

- [ ] **Step 2: Add the Webhook URL card**

Inside the page component, add the hook call after the existing hooks:

```typescript
const { data: webhookConfig } = useWebhookConfig();
```

Then add the Webhook URL card just before the `<Tabs>` component (place it between the strategy header and the tabs):

```typescript
{/* Webhook URL card */}
{strategy && webhookConfig && (
  <WebhookUrlCard
    token={webhookConfig.token}
    slug={strategy.slug}
  />
)}

<Tabs ...>
```

Add the `WebhookUrlCard` component above the page default export:

```typescript
function WebhookUrlCard({ token, slug }: { token: string; slug: string }) {
  const url = `${typeof window !== "undefined" ? window.location.origin : ""}/api/v1/webhook/${token}/${slug}`;
  const { onCopy, hasCopied } = useClipboard(url);

  return (
    <Card mb={6}>
      <CardHeader pb={2}>
        <Heading size="sm">Webhook URL</Heading>
      </CardHeader>
      <CardBody pt={0}>
        <HStack>
          <Code fontSize="sm" flex={1} p={2} borderRadius="md" overflowX="auto">
            {url}
          </Code>
          <IconButton
            aria-label="Copy webhook URL"
            icon={hasCopied ? <span>✓</span> : <span>⎘</span>}
            onClick={onCopy}
            size="sm"
          />
        </HStack>
        <Text fontSize="xs" color="gray.500" mt={2}>
          Slug: <Code fontSize="xs">{slug}</Code>
        </Text>
      </CardBody>
    </Card>
  );
}
```

- [ ] **Step 3: Verify the frontend builds**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: no TypeScript errors

- [ ] **Step 4: Run the full backend test suite to confirm nothing regressed**

```bash
cd backend && pytest tests/ -v --tb=short 2>&1 | tail -40
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add frontend/app/\(dashboard\)/strategies/\[id\]/page.tsx
git commit -m "feat(frontend): add Webhook URL card to strategy detail page"
```

- [ ] **Step 6: Push**

```bash
git push origin main
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `/api/v1/webhook/{token}/{slug}` route | Task 6 |
| Slug auto-generated from name | Task 1, 3 |
| Collision resolution `nifty-momentum-2` | Task 1 |
| Slug regenerated on rename | Task 3 |
| `open_positions` / `signals_today` Redis counters | Task 4 |
| Fan-out concurrent for paper | Task 5 |
| Live orders → ARQ background job | Task 5, 7 |
| ARQ pool in app lifespan | Task 7 |
| `execute_live_order_task` registered in worker | Task 7 |
| `slug` on `StrategyResponse` | Task 3 |
| Webhooks page strategy URLs table | Task 8 |
| Strategy detail Webhook URL card | Task 9 |
| `useWebhookConfig` shared between pages | Task 9 (existing hook reused) |
| DB migration with backfill | Task 2 |

All spec requirements covered. ✓
