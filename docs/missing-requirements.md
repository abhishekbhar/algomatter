# AlgoMatter — Missing Requirements

_Last updated: 2026-04-10_

---

## Overview

This document catalogues gaps, stubs, and missing features identified during a full codebase review. Items are grouped by severity.

---

## Critical

### 1. CORS production domain not configured

**File:** `backend/app/main.py:44-49`

`allow_origins` only includes `localhost` variants:

```python
allow_origins=[
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
],
```

`https://algomatter.in` is absent. Every authenticated API call from the production frontend fails with a CORS error. The app is effectively broken in production for any cross-origin request.

**Fix:** Add `"https://algomatter.in"` to `allow_origins`, or read the list from an env var (`ALGOMATTER_CORS_ORIGINS`) so it can differ between environments.

---

### 2. Async backtest execution is a stub

**File:** `backend/app/backtesting/tasks.py:9-11`

```python
async def run_backtest_task(ctx: dict, backtest_id: str) -> None:
    """ARQ task wrapper. Stub for future async job queue integration."""
    pass
```

This task is registered with the ARQ worker (`backend/worker.py:10`) but does nothing. Backtests currently run **synchronously inside the API request handler**, blocking a uvicorn worker for the entire backtest duration. Long or concurrent backtests will starve other API requests and may time out.

**Fix:** Move the backtest execution logic into `run_backtest_task`, enqueue it from the router, and poll for completion from the frontend (the router already has a `GET /api/v1/backtests/{id}` status endpoint).

---

### 3. Historical data cron job broken

**File:** `backend/app/historical/tasks.py:29-33`

```python
for name in strategy_names:
    # Each strategy name could encode symbol info;
    # this is a placeholder for real symbol extraction logic.
    await fetch_and_cache_ohlcv(
        session,
        symbol=name,   # ← strategy name used as symbol
        exchange="NSE",
        ...
    )
```

The daily 6 AM ARQ cron uses the strategy's display name as the trading symbol. Strategy names are user-chosen labels (e.g. "NIFTY Momentum"), not exchange symbols (e.g. `NIFTY`). The fetch either silently fails or stores garbage data. The historical data cache is never populated automatically.

**Fix:** Add a `symbols` field to the `Strategy` model (already exists as a comma-separated string in the webhook strategy schema) and parse it here, or derive the symbol list from `StrategyDeployment` records.

---

## High Priority

### 4. No password change or profile update endpoint

**File:** `backend/app/auth/router.py`

The auth module exposes: `signup`, `login`, `logout`, `refresh`, `me`. There is no `PATCH /api/v1/auth/me` to change a password or update a display name. The settings page (`frontend/app/(dashboard)/settings/page.tsx`) shows the user's email and plan but provides no controls to modify them.

**Fix:** Add `PATCH /api/v1/auth/me` accepting `{ current_password, new_password }`, verify the current password with `verify_password()`, and store the new hash.

---

### 5. Live trading price data bypasses the backend entirely

**File:** `frontend/lib/hooks/useBinanceWebSocket.ts:24`

```ts
const BINANCE_WS_URL = "wss://stream.binance.com:9443/stream";
```

The live-trading page connects directly to Binance's public WebSocket stream. Consequences:

- Users connected to **Exchange1** (or any future non-Binance broker) see no live price data.
- The connection is unauthenticated and unlogged — no audit trail.
- Rate limiting and reconnect logic are implemented client-side only.
- Any future broker abstraction requires a backend WebSocket proxy.

**Fix:** Add a WebSocket endpoint to the FastAPI backend (`/api/v1/ws/ticker`) that proxies the appropriate broker's market data stream based on the user's active broker connection.

---

### 6. Feature flags incomplete

**File:** `backend/app/feature_flags.py`

Only two flags are defined:

```python
def require_paper_trading_enabled() -> None: ...
def require_backtesting_enabled() -> None: ...
```

`live_trading` and `hosted_strategies` have no corresponding guards. These features cannot be toggled per-environment without code changes.

**Fix:** Add `enable_live_trading: bool = True` and `enable_hosted_strategies: bool = True` to `Settings`, create corresponding guard functions, and apply them to the relevant routers.

---

## Moderate

### 7. No email system

There is no email infrastructure anywhere in the codebase. Missing flows:

| Flow | Impact |
|------|--------|
| Email verification at signup | Anyone can register with a fake address |
| Password reset via email | Forgotten password = locked out permanently |
| Trade alert notifications | No way to notify users of fills or errors |
| Deployment status emails | No notification when a deployment stops unexpectedly |

**Fix:** Integrate an email provider (e.g. Resend, SendGrid) via an `app/email/` module and add verification + reset token logic to the auth module.

---

### 8. No account deletion

There is no `DELETE /api/v1/auth/me` endpoint and no UI for it. Users cannot remove their accounts or data. This is a GDPR / compliance gap for any users in regulated jurisdictions.

**Fix:** Add an authenticated `DELETE /api/v1/auth/me` that cascades deletes across all user-owned records (strategies, deployments, broker connections, trades) and invalidates all refresh tokens.

---

### 9. `StrategyResult` records are write-only

**File:** `backend/app/db/models.py` (model exists), `backend/app/strategies/router.py` (no read endpoint)

The `StrategyResult` model is written during webhook signal processing and cleaned up on strategy delete. There is no `GET /api/v1/strategies/{id}/results` endpoint to read these records. The data is stored but never surfaced — the analytics module computes metrics independently from trades/positions instead.

**Fix:** Either add a results endpoint to the strategies router, or consolidate `StrategyResult` into the analytics service so it is not a silent dead-end.

---

## Low Priority / Technical Debt

### 10. ARQ worker underutilised

**File:** `backend/worker.py`

```python
functions = [run_backtest_task]           # ← stub, does nothing
cron_jobs = [cron(daily_data_fetch, ...)] # ← broken (see item 3)
```

The ARQ worker infrastructure is in place (queue, result TTL, job timeout) but no working jobs are registered. The strategy runner uses APScheduler independently and does not integrate with ARQ.

**Fix:** Address items 2 and 3 first. Once real tasks are enqueued, consider migrating strategy runner scheduling to ARQ for a unified job queue.

---

### 11. Exchange1 historical data fetched from Binance

**File:** `backend/app/brokers/exchange1.py:800`

A comment states: *"Exchange1 only provides klines via WebSocket, so we use Binance's REST API."* Exchange1's `get_historical()` method silently calls Binance. This is a hidden dependency — if Binance changes its API or if the user trades symbols that don't exist on Binance, the call fails with a confusing error.

**Fix:** Document this limitation explicitly at the API response level, or implement a WebSocket kline collector for Exchange1 that stores data locally and serves it from the DB.

---

## Summary

| # | Area | Severity | Primary File |
|---|------|----------|-------------|
| 1 | CORS production domain missing | Critical | `backend/app/main.py` |
| 2 | Async backtest stub | Critical | `backend/app/backtesting/tasks.py` |
| 3 | Historical cron broken | Critical | `backend/app/historical/tasks.py` |
| 4 | No password change endpoint | High | `backend/app/auth/router.py` |
| 5 | Live data bypasses backend | High | `frontend/lib/hooks/useBinanceWebSocket.ts` |
| 6 | Feature flags incomplete | High | `backend/app/feature_flags.py` |
| 7 | No email system | Moderate | (no file — missing module) |
| 8 | No account deletion | Moderate | `backend/app/auth/router.py` |
| 9 | StrategyResult write-only | Moderate | `backend/app/strategies/router.py` |
| 10 | ARQ worker underutilised | Low | `backend/worker.py` |
| 11 | Exchange1 uses Binance data | Low | `backend/app/brokers/exchange1.py` |
