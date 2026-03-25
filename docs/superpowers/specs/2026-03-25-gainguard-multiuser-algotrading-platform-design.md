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
|          | |  pubsub)|    |             |
+----------+ +---------+    +-------------+
```

**Key design decisions:**
- Single backend, multi-tenant via PostgreSQL row-level security (RLS). Every tenant-scoped table has a `tenant_id` column enforced at the DB level.
- Unified Broker Adapter interface — all brokers/exchanges implement the same abstract class. Adding a new broker = one Python module.
- Webhook-first strategy integration — platform receives signals, doesn't host strategy logic.
- Task queue (ARQ) for heavy work — backtests and data fetching run as background jobs.
- Event bus (Redis Pub/Sub) built in from Phase 1, notification workers added in Phase 2.

---

## Multi-Tenancy & Auth

### Data Model

```sql
-- users
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE,
    plan        TEXT DEFAULT 'free',  -- for future use
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
```

### Auth Flow

- Email/password signup with JWT tokens
- JWT access tokens: short-lived (15 min)
- Refresh tokens: 7 days, stored in DB, rotated on use
- Optional OAuth (Google) added later

### Security

- Broker credentials encrypted at rest using per-tenant derived key (AES-256-GCM)
- PostgreSQL RLS policies on every tenant-scoped table
- Webhook endpoints use unique per-user secret tokens: `POST /api/webhook/{user_webhook_token}`
- Rate limiting per user (60 signals/minute)

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

---

## Webhook Engine & Signal Flow

### Flow

```
TradingView / AmiBroker / ChartInk
        |
        |  POST /api/webhook/{user_webhook_token}
        |  { "symbol": "RELIANCE", "action": "BUY",
        |    "quantity": 10, "order_type": "MARKET" }
        v
+---------------------+
|  Webhook Receiver    | -- Validates token, rate-limits, parses payload
+---------+-----------+
          |
          v
+---------------------+
|  Signal Processor    | -- Applies user-defined rules:
|                      |    - Position sizing limits
|                      |    - Max open positions
|                      |    - Symbol whitelist/blacklist
|                      |    - Trading hours filter
+---------+-----------+
          |
          +---> Paper Trading Engine (Phase 1)
          |        SimulatedBroker fills against live/delayed quotes
          |
          +---> Live Broker Adapter (Phase 2)
                   Actual order to Zerodha/Exchange1/etc.
```

### Webhook Payload

Flexible JSON. Users configure a mapping template in the UI that translates their tool's output format into the platform's standard signal format. No forced schema for TradingView alerts.

### Signal Logging

Every webhook received is logged: timestamp, raw payload, parsed signal, execution result. Stored in `webhook_signals` table for debugging and analytics.

---

## Backtesting & Paper Trading Engine

### Backtesting

- User selects date range, initial capital, and replays webhook signals (or uploads CSV of historical signals)
- Runs as ARQ background task
- Configurable: slippage model (fixed/percentage), commission per trade, starting capital
- Results stored in DB: trade log, equity curve data points, drawdown series

### Historical Data

- Indian equities: `yfinance` / `jugaad-data` for NSE/BSE
- Crypto: Exchange1 REST API (`GET /openapi/v1/{category}/kline`)
- Stored in PostgreSQL: `symbol`, `interval`, `timestamp`, `O`, `H`, `L`, `C`, `V`
- Background job fetches and caches data daily

### Paper Trading

- Routes all signals to `SimulatedBroker` instead of real broker
- Fills simulated against real-time or near-real-time quotes
- Virtual portfolio per user with configurable starting capital
- Can run simultaneously with backtesting on different strategies

### Results Schema

```sql
CREATE TABLE strategy_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES users(id),
    strategy_name   TEXT NOT NULL,
    result_type     TEXT NOT NULL,  -- 'backtest' or 'paper_trade'
    trade_log       JSONB NOT NULL, -- array of fills
    equity_curve    JSONB NOT NULL, -- array of {timestamp, equity}
    metrics         JSONB NOT NULL, -- {total_return, sharpe_ratio, max_drawdown,
                                    --  win_rate, avg_trade_pnl, profit_factor}
    config          JSONB NOT NULL, -- {start_date, end_date, capital, slippage, ...}
    status          TEXT DEFAULT 'running', -- running, completed, failed
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

---

## Analytics & PnL Dashboard

### Views

- **Overview:** Total P&L, active strategies, open positions, today's trades
- **Strategy Performance:** Per-strategy metrics (return %, Sharpe, max drawdown, win rate, profit factor). Side-by-side comparison.
- **Trade Log:** Filterable table of all trades. CSV export.
- **Equity Curve:** Interactive chart (TradingView Lightweight Charts). Overlay multiple strategies.
- **Drawdown Chart:** Peak-to-trough drawdown visualization

### Implementation

- Metrics pre-computed when backtest completes or paper trade closes, stored as JSONB
- Dashboard reads pre-computed metrics — no heavy computation at query time
- For live paper trading, metrics refresh every 5 min via background job (or on-demand)
- Redis caches current dashboard state per user
- No real-time WebSocket streaming for MVP — near-real-time with last-refresh timestamp shown

---

## Alerts & Notifications (Phase 2)

### Architecture (Hooks Built in Phase 1)

```
Any event (webhook received, order filled, drawdown threshold hit)
        |
        v
+---------------------+
|  Event Bus (Redis    | -- All significant platform events publish here
|  Pub/Sub)            |
+---------+-----------+
          |
          v
+---------------------+
|  Notification        | -- Phase 2: listens for events, checks user
|  Worker (ARQ task)   |    preferences, dispatches to channels
+---------+-----------+
          |
          +---> Telegram Bot
          +---> Email (SMTP / Resend)
          +---> Generic Webhook (user-provided URL)
```

In Phase 1, the event bus is built and events are published. Nothing listens. In Phase 2, the notification worker is plugged in — no refactoring needed.

User configuration: preferences page — "Notify me via Telegram when: order filled / drawdown exceeds X% / daily P&L summary."

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Backend | FastAPI (Python 3.12) | Async-native, WebSocket support, trading/data ecosystem |
| Frontend | Next.js 14 (TypeScript) | SSR for dashboards, good DX |
| Database | PostgreSQL 16 + RLS | Multi-tenant isolation, mature |
| Cache/PubSub | Redis | Session cache, event bus, dashboard caching |
| Task Queue | ARQ | Lightweight async queue, Python + Redis native |
| Charts | TradingView Lightweight Charts | Purpose-built for financial data |
| Auth | JWT (PyJWT) + bcrypt | Simple, stateless |
| Historical Data | yfinance / jugaad-data + Exchange1 API | Free data sources for MVP |
| Deployment | Docker Compose on VPS | Single command deploy |

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
│   │   │   ├── session.py          # DB session + RLS setup
│   │   │   └── migrations/         # Alembic
│   │   ├── auth/
│   │   │   ├── router.py           # Signup, login, refresh
│   │   │   ├── deps.py             # get_current_user dependency
│   │   │   └── service.py
│   │   ├── brokers/
│   │   │   ├── base.py             # BrokerAdapter ABC
│   │   │   ├── simulated.py        # Paper/backtest adapter
│   │   │   ├── zerodha.py
│   │   │   ├── angel_one.py
│   │   │   ├── exchange1.py
│   │   │   └── router.py           # Connect/disconnect endpoints
│   │   ├── webhooks/
│   │   │   ├── router.py           # Webhook receiver
│   │   │   ├── processor.py        # Signal processing + rules
│   │   │   └── models.py
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
│   │   └── events/
│   │       └── bus.py              # Redis pub/sub event bus
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/                    # Next.js app router
│   │   ├── components/
│   │   ├── lib/                    # API client, auth helpers
│   │   └── hooks/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml              # Backend + Frontend + Postgres + Redis
└── docs/
```

---

## Phase Summary

### Phase 1 (MVP)
- User signup/auth (email + JWT)
- Broker connection management (UI + encrypted storage)
- Webhook receiver with signal processing and user-defined rules
- Backtesting engine with historical data (NSE/BSE + Exchange1 crypto)
- Paper trading engine with simulated fills
- Analytics dashboard (P&L, equity curve, drawdown, trade log)
- Event bus (publishing only, no listeners yet)

### Phase 2
- Live trading via real broker adapters (Zerodha, Angel One, Fyers, Exchange1)
- Notification worker (Telegram, email, generic webhook)
- Real-time dashboard updates via WebSocket
- Advanced order types and risk management
