# GainGuard: Multiuser Algo-Testing Platform — Design Spec

## Overview

GainGuard is a multi-tenant SaaS platform where Indian retail traders sign up, connect their broker/exchange accounts, receive webhook signals from external tools (TradingView, AmiBroker, ChartInk), and execute backtests, paper trades, and live trades.

**Target users:** Indian retail traders (NSE/BSE) + cryptocurrency traders via Exchange1.

**Phased delivery:**
- **Phase 1:** Auth + broker linking, backtesting, paper trading, portfolio analytics
- **Phase 2:** Live trading, alerts/notifications

**Strategy model:** Webhook-based. The platform receives signals, not strategy logic. Users bring strategies from external tools.

**Scale target:** Under 100 users initially (early beta).

**Deployment:** Docker Compose on a self-hosted VPS.

**Terminology:** In this spec, "tenant" and "user" are synonymous. Each user is a tenant. There is no organization/team hierarchy for MVP. If multi-user organizations are needed later, a separate `tenants` table would be introduced with a `tenant_id` FK on `users`.

---

## Decision: Why Not Fork OpenAlgo

OpenAlgo (github.com/marketcalls/openalgo) was evaluated as a starting point. It provides 30+ Indian broker integrations, webhook support, and a visual flow builder. However:

1. **AGPL v3 license** — offering a modified version as SaaS legally requires open-sourcing the entire codebase, including all custom multi-tenant logic, billing, and proprietary features.
2. **Single-user architecture** — SQLite x4, session management, and API key handling are deeply single-user. Retrofitting multi-tenancy is more work than building fresh.
3. **Synchronous Flask** — poor fit for real-time trading workloads that benefit from async I/O.

**Approach chosen:** Build from scratch with a modern async stack. Use OpenAlgo's unified broker API *concept* (not code) as a design pattern.

---

## Architecture

```
+-----------------------------------------------------+
|                    Next.js Frontend                  |
|   (Auth UI, Dashboard, Backtest Viewer, Analytics)   |
+------------------------+----------------------------+
                         | REST + WebSocket
+------------------------v----------------------------+
|                  FastAPI Backend                      |
|  +----------+ +-----------+ +--------------------+  |
|  | Auth &   | | Webhook   | | Backtest / Paper   |  |
|  | User Mgmt| | Engine    | | Trading Engine     |  |
|  +----------+ +-----------+ +--------------------+  |
|  +------------------+ +--------------------------+  |
|  | Broker Adapter   | | Analytics / PnL          |  |
|  | Layer (Unified)  | | Service                  |  |
|  +------------------+ +--------------------------+  |
+----+----------+------------------+------------------+
     |          |                  |
+----v----+ +---v-----+    +------v------+
|PostgreSQL| |  Redis  |    | Task Queue  |
| (data)   | | (cache, |    | (ARQ)       |
|          | | streams)|    |             |
+----------+ +---------+    +-------------+
```

**Key design decisions:**
- Single backend, multi-tenant via PostgreSQL row-level security (RLS). Every tenant-scoped table has a `tenant_id` column enforced at the DB level.
- Unified Broker Adapter interface — all brokers/exchanges implement the same abstract class. Adding a new broker = one Python module.
- Webhook-first strategy integration — platform receives signals, doesn't host strategy logic.
- Task queue (ARQ) for heavy work — backtests and data fetching run as background jobs. Single ARQ worker process in its own Docker container, with concurrency controlled via ARQ's `max_jobs` setting (default 10). Separate from the API container.
- Event bus uses **Redis Streams** (not Pub/Sub) — durable, replayable events with consumer groups. Events persist even when no consumer is listening in Phase 1, enabling backfill when notification workers are added in Phase 2.

---

## Multi-Tenancy & Auth

### Data Model

```sql
-- users
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active     BOOLEAN DEFAULT TRUE,
    plan          TEXT DEFAULT 'free',  -- for future use
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- refresh_tokens
CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL,  -- SHA-256 hash of the refresh token
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- broker_connections
CREATE TABLE broker_connections (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES users(id),
    broker_type TEXT NOT NULL,  -- 'zerodha', 'angel_one', 'exchange1', etc.
    credentials BYTEA NOT NULL, -- AES-256-GCM encrypted JSON
    is_active   BOOLEAN DEFAULT TRUE,
    connected_at TIMESTAMPTZ DEFAULT now()
);

-- RLS policy (applied to all tenant-scoped tables)
ALTER TABLE broker_connections ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON broker_connections
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

### RLS Activation

Every database request goes through a FastAPI dependency that:
1. Extracts `user_id` from the JWT token
2. Calls `SET LOCAL app.current_tenant_id = '{user_id}'` at the start of the DB transaction
3. `SET LOCAL` scopes the setting to the current transaction only — no leakage between requests

This is implemented as a SQLAlchemy `SessionEvents.after_begin` hook wired into the FastAPI dependency injection chain via `get_db_session()`.

### Auth Flow

- Email/password signup with JWT tokens. Tokens sent via `Authorization: Bearer` header (not cookies — no CSRF concern).
- JWT access tokens: short-lived (15 min), contain `user_id` and `email`
- Refresh tokens: 7 days, stored as SHA-256 hash in DB, rotated on use (old token invalidated)
- Optional OAuth (Google) added later

### Security

- **Encryption key management:** A master key is stored as an environment variable (`GAINGUARD_MASTER_KEY`). Per-tenant encryption keys are derived using HKDF-SHA256 with the master key and `tenant_id` as salt. This means: (a) compromising one tenant's derived key does not expose others, (b) password changes do not affect credential encryption, (c) key rotation requires re-encrypting all credentials (admin operation). For MVP on a single VPS this is acceptable; for production scale, the master key should move to a secrets manager (HashiCorp Vault, AWS KMS).
- PostgreSQL RLS policies on every tenant-scoped table (see above)
- Webhook endpoints use unique per-user secret tokens: `POST /api/v1/webhook/{user_webhook_token}`. Tokens are 32 bytes of `secrets.token_urlsafe()` (256-bit entropy). Users can regenerate tokens from the UI (old token immediately invalidated — user must update TradingView config).
- **Rate limiting:** Redis-backed sliding window rate limiter, implemented as FastAPI middleware. 60 signals/minute per user. Returns HTTP 429 with `Retry-After` header when exceeded.
- **Webhook input validation:** Max payload size 64KB (enforced by FastAPI). Payload parsed with Pydantic model that rejects unknown nested structures deeper than 3 levels. All string fields stripped and length-capped before storage.

---

## API Endpoints

All endpoints are versioned under `/api/v1/`.

### Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/signup` | Register. Body: `{email, password}`. Returns: `{access_token, refresh_token}` |
| POST | `/api/v1/auth/login` | Login. Body: `{email, password}`. Returns: `{access_token, refresh_token}` |
| POST | `/api/v1/auth/refresh` | Rotate refresh token. Body: `{refresh_token}`. Returns: `{access_token, refresh_token}` |
| GET | `/api/v1/auth/me` | Get current user profile |

### Broker Connections

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/brokers` | List user's broker connections |
| POST | `/api/v1/brokers` | Add broker connection. Body: `{broker_type, credentials}`. Verifies connection before saving. |
| DELETE | `/api/v1/brokers/{id}` | Remove broker connection |
| POST | `/api/v1/brokers/{id}/verify` | Re-verify an existing connection |

### Webhooks

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/webhook/{token}` | Receive webhook signal (public, token-authenticated) |
| GET | `/api/v1/webhooks/config` | Get user's webhook token and mapping templates |
| POST | `/api/v1/webhooks/config/regenerate-token` | Regenerate webhook token |
| GET | `/api/v1/webhooks/signals` | List webhook signal history (paginated, filterable) |
| PUT | `/api/v1/webhooks/rules` | Update signal processing rules |

### Strategies & Signal Rules

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/strategies` | List user's strategies (named webhook configurations) |
| POST | `/api/v1/strategies` | Create strategy. Body: `{name, broker_connection_id, mode, rules, mapping_template}` |
| PUT | `/api/v1/strategies/{id}` | Update strategy config |
| DELETE | `/api/v1/strategies/{id}` | Delete strategy |

### Backtesting

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/backtests` | Start backtest. Body: `{strategy_id, start_date, end_date, capital, slippage, commission}`. Returns: `{backtest_id, status: "queued"}` |
| GET | `/api/v1/backtests` | List user's backtests (paginated) |
| GET | `/api/v1/backtests/{id}` | Get backtest result (status, metrics, trade_log, equity_curve) |
| DELETE | `/api/v1/backtests/{id}` | Delete backtest result |

### Paper Trading

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/paper-trading/sessions` | Start paper trading session. Body: `{strategy_id, capital}` |
| GET | `/api/v1/paper-trading/sessions` | List sessions |
| GET | `/api/v1/paper-trading/sessions/{id}` | Get session state (positions, balance, trades) |
| POST | `/api/v1/paper-trading/sessions/{id}/stop` | Stop session |

### Analytics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/analytics/overview` | Dashboard overview (total P&L, active strategies, today's trades) |
| GET | `/api/v1/analytics/strategies/{id}/metrics` | Per-strategy metrics |
| GET | `/api/v1/analytics/strategies/{id}/equity-curve` | Equity curve data points |
| GET | `/api/v1/analytics/strategies/{id}/trades` | Trade log (paginated, filterable). Query: `?format=csv` for export. |

### System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check (DB, Redis, ARQ worker status) |

---

## Broker Adapter Layer

### Interface

```python
class BrokerAdapter(ABC):
    # Connection
    async def authenticate(self, credentials: dict) -> bool
    async def verify_connection(self) -> bool

    # Orders
    async def place_order(self, order: OrderRequest) -> OrderResponse
    async def cancel_order(self, order_id: str) -> bool
    async def get_order_status(self, order_id: str) -> OrderStatus

    # Portfolio
    async def get_positions(self) -> list[Position]
    async def get_holdings(self) -> list[Holding]
    async def get_balance(self) -> AccountBalance

    # Market Data
    async def get_quotes(self, symbols: list[str]) -> list[Quote]
    async def get_historical(self, symbol: str, interval: str,
                             start: datetime, end: datetime) -> list[OHLCV]
```

All broker responses are normalized into platform-standard models (`OrderRequest`, `Position`, `Quote`, `OHLCV`, etc.). The adapter handles translation.

### Adapters

**Phase 1:**
- `SimulatedBroker` — in-memory adapter for paper trading and backtests. Simulates order fills against historical data with configurable slippage/commission models.

**Phase 2:**
- `Zerodha` (Kite Connect API)
- `AngelOne` (SmartAPI)
- `Fyers` (Fyers API v3)
- `Exchange1` (REST + WebSocket, SHA256WithRSA signed auth)

Each adapter is a single Python module: `adapters/zerodha.py`, `adapters/exchange1.py`, etc.

### Exchange1 Specifics

- Auth: Asymmetric cryptography (SHA256WithRSA) — API key + private key, signed headers with UTC millisecond timestamps
- Markets supported: Futures (perpetual, up to 100x leverage), Spot, Options
- Key endpoints: `/openapi/v1/{category}/order/create`, `/openapi/v1/{category}/order/close`, `/openapi/v1/balance`
- WebSocket: `wss://www.exchange1.global/v1/pusher/ws` for real-time data

### Error Handling

All broker adapter methods follow a consistent error strategy:

- **Transient errors** (network timeout, 5xx from broker): Retry up to 3 times with exponential backoff (1s, 2s, 4s). If all retries fail, the signal is marked `failed` in `webhook_signals` and an event is published to the event bus.
- **Permanent errors** (invalid credentials, insufficient balance, 4xx): No retry. Signal marked `failed` with error reason.
- **Partial failures** in backtests: Individual signal failures are logged in the trade log but the backtest continues. A `warnings` field in the result captures failed signals.
- All errors are logged with structured context: `{tenant_id, broker_type, operation, error_code, error_message}`.

---

## Webhook Engine & Signal Flow

### Flow

```
TradingView / AmiBroker / ChartInk
        |
        |  POST /api/v1/webhook/{user_webhook_token}
        |  { "symbol": "RELIANCE", "action": "BUY",
        |    "quantity": 10, "order_type": "MARKET" }
        v
+---------------------+
|  Webhook Receiver    | -- Validates token, rate-limits, parses payload
+---------+-----------+
          |
          v
+---------------------+
|  Signal Processor    | -- Applies user-defined rules (see rules schema below)
+---------+-----------+
          |
          +---> Paper Trading Engine (Phase 1)
          |        SimulatedBroker fills against cached historical quotes
          |
          +---> Live Broker Adapter (Phase 2)
                   Actual order to Zerodha/Exchange1/etc.
```

### Standard Signal Format

The platform's internal signal format that all webhooks are mapped to:

```json
{
  "symbol": "RELIANCE",
  "exchange": "NSE",
  "action": "BUY",
  "quantity": 10,
  "order_type": "MARKET",
  "price": null,
  "trigger_price": null,
  "product_type": "INTRADAY"
}
```

### Webhook Mapping Templates

Users configure a key-value mapping that translates incoming webhook fields to the standard signal format. Stored as JSON in the `strategies` table.

```json
{
  "symbol": "$.ticker",
  "exchange": "$.exchange",
  "action": "$.strategy.order_action",
  "quantity": "$.strategy.order_contracts",
  "order_type": "MARKET",
  "product_type": "INTRADAY"
}
```

Values starting with `$.` are treated as JSONPath expressions evaluated against the incoming payload. Literal values (like `"MARKET"`) are used as-is. This is simple, predictable, and covers TradingView's webhook format without requiring a template language. Implemented using the `jsonpath-ng` Python library.

### Signal Processing Rules Schema

```sql
CREATE TABLE strategies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES users(id),
    name                TEXT NOT NULL,
    broker_connection_id UUID REFERENCES broker_connections(id),
    mode                TEXT NOT NULL DEFAULT 'paper',  -- 'paper', 'live', 'backtest'
    mapping_template    JSONB NOT NULL,  -- JSONPath mapping (see above)
    rules               JSONB NOT NULL DEFAULT '{}',
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT now()
);
```

The `rules` JSONB field structure:

```json
{
  "max_position_size": 100000,
  "max_open_positions": 5,
  "symbol_whitelist": ["RELIANCE", "TCS", "INFY"],
  "symbol_blacklist": [],
  "trading_hours": {"start": "09:15", "end": "15:30", "timezone": "Asia/Kolkata"},
  "max_signals_per_day": 50
}
```

All fields are optional. Missing fields mean no restriction.

### Signal Logging

```sql
CREATE TABLE webhook_signals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES users(id),
    strategy_id     UUID REFERENCES strategies(id),
    received_at     TIMESTAMPTZ DEFAULT now(),
    raw_payload     JSONB NOT NULL,
    parsed_signal   JSONB,          -- null if parsing failed
    rule_result     TEXT,           -- 'passed', 'blocked_by_rule', 'parse_error'
    rule_detail     TEXT,           -- which rule blocked, or error message
    execution_result TEXT,          -- 'filled', 'failed', 'pending'
    execution_detail JSONB,         -- order response or error detail
    processing_ms   INTEGER         -- end-to-end processing time
);
```

---

## Backtesting & Paper Trading Engine

### Backtesting

- User selects date range, initial capital, and a strategy (whose mapping template + rules are applied to replayed signals)
- Signal sources for backtest: upload CSV of historical signals with columns `timestamp, symbol, action, quantity, order_type, price`
- Runs as ARQ background task
- Configurable: slippage model (fixed bps or percentage), commission per trade, starting capital
- Results stored in DB: trade log, equity curve data points, drawdown series

### Historical Data

- **Indian equities:** `yfinance` / `jugaad-data` for NSE/BSE. **Known risk:** these are unofficial scrapers that break periodically. Acceptable for MVP. For production, migrate to a paid data provider (e.g., TrueData, Global Datafeeds) or NSE's official data API.
- **Crypto:** Exchange1 REST API (`GET /openapi/v1/{category}/kline`)
- Background job fetches and caches data daily. Staleness check: if data for a symbol is older than 24h, re-fetch on demand before backtest starts.

```sql
CREATE TABLE historical_ohlcv (
    symbol      TEXT NOT NULL,
    exchange    TEXT NOT NULL,       -- 'NSE', 'BSE', 'EXCHANGE1'
    interval    TEXT NOT NULL,       -- '1m', '5m', '15m', '1h', '1d'
    timestamp   TIMESTAMPTZ NOT NULL,
    open        NUMERIC(20,8) NOT NULL,
    high        NUMERIC(20,8) NOT NULL,
    low         NUMERIC(20,8) NOT NULL,
    close       NUMERIC(20,8) NOT NULL,
    volume      NUMERIC(20,8) NOT NULL,
    PRIMARY KEY (symbol, exchange, interval, timestamp)
);

-- Partition by exchange for query performance
CREATE INDEX idx_ohlcv_lookup ON historical_ohlcv (symbol, exchange, interval, timestamp DESC);
```

### Paper Trading

- Routes all signals to `SimulatedBroker` instead of real broker
- **Quote source in Phase 1:** SimulatedBroker fills against the most recent cached historical data (last close price with configurable slippage). Not true real-time, but sufficient for testing strategy logic. In Phase 2, live broker adapters provide real-time quotes.
- Virtual portfolio tracked per session (see schema below)
- Can run simultaneously with backtesting on different strategies

### Paper Trading State Schema

```sql
CREATE TABLE paper_trading_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES users(id),
    strategy_id     UUID NOT NULL REFERENCES strategies(id),
    initial_capital NUMERIC(20,8) NOT NULL,
    current_balance NUMERIC(20,8) NOT NULL,
    status          TEXT DEFAULT 'active',  -- 'active', 'stopped'
    started_at      TIMESTAMPTZ DEFAULT now(),
    stopped_at      TIMESTAMPTZ
);

CREATE TABLE paper_positions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES paper_trading_sessions(id),
    tenant_id       UUID NOT NULL REFERENCES users(id),
    symbol          TEXT NOT NULL,
    exchange        TEXT NOT NULL,
    side            TEXT NOT NULL,       -- 'long', 'short'
    quantity        NUMERIC(20,8) NOT NULL,
    avg_entry_price NUMERIC(20,8) NOT NULL,
    current_price   NUMERIC(20,8),
    unrealized_pnl  NUMERIC(20,8),
    opened_at       TIMESTAMPTZ DEFAULT now(),
    closed_at       TIMESTAMPTZ
);

CREATE TABLE paper_trades (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES paper_trading_sessions(id),
    tenant_id       UUID NOT NULL REFERENCES users(id),
    signal_id       UUID REFERENCES webhook_signals(id),
    symbol          TEXT NOT NULL,
    exchange        TEXT NOT NULL,
    action          TEXT NOT NULL,       -- 'BUY', 'SELL'
    quantity        NUMERIC(20,8) NOT NULL,
    fill_price      NUMERIC(20,8) NOT NULL,
    commission      NUMERIC(20,8) DEFAULT 0,
    slippage        NUMERIC(20,8) DEFAULT 0,
    realized_pnl    NUMERIC(20,8),
    executed_at     TIMESTAMPTZ DEFAULT now()
);
```

### Backtest Results Schema

```sql
CREATE TABLE strategy_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES users(id),
    strategy_id     UUID REFERENCES strategies(id),
    result_type     TEXT NOT NULL,  -- 'backtest'
    trade_log       JSONB NOT NULL, -- array of fills (same shape as paper_trades)
    equity_curve    JSONB NOT NULL, -- array of {timestamp, equity}
    metrics         JSONB NOT NULL, -- {total_return, sharpe_ratio, max_drawdown,
                                    --  win_rate, avg_trade_pnl, profit_factor}
    config          JSONB NOT NULL, -- {start_date, end_date, capital, slippage, ...}
    warnings        JSONB,          -- array of failed/skipped signals during backtest
    status          TEXT DEFAULT 'queued', -- queued, running, completed, failed
    error_message   TEXT,           -- populated if status = 'failed'
    created_at      TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ
);
```

**Note on JSONB trade_log scaling:** For MVP scale (<100 users), JSONB is acceptable. If backtests regularly exceed 10,000 trades, the trade log should be normalized into a separate `backtest_trades` table. This is a known trade-off — simplicity now, normalize later if needed.

---

## Analytics & PnL Dashboard

### Views

- **Overview:** Total P&L, active strategies, open positions, today's trades
- **Strategy Performance:** Per-strategy metrics (return %, Sharpe, max drawdown, win rate, profit factor). Side-by-side comparison.
- **Trade Log:** Filterable table of all trades. CSV export via `?format=csv` query param.
- **Equity Curve:** Interactive chart (TradingView Lightweight Charts). Overlay multiple strategies.
- **Drawdown Chart:** Peak-to-trough drawdown visualization

### Implementation

- Metrics pre-computed when backtest completes or paper trade closes, stored as JSONB in `strategy_results.metrics` or computed on-demand from `paper_trades`
- Dashboard reads pre-computed metrics — no heavy computation at query time
- For live paper trading, metrics refresh every 5 min via ARQ background job (or on-demand when user opens dashboard)
- Redis caches current dashboard state per user (TTL: 5 min)
- No real-time WebSocket streaming for MVP — near-real-time with last-refresh timestamp shown

---

## Alerts & Notifications (Phase 2)

### Architecture (Hooks Built in Phase 1)

```
Any event (webhook received, order filled, drawdown threshold hit)
        |
        v
+---------------------+
|  Event Bus (Redis    | -- All significant platform events published here
|  Streams)            |
+---------+-----------+
          |
          v
+---------------------+
|  Notification        | -- Phase 2: listens via consumer group, checks user
|  Worker (ARQ task)   |    preferences, dispatches to channels
+---------+-----------+
          |
          +---> Telegram Bot
          +---> Email (SMTP / Resend)
          +---> Generic Webhook (user-provided URL)
```

In Phase 1, the event bus publishes events to Redis Streams. Events are durable and persist (with a max length cap, e.g., 100,000 entries per stream). In Phase 2, the notification worker is added as a consumer group — it can process both new and historical events. No refactoring needed.

User configuration: preferences page — "Notify me via Telegram when: order filled / drawdown exceeds X% / daily P&L summary."

---

## Testing Strategy

### Unit Tests
- **Broker adapters:** Test each adapter method against mocked HTTP responses. Verify request signing (especially Exchange1 RSA), payload normalization, error handling.
- **Signal processor:** Test rule evaluation (whitelist, position limits, trading hours) with various signal + rule combinations.
- **Metrics computation:** Test Sharpe ratio, drawdown, win rate calculations against known datasets with expected outputs.
- **Webhook mapping:** Test JSONPath template evaluation against sample TradingView/ChartInk payloads.

### Integration Tests
- **Auth flow:** Signup → login → refresh → access protected endpoint. Test token expiry, invalid tokens, RLS isolation (user A cannot see user B's data).
- **Webhook → Paper Trade pipeline:** Send webhook → verify signal logged → verify paper trade executed → verify position updated → verify analytics updated.
- **Backtest execution:** Submit backtest → poll status → verify results against a known dataset with pre-computed expected metrics.

### Test Infrastructure
- PostgreSQL and Redis test instances via Docker (docker-compose.test.yml)
- `pytest` + `httpx.AsyncClient` for FastAPI testing
- Factory functions for creating test users, broker connections, strategies
- No mocking of the database — integration tests hit real PostgreSQL with RLS enabled

---

## Logging & Observability

- **Structured logging:** `structlog` with JSON output. Every log line includes `tenant_id`, `request_id`, `module`.
- **Request logging:** FastAPI middleware logs every request: method, path, status code, duration_ms, tenant_id.
- **Health endpoint:** `GET /api/v1/health` checks DB connectivity, Redis connectivity, ARQ worker heartbeat. Returns HTTP 200 or 503 with details.
- **Key metrics to monitor** (via logs, alerting added in Phase 2):
  - Webhook processing latency (p50, p95)
  - ARQ queue depth and task failure rate
  - Broker API error rates per broker type
  - Active paper trading sessions count

---

## Database Migrations

- **Tool:** Alembic with async SQLAlchemy
- **Workflow:** Migrations are auto-generated from model changes (`alembic revision --autogenerate`), reviewed manually, and committed to git.
- **RLS consideration:** Migration scripts must run as the database superuser (to create/alter RLS policies). The application connects as a restricted user that is subject to RLS policies.
- **Rollback:** Every migration includes a `downgrade()` function. Tested in CI before deployment.
- **Deployment:** Migrations run as a separate Docker entrypoint step before the API server starts (`alembic upgrade head && uvicorn ...`).

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Backend | FastAPI (Python 3.12) | Async-native, WebSocket support, trading/data ecosystem |
| Frontend | Next.js 14 (TypeScript) | SSR for dashboards, good DX |
| Database | PostgreSQL 16 + RLS | Multi-tenant isolation, mature |
| Cache/Events | Redis (Streams) | Dashboard caching, durable event bus |
| Task Queue | ARQ | Lightweight async queue, Python + Redis native |
| Charts | TradingView Lightweight Charts | Purpose-built for financial data |
| Auth | JWT (PyJWT) + bcrypt | Stateless, Bearer token (no CSRF concern) |
| Historical Data | yfinance / jugaad-data + Exchange1 API | Free data sources for MVP (see known risks above) |
| Logging | structlog | Structured JSON logging |
| Testing | pytest + httpx | Async test support, real DB integration tests |
| API Docs | FastAPI auto-generated OpenAPI | Frontend can generate TypeScript types from OpenAPI spec |
| Deployment | Docker Compose on VPS | Single command deploy |

### Frontend-Backend Contract

FastAPI auto-generates an OpenAPI 3.1 spec at `/api/v1/openapi.json`. The frontend uses `openapi-typescript` to generate TypeScript types from this spec, ensuring type safety across the stack. This is run as a build step: `npx openapi-typescript http://localhost:8000/api/v1/openapi.json -o src/lib/api-types.ts`.

---

## Project Structure

```
gain-guard/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app entry
│   │   ├── config.py               # Settings (pydantic-settings)
│   │   ├── db/
│   │   │   ├── models.py           # SQLAlchemy models
│   │   │   ├── session.py          # DB session + RLS activation
│   │   │   └── migrations/         # Alembic
│   │   ├── auth/
│   │   │   ├── router.py           # Signup, login, refresh
│   │   │   ├── deps.py             # get_current_user, get_db_session
│   │   │   └── service.py          # Password hashing, JWT, encryption
│   │   ├── brokers/
│   │   │   ├── base.py             # BrokerAdapter ABC
│   │   │   ├── simulated.py        # Paper/backtest adapter
│   │   │   ├── zerodha.py          # Phase 2
│   │   │   ├── angel_one.py        # Phase 2
│   │   │   ├── exchange1.py        # Phase 2
│   │   │   └── router.py           # Connect/disconnect endpoints
│   │   ├── webhooks/
│   │   │   ├── router.py           # Webhook receiver
│   │   │   ├── processor.py        # Signal processing + rules
│   │   │   └── mapper.py           # JSONPath mapping template engine
│   │   ├── strategies/
│   │   │   └── router.py           # Strategy CRUD
│   │   ├── backtesting/
│   │   │   ├── router.py
│   │   │   ├── engine.py           # Backtest runner
│   │   │   └── tasks.py            # ARQ background tasks
│   │   ├── paper_trading/
│   │   │   ├── router.py
│   │   │   └── engine.py
│   │   ├── analytics/
│   │   │   ├── router.py
│   │   │   ├── metrics.py          # Sharpe, drawdown, etc.
│   │   │   └── service.py
│   │   ├── events/
│   │   │   └── bus.py              # Redis Streams event bus
│   │   └── middleware/
│   │       ├── rate_limiter.py     # Redis sliding window rate limiter
│   │       └── logging.py          # Request logging middleware
│   ├── tests/
│   │   ├── conftest.py             # Fixtures: test DB, test user factory
│   │   ├── test_auth.py
│   │   ├── test_webhooks.py
│   │   ├── test_backtesting.py
│   │   └── test_paper_trading.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.test.yml     # Test infrastructure
├── frontend/
│   ├── src/
│   │   ├── app/                    # Next.js app router
│   │   ├── components/
│   │   ├── lib/
│   │   │   ├── api-client.ts       # Typed API client
│   │   │   └── api-types.ts        # Generated from OpenAPI
│   │   └── hooks/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml              # Backend + Frontend + Postgres + Redis + ARQ Worker
└── docs/
```

---

## Deployment

- **Docker Compose** with 5 services: `api` (FastAPI + Uvicorn), `worker` (ARQ), `frontend` (Next.js), `postgres`, `redis`
- **Environment variables** managed via `.env` file (gitignored). Template provided as `.env.example`.
- **SSL/TLS:** Caddy or nginx reverse proxy with automatic Let's Encrypt certificates in front of the Docker stack.
- **Backups:** Daily `pg_dump` via cron to an offsite location (S3-compatible storage or separate VPS).
- **Secrets:** `GAINGUARD_MASTER_KEY`, `JWT_SECRET`, `DATABASE_URL`, `REDIS_URL` in `.env`. For production, consider moving to Docker secrets or a vault.

---

## Phase Summary

### Phase 1 (MVP)
- User signup/auth (email + JWT)
- Broker connection management (UI + encrypted storage)
- Webhook receiver with JSONPath mapping templates and signal processing rules
- Backtesting engine with historical data (NSE/BSE + Exchange1 crypto)
- Paper trading engine with simulated fills against cached data
- Analytics dashboard (P&L, equity curve, drawdown, trade log)
- Event bus (Redis Streams, publishing events, no consumers yet)
- Health check endpoint, structured logging
- Integration test suite

### Phase 2
- Live trading via real broker adapters (Zerodha, Angel One, Fyers, Exchange1)
- Notification worker (Telegram, email, generic webhook) consuming from Redis Streams
- Real-time dashboard updates via WebSocket
- Real-time quote feed for paper trading (via live broker adapters)
- Advanced order types and risk management
- Audit logging
