# AlgoMatter — Comprehensive Technical Documentation

> Last updated: 2026-04-10

---

## Table of Contents

1. [Overview](#1-overview)
2. [Infrastructure](#2-infrastructure)
3. [Backend Architecture](#3-backend-architecture)
4. [Database Schema](#4-database-schema)
5. [Authentication & Security](#5-authentication--security)
6. [Webhook Signal Pipeline](#6-webhook-signal-pipeline)
7. [Broker Adapter System](#7-broker-adapter-system)
8. [Paper Trading Engine](#8-paper-trading-engine)
9. [Backtesting System](#9-backtesting-system)
10. [Live Deployments](#10-live-deployments)
11. [Analytics System](#11-analytics-system)
12. [ARQ Background Worker](#12-arq-background-worker)
13. [Structured Logging & Observability](#13-structured-logging--observability)
14. [Frontend Architecture](#14-frontend-architecture)
15. [API Reference Summary](#15-api-reference-summary)
16. [Deployment Guide](#16-deployment-guide)
17. [Key Design Decisions](#17-key-design-decisions)

---

## 1. Overview

AlgoMatter is a multi-tenant algorithmic trading platform that lets users:

- **Create trading strategies** with Python code or webhook-driven signal mapping
- **Paper trade** with simulated capital to test strategies risk-free
- **Backtest** strategies against historical OHLCV data using Nautilus Trader
- **Deploy live** to connected brokers via webhook signals or automated runners
- **Analyze** performance with equity curves, drawdown charts, and trade logs
- **Manage brokers** — connect, configure, and monitor live exchange accounts

The system is built around a **webhook-first architecture**: external tools (TradingView, Pine Script, custom bots) send JSON payloads to user-specific webhook URLs. The platform maps those signals to standardized orders, evaluates configurable rules, and executes them against the target mode (paper/live/log).

---

## 2. Infrastructure

### Production Server

| Property | Value |
|----------|-------|
| Provider | Contabo VPS |
| IP | `194.61.31.226` |
| OS | Linux |
| Domain | `algomatter.in` (SSL via Let's Encrypt / certbot) |
| SSH | `root@194.61.31.226` via `~/.ssh/id_ed25519` |

### Services (Systemd)

| Service | Description | Port |
|---------|-------------|------|
| `algomatter-api` | FastAPI backend (uvicorn) | 8000 |
| `algomatter-worker` | ARQ background job worker | — |
| `algomatter-strategy-runner` | Strategy deployment runner | — |
| `algomatter-frontend` | Next.js app (basePath `/app`) | 3000 |
| `algomatter-website` | Next.js marketing site | 3001 |

### Nginx Reverse Proxy

Nginx sits in front of all services and terminates SSL:

- `algomatter.in/` → Next.js website (port 3001)
- `algomatter.in/app/` → Next.js app (port 3000, basePath `/app`)
- `algomatter.in/api/` → FastAPI backend (port 8000)

### Infrastructure (Docker Compose)

Located at `/opt/algomatter/docker-compose.infra.yml`:

```yaml
services:
  postgres:
    image: postgres:16
    volumes: [pgdata:/var/lib/postgresql/data]
  redis:
    image: redis:7-alpine
```

PostgreSQL 16 is the primary database. Redis 7 serves both as the ARQ job queue and application cache.

### Development Environment

AlgoMatter uses **Nix** for reproducible local development:

```bash
cd algomatter/
nix develop    # enters dev shell with Node 20, Python 3, pip, virtualenv, nginx
```

Backend virtualenv: `backend/.venv`
Frontend: `frontend/` (npm)

### Package Installation Pattern

The backend Python package is installed as `algomatter-0.1.0` in `.venv/site-packages`. This is important: **rsync alone does not update the installed package**. After any backend code change on the server:

```bash
cd /opt/algomatter/backend && .venv/bin/pip install --no-cache-dir .
```

Without this, the ARQ worker imports the old installed version, not the rsynced source files.

---

## 3. Backend Architecture

### Technology Stack

| Component | Technology |
|-----------|-----------|
| Web Framework | FastAPI (Python 3.12+) |
| ASGI Server | Uvicorn |
| ORM | SQLAlchemy 2.x (async) |
| Database | PostgreSQL 16 |
| Job Queue | ARQ (async Redis Queue) |
| Cache | Redis 7 |
| Logging | structlog with JSON output |
| Migrations | Alembic |
| Encryption | Fernet (symmetric) |
| Testing | pytest + httpx |
| Package Manager | pip + virtualenv (Nix-managed) |

### Application Entry Point

`backend/app/main.py` bootstraps the FastAPI application:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Redis connection pools
    app.state.redis = await aioredis.from_url(settings.REDIS_URL)
    app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    yield
    await app.state.redis.close()
    await app.state.arq_pool.close()
```

**Structlog** is configured globally with:
- Custom `_inject_trace_id` processor that reads from `trace_id_var` ContextVar
- stdlib logging bridge (for SQLAlchemy, uvicorn, etc.)
- `PrintLoggerFactory` with JSON output
- `add_log_level`, `TimeStamper(fmt="iso")`, `ExceptionRenderer`

Note: `add_logger_name` is intentionally excluded — it requires a stdlib Logger with `.name`, which `PrintLoggerFactory` does not provide.

### Directory Structure

```
backend/app/
├── main.py                  # FastAPI app, lifespan, middleware, routers
├── context.py               # trace_id_var ContextVar
├── config.py                # Settings (from environment variables)
├── feature_flags.py         # Feature toggle definitions
├── auth/                    # JWT authentication
│   ├── router.py            # /api/v1/auth/* endpoints
│   ├── service.py           # Token creation, validation
│   └── dependencies.py      # get_current_user FastAPI dependency
├── db/
│   ├── models.py            # All SQLAlchemy ORM models
│   ├── session.py           # Async engine, session factory, RLS helper
│   └── migrations/          # Alembic migrations
├── brokers/
│   ├── base.py              # BrokerAdapter ABC + OrderRequest/Response models
│   ├── exchange1.py         # Exchange1 Global adapter
│   ├── binance_testnet.py   # Binance Testnet adapter
│   ├── simulated.py         # Simulated broker for paper trading
│   ├── factory.py           # Broker instantiation by type
│   ├── router.py            # /api/v1/brokers/* endpoints
│   └── schemas.py           # Pydantic request/response schemas
├── webhooks/
│   ├── router.py            # Public + authenticated webhook endpoints
│   └── executor.py          # Signal processing, ARQ job management
├── strategies/
│   └── router.py            # Strategy CRUD, code versioning
├── paper_trading/
│   ├── engine.py            # Trade simulation logic
│   └── router.py            # Paper session management endpoints
├── backtesting/
│   └── router.py            # Backtest submission endpoints
├── deployments/
│   └── router.py            # Deployment management endpoints
├── strategy_runner/
│   └── runner.py            # Automated strategy execution loop
├── analytics/
│   └── router.py            # P&L, metrics, equity curve endpoints
├── manual_trades/
│   └── router.py            # Manual order placement endpoints
├── historical/
│   └── router.py            # OHLCV data fetch and cache endpoints
├── crypto/
│   └── encryption.py        # Fernet-based credential encryption
├── middleware/
│   ├── logging.py           # RequestLoggingMiddleware (trace ID injection)
│   └── rate_limiter.py      # Per-user rate limiting via Redis
└── nautilus_integration/    # Nautilus Trader SDK bridge
```

### Request Middleware Chain

1. **Rate Limiter** — checks Redis per-user request count, returns 429 if exceeded
2. **RequestLoggingMiddleware** — generates `X-Request-ID` (or passes through if provided), sets `trace_id_var`, logs request start/end with duration

### CORS Configuration

Development origins allowed:
- `http://localhost:3000`
- `http://localhost:5173`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:5173`

Production adds:
- `https://algomatter.in`
- `https://www.algomatter.in`
- `http://194.61.31.226`

---

## 4. Database Schema

### Row-Level Security (RLS)

Every table with user data is protected by PostgreSQL Row-Level Security policies. Before any query, the session sets:

```sql
SET app.current_tenant_id = '<user_uuid>';
```

This is handled by `activate_rls(session, user_id)` in `db/session.py`. All queries automatically filter to the current tenant without application-level WHERE clauses.

### Models

#### `users`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `email` | String | Unique, indexed |
| `password_hash` | String | bcrypt |
| `webhook_token` | String | Random UUID, used in webhook URLs |
| `plan` | String | `"free"`, `"pro"`, `"enterprise"` |
| `created_at` | DateTime | UTC |

#### `refresh_tokens`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users |
| `token_hash` | String | SHA256 of the token |
| `expires_at` | DateTime | |
| `revoked` | Boolean | Soft-delete on logout |

#### `broker_connections`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users |
| `broker_type` | String | `"exchange1"`, `"binance_testnet"` |
| `display_name` | String | User-provided label |
| `credentials_encrypted` | Text | Fernet-encrypted JSON |
| `is_active` | Boolean | |
| `last_verified_at` | DateTime | |
| `extra_config` | JSONB | Broker-specific settings |

#### `strategies`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users |
| `name` | String | |
| `slug` | String | URL-safe identifier for webhook targeting |
| `description` | Text | |
| `is_active` | Boolean | Controls webhook processing |
| `execution_mode` | String | `"paper"`, `"live"`, `"log"` |
| `broker_connection_id` | UUID | FK → broker_connections (nullable) |
| `mapping_template` | JSONB | Signal-to-order field mapping |
| `rules` | JSONB | Array of evaluation rules |
| `paper_session_id` | UUID | FK → paper_trading_sessions (nullable) |
| `created_at` | DateTime | |

**`mapping_template` schema:**
```json
{
  "symbol": {"type": "fixed", "value": "BTC"},
  "action": {"type": "jsonpath", "path": "$.action"},
  "quantity": {"type": "fixed", "value": "1"},
  "order_type": {"type": "fixed", "value": "MARKET"},
  "product_type": {"type": "fixed", "value": "FUTURES"},
  "leverage": {"type": "fixed", "value": "10"},
  "position_model": {"type": "fixed", "value": "isolated"}
}
```

**`rules` schema (array of rule objects):**
```json
[
  {"type": "max_open_positions", "value": 3},
  {"type": "max_daily_signals", "value": 10},
  {"type": "allowed_symbols", "value": ["BTC", "ETH"]}
]
```

#### `webhook_signals`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users |
| `strategy_id` | UUID | FK → strategies |
| `strategy_name` | String | Denormalized for query efficiency |
| `raw_payload` | JSONB | Original webhook body |
| `parsed_signal` | JSONB | Mapped signal fields |
| `status` | String | Rule evaluation result: `"passed"`, `"blocked_by_rule"`, `"mapping_error"` |
| `execution_result` | String | `"filled"`, `"queued"`, `"recovering"`, `"broker_error"`, `"cancelled"`, `"log_only"` |
| `execution_detail` | JSONB | Fill price, order ID, broker response |
| `error_message` | Text | Error description if failed |
| `received_at` | DateTime | |

#### `paper_trading_sessions`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users |
| `strategy_id` | UUID | FK → strategies (nullable) |
| `name` | String | |
| `status` | String | `"active"`, `"stopped"` |
| `initial_capital` | Numeric | Starting balance |
| `current_balance` | Numeric | Cash balance (updated on each trade) |
| `created_at` | DateTime | |
| `stopped_at` | DateTime | |

#### `paper_positions`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `session_id` | UUID | FK → paper_trading_sessions |
| `symbol` | String | |
| `side` | String | `"long"` / `"short"` |
| `quantity` | Numeric | |
| `avg_entry_price` | Numeric | |
| `unrealized_pnl` | Numeric | |
| `opened_at` | DateTime | |
| `closed_at` | DateTime | Null if open |

#### `paper_trades`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `session_id` | UUID | FK → paper_trading_sessions |
| `position_id` | UUID | FK → paper_positions |
| `symbol` | String | |
| `action` | String | `"BUY"` / `"SELL"` |
| `quantity` | Numeric | |
| `fill_price` | Numeric | |
| `commission` | Numeric | |
| `realized_pnl` | Numeric | |
| `executed_at` | DateTime | |

#### `manual_trades`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users |
| `broker_connection_id` | UUID | FK → broker_connections |
| `symbol` | String | |
| `action` | String | `"BUY"` / `"SELL"` |
| `order_type` | String | `"MARKET"`, `"LIMIT"`, `"SL"`, `"SL-M"` |
| `quantity` | Numeric | |
| `price` | Numeric | Null for market orders |
| `fill_price` | Numeric | After execution |
| `fill_quantity` | Numeric | |
| `status` | String | `"open"`, `"filled"`, `"cancelled"`, `"rejected"` |
| `broker_order_id` | String | Exchange-assigned ID |
| `created_at` | DateTime | |

#### `strategy_codes`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users |
| `name` | String | |
| `current_code` | Text | Latest Python strategy code |
| `created_at` | DateTime | |

#### `strategy_code_versions`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `strategy_code_id` | UUID | FK → strategy_codes |
| `version` | Integer | Auto-incrementing |
| `code` | Text | Snapshot at this version |
| `created_at` | DateTime | |

#### `strategy_deployments`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users |
| `strategy_code_id` | UUID | FK → strategy_codes |
| `broker_connection_id` | UUID | FK → broker_connections |
| `status` | String | `"running"`, `"stopped"`, `"error"` |
| `config` | JSONB | Deployment parameters |
| `started_at` | DateTime | |
| `stopped_at` | DateTime | |

---

## 5. Authentication & Security

### JWT Token Strategy

AlgoMatter uses a **dual-token** approach:

- **Access token** — short-lived JWT (15 minutes), sent as `Authorization: Bearer <token>`
- **Refresh token** — long-lived random UUID (30 days), stored hashed in `refresh_tokens` table, sent as httponly cookie or in response body

Token flow:
```
Login → {access_token, refresh_token}
     → Use access_token for all API calls
     → When expired: POST /auth/refresh with refresh_token → new access_token
     → Logout: POST /auth/logout → refresh_token revoked in DB
```

### Password Security

Passwords are hashed with **bcrypt** (work factor 12) before storage. Plain passwords are never persisted.

### Credential Encryption

Broker API credentials (keys, secrets, RSA private keys) are encrypted at rest using **Fernet** symmetric encryption:

- Encryption key stored in `CREDENTIAL_ENCRYPTION_KEY` environment variable
- `crypto/encryption.py` provides `encrypt(data: str) → str` and `decrypt(data: str) → str`
- Credentials are decrypted only at the moment of order placement inside ARQ worker

### Row-Level Security

PostgreSQL RLS ensures users can only see their own data. The application:
1. Authenticates the user via JWT
2. Extracts user UUID
3. Sets `app.current_tenant_id` in each database session
4. PostgreSQL RLS policies automatically filter all queries

This means even if a bug bypassed application-level auth, the database would not return other users' data.

### Webhook Token Authentication

Webhook endpoints use a simpler token scheme (no JWT):
- Each user has a `webhook_token` (UUID) stored in `users` table
- Webhook URL: `/api/v1/webhook/{token}` or `/api/v1/webhook/{token}/{strategy_slug}`
- Users can regenerate their token at any time (invalidates old webhook URLs)

### Rate Limiting

A Redis-based rate limiter middleware applies per-user request limits to prevent abuse. Limits are configured via environment variables.

### Content Security Policy

The frontend Next.js app sets CSP headers via `next.config.mjs`:
- Development: allows `http://localhost:8000` and `http://localhost:3000` as connect-src
- Production: patched at deploy time to `https://algomatter.in`

---

## 6. Webhook Signal Pipeline

This is the core feature of AlgoMatter. The complete flow from webhook receipt to order placement is:

### Step 1: Webhook Ingestion

```
POST /api/v1/webhook/{token}
POST /api/v1/webhook/{token}/{slug}
```

1. Validate token against user's `webhook_token` field
2. Check payload size (reject if > MAX_PAYLOAD_BYTES)
3. Parse JSON body
4. If slug provided: route to that specific strategy only
5. If no slug: find all active strategies for this user (cached in Redis for 60s)

### Step 2: Signal Mapping

For each matched strategy, the raw JSON payload is transformed using the strategy's `mapping_template`:

```python
def apply_mapping(payload: dict, template: dict) -> StandardSignal:
    result = {}
    for field, spec in template.items():
        if spec["type"] == "fixed":
            result[field] = spec["value"]
        elif spec["type"] == "jsonpath":
            result[field] = jsonpath_ng.parse(spec["path"]).find(payload)[0].value
    return StandardSignal(**result)
```

If mapping fails (missing field, JSONPath no match), the signal is recorded with `status="mapping_error"` and processing stops.

### Step 3: Rule Evaluation

Each strategy has a `rules` array. Rules are evaluated in order:

| Rule Type | Description |
|-----------|-------------|
| `max_open_positions` | Block if user has ≥ N open positions in this strategy |
| `max_daily_signals` | Block if ≥ N signals processed today for this strategy |
| `allowed_symbols` | Block if signal symbol not in allowed list |
| `allowed_hours` | Block if current UTC hour not in allowed range |

If any rule blocks the signal: record `status="blocked_by_rule"`, stop processing.

### Step 4: Mode-Specific Execution

Based on `strategy.execution_mode`:

#### Paper Mode
```python
result = await execute_paper_trade(session, strategy.paper_session_id, signal)
```
Runs synchronously in the request handler, returns fill/reject immediately.

#### Live Mode
```python
job_id = await arq_pool.enqueue_job(
    "execute_live_order_task",
    job_payload={
        "signal": signal.dict(),
        "broker_connection_id": str(strategy.broker_connection_id),
        "trace_id": trace_id_var.get(""),
    }
)
```
Enqueues an ARQ background job, returns `execution_result="queued"` immediately to the caller.

#### Log Mode
Records the signal with `execution_result="log_only"`. No execution.

### Step 5: Result Persistence

A `WebhookSignal` record is written with:
- Raw payload, mapped signal, rule evaluation status
- Execution result and any execution details (fill price, order ID, error)
- Structured logs emitted at each step for observability

### Step 6: ARQ Live Order Execution

`execute_live_order_task()` in `executor.py`:

1. Restore trace ID from job payload
2. Decrypt broker credentials from DB
3. Instantiate broker adapter via factory
4. Call `broker.place_order(order_request)`
5. Update `WebhookSignal.execution_result` to `"filled"` or `"broker_error"`
6. Store fill details in `execution_detail` JSONB

### Queued Signal Recovery

A cron job (`recover_queued_signals`) runs every 5 minutes to recover stuck signals:

```python
# Signals older than 3 minutes still in queued/recovering state
signals = await db.execute(
    select(WebhookSignal).where(
        WebhookSignal.execution_result.in_(["queued", "recovering"]),
        WebhookSignal.received_at < datetime.utcnow() - timedelta(minutes=3)
    )
)
# Atomically mark as recovering, then re-enqueue
```

Re-enqueuing uses the same `job_id` so ARQ deduplicates if the original job is still running.

---

## 7. Broker Adapter System

### Abstract Base Class

`brokers/base.py` defines `BrokerAdapter`:

```python
class BrokerAdapter(ABC):
    @abstractmethod
    async def authenticate(self) -> bool: ...

    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResponse: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderResponse: ...

    @abstractmethod
    async def get_balance(self, product_type: str) -> AccountBalance: ...

    @abstractmethod
    async def get_positions(self) -> list[Position]: ...

    @abstractmethod
    async def get_quotes(self, symbols: list[str]) -> dict[str, Decimal]: ...

    @abstractmethod
    async def get_historical(self, symbol: str, interval: str, limit: int) -> list[OHLCVBar]: ...
```

### Data Models

```python
class OrderRequest(BaseModel):
    symbol: str
    exchange: str
    action: Literal["BUY", "SELL"]
    quantity: Decimal
    order_type: Literal["MARKET", "LIMIT", "SL", "SL-M"]
    price: Decimal
    product_type: Literal["INTRADAY", "DELIVERY", "CNC", "MIS", "FUTURES"]
    trigger_price: Decimal | None = None
    leverage: int | None = None
    position_model: str | None = None   # "isolated" → "fix", "cross" → "cross"
    take_profit: Decimal | None = None
    stop_loss: Decimal | None = None
    position_side: Literal["long", "short"] | None = None

class OrderResponse(BaseModel):
    order_id: str
    status: Literal["filled", "open", "rejected", "cancelled"]
    fill_price: Decimal | None = None
    fill_quantity: Decimal | None = None
    message: str = ""

class AccountBalance(BaseModel):
    available: Decimal
    total: Decimal
    currency: str

class Position(BaseModel):
    symbol: str
    side: str
    quantity: Decimal
    avg_entry_price: Decimal
    unrealized_pnl: Decimal
```

### Exchange1 Adapter

`brokers/exchange1.py` implements the Exchange1 Global/India API.

**Authentication:**
- RSA SHA256WithRSA signature on all requests
- Headers: `X-SAASAPI-API-KEY`, `X-SAASAPI-TIMESTAMP`, `X-SAASAPI-SIGN`
- Signature: sort params by ASCII, concatenate as `key=value&...`, sign with RSA private key, base64 encode

**Order Routing Dispatch Table:**

| Action | Position Side | Route |
|--------|--------------|-------|
| BUY | long (default) | `POST /futures/order/create` with `positionSide=long` |
| SELL | short | `POST /futures/order/create` with `positionSide=short` |
| SELL | long (default) | `POST /futures/order/close` (close long) |
| BUY | short | `POST /futures/order/close` (close short) |

**Balance Logic:**

Exchange1 India uses INR for futures margin, stored in the `asset` account (not `cfd`). The adapter handles this:

```python
if product_type == "FUTURES":
    # Try cfd account first (Exchange1 Global)
    for acc in accounts:
        if acc["account_type"] == "cfd":
            if Decimal(acc.get("available_margin", "0")) > 0:
                return AccountBalance(available=..., currency="USDT")
    # Fallback to asset account (Exchange1 India uses INR)
    for acc in accounts:
        if acc["account_type"] == "asset":
            return AccountBalance(available=..., currency="INR")
```

**Order ID Encoding:**

Futures orders encode the positionType and symbol into the ID for cancellation:
```
futures:{positionType}:{symbol}:{raw_exchange_id}
```

This allows the adapter to reconstruct the cancel request parameters.

**Key Constraints:**
- Cannot close the same position within 30 seconds
- `takeProfitPrice`/`stopLossPrice` in create order payload causes 401 sign error — must be stripped
- `positionModel=fix` means isolated margin, `cross` means cross margin
- Error 9050: margin mode mismatch (strategy config vs account setting)
- Error 9012: position not found (trying to close non-existent position)
- Error 9257: no isolated-margin wallet for symbol
- All states returned as uppercase; adapter lowercases before mapping

**USDT/INR Rate:**

Exchange1 India quotes prices in INR. The adapter derives the USDT/INR rate by comparing BTCINR and BTCUSDT orderbooks.

### Binance Testnet Adapter

`brokers/binance_testnet.py` connects to Binance's testnet API for safe testing without real funds. Uses standard Binance REST API with HMAC-SHA256 signing.

### Simulated Broker

`brokers/simulated.py` is used internally by the paper trading engine. Always returns filled orders at the provided price. No external API calls.

### Broker Factory

`brokers/factory.py` instantiates the correct adapter:

```python
def create_broker(broker_type: str, credentials: dict) -> BrokerAdapter:
    if broker_type == "exchange1":
        return Exchange1Adapter(**credentials)
    elif broker_type == "binance_testnet":
        return BinanceTestnetAdapter(**credentials)
    raise ValueError(f"Unknown broker: {broker_type}")
```

---

## 8. Paper Trading Engine

`paper_trading/engine.py` provides `execute_paper_trade()`.

### BUY Flow

```
1. Load paper session → validate status == "active"
2. Validate price > 0 and quantity > 0
3. Compute cost = price × quantity + commission
4. Check current_balance >= cost → reject if insufficient
5. Create PaperPosition (side="long", avg_entry_price=price)
6. Create PaperTrade (action="BUY", fill_price=price, realized_pnl=0)
7. current_balance -= cost
8. Return OrderResponse(status="filled")
```

### SELL Flow

```
1. Load paper session → validate status == "active"
2. Validate price > 0 and quantity > 0
3. Find open PaperPosition for symbol → reject if not found
4. Compute realized_pnl = (price - avg_entry_price) × quantity - commission
5. Close position (set closed_at = now())
6. Create PaperTrade (action="SELL", realized_pnl=...)
7. current_balance += price × quantity - commission
8. Return OrderResponse(status="filled")
```

### Logging

All paper trade events are structured-logged:
- `paper_trade_rejected` with `reason`, `symbol`, `cost`, `balance`
- `paper_trade_filled` with `action`, `symbol`, `quantity`, `fill_price`, `balance_after`

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/paper-trading/sessions` | Create new paper session |
| `GET /api/v1/paper-trading/sessions` | List all sessions |
| `GET /api/v1/paper-trading/sessions/{id}` | Session detail with positions and trades |
| `POST /api/v1/paper-trading/sessions/{id}/stop` | Stop session (close all positions) |

---

## 9. Backtesting System

### Nautilus Trader Integration

AlgoMatter integrates with [Nautilus Trader](https://nautilustrader.io/) for backtesting. Nautilus is a high-performance algorithmic trading engine written in Python and Rust.

`nautilus_integration/` bridges user strategy code to Nautilus actor patterns:
- User writes strategy in AlgoMatter's Python SDK (`strategy_sdk/`)
- Bridge wraps it in a Nautilus Actor
- Backtest runs against historical OHLCV data from `historical_ohlcv` table

### Historical Data

`historical/router.py` manages OHLCV data:
- Fetches from Exchange1's Binance API historical endpoint
- Caches in `historical_ohlcv` PostgreSQL table with composite key `(symbol, interval, timestamp)`
- Used by backtesting and strategy runner

### Backtest Execution

```
POST /api/v1/backtesting/run
→ Validates strategy code
→ Enqueues ARQ job: run_backtest_task
→ Returns job_id for polling

GET /api/v1/backtesting/results/{job_id}
→ Returns StrategyResult with equity curve, metrics, trade log
```

The backtest runs in the ARQ worker process (separate from the API server) to avoid blocking.

---

## 10. Live Deployments

Live deployments allow strategies to run automatically on a schedule (rather than waiting for webhook signals).

### Models

- `strategy_deployments` — records of running/stopped deployments
- `deployment_state` — current positions, orders, and portfolio state
- `deployment_logs` — execution log entries
- `deployment_trades` — trades executed by the deployment

### Strategy Runner

`strategy_runner/runner.py` is a separate systemd service (`algomatter-strategy-runner`) that:
1. Loads all running deployments from DB
2. Instantiates strategy code as a Python class
3. Runs the strategy's `on_bar()` method on each new candle
4. Places orders via the broker adapter when the strategy signals

---

## 11. Analytics System

`analytics/router.py` provides read-only metrics endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/analytics/strategies` | All strategies with aggregate metrics |
| `GET /api/v1/analytics/strategies/{id}` | Single strategy overview |
| `GET /api/v1/analytics/strategies/{id}/metrics` | Win rate, Sharpe, drawdown, etc. |
| `GET /api/v1/analytics/strategies/{id}/equity-curve` | Time-series equity data |
| `GET /api/v1/analytics/strategies/{id}/trades` | Full trade log (CSV export supported) |

### Metrics Computed

| Metric | Formula |
|--------|---------|
| Total Return | Sum of all realized P&L |
| Win Rate | (Profitable trades / Total trades) × 100 |
| Profit Factor | Gross profit / Gross loss |
| Sharpe Ratio | Mean daily return / Std dev of daily returns × √252 |
| Max Drawdown | Largest peak-to-trough equity decline (%) |
| Total Trades | Count of all filled trades |

### Equity Curve Construction

Equity curves are built from trade data:
1. Sort trades by `executed_at`
2. Accumulate `realized_pnl - commission` onto initial capital
3. Group by date (daily points)
4. Return `{time: "2024-01-15", value: 105320}` array

---

## 12. ARQ Background Worker

### Configuration

`backend/worker.py`:

```python
class WorkerSettings:
    functions = [run_backtest_task, execute_live_order_task]
    cron_jobs = [
        cron(daily_data_fetch, hour=6, minute=0),  # 6 AM UTC
        cron(recover_queued_signals, minute={0, 5, 10, ...}),  # Every 5 min
    ]
    max_jobs = 100          # Concurrent job limit
    job_timeout = 3600      # 1 hour max per job
    keep_result = 86400     # 24 hour result TTL in Redis
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
```

### Jobs

#### `execute_live_order_task(ctx, job_payload)`

The live order execution job:

```python
async def execute_live_order_task(ctx: dict, job_payload: dict) -> dict:
    # 1. Restore trace ID for correlation
    _token = trace_id_var.set(job_payload.get("trace_id", ""))
    try:
        return await _execute_live_order(ctx, job_payload)
    finally:
        trace_id_var.reset(_token)

async def _execute_live_order(ctx, payload):
    # 2. Decrypt credentials
    # 3. Instantiate broker
    # 4. place_order()
    # 5. Update WebhookSignal record
    # 6. Log result
```

**Critical**: The `_max_retries` ARQ kwarg is NOT used — this ARQ version serializes it into the job kwargs dict and passes it as a function argument, causing `TypeError`. Retry logic is handled by `recover_queued_signals` instead.

#### `run_backtest_task(ctx, job_payload)`

Runs a full Nautilus backtest, stores `StrategyResult` with equity data.

#### `daily_data_fetch(ctx)`

Cron at 6 AM UTC. Fetches and caches latest OHLCV data for all tracked symbols.

#### `recover_queued_signals(ctx)`

Cron every 5 minutes. Finds `WebhookSignal` records stuck in `"queued"` or `"recovering"` state for more than 3 minutes, marks them `"recovering"`, and re-enqueues the ARQ job with the same `_job_id` (ARQ deduplicates).

### Running the Worker

```bash
cd backend
.venv/bin/arq worker.WorkerSettings
```

---

## 13. Structured Logging & Observability

### structlog Configuration

```python
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        _inject_trace_id,              # Custom: reads trace_id_var ContextVar
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)
```

All log output is JSON, one object per line — ready for ingestion by log aggregators (Datadog, Grafana Loki, etc.).

### Trace ID Propagation

```python
# context.py
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
```

1. **HTTP Request** → `RequestLoggingMiddleware` generates `X-Request-ID` UUID, sets `trace_id_var`
2. **Signal Processing** → trace_id flows naturally (same async context)
3. **ARQ Job Enqueue** → trace_id extracted and stored in job payload dict
4. **ARQ Job Execute** → trace_id restored from payload via `trace_id_var.set()`
5. All `structlog` calls emit `trace_id` field → end-to-end correlation possible

### Log Events

Key log events emitted throughout the system:

| Event | Location | Key Fields |
|-------|----------|------------|
| `webhook_received` | webhooks/router.py | `strategy_count`, `payload_size` |
| `webhook_payload_too_large` | webhooks/router.py | `size`, `max_size` |
| `webhook_invalid_json` | webhooks/router.py | `error` |
| `webhook_strategy_not_found` | webhooks/router.py | `slug` |
| `signal_mapping_error` | executor.py | `strategy_id`, `error` |
| `signal_rule_blocked` | executor.py | `strategy_id`, `rule` |
| `signal_dispatched` | router.py | `strategy_id`, `mode` |
| `live_order_queued` | executor.py | `strategy_id`, `job_id` |
| `live_order_task_start` | executor.py | `job_id`, `trace_id` |
| `live_order_placed` | executor.py | `order_id`, `fill_price`, `status` |
| `live_order_broker_error` | executor.py | `error`, `broker_type` |
| `paper_trade_filled` | engine.py | `action`, `symbol`, `fill_price`, `balance_after` |
| `paper_trade_rejected` | engine.py | `reason`, `symbol`, `cost`, `balance` |

### Viewing Logs (Production)

```bash
# API service logs
ssh root@194.61.31.226 'journalctl -u algomatter-api --no-pager -n 100'

# Worker logs
ssh root@194.61.31.226 'journalctl -u algomatter-worker --no-pager -n 100'

# Strategy runner logs
ssh root@194.61.31.226 'journalctl -u algomatter-strategy-runner --no-pager -n 100'
```

---

## 14. Frontend Architecture

### Technology Stack

| Component | Technology |
|-----------|-----------|
| Framework | Next.js 14 (App Router) |
| UI Library | Chakra UI v2 |
| Data Fetching | SWR (stale-while-revalidate) |
| Code Editor | Monaco Editor |
| Charts | Recharts |
| HTTP Client | Custom `apiClient` wrapper |

### Directory Structure

```
frontend/
├── app/
│   ├── (dashboard)/        # Authenticated app shell
│   │   ├── layout.tsx      # Sidebar + header shell
│   │   ├── paper-trading/  # Paper trading pages
│   │   ├── live-trading/   # Manual order placement
│   │   ├── backtesting/    # Backtest runner
│   │   ├── strategies/     # Strategy editor
│   │   ├── webhooks/       # Webhook config + signal log
│   │   ├── brokers/        # Broker connection management
│   │   ├── analytics/      # Performance analytics
│   │   └── settings/       # User settings
│   ├── (auth)/             # Login/signup pages
│   └── api/                # Next.js API routes (proxies to FastAPI)
├── components/
│   ├── shared/             # Reusable components
│   │   ├── DataTable.tsx   # Sortable table with loading state
│   │   ├── StatCard.tsx    # Metric display card
│   │   ├── StatusBadge.tsx # Colored status indicator
│   │   ├── Pagination.tsx  # Prev/Next pagination control
│   │   └── ConfirmModal.tsx # Confirmation dialog
│   ├── charts/
│   │   ├── EquityCurve.tsx      # Area chart for equity
│   │   ├── DrawdownChart.tsx    # Drawdown visualization
│   │   └── ChartContainer.tsx   # Timeframe filter wrapper
│   ├── strategies/
│   │   ├── WebhookParameterBuilder.tsx  # Signal mapping UI
│   │   └── WebhookTradesTable.tsx       # Filtered trade log
│   └── trade/
│       ├── TradeHistory.tsx     # Open/history order log
│       └── BrokerCapabilities.ts # Per-broker config constants
├── lib/
│   ├── api/
│   │   ├── client.ts       # apiClient fetch wrapper
│   │   └── types.ts        # TypeScript API type definitions
│   ├── hooks/
│   │   ├── useApi.ts        # SWR data-fetching hooks
│   │   └── useManualTrades.ts # Manual trades hooks
│   └── utils/
│       └── formatters.ts   # formatCurrency, formatDate, formatPercent
└── next.config.mjs         # Next.js config, rewrites, CSP headers
```

### API Client

`lib/api/client.ts` — a typed fetch wrapper:

```typescript
export async function apiClient<T>(
  path: string,
  options?: { method?: string; body?: unknown; rawResponse?: boolean }
): Promise<T> {
  const res = await fetch(path, {
    method: options?.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getAccessToken()}`,
    },
    body: options?.body ? JSON.stringify(options.body) : undefined,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  if (options?.rawResponse) return res as unknown as T;
  return res.json();
}
```

Access tokens are stored in memory (not localStorage) and refreshed automatically on 401.

### SWR Data Fetching

All data fetching uses SWR hooks in `lib/hooks/useApi.ts`:

```typescript
function useApiGet<T>(url: string, options?: SWROptions) {
  return useSWR<T>(url, (url) => apiClient(url), options);
}
```

Polling intervals (for real-time data):
- Signals: 5 seconds
- Trades: 10 seconds
- Balances: 30 seconds
- Strategy list: 60 seconds

### Pagination Strategy

Two approaches are used depending on data source:

**Server-side pagination** (offset sent to API):
- Webhook signals (`/api/v1/webhooks/signals?offset=N&limit=50`)
- Manual trades (`/api/v1/trades/manual?offset=N&limit=50`)

**Client-side pagination** (full data fetched, sliced in component):
- Analytics trades (full set needed for equity curve computation)
- Paper trading trades (full set needed for equity curve)
- WebhookTradesTable (filtered subset of signals)

The shared `Pagination` component (`components/shared/Pagination.tsx`):
- Renders Prev/Next buttons + `"X–Y of Z"` label
- Hidden when all data fits on one page (`total <= pageSize`)

### Key Pages

#### Strategy Editor (`/strategies/[id]`)
- Tabs: Overview, Code (Monaco), Webhook mapping, Signal log
- `WebhookParameterBuilder` for visual signal mapping with Futures/Spot mode tabs
- Webhook URL displayed with strategy-specific slug for targeted signals

#### Webhooks (`/webhooks`)
- Broadcast URL with copy button
- Per-strategy URLs table with copy buttons
- Signal log with server-side pagination

#### Paper Trading (`/paper-trading/[id]`)
- StatCards: Initial Capital, Current Equity, Unrealized P&L, Realized P&L, Open Positions
- Positions tab + Trades tab (paginated)
- Equity curve chart (built from full trade set)

#### Analytics Strategy Detail (`/analytics/strategies/[id]`)
- Metric StatCards (6 KPIs)
- Equity Curve + Drawdown side-by-side charts with timeframe filter
- Trade log with CSV export + pagination

#### Broker Detail (`/brokers/[id]`)
- Separate Futures and Spot balance display
- Currency-aware (INR for Exchange1 India futures)
- Open positions table

### WebhookParameterBuilder

`components/strategies/WebhookParameterBuilder.tsx` — complex UI for building signal mapping:

- **Futures mode**: symbol, leverage, position model (isolated/cross), position side
- **Spot mode**: symbol only
- Each field: toggle between "Fixed value" (user types it) and "JSONPath" (maps from payload)
- On edit: restores from saved `mapping_template` via `useEffect` with `initializedRef` guard (runs once on first render)

```typescript
useEffect(() => {
  if (initializedRef.current || !value) return;
  initializedRef.current = true;
  // Parse value (mapping_template) and populate internal state
}, [value]);
```

---

## 15. API Reference Summary

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/auth/signup` | None | Register new user |
| POST | `/api/v1/auth/login` | None | Login, get tokens |
| POST | `/api/v1/auth/refresh` | Refresh token | Get new access token |
| POST | `/api/v1/auth/logout` | Bearer | Revoke refresh token |
| GET | `/api/v1/auth/me` | Bearer | Current user profile |

### Strategies

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/strategies` | List all strategies |
| POST | `/api/v1/strategies` | Create strategy |
| GET | `/api/v1/strategies/{id}` | Get strategy |
| PUT | `/api/v1/strategies/{id}` | Update strategy |
| DELETE | `/api/v1/strategies/{id}` | Delete strategy |

### Webhooks

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/webhook/{token}` | Token | Broadcast signal |
| POST | `/api/v1/webhook/{token}/{slug}` | Token | Strategy-specific signal |
| GET | `/api/v1/webhooks/config` | Bearer | Get webhook URL + token |
| POST | `/api/v1/webhooks/config/regenerate-token` | Bearer | Rotate token |
| GET | `/api/v1/webhooks/signals` | Bearer | Signal log (paginated) |
| GET | `/api/v1/webhooks/signals/strategy/{id}` | Bearer | Signals for strategy |

### Brokers

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/brokers` | List connections |
| POST | `/api/v1/brokers` | Add broker connection |
| GET | `/api/v1/brokers/{id}` | Get broker detail |
| PUT | `/api/v1/brokers/{id}` | Update connection |
| DELETE | `/api/v1/brokers/{id}` | Remove connection |
| GET | `/api/v1/brokers/{id}/balance` | Get account balance |
| GET | `/api/v1/brokers/{id}/positions` | Get open positions |

### Paper Trading

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/paper-trading/sessions` | List sessions |
| POST | `/api/v1/paper-trading/sessions` | Create session |
| GET | `/api/v1/paper-trading/sessions/{id}` | Session detail |
| POST | `/api/v1/paper-trading/sessions/{id}/stop` | Stop session |

### Manual Trades

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/trades/manual` | Trade history (paginated) |
| GET | `/api/v1/trades/manual/open` | Open orders |
| POST | `/api/v1/trades/manual` | Place order |
| POST | `/api/v1/trades/manual/{id}/cancel` | Cancel order |

### Analytics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/analytics/strategies` | All strategy metrics |
| GET | `/api/v1/analytics/strategies/{id}/metrics` | KPIs |
| GET | `/api/v1/analytics/strategies/{id}/equity-curve` | Time-series equity |
| GET | `/api/v1/analytics/strategies/{id}/trades` | Trade log |

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | DB + Redis health check |

---

## 16. Deployment Guide

### Standard Deployment (Backend + Frontend)

```bash
# 1. Read credentials
SERVER_PASS=$(grep '^password:' ../contabo-server.txt | awk '{print $2}')

# 2. Rsync backend
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e rsync -avz --progress -e "ssh -o StrictHostKeyChecking=no" \
  --exclude=".venv" --exclude="__pycache__" --exclude="*.egg-info" --exclude=".env" \
  backend/ root@194.61.31.226:/opt/algomatter/backend/'

# 3. Rsync frontend
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e rsync -avz --progress -e "ssh -o StrictHostKeyChecking=no" \
  --exclude="node_modules" --exclude=".next" \
  frontend/ root@194.61.31.226:/opt/algomatter/frontend/'

# 4. Install Python package (CRITICAL - rsync alone is not enough)
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "cd /opt/algomatter/backend && .venv/bin/pip install --no-cache-dir . 2>&1 | tail -5"'

# 5. Run migrations
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "cd /opt/algomatter/backend && .venv/bin/alembic upgrade head"'

# 6. Build frontend
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "cd /opt/algomatter/frontend && NODE_OPTIONS=\"--max-old-space-size=512\" NEXT_PUBLIC_API_BASE_URL=\"\" npm run build 2>&1 | tail -5"'

# 7. Restart services
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "systemctl restart algomatter-api algomatter-worker algomatter-strategy-runner algomatter-frontend"'

# 8. Verify (wait 8s for API startup)
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "sleep 8 && curl -s https://algomatter.in/api/v1/health"'
```

### Environment Variables

Backend `.env` (at `/opt/algomatter/backend/.env` — never synced):

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `SECRET_KEY` | JWT signing secret |
| `CREDENTIAL_ENCRYPTION_KEY` | Fernet key for broker credentials |
| `ENVIRONMENT` | `"production"` |

### Alembic Migrations

```bash
# Generate migration
cd backend
.venv/bin/alembic revision --autogenerate -m "description"

# Apply on server
.venv/bin/alembic upgrade head

# Rollback one
.venv/bin/alembic downgrade -1
```

---

## 17. Key Design Decisions

### Why Webhook-First?

Webhooks allow AlgoMatter to be compatible with any signal source without custom integrations:
- TradingView Pine Script alerts
- Custom Python bots
- Third-party signal providers

The platform decouples signal generation from execution.

### Why ARQ for Live Orders?

Live order placement must survive API request failures. By enqueueing to Redis before responding to the webhook caller:
- The webhook endpoint is fast (returns 200 immediately)
- Order execution is durable (Redis persists across restarts)
- Recovery cron handles stuck jobs automatically

### Why Pip Install vs Rsync?

The backend runs as an installed Python package (`algomatter-0.1.0`). Python's import system resolves from the installed location, not from source files. Rsync updates source but ARQ worker imports from the installed package. Solution: always `pip install --no-cache-dir .` after syncing.

### Why PostgreSQL RLS?

RLS provides a defense-in-depth guarantee: even if application auth is bypassed, the database enforces tenant isolation. This is particularly important because the application uses a single database user for all tenants (simpler connection pooling) rather than per-tenant database users.

### Why ContextVar for Trace IDs?

Python's `asyncio` propagates `contextvars.ContextVar` automatically within a coroutine tree. This means setting the trace ID in the middleware automatically propagates to all async callees without passing it explicitly. For ARQ (different process/context), the trace ID is explicitly included in the job payload and restored at job start.

### Client-side vs Server-side Pagination

- **Analytics/paper trading**: full dataset fetched because equity curve requires all trades to compute cumulative P&L. Pagination is then applied client-side.
- **Webhook signals/manual trades**: can grow to thousands of records; server-side pagination with offset/limit reduces payload and DB query cost.

### Structured Logging vs Print Debugging

All application events are emitted as JSON log lines with consistent fields (`trace_id`, `event`, `level`, `timestamp`). This allows:
- Correlation of a single user request across HTTP handler → ARQ job
- Easy grep/filter in log aggregators
- No ambiguity about log levels or event types

---

*End of AlgoMatter Technical Documentation*
