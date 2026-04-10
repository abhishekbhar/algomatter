# Performance Optimizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the top performance bottlenecks: missing DB indexes, a Python-loop PnL aggregation, 4 redundant polling requests every 2 seconds, un-memoized chart components, and conservative ARQ worker limits.

**Architecture:** Backend changes are independent DB/query fixes and Redis caching on the webhook hot path. Frontend changes replace hardcoded poll intervals with constants and consolidate `useActiveDeployments` from 4 SWR calls to 1. No new services or tables — only indexes, query rewrites, and config changes.

**Tech Stack:** Python/SQLAlchemy/Alembic (backend), Redis (caching), TypeScript/SWR/React (frontend), ARQ (worker)

---

## Files Modified / Created

| File | Change |
|------|--------|
| `backend/app/db/models.py` | Add 5 `Index(...)` declarations |
| `backend/app/db/migrations/versions/e5f6a7b8c9d0_add_missing_tenant_indexes.py` | New Alembic migration |
| `backend/app/analytics/service.py` | Replace Python-loop PnL sum with SQL SUM |
| `backend/app/webhooks/router.py` | Cache active strategies in Redis (60 s TTL) |
| `backend/app/deployments/router.py` | Accept comma-separated `status` query param |
| `backend/worker.py` | Increase max_jobs, add job_timeout + result_ttl |
| `frontend/lib/utils/constants.ts` | Add `LIVE_TRADING` and `DEPLOYMENT` intervals |
| `frontend/lib/hooks/useApi.ts` | Fix useActiveDeployments (1 call), fix polling |
| `frontend/components/charts/EquityCurve.tsx` | Wrap in React.memo |
| `frontend/components/charts/CandlestickChart.tsx` | Wrap in React.memo |

---

## Task 1: Add 5 missing DB indexes

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/app/db/migrations/versions/e5f6a7b8c9d0_add_missing_tenant_indexes.py`

Without these indexes every `WHERE tenant_id = X` on `strategies`, `paper_trading_sessions`, `paper_positions` is a full table scan. The `(session_id, symbol)` index on `paper_positions` is hit on every SELL signal execution.

- [ ] **Step 1: Add index declarations to models**

Edit `backend/app/db/models.py`. Add `__table_args__` to three classes (two already have it):

```python
# strategies (line 81) — add __table_args__
class Strategy(Base):
    __tablename__ = "strategies"
    __table_args__ = (
        Index("ix_strategies_tenant_id", "tenant_id"),
    )

# paper_trading_sessions (line 174) — add __table_args__
class PaperTradingSession(Base):
    __tablename__ = "paper_trading_sessions"
    __table_args__ = (
        Index("ix_paper_trading_sessions_tenant_id", "tenant_id"),
    )

# paper_positions (line 198) — add __table_args__
class PaperPosition(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (
        Index("ix_paper_positions_tenant_id", "tenant_id"),
        Index("ix_paper_positions_session_symbol", "session_id", "symbol"),
    )

# webhook_signals already has __table_args__ at line 103 — append to tuple:
class WebhookSignal(Base):
    __tablename__ = "webhook_signals"
    __table_args__ = (
        Index("ix_webhook_signals_tenant_received", "tenant_id", "received_at"),
        Index("ix_webhook_signals_strategy_received", "tenant_id", "strategy_id", "received_at"),
    )
```

- [ ] **Step 2: Create the Alembic migration**

Create `backend/app/db/migrations/versions/e5f6a7b8c9d0_add_missing_tenant_indexes.py`:

```python
"""add_missing_tenant_indexes

Revision ID: e5f6a7b8c9d0
Revises: d3e4f5a6b7c8
Create Date: 2026-04-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_strategies_tenant_id", "strategies", ["tenant_id"])
    op.create_index("ix_paper_trading_sessions_tenant_id", "paper_trading_sessions", ["tenant_id"])
    op.create_index("ix_paper_positions_tenant_id", "paper_positions", ["tenant_id"])
    op.create_index("ix_paper_positions_session_symbol", "paper_positions", ["session_id", "symbol"])
    op.create_index("ix_webhook_signals_strategy_received", "webhook_signals", ["tenant_id", "strategy_id", "received_at"])


def downgrade() -> None:
    op.drop_index("ix_strategies_tenant_id", table_name="strategies")
    op.drop_index("ix_paper_trading_sessions_tenant_id", table_name="paper_trading_sessions")
    op.drop_index("ix_paper_positions_tenant_id", table_name="paper_positions")
    op.drop_index("ix_paper_positions_session_symbol", table_name="paper_positions")
    op.drop_index("ix_webhook_signals_strategy_received", table_name="webhook_signals")
```

- [ ] **Step 3: Verify migration chains correctly**

```bash
cd backend
ALGOMATTER_SKIP_SECRET_CHECK=1 .venv/bin/alembic history | head -8
```

Expected output includes `e5f6a7b8c9d0 -> (head)` and `d3e4f5a6b7c8 -> e5f6a7b8c9d0`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/models.py backend/app/db/migrations/versions/e5f6a7b8c9d0_add_missing_tenant_indexes.py
git commit -m "perf: add missing tenant_id and session/symbol indexes

5 new indexes eliminate full-table scans on strategies, paper_trading_sessions,
paper_positions (tenant and session+symbol), and webhook_signals (strategy_id).
SELL execution hot path benefits most from ix_paper_positions_session_symbol."
```

---

## Task 2: Replace Python-loop PnL aggregation with SQL SUM

**Files:**
- Modify: `backend/app/analytics/service.py:33-44`

`get_overview()` currently loads every `StrategyResult.metrics` row into Python memory and sums `total_return` in a loop. With 1,000 completed backtests this pulls ~1 MB of JSON per request.

- [ ] **Step 1: Update the imports in service.py**

At the top of `backend/app/analytics/service.py`, add `Float` to the sqlalchemy import:

```python
from sqlalchemy import Float, func, select
```

- [ ] **Step 2: Replace the Python-loop aggregation**

Replace lines 32–56 (the two separate PnL queries) with a single SQL SUM each:

```python
# Sum total_return from completed StrategyResults via SQL — avoids loading all rows into memory
strategy_pnl_q = await session.execute(
    select(
        func.coalesce(
            func.sum(
                func.cast(
                    StrategyResult.metrics["total_return"].as_float(),
                    Float,
                )
            ),
            0.0,
        )
    ).where(
        StrategyResult.tenant_id == tenant_id,
        StrategyResult.status == "completed",
        StrategyResult.metrics.isnot(None),
    )
)
total_pnl = float(strategy_pnl_q.scalar() or 0.0)

# Add realized PnL from paper trades (webhook strategies)
paper_pnl_q = await session.execute(
    select(func.coalesce(func.sum(PaperTrade.realized_pnl), 0.0)).where(
        PaperTrade.tenant_id == tenant_id,
        PaperTrade.realized_pnl.isnot(None),
    )
)
total_pnl += float(paper_pnl_q.scalar() or 0.0)
```

- [ ] **Step 3: Run existing analytics tests to verify no regression**

```bash
cd backend
ALGOMATTER_SKIP_SECRET_CHECK=1 .venv/bin/pytest tests/test_analytics.py -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/analytics/service.py
git commit -m "perf: replace Python-loop StrategyResult PnL sum with SQL SUM

Previously loaded all StrategyResult.metrics rows into Python memory.
Now uses func.sum(cast(metrics['total_return'].as_float())) in SQL."
```

---

## Task 3: Cache active strategies in webhook hot path

**Files:**
- Modify: `backend/app/webhooks/router.py:47-54`

Every webhook POST loads all active strategies from DB. With Redis already on `request.app.state.redis`, a 60-second cache eliminates this for all but the first request per minute.

- [ ] **Step 1: Add a cache helper at the top of the webhook router module**

In `backend/app/webhooks/router.py`, after the existing imports, add:

```python
import json as _json

_STRATEGY_CACHE_TTL = 60  # seconds


async def _get_active_strategies(redis, session, tenant_id):
    """Return active strategies for tenant, using Redis cache (60 s TTL)."""
    cache_key = f"strategies:active:{tenant_id}"
    cached = await redis.get(cache_key)
    if cached:
        # Reconstruct lightweight dicts; router only needs id, mapping_template,
        # mode, broker_connection_id, rules
        return _json.loads(cached)

    result = await session.execute(
        select(Strategy).where(
            Strategy.tenant_id == tenant_id,
            Strategy.is_active.is_(True),
        )
    )
    strategies = result.scalars().all()

    # Serialise to JSON-safe dicts for cache
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
    await redis.set(cache_key, _json.dumps(payload), ex=_STRATEGY_CACHE_TTL)
    return payload
```

- [ ] **Step 2: Update the webhook ingest handler to use the cache**

In the `ingest_webhook` handler, replace the direct DB query (lines 47–54) with the cache helper. The handler receives `request: Request` — confirm this by checking the function signature; add it if missing.

Replace:
```python
    strat_result = await session.execute(
        select(Strategy).where(
            Strategy.tenant_id == user.id,
            Strategy.is_active.is_(True),
        )
    )
    strategies = strat_result.scalars().all()
```

With:
```python
    redis = request.app.state.redis
    strategy_dicts = await _get_active_strategies(redis, session, user.id)
```

- [ ] **Step 3: Update the loop to work with dicts instead of ORM objects**

The loop at line 58 iterates `for strategy in strategies:`. Replace every attribute access with dict access:

```python
    for strategy in strategy_dicts:
        if not strategy["mapping_template"]:
            continue
        # Use strategy["id"], strategy["mode"], strategy["broker_connection_id"],
        # strategy["rules"], strategy["mapping_template"] throughout the loop.
        # strategy["id"] is a str — convert to uuid.UUID where needed:
        #   strategy_id = uuid.UUID(strategy["id"])
```

Go through the full loop body and replace `strategy.X` with `strategy["X"]` and `strategy.id` with `uuid.UUID(strategy["id"])`. The `WebhookSignal(strategy_id=strategy.id, ...)` line becomes `strategy_id=uuid.UUID(strategy["id"])`.

- [ ] **Step 4: Invalidate the cache on strategy create/update/delete**

In `backend/app/strategies/router.py`, at the end of `create_strategy`, `update_strategy`, and `delete_strategy` handlers, add cache invalidation. Each handler already has `session: AsyncSession` — add `request: Request` dependency and invalidate:

```python
# At the end of create_strategy, update_strategy, delete_strategy:
redis = request.app.state.redis
await redis.delete(f"strategies:active:{tenant_id}")
```

Import `Request` from `fastapi` at the top of `strategies/router.py` if not already present.

- [ ] **Step 5: Commit**

```bash
git add backend/app/webhooks/router.py backend/app/strategies/router.py
git commit -m "perf: cache active strategies in Redis on webhook hot path (60 s TTL)

Every webhook POST was hitting the DB to load active strategies.
Now cached per-tenant with 60 s TTL. Cache invalidated on strategy
create/update/delete."
```

---

## Task 4: Fix useActiveDeployments — 4 SWR calls → 1

**Files:**
- Modify: `frontend/lib/hooks/useApi.ts:236-255`

`useActiveDeployments` currently makes 4 separate API calls every 2 seconds (running/live, running/paper, paused/live, paused/paper). The backend `/api/v1/deployments` already returns all deployments when no filters are applied — filter client-side instead.

- [ ] **Step 1: Rewrite useActiveDeployments**

In `frontend/lib/hooks/useApi.ts`, replace lines 236–255:

```typescript
export function useActiveDeployments() {
  const result = useApiGet<Deployment[]>("/api/v1/deployments", {
    refreshInterval: POLLING_INTERVALS.DEPLOYMENT,
  });
  const active = (result.data ?? []).filter(
    (d) => d.status === "running" || d.status === "paused"
  );
  return {
    ...result,
    data: result.data !== undefined ? active : undefined,
  };
}
```

- [ ] **Step 2: Verify pages that consume useActiveDeployments still compile**

```bash
cd frontend
npm run build 2>&1 | grep -E "error|Error" | head -20
```

Expected: no TypeScript errors related to `useActiveDeployments`.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/hooks/useApi.ts
git commit -m "perf: useActiveDeployments — 4 SWR calls replaced with 1

Was making 4 separate API requests every 2 seconds. Now fetches all
deployments once and filters client-side to running/paused."
```

---

## Task 5: Fix hardcoded 2000ms poll intervals

**Files:**
- Modify: `frontend/lib/utils/constants.ts`
- Modify: `frontend/lib/hooks/useApi.ts`

Three hooks use hardcoded `2000` ms instead of a constant: `useDeployment`, `useAggregateStats`, and the old `useActiveDeployments` (now fixed in Task 4).

- [ ] **Step 1: Add DEPLOYMENT and LIVE_TRADING to constants**

In `frontend/lib/utils/constants.ts`, replace the existing object:

```typescript
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "";

export const POLLING_INTERVALS = {
  DASHBOARD: 10_000,
  SIGNALS: 5_000,
  PAPER_TRADING: 10_000,
  HEALTH: 30_000,
  BACKTEST_STATUS: 2_000,
  MARKET_CHART: 30_000,
  DEPLOYMENT: 5_000,
  LIVE_TRADING: 5_000,
} as const;
```

- [ ] **Step 2: Replace hardcoded 2000ms in useApi.ts**

In `frontend/lib/hooks/useApi.ts`:

Replace `useDeployment` (line 216–220):
```typescript
export function useDeployment(id: string | undefined, config?: { refreshInterval?: number }) {
  return useApiGet<Deployment>(id ? `/api/v1/deployments/${id}` : null, {
    refreshInterval: config?.refreshInterval ?? POLLING_INTERVALS.DEPLOYMENT,
  });
}
```

Replace `useAggregateStats` (line 264–266):
```typescript
export function useAggregateStats() {
  return useApiGet<AggregateStats>("/api/v1/deployments/aggregate-stats", {
    refreshInterval: POLLING_INTERVALS.LIVE_TRADING,
  });
}
```

Replace `useBacktestDeployments` (line 222–226):
```typescript
export function useBacktestDeployments() {
  return useApiGet<Deployment[]>("/api/v1/deployments?mode=backtest", {
    refreshInterval: POLLING_INTERVALS.BACKTEST_STATUS,
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/utils/constants.ts frontend/lib/hooks/useApi.ts
git commit -m "perf: replace hardcoded 2000ms poll intervals with named constants

useDeployment, useAggregateStats, useBacktestDeployments now use
POLLING_INTERVALS.DEPLOYMENT/LIVE_TRADING/BACKTEST_STATUS (5 s, 5 s, 2 s).
Reduces live-trading page to ~2 requests/second from ~4."
```

---

## Task 6: Memoize chart components

**Files:**
- Modify: `frontend/components/charts/EquityCurve.tsx`
- Modify: `frontend/components/charts/CandlestickChart.tsx`

Both chart components re-create their `lightweight-charts` instance (expensive) on every render because they are not memoized. Parent components re-render on every SWR poll tick, triggering chart rebuilds even when data hasn't changed.

- [ ] **Step 1: Memoize EquityCurve**

Replace the full contents of `frontend/components/charts/EquityCurve.tsx`:

```typescript
"use client";
import { memo, useRef, useEffect } from "react";
import { createChart, AreaSeries, IChartApi, AreaData, Time } from "lightweight-charts";
import { useColorModeValue } from "@chakra-ui/react";

interface EquityCurveProps { data: Array<{ time: string | number; value: number }>; height?: number; }

export const EquityCurve = memo(function EquityCurve({ data, height = 300 }: EquityCurveProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const bgColor = useColorModeValue("#ffffff", "#1a202c");
  const textColor = useColorModeValue("#2d3748", "#e2e8f0");

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth, height,
      layout: { background: { color: bgColor }, textColor },
      grid: { vertLines: { visible: false }, horzLines: { color: "#e2e8f020" } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    chartRef.current = chart;
    const series = chart.addSeries(AreaSeries, {
      lineColor: "#3182ce", topColor: "rgba(49, 130, 206, 0.4)",
      bottomColor: "rgba(49, 130, 206, 0.0)", lineWidth: 2,
    });
    const sorted = [...data].sort((a, b) => {
      if (typeof a.time === "number" && typeof b.time === "number") return a.time - b.time;
      return String(a.time).localeCompare(String(b.time));
    });
    series.setData(sorted as AreaData<Time>[]);
    chart.timeScale().fitContent();
    const handleResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", handleResize);
    return () => { window.removeEventListener("resize", handleResize); chart.remove(); };
  }, [data, height, bgColor, textColor]);

  return <div ref={containerRef} />;
});
```

- [ ] **Step 2: Memoize CandlestickChart**

In `frontend/components/charts/CandlestickChart.tsx`, change:

```typescript
// Line 1: add memo to import
import { memo, useRef, useEffect } from "react";

// Change the export line from:
export function CandlestickChart({ data, trades = [], height = 400 }: CandlestickChartProps) {
// To:
export const CandlestickChart = memo(function CandlestickChart({ data, trades = [], height = 400 }: CandlestickChartProps) {
// And close with:
});
```

- [ ] **Step 3: Verify build**

```bash
cd frontend
npm run build 2>&1 | grep -E "error TS|Error:" | head -10
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/charts/EquityCurve.tsx frontend/components/charts/CandlestickChart.tsx
git commit -m "perf: wrap chart components in React.memo

EquityCurve and CandlestickChart were re-creating their lightweight-charts
instance on every parent render (every SWR poll tick). memo() prevents
re-renders when data/height/colors haven't changed."
```

---

## Task 7: Fix ARQ worker settings

**Files:**
- Modify: `backend/worker.py`

`max_jobs = 10` means the worker stops accepting new jobs once 10 are in flight. With backtests taking 10–60 seconds each, this can queue up quickly. No `job_timeout` means hung backtests block the queue forever.

- [ ] **Step 1: Update WorkerSettings**

Replace the full contents of `backend/worker.py`:

```python
from arq import cron
from arq.connections import RedisSettings

from app.backtesting.tasks import run_backtest_task
from app.config import settings
from app.historical.tasks import daily_data_fetch


class WorkerSettings:
    functions = [run_backtest_task]
    cron_jobs = [cron(daily_data_fetch, hour=6, minute=0)]  # 6 AM daily
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 100          # up from 10 — allows burst of concurrent tasks
    job_timeout = 3600      # 1 hour max per job — prevents hung backtests blocking queue
    keep_result_forever = False
    result_ttl = 86400      # store results for 24 h then auto-expire from Redis
```

- [ ] **Step 2: Commit**

```bash
git add backend/worker.py
git commit -m "perf: raise ARQ max_jobs to 100, add 1h job_timeout and 24h result_ttl

max_jobs=10 caused queue starvation under burst load. job_timeout prevents
hung backtests from blocking the queue indefinitely. result_ttl prevents
Redis accumulating stale job results forever."
```

---

## Final: Deploy

- [ ] **Step 1: Run all backend tests**

```bash
cd backend
ALGOMATTER_SKIP_SECRET_CHECK=1 .venv/bin/pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 2: Deploy backend + frontend**

```
/deploy
```

- [ ] **Step 3: Run the migration on production**

```bash
# Included in deploy step via alembic upgrade head
```

- [ ] **Step 4: Verify**

```bash
curl -s https://algomatter.in/api/v1/health
# Expected: {"database":"ok","redis":"ok"}
```
