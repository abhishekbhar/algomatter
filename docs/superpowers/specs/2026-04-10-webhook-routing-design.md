# Webhook Routing Architecture — Design Spec

_Date: 2026-04-10_
_Status: Approved_

---

## Problem Statement

The current webhook system uses a single URL per user (`/api/v1/webhook/{token}`) that fans out to all active strategies sequentially. This has three concrete problems:

1. **No targeting** — a signal intended for one strategy triggers all strategies.
2. **Broken rules** — `open_positions` and `signals_today` are hardcoded to `0`, so `max_open_positions` and `max_signals_per_day` rules never block anything.
3. **Blocking execution** — live broker calls run sequentially inside the HTTP request, tying up a uvicorn worker for several seconds per signal.

---

## Solution Overview

- Add an optional `/{slug}` path segment to the existing webhook URL.
- Auto-generate a URL-safe slug from each strategy's name.
- Fix rule counters using Redis keys scoped per strategy.
- Execute paper trades concurrently; enqueue live orders as ARQ background jobs.
- Surface per-strategy URLs on both the webhooks page and strategy detail page.

---

## URL Scheme

```
POST /api/v1/webhook/{token}          → broadcast: fans out to all active strategies
POST /api/v1/webhook/{token}/{slug}   → targeted: triggers exactly one strategy
```

Both routes share the same auth and execution pipeline. The only difference is how the strategy list is resolved after authentication.

**Examples:**
```
https://algomatter.in/api/v1/webhook/abc123xyz              ← broadcast
https://algomatter.in/api/v1/webhook/abc123xyz/nifty-momentum  ← targeted
```

Rotating the token (via `/api/v1/webhooks/config/regenerate-token`) invalidates both forms simultaneously. No per-strategy token management.

---

## Section 1 — Data Model

### Strategy model change

```
Strategy
  + slug: str, indexed, unique per (tenant_id, slug)
```

**Slug generation rules:**
- Derived from `name` at strategy creation and on rename
- Lowercase, spaces → hyphens, non-alphanumeric characters stripped
- Examples: "NIFTY Momentum" → `nifty-momentum`, "BankNifty Short!" → `banknifty-short`
- Collision resolution scoped per tenant: `nifty-momentum`, `nifty-momentum-2`, `nifty-momentum-3`, …
- Slug is system-generated and read-only to the user

### `StrategyResponse` schema change

Add `slug: str` to the existing response schema so the frontend can construct per-strategy URLs client-side.

### Migration

- New Alembic migration: add `slug VARCHAR NOT NULL` column with composite unique constraint `(tenant_id, slug)`
- Backfill existing strategies: generate slug from `name`, resolve collisions in insertion order

---

## Section 2 — Backend Architecture

```
backend/app/webhooks/
  router.py       ← HTTP layer: auth, slug resolution, delegates to executor
  processor.py    ← Rule evaluation + Redis counter reads (extend existing)
  executor.py     ← NEW: concurrent paper execution + ARQ enqueue for live
  slug.py         ← NEW: slug generation and uniqueness enforcement
  mapper.py       ← unchanged
  schemas.py      ← unchanged
```

### `router.py`

Two route handlers, both thin:

```
POST /api/v1/webhook/{token}
  1. Resolve user by token (401 if not found)
  2. Fetch all active strategies for tenant (Redis-cached, 60s TTL)
  3. Call executor.execute(strategies, payload, redis, session)
  4. Return {"received": True, "signals_processed": N}

POST /api/v1/webhook/{token}/{slug}
  1. Resolve user by token (401 if not found)
  2. Fetch single strategy by (tenant_id, slug) (404 if not found or inactive)
  3. Call executor.execute([strategy], payload, redis, session)
  4. Return {"received": True, "signals_processed": N}
```

Router has no knowledge of rule evaluation or execution mode.

### `processor.py` (extended)

New function added alongside existing `evaluate_rules()`:

```python
async def get_strategy_counts(redis, strategy_id: str) -> tuple[int, int]:
    """Returns (open_positions, signals_today) for a strategy."""
    today = date.today().strftime("%Y-%m-%d")
    positions_key = f"wh:positions:{strategy_id}"
    signals_key   = f"wh:signals:{strategy_id}:{today}"
    positions, signals = await redis.mget(positions_key, signals_key)
    return (int(positions or 0), int(signals or 0))
```

`evaluate_rules()` signature is unchanged. Callers pass the values returned by `get_strategy_counts()`.

### `executor.py` (new)

Single public entry point:

```python
async def execute(
    strategies: list[dict],
    payload: dict,
    redis,
    session: AsyncSession,
    arq_redis,
) -> list[SignalResult]
```

Internal flow:

```
for each strategy:
  1. apply_mapping(payload, template)              → StandardSignal or mapping_error
  2. get_strategy_counts(redis, strategy_id)       → (open_positions, signals_today)
  3. evaluate_rules(signal, rules, positions, signals_today) → RuleResult

  if passed:
    mode == "paper"  → collect coroutine into paper_tasks[]
    mode == "live"   → enqueue ARQ job immediately, record execution_result="queued"
    mode == "log"    → no execution, signal logged only

asyncio.gather(*paper_tasks)    ← all paper trades execute concurrently

write all WebhookSignal records to DB
session.commit()
```

Live orders are enqueued before `asyncio.gather` so paper and live dispatch proceed without blocking each other. Each strategy's result is captured independently — one failure does not affect others.

### `slug.py` (new)

```python
def generate_slug(name: str) -> str:
    """Lowercase, replace spaces with hyphens, strip non-alphanumeric."""

async def ensure_unique_slug(session, tenant_id, base_slug: str) -> str:
    """Append -2, -3, ... until unique within tenant."""

async def regenerate_slug_on_rename(session, strategy) -> str:
    """Called from strategy update handler when name changes."""
```

---

## Section 3 — Redis Counters

### `signals_today`

```
Key:   wh:signals:{strategy_id}:{YYYY-MM-DD}
Type:  integer (INCR)
TTL:   seconds remaining until midnight (Asia/Kolkata timezone)
```

- Incremented once per signal that passes rule evaluation and reaches execution
- Date in key — expires automatically at midnight, no explicit reset job needed
- Redis unavailable: fall through to `signals_today=0` (rules still enforced on other dimensions)

### `open_positions`

```
Key:   wh:positions:{strategy_id}
Type:  integer (INCR / DECR)
TTL:   none (persistent)
```

- Incremented on successful BUY execution (paper or live)
- Decremented on successful SELL execution; floored at 0
- Deleted when strategy is deleted (alongside DB cascade)
- Missing key treated as 0

### Caveat

`open_positions` tracks webhook-triggered executions only. Manual trades placed via the manual trades UI or deployment order form do not update this counter. The counter is a guard rail, not a ledger. A future reconciliation job can sync it from actual DB positions if needed.

---

## Section 4 — ARQ Job: Live Orders

### Task definition

```python
# backend/app/webhooks/executor.py

async def execute_live_order_task(ctx: dict, job_payload: dict) -> dict:
    """
    job_payload keys:
      strategy_id, broker_connection_id, tenant_id,
      signal (serialised StandardSignal),
      webhook_signal_id (UUID of the WebhookSignal log record)
    """
```

Task steps:
1. Fetch `BrokerConnection` from DB
2. Decrypt credentials
3. Instantiate broker via `get_broker()`
4. Place order
5. Update `WebhookSignal` record with `execution_result` and `execution_detail`
6. Increment/decrement Redis position counter based on action + result

### Enqueue pattern

```python
await arq_redis.enqueue_job(
    "execute_live_order_task",
    job_payload,
    _job_id=f"live-order:{webhook_signal_id}",
)
```

`_job_id` is the `webhook_signal_id` — ARQ deduplicates by job ID, preventing double execution if the same signal is replayed.

### `WebhookSignal` record lifecycle

| Stage | `execution_result` | `execution_detail` |
|-------|-------------------|-------------------|
| Enqueued | `"queued"` | `{"job_id": "live-order:{id}"}` |
| Completed | `"filled"` / `"rejected"` / `"broker_error"` | full broker response |

### `worker.py` registration

```python
from app.webhooks.executor import execute_live_order_task

class WorkerSettings:
    functions = [run_backtest_task, execute_live_order_task]
```

---

## Section 5 — Frontend Changes

### Webhooks page (`/webhooks`)

**Broadcast URL section** (existing, relabelled):
- Label: "Broadcast URL"
- Description: "Triggers all active strategies simultaneously"
- Token rotation invalidates all strategy URLs at once (token is shared)

**Strategy URLs table** (new):

| Strategy Name | Slug | URL | |
|---|---|---|---|
| NIFTY Momentum | `nifty-momentum` | `.../webhook/{token}/nifty-momentum` | Copy |
| BankNifty Short | `banknifty-short` | `.../webhook/{token}/banknifty-short` | Copy |

Signal log table is unchanged.

### Strategy detail page (`/strategies/{id}`)

New "Webhook URL" card added above the mapping template editor:

```
┌─ Webhook URL ─────────────────────────────────────────────┐
│  https://algomatter.in/api/v1/webhook/{token}/nifty-...   │
│  [Copy URL]                                                │
│  Slug: nifty-momentum                                      │
└───────────────────────────────────────────────────────────┘
```

- URL is read-only; copy-to-clipboard button
- Slug displayed for transparency
- URL reflects current slug — updates automatically if strategy is renamed

### API dependency

`GET /api/v1/strategies/{id}` response adds `slug` field. Frontend constructs the full URL as:

```ts
`${baseUrl}/api/v1/webhook/${token}/${strategy.slug}`
```

Token fetched from the existing `/api/v1/webhooks/config` endpoint (already called on the webhooks page). On the strategy detail page, this is a **new fetch** — the page does not currently call this endpoint. A small `useWebhookConfig()` hook can be extracted and shared between both pages.

No new backend endpoints required.

---

## Out of Scope

- Per-strategy token rotation (token remains user-scoped)
- Manual slug editing by users
- Reconciliation job for `open_positions` counter vs actual DB positions
- Notification when a queued live order resolves

---

## Files Changed Summary

| File | Change |
|------|--------|
| `backend/app/webhooks/router.py` | Add `/{slug}` route; slim down handler logic |
| `backend/app/webhooks/processor.py` | Add `get_strategy_counts()` |
| `backend/app/webhooks/executor.py` | New file — execution pipeline |
| `backend/app/webhooks/slug.py` | New file — slug generation |
| `backend/app/db/models.py` | Add `slug` column to `Strategy` |
| `backend/app/strategies/router.py` | Call `ensure_unique_slug` on create/rename; add `slug` to response |
| `backend/app/strategies/schemas.py` | Add `slug` to `StrategyResponse` |
| `backend/worker.py` | Register `execute_live_order_task` |
| `backend/app/db/migrations/` | New Alembic migration |
| `frontend/app/(dashboard)/webhooks/page.tsx` | Add strategy URLs table |
| `frontend/app/(dashboard)/strategies/[id]/page.tsx` | Add Webhook URL card |
