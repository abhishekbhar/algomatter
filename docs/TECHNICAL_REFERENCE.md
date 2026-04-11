# AlgoMatter — Complete Technical Reference

> This document is a comprehensive technical reference sufficient to recreate the AlgoMatter application from scratch. It covers architecture, database schema, API contracts, business logic, data flows, configuration, and frontend structure.

---

## Table of Contents

1. [Application Overview](#1-application-overview)
2. [System Architecture](#2-system-architecture)
3. [Infrastructure & Deployment](#3-infrastructure--deployment)
4. [Database Schema](#4-database-schema)
5. [Backend API Reference](#5-backend-api-reference)
6. [Core Business Logic](#6-core-business-logic)
7. [Background Jobs & Crons](#7-background-jobs--crons)
8. [Broker Adapters](#8-broker-adapters)
9. [Security & Authentication](#9-security--authentication)
10. [Configuration & Environment Variables](#10-configuration--environment-variables)
11. [Frontend Structure](#11-frontend-structure)
12. [Frontend Pages & Routes](#12-frontend-pages--routes)
13. [Frontend Components](#13-frontend-components)
14. [Frontend Hooks & API Client](#14-frontend-hooks--api-client)
15. [Key Data Flows](#15-key-data-flows)
16. [External Integrations](#16-external-integrations)
17. [Redis Key Reference](#17-redis-key-reference)
18. [Feature Flags & Limits](#18-feature-flags--limits)
19. [Dependencies](#19-dependencies)

---

## 1. Application Overview

**AlgoMatter** is a multi-tenant algorithmic trading platform. It allows users to:

- **Webhook Strategies** — receive trading signals via HTTP webhooks from external tools (TradingView, custom bots), map payload fields to order parameters, apply rule filters, and execute orders on connected brokers.
- **Hosted Strategies** — write Python trading strategies in-app, version them, and deploy as backtests, paper trades, or live executions on a cron schedule.
- **Paper Trading** — simulate order execution with virtual capital, tracking positions and P&L.
- **Manual Trading** — place individual orders directly through connected broker accounts.
- **Analytics** — view trade history, P&L, equity curves, win rate, Sharpe ratio, and drawdown metrics across all strategies.

**Tech Stack:**
- Backend: Python 3.12, FastAPI, SQLAlchemy 2 (async), PostgreSQL 16, Redis 7, ARQ
- Frontend: Next.js 14 (App Router), React 18, Chakra UI 2, SWR
- Infrastructure: Systemd services, Nginx reverse proxy, Docker (DB/Redis), Let's Encrypt SSL

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Browser                        │
│                 Next.js App (basePath: /app)                 │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTPS
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Nginx (algomatter.in)                      │
│  /app/*  → algomatter-frontend (Next.js, port 3000)          │
│  /api/*  → algomatter-api (FastAPI, port 8000)               │
│  /       → algomatter-website (marketing site, port 3001)    │
└───────┬──────────────────────────┬──────────────────────────┘
        │                          │
        ▼                          ▼
┌───────────────┐        ┌─────────────────────┐
│  FastAPI API  │        │  Next.js Frontend    │
│  (port 8000)  │        │  (port 3000)         │
│               │        │                      │
│ ┌───────────┐ │        │  SWR polling (5–30s) │
│ │  Routers  │ │        │  Token auto-refresh  │
│ │  Services │ │        │  Feature flags ctx   │
│ │  Brokers  │ │        └─────────────────────┘
│ └─────┬─────┘ │
│       │       │
│ ┌─────▼─────┐ │     ┌─────────────────────┐
│ │SQLAlchemy │─┼────▶│  PostgreSQL 16       │
│ │  (async)  │ │     │  (Docker)            │
│ └─────┬─────┘ │     │  Row-Level Security  │
│       │       │     └─────────────────────┘
│ ┌─────▼─────┐ │
│ │  Redis    │ │     ┌─────────────────────┐
│ │  Client   │─┼────▶│  Redis 7 (Docker)   │
│ └───────────┘ │     │  Cache + Rate limit │
└───────┬───────┘     │  + ARQ job queue    │
        │             └─────────────────────┘
        ▼
┌───────────────┐
│  ARQ Worker   │   Background jobs: order recovery,
│  (port N/A)   │   daily data fetch, backtest runner
└───────────────┘
        │
        ▼
┌───────────────────────────────┐
│  Broker Adapters              │
│  ├─ Exchange1 REST API        │
│  ├─ Binance Testnet REST API  │
│  └─ Simulated Engine          │
└───────────────────────────────┘
```

### Multi-Tenancy

All data is isolated per user (tenant) via:
1. `tenant_id` column on every table (FK to `users.id`)
2. PostgreSQL Row-Level Security (RLS) — `SET LOCAL app.current_tenant_id = '{id}'` per transaction
3. JWT-based authentication — `tenant_id` extracted from token for every request
4. AES-GCM credential encryption with HKDF-derived per-tenant keys

---

## 3. Infrastructure & Deployment

### Production Server

- **Host:** `194.61.31.226` (Contabo VPS)
- **OS:** Linux
- **SSH:** `root@194.61.31.226` with `~/.ssh/id_ed25519`
- **Domain:** `algomatter.in` (SSL via Let's Encrypt / Certbot)

### Systemd Services

| Service | Command | Port | Description |
|---------|---------|------|-------------|
| `algomatter-api` | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | 8000 | FastAPI backend |
| `algomatter-worker` | `python -m arq worker.WorkerSettings` | — | ARQ background worker |
| `algomatter-strategy-runner` | Strategy runner process | — | Scheduled strategy execution |
| `algomatter-frontend` | `npm run start` (Next.js) | 3000 | Dashboard frontend |
| `algomatter-website` | `npm run start` (Next.js) | 3001 | Marketing website |

### Docker (Database & Cache)

**File:** `/opt/algomatter/docker-compose.infra.yml`

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: algomatter
      POSTGRES_USER: algomatter
      POSTGRES_PASSWORD: <secret>
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    volumes:
      - redis_data:/data
```

### Nginx Configuration

```nginx
# API
location /api/ {
    proxy_pass http://127.0.0.1:8000;
}

# Frontend app
location /app/ {
    proxy_pass http://127.0.0.1:3000;
}

# Marketing site
location / {
    proxy_pass http://127.0.0.1:3001;
}
```

### Deployment Process

```bash
# 1. Rsync backend
rsync -avz --exclude='.venv' --exclude='__pycache__' \
  backend/ root@194.61.31.226:/opt/algomatter/backend/

# 2. Install Python deps (if pyproject.toml changed)
ssh root@194.61.31.226 'cd /opt/algomatter/backend && .venv/bin/pip install -e .'

# 3. Run DB migrations
ssh root@194.61.31.226 'cd /opt/algomatter/backend && .venv/bin/alembic upgrade head'

# 4. Restart backend services
ssh root@194.61.31.226 'systemctl restart algomatter-api algomatter-worker'

# 5. Build and deploy frontend
rsync -avz frontend/ root@194.61.31.226:/opt/algomatter/frontend/
ssh root@194.61.31.226 'cd /opt/algomatter/frontend && npm install && npm run build'
ssh root@194.61.31.226 'systemctl restart algomatter-frontend'
```

---

## 4. Database Schema

### Entity Relationship Overview

```
users
  ├── refresh_tokens (1:M)
  ├── broker_connections (1:M)
  ├── strategies (1:M) ──────────────────┐
  │     └── webhook_signals (1:M)        │
  │     └── paper_trading_sessions (1:M) │ (via strategy_id)
  ├── strategy_codes (1:M)               │
  │     ├── strategy_code_versions (1:M) │
  │     └── strategy_deployments (1:M)   │
  │           ├── deployment_states (1:1)│
  │           ├── deployment_logs (1:M)  │
  │           ├── deployment_trades (1:M)│
  │           └── strategy_results (1:M) │
  ├── paper_trading_sessions (1:M) ──────┘
  │     ├── paper_positions (1:M)
  │     └── paper_trades (1:M)
  ├── manual_trades (1:M)
  └── historical_ohlcv (shared, no FK)
      exchange_instruments (shared, no FK)
```

---

### Table: `users`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | User identifier |
| `email` | VARCHAR(255) | UNIQUE NOT NULL | Login email |
| `password_hash` | TEXT | NOT NULL | Bcrypt hash |
| `is_active` | BOOLEAN | DEFAULT TRUE | Account status |
| `plan` | VARCHAR(50) | DEFAULT 'free' | Subscription plan |
| `webhook_token` | VARCHAR(64) | DEFAULT random | Secret for webhook auth |
| `created_at` | TIMESTAMPTZ | server_default NOW() | Registration time |

---

### Table: `refresh_tokens`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Token ID |
| `user_id` | UUID | FK→users.id CASCADE | Owner |
| `token_hash` | TEXT | NOT NULL | SHA256 of token |
| `expires_at` | TIMESTAMPTZ | NOT NULL | Expiry |
| `created_at` | TIMESTAMPTZ | server_default NOW() | Created |

---

### Table: `broker_connections`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Connection ID |
| `tenant_id` | UUID | FK→users.id NOT NULL | Owner |
| `broker_type` | VARCHAR(50) | NOT NULL | 'binance_testnet', 'exchange1' |
| `label` | VARCHAR(40) | NOT NULL | User-facing name |
| `credentials` | BYTEA | NOT NULL | AES-GCM encrypted JSON |
| `is_active` | BOOLEAN | DEFAULT TRUE | Connection status |
| `connected_at` | TIMESTAMPTZ | server_default NOW() | Created |

**Indexes:** UNIQUE (tenant_id, label)

---

### Table: `strategies`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Strategy ID |
| `tenant_id` | UUID | FK→users.id NOT NULL INDEXED | Owner |
| `name` | VARCHAR(255) | NOT NULL | Display name |
| `slug` | VARCHAR(255) | NOT NULL | URL-safe identifier |
| `broker_connection_id` | UUID | FK→broker_connections.id SET NULL | Broker (nullable) |
| `mode` | VARCHAR(50) | DEFAULT 'paper' | 'paper', 'live', 'log' |
| `mapping_template` | JSON | nullable | JSONPath field mapping |
| `rules` | JSON | DEFAULT {} | Execution rules |
| `is_active` | BOOLEAN | DEFAULT TRUE | Receives signals |
| `created_at` | TIMESTAMPTZ | server_default NOW() | Created |

**Indexes:** UNIQUE (tenant_id, slug)

**`rules` JSON structure:**
```json
{
  "symbol_whitelist": ["NIFTY", "BANKNIFTY"],
  "symbol_blacklist": ["PENNY1"],
  "max_positions": 10,
  "max_signals_per_day": 50,
  "trading_hours": {
    "start": "09:15",
    "end": "15:30",
    "timezone": "Asia/Kolkata"
  },
  "dual_leg": {
    "enabled": true,
    "max_trades": 5
  }
}
```

**`mapping_template` JSON structure:**
```json
{
  "exchange": "EXCHANGE1",
  "product_type": "FUTURES",
  "symbol": "BTCUSDT",
  "action": "$.action",
  "order_type": "MARKET",
  "quantity": "$.qty",
  "leverage": 10,
  "position_model": "cross",
  "price": "$.price"
}
```
Values prefixed with `$.` are JSONPath refs into the webhook payload. Others are fixed.

---

### Table: `webhook_signals`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Signal ID |
| `tenant_id` | UUID | FK→users.id NOT NULL | Owner |
| `strategy_id` | UUID | FK→strategies.id nullable | Target strategy |
| `received_at` | TIMESTAMPTZ | server_default NOW() | Arrival time |
| `raw_payload` | JSON | NOT NULL | Original webhook body |
| `parsed_signal` | JSON | nullable | Mapped StandardSignal |
| `rule_result` | VARCHAR(50) | nullable | 'passed', 'blocked_by_rule', 'mapping_error' |
| `rule_detail` | TEXT | nullable | Reason if blocked |
| `execution_result` | VARCHAR(50) | nullable | 'filled', 'accepted', 'rejected', 'queued', 'recovering', 'broker_error' |
| `execution_detail` | JSON | nullable | Order response or error details |
| `processing_ms` | INTEGER | nullable | Processing latency |

**Indexes:** (tenant_id, received_at), (tenant_id, strategy_id, received_at)

**`parsed_signal` JSON structure:**
```json
{
  "symbol": "BTCUSDT",
  "exchange": "EXCHANGE1",
  "product_type": "FUTURES",
  "action": "BUY",
  "order_type": "MARKET",
  "quantity": 1.0,
  "leverage": 10,
  "position_model": "cross",
  "price": null
}
```

**`execution_detail` JSON structure (success):**
```json
{
  "order_id": "algomatter-xxx",
  "broker_order_id": "broker-123",
  "status": "filled",
  "fill_price": "42000.00",
  "fill_quantity": "1.0",
  "message": "",
  "placed_at": "2026-04-11T10:00:00Z"
}
```

**`execution_detail` JSON structure (error):**
```json
{
  "error": "Insufficient margin",
  "broker_error_code": "9001"
}
```

---

### Table: `paper_trading_sessions`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Session ID |
| `tenant_id` | UUID | FK→users.id NOT NULL INDEXED | Owner |
| `strategy_id` | UUID | FK→strategies.id nullable | Webhook strategy |
| `strategy_code_id` | UUID | FK→strategy_codes.id nullable | Hosted strategy |
| `initial_capital` | NUMERIC(20,8) | NOT NULL | Starting balance |
| `current_balance` | NUMERIC(20,8) | NOT NULL | Current balance |
| `status` | VARCHAR(50) | DEFAULT 'active' | 'active', 'stopped' |
| `started_at` | TIMESTAMPTZ | server_default NOW() | Session start |
| `stopped_at` | TIMESTAMPTZ | nullable | Session end |

---

### Table: `paper_positions`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Position ID |
| `session_id` | UUID | FK→paper_trading_sessions.id NOT NULL | Session |
| `tenant_id` | UUID | FK→users.id NOT NULL | Owner |
| `symbol` | VARCHAR(50) | NOT NULL | Trading symbol |
| `exchange` | VARCHAR(50) | NOT NULL | Exchange name |
| `side` | VARCHAR(10) | NOT NULL | 'long' (from BUY) |
| `quantity` | NUMERIC(20,8) | NOT NULL | Position size |
| `avg_entry_price` | NUMERIC(20,8) | NOT NULL | Average entry |
| `current_price` | NUMERIC(20,8) | nullable | Last known price |
| `unrealized_pnl` | NUMERIC(20,8) | nullable | Unrealized P&L |
| `opened_at` | TIMESTAMPTZ | server_default NOW() | Opened |
| `closed_at` | TIMESTAMPTZ | nullable | Closed (null = open) |

**Indexes:** (session_id, symbol)

---

### Table: `paper_trades`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Trade ID |
| `session_id` | UUID | FK→paper_trading_sessions.id NOT NULL | Session |
| `tenant_id` | UUID | FK→users.id NOT NULL | Owner |
| `signal_id` | UUID | FK→webhook_signals.id nullable | Source signal |
| `symbol` | VARCHAR(50) | NOT NULL | Symbol |
| `exchange` | VARCHAR(50) | NOT NULL | Exchange |
| `action` | VARCHAR(20) | NOT NULL | 'BUY', 'SELL' |
| `quantity` | NUMERIC(20,8) | NOT NULL | Size |
| `fill_price` | NUMERIC(20,8) | NOT NULL | Simulated fill price |
| `commission` | NUMERIC(20,8) | DEFAULT 0 | Fee |
| `slippage` | NUMERIC(20,8) | DEFAULT 0 | Slippage |
| `realized_pnl` | NUMERIC(20,8) | nullable | P&L (SELL only) |
| `executed_at` | TIMESTAMPTZ | server_default NOW() | Execution time |

---

### Table: `strategy_codes`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Strategy code ID |
| `tenant_id` | UUID | FK→users.id NOT NULL INDEXED | Owner |
| `name` | VARCHAR(255) | NOT NULL | Display name |
| `description` | TEXT | nullable | Description |
| `code` | TEXT | NOT NULL | Current Python code |
| `version` | INTEGER | DEFAULT 1 | Current version number |
| `entrypoint` | VARCHAR(100) | DEFAULT 'Strategy' | Python class name |
| `created_at` | TIMESTAMPTZ | server_default NOW() | Created |
| `updated_at` | TIMESTAMPTZ | server_default NOW() | Last modified |

---

### Table: `strategy_code_versions`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Version ID |
| `tenant_id` | UUID | FK→users.id NOT NULL INDEXED | Owner |
| `strategy_code_id` | UUID | FK→strategy_codes.id CASCADE INDEXED | Parent strategy |
| `version` | INTEGER | NOT NULL | Version number |
| `code` | TEXT | NOT NULL | Snapshot of code |
| `created_at` | TIMESTAMPTZ | server_default NOW() | Created |

**Indexes:** UNIQUE (strategy_code_id, version)

---

### Table: `strategy_deployments`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Deployment ID |
| `tenant_id` | UUID | FK→users.id NOT NULL INDEXED | Owner |
| `strategy_code_id` | UUID | FK→strategy_codes.id CASCADE INDEXED | Strategy |
| `strategy_code_version_id` | UUID | FK→strategy_code_versions.id CASCADE | Version deployed |
| `mode` | VARCHAR(20) | NOT NULL | 'backtest', 'paper', 'live' |
| `status` | VARCHAR(20) | DEFAULT 'pending' | 'pending', 'running', 'paused', 'stopped', 'completed', 'failed' |
| `symbol` | VARCHAR(20) | NOT NULL | e.g. 'BTCUSDT' |
| `exchange` | VARCHAR(20) | NOT NULL | e.g. 'BINANCE' |
| `product_type` | VARCHAR(20) | DEFAULT 'DELIVERY' | 'DELIVERY', 'INTRADAY', 'FUTURES', 'CNC', 'MIS' |
| `interval` | VARCHAR(10) | NOT NULL | '1m', '5m', '1h', '1d' |
| `broker_connection_id` | UUID | FK→broker_connections.id CASCADE nullable | Broker |
| `cron_expression` | VARCHAR(50) | nullable | e.g. '*/5 * * * *' |
| `config` | JSON | DEFAULT {} | User config params |
| `params` | JSON | DEFAULT {} | Runtime params |
| `promoted_from_id` | UUID | FK→strategy_deployments.id SET NULL nullable | Promotion source |
| `created_at` | TIMESTAMPTZ | server_default NOW() | Created |
| `started_at` | TIMESTAMPTZ | nullable | When started |
| `stopped_at` | TIMESTAMPTZ | nullable | When stopped |

---

### Table: `deployment_states`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `deployment_id` | UUID | PK FK→strategy_deployments.id CASCADE | Deployment |
| `tenant_id` | UUID | FK→users.id NOT NULL INDEXED | Owner |
| `position` | JSON | nullable | Current position state |
| `open_orders` | JSON | DEFAULT [] | Open order array |
| `portfolio` | JSON | DEFAULT {} | Holdings/balances |
| `user_state` | JSON | DEFAULT {} | Custom strategy state |
| `updated_at` | TIMESTAMPTZ | server_default NOW() | Last updated |

---

### Table: `deployment_logs`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Log entry ID |
| `tenant_id` | UUID | FK→users.id NOT NULL INDEXED | Owner |
| `deployment_id` | UUID | FK→strategy_deployments.id CASCADE INDEXED | Deployment |
| `timestamp` | TIMESTAMPTZ | server_default NOW() | Log time |
| `level` | VARCHAR(10) | DEFAULT 'info' | 'info', 'warning', 'error' |
| `message` | TEXT | NOT NULL | Log content |

---

### Table: `deployment_trades`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Trade ID |
| `tenant_id` | UUID | FK→users.id NOT NULL INDEXED | Owner |
| `deployment_id` | UUID | FK→strategy_deployments.id CASCADE INDEXED | Deployment |
| `order_id` | VARCHAR(32) | NOT NULL | Internal order ID |
| `broker_order_id` | VARCHAR(64) | nullable | Broker's order ID |
| `action` | VARCHAR(10) | NOT NULL | 'BUY', 'SELL' |
| `quantity` | NUMERIC | NOT NULL | Order size |
| `order_type` | VARCHAR(10) | NOT NULL | 'MARKET', 'LIMIT', 'SL', 'SL-M' |
| `price` | NUMERIC | nullable | Limit price |
| `trigger_price` | NUMERIC | nullable | Stop trigger |
| `fill_price` | NUMERIC | nullable | Actual fill price |
| `fill_quantity` | NUMERIC | nullable | Actual fill size |
| `status` | VARCHAR(20) | NOT NULL DEFAULT 'submitted' | 'submitted', 'filled', 'open', 'rejected', 'cancelled' |
| `is_manual` | BOOLEAN | DEFAULT FALSE | Manual order flag |
| `realized_pnl` | NUMERIC | nullable | Realized P&L |
| `created_at` | TIMESTAMPTZ | server_default NOW() | Created |
| `filled_at` | TIMESTAMPTZ | nullable | Fill time |

---

### Table: `strategy_results`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Result ID |
| `tenant_id` | UUID | FK→users.id NOT NULL | Owner |
| `strategy_id` | UUID | FK→strategies.id nullable | Webhook strategy |
| `deployment_id` | UUID | FK→strategy_deployments.id CASCADE nullable | Deployment |
| `strategy_code_version_id` | UUID | FK→strategy_code_versions.id CASCADE nullable | Version |
| `result_type` | VARCHAR(50) | NOT NULL | 'backtest', 'paper_summary' |
| `trade_log` | JSON | nullable | Array of trades |
| `equity_curve` | JSON | nullable | Time-series equity values |
| `metrics` | JSON | nullable | Sharpe, Sortino, win_rate, etc. |
| `config` | JSON | nullable | Run configuration |
| `warnings` | JSON | nullable | Strategy warnings |
| `status` | VARCHAR(50) | DEFAULT 'queued' | 'queued', 'running', 'completed', 'failed' |
| `error_message` | TEXT | nullable | Failure reason |
| `created_at` | TIMESTAMPTZ | server_default NOW() | Created |
| `completed_at` | TIMESTAMPTZ | nullable | Completion time |

---

### Table: `manual_trades`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Trade ID |
| `tenant_id` | UUID | FK→users.id NOT NULL | Owner |
| `broker_connection_id` | UUID | FK→broker_connections.id CASCADE NOT NULL | Broker |
| `symbol` | VARCHAR(32) | NOT NULL | Symbol |
| `exchange` | VARCHAR(32) | NOT NULL | Exchange |
| `product_type` | VARCHAR(16) | NOT NULL | 'SPOT', 'FUTURES', etc. |
| `action` | VARCHAR(8) | NOT NULL | 'BUY', 'SELL' |
| `quantity` | FLOAT | NOT NULL | Order size |
| `order_type` | VARCHAR(16) | NOT NULL | 'MARKET', 'LIMIT', 'SL', 'SL-M' |
| `price` | FLOAT | nullable | Limit price |
| `trigger_price` | FLOAT | nullable | Stop trigger |
| `leverage` | INTEGER | nullable | Leverage multiplier |
| `position_model` | VARCHAR(16) | nullable | 'isolated', 'cross' |
| `position_side` | VARCHAR(16) | nullable | 'long', 'short' |
| `take_profit` | FLOAT | nullable | TP price |
| `stop_loss` | FLOAT | nullable | SL price |
| `fill_price` | FLOAT | nullable | Actual fill |
| `fill_quantity` | FLOAT | nullable | Actual size |
| `status` | VARCHAR(16) | NOT NULL DEFAULT 'submitted' | Order status |
| `broker_order_id` | VARCHAR(64) | nullable | Broker's ID |
| `broker_symbol` | VARCHAR(32) | nullable | Broker-normalized symbol |
| `error_message` | VARCHAR(512) | nullable | Error if failed |
| `created_at` | TIMESTAMPTZ | server_default NOW() | Created |
| `updated_at` | TIMESTAMPTZ | onupdate NOW() | Last updated |
| `filled_at` | TIMESTAMPTZ | nullable | Fill time |

---

### Table: `historical_ohlcv`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `symbol` | VARCHAR(50) | PK (composite) | Trading symbol |
| `exchange` | VARCHAR(50) | PK (composite) | Exchange |
| `interval` | VARCHAR(10) | PK (composite) | '1m', '5m', '1h', '1d' |
| `timestamp` | TIMESTAMPTZ | PK (composite) | Candle open time |
| `open` | NUMERIC(20,8) | NOT NULL | Open price |
| `high` | NUMERIC(20,8) | NOT NULL | High price |
| `low` | NUMERIC(20,8) | NOT NULL | Low price |
| `close` | NUMERIC(20,8) | NOT NULL | Close price |
| `volume` | NUMERIC(20,8) | NOT NULL | Volume |

---

### Table: `exchange_instruments`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PK autoincrement | ID |
| `exchange` | VARCHAR(50) | NOT NULL INDEXED | Exchange name |
| `symbol` | VARCHAR(50) | NOT NULL | Symbol |
| `base_asset` | VARCHAR(20) | NOT NULL | Base currency |
| `quote_asset` | VARCHAR(20) | NOT NULL | Quote currency |
| `product_type` | VARCHAR(20) | NOT NULL | 'SPOT', 'FUTURES', 'DELIVERY' |
| `is_active` | BOOLEAN | DEFAULT TRUE | Tradeable |

**Indexes:** UNIQUE (exchange, symbol, product_type)

---

## 5. Backend API Reference

**Base URL:** `https://algomatter.in/api/v1`

**Auth:** All routes except `POST /auth/signup`, `POST /auth/login`, `POST /auth/refresh`, and webhook ingestion (`POST /webhook/{token}*`) require `Authorization: Bearer <access_token>` header.

---

### Authentication (`/api/v1/auth`)

| Method | Path | Request Body | Response | Description |
|--------|------|--------------|----------|-------------|
| POST | `/auth/signup` | `{email, password}` | `{access_token, refresh_token, token_type}` | Register. Min 8-char password. |
| POST | `/auth/login` | `{email, password}` | `{access_token, refresh_token, token_type}` | Login |
| POST | `/auth/refresh` | `{refresh_token}` | `{access_token, refresh_token}` | Refresh tokens |
| POST | `/auth/logout` | — | 204 | Revoke refresh token |
| GET | `/auth/me` | — | `User` | Current user profile |

---

### Webhook Ingestion (`/api/v1/webhook`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/webhook/{token}` | Token | Broadcast to all active strategies |
| POST | `/webhook/{token}/{slug}` | Token | Route to specific strategy |

**Response:**
```json
{
  "received": true,
  "signals_processed": 2
}
```

---

### Webhook Config (`/api/v1/webhooks`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/webhooks/config` | Get webhook URL and token |
| POST | `/webhooks/config/regenerate-token` | Generate new webhook token |
| GET | `/webhooks/signals?offset=0&limit=50` | List all signals (paginated) |
| GET | `/webhooks/signals/strategy/{strategy_id}` | Signals for one strategy |

**`/webhooks/signals` response:**
```json
{
  "signals": [...],
  "total": 150,
  "offset": 0,
  "limit": 50
}
```

---

### Strategies (`/api/v1/strategies`)

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/strategies` | `CreateStrategyRequest` | Create webhook strategy |
| GET | `/strategies` | — | List all strategies |
| GET | `/strategies/{id}` | — | Get strategy |
| PUT | `/strategies/{id}` | `UpdateStrategyRequest` | Update strategy |
| DELETE | `/strategies/{id}` | — | Delete (cascades signals) |

**`CreateStrategyRequest` / `UpdateStrategyRequest`:**
```json
{
  "name": "NIFTY Momentum",
  "broker_connection_id": "uuid-or-null",
  "mode": "paper",
  "is_active": true,
  "mapping_template": {
    "exchange": "EXCHANGE1",
    "product_type": "FUTURES",
    "symbol": "$.symbol",
    "action": "$.action",
    "order_type": "MARKET",
    "quantity": "$.qty",
    "leverage": 10
  },
  "rules": {
    "symbol_whitelist": ["NIFTY", "BANKNIFTY"],
    "symbol_blacklist": [],
    "max_positions": 10,
    "max_signals_per_day": 50,
    "trading_hours": {
      "start": "09:15",
      "end": "15:30",
      "timezone": "Asia/Kolkata"
    },
    "dual_leg": {
      "enabled": true,
      "max_trades": 5
    }
  }
}
```

---

### Hosted Strategies (`/api/v1/hosted-strategies`)

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/hosted-strategies` | `{name, code, description, entrypoint}` | Create |
| GET | `/hosted-strategies` | — | List |
| GET | `/hosted-strategies/{id}` | — | Get |
| PUT | `/hosted-strategies/{id}` | `{name, code, description, entrypoint}` | Update (creates version) |
| DELETE | `/hosted-strategies/{id}` | — | Delete |
| POST | `/hosted-strategies/{id}/upload` | File (max 100KB) | Upload Python file |
| GET | `/hosted-strategies/{id}/versions` | — | List versions |
| GET | `/hosted-strategies/{id}/versions/{version}` | — | Get version |
| POST | `/hosted-strategies/{id}/versions/{version}/restore` | — | Restore to version |

---

### Deployments (`/api/v1/deployments`)

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/hosted-strategies/{id}/deployments` | `CreateDeploymentRequest` | Create deployment |
| GET | `/hosted-strategies/{id}/deployments` | — | Deployments for strategy |
| GET | `/deployments` | — | All deployments |
| GET | `/deployments/{id}` | — | Get deployment |
| POST | `/deployments/{id}/pause` | — | Pause |
| POST | `/deployments/{id}/resume` | — | Resume |
| POST | `/deployments/{id}/stop` | — | Stop |
| POST | `/deployments/stop-all` | — | Stop all active |
| POST | `/deployments/{id}/promote` | `{target_mode}` | Promote backtest→paper or paper→live |
| GET | `/deployments/{id}/trades?offset=0&limit=50` | — | Trade history |
| GET | `/deployments/{id}/position` | — | Current position |
| GET | `/deployments/{id}/results` | — | Backtest results |
| GET | `/deployments/{id}/orders` | — | Open orders |
| GET | `/deployments/{id}/logs?offset=0&limit=100` | — | Execution logs |
| GET | `/deployments/{id}/metrics` | — | Performance metrics |
| GET | `/deployments/{id}/comparison` | — | Backtest vs. live comparison |
| POST | `/deployments/{id}/manual-order` | `ManualOrderRequest` | Place manual order |
| POST | `/deployments/{id}/cancel-order` | `{order_id}` | Cancel order |

**`CreateDeploymentRequest`:**
```json
{
  "mode": "backtest",
  "symbol": "BTCUSDT",
  "exchange": "BINANCE",
  "product_type": "DELIVERY",
  "interval": "1h",
  "broker_connection_id": null,
  "cron_expression": "*/5 * * * *",
  "config": {},
  "params": {},
  "strategy_code_version": null
}
```

---

### Brokers (`/api/v1/brokers`)

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/brokers` | `{broker_type, label, credentials}` | Create connection |
| GET | `/brokers` | — | List connections |
| GET | `/brokers/{id}` | — | Get connection |
| PUT | `/brokers/{id}` | `{label?, credentials?}` | Update |
| DELETE | `/brokers/{id}` | — | Delete |
| GET | `/brokers/{id}/balance?product_type=FUTURES` | — | Account balance |
| GET | `/brokers/{id}/positions` | — | Open positions |
| GET | `/brokers/instruments?exchange=BINANCE` | — | Symbol list |

---

### Paper Trading (`/api/v1/paper-trading`)

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/paper-trading/sessions` | `{strategy_id, capital}` | Create session |
| GET | `/paper-trading/sessions` | — | List sessions |
| GET | `/paper-trading/sessions/{id}` | — | Session detail |
| POST | `/paper-trading/sessions/{id}/stop` | — | Stop session |
| GET | `/paper-trading/sessions/{id}/trades` | — | Trade history |
| GET | `/paper-trading/sessions/{id}/positions` | — | Open positions |

---

### Manual Trades (`/api/v1/trades/manual`)

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/trades/manual` | `PlaceManualTradeRequest` | Place order |
| GET | `/trades/manual?offset=0&limit=50` | — | Trade history |
| POST | `/trades/manual/{id}/cancel` | — | Cancel open order |

**`PlaceManualTradeRequest`:**
```json
{
  "broker_connection_id": "uuid",
  "symbol": "BTCUSDT",
  "exchange": "BINANCE",
  "product_type": "FUTURES",
  "action": "BUY",
  "quantity": 0.001,
  "order_type": "MARKET",
  "price": null,
  "trigger_price": null,
  "leverage": 10,
  "position_model": "cross",
  "position_side": "long",
  "take_profit": null,
  "stop_loss": null
}
```

---

### Historical Data (`/api/v1/historical`)

| Method | Path | Query Params | Description |
|--------|------|--------------|-------------|
| GET | `/historical/coverage` | — | Available symbols/intervals |
| GET | `/historical/ohlcv` | symbol, interval, start, end, exchange, limit, offset | OHLCV candles |
| GET | `/historical/export` | symbol, interval, start, end, exchange | CSV download |

---

### Analytics & Config

| Method | Path | Description |
|--------|------|-------------|
| GET | `/analytics/stats` | Cross-deployment performance stats |
| GET | `/health` | DB + Redis health check |
| GET | `/config` | Public config (feature flags) |

---

## 6. Core Business Logic

### 6.1 Webhook Signal Processing

**Trigger:** `POST /api/v1/webhook/{token}` or `POST /api/v1/webhook/{token}/{slug}`

**Full Processing Pipeline:**

```
Incoming HTTP request
│
├─ 1. Token Auth — look up user by webhook_token (Redis cache, 60s TTL)
├─ 2. Rate Limit — check rolling 60s window, 429 if exceeded
├─ 3. Payload Parse — JSON decode, enforce max 65KB
│
├─ 4. Strategy Resolution
│   ├─ Broadcast (/token): fetch all active strategies for tenant
│   └─ Targeted (/token/slug): fetch single strategy by slug
│
└─ 5. For each strategy (concurrent async):
    │
    ├─ a. Mapping — apply mapping_template JSONPath to payload
    │   ├─ Values starting with "$." → extract from payload
    │   ├─ Other values → use as-is
    │   └─ Required fields: symbol, exchange, action, quantity, order_type, product_type
    │   → On error: rule_result = "mapping_error", skip execution
    │
    ├─ b. Rules Evaluation
    │   ├─ Symbol whitelist (if configured): reject if not in list
    │   ├─ Symbol blacklist (if configured): reject if in list
    │   ├─ Max open positions: count from Redis wh:positions:{strategy_id}
    │   ├─ Max signals per day: count from Redis wh:signals:{id}:{date}
    │   ├─ Trading hours (if enabled): check current time in strategy timezone
    │   └─ Dual-leg: route through dual-leg handler instead of direct execution
    │
    ├─ c. Execution
    │   ├─ mode="paper" → execute_paper_trade() (no broker call)
    │   ├─ mode="live" → _place_live_order() (broker API call)
    │   └─ mode="log" → record only, no execution
    │
    └─ d. Logging — write WebhookSignal record (background task)
```

### 6.2 Dual-Leg Trading

When `rules.dual_leg.enabled = true`:

**State (Redis, keys expire at midnight IST):**
- `dual_leg:{strategy_id}:position_side` — "" | "long" | "short"
- `dual_leg:{strategy_id}:trade_count` — number of legs placed today

**Logic for each signal:**

```
1. Get current position_side from Redis
2. Check max_trades limit (if 0 = unlimited)
3. If signal.action = "BUY" and position_side = "short":
   → Close short: place SELL MARKET order
   → If broker error 9012 (position not found): treat as success
   → Clear position_side in Redis
4. If signal.action = "SELL" and position_side = "long":
   → Close long: place BUY MARKET order
   → Error 9012 → treat as success
   → Clear position_side in Redis
5. If max_trades reached OR outside trading hours:
   → Close only (step 3/4 above)
   → Do NOT open new position
6. Otherwise:
   → Open new position with signal's action
   → Set position_side = "long" (BUY) or "short" (SELL)
   → Increment trade_count
```

### 6.3 Paper Trading Engine

**`execute_paper_trade(session, paper_session_id, tenant_id, signal, signal_id)`**

**BUY:**
```
cost = fill_price × quantity
if current_balance < cost → reject "Insufficient balance"
Create PaperPosition(symbol, side="long", quantity, avg_entry_price=fill_price)
Create PaperTrade(action="BUY", fill_price, quantity)
current_balance -= cost
return "filled"
```

**SELL:**
```
Find open PaperPosition matching symbol
if not found → reject "No open position"
realized_pnl = (fill_price - avg_entry_price) × quantity
Close position (closed_at=now, unrealized_pnl=0)
Create PaperTrade(action="SELL", fill_price, quantity, realized_pnl)
current_balance += fill_price × quantity
return "filled"
```

**Rejection conditions:** Session inactive, price ≤ 0, quantity ≤ 0, insufficient balance (BUY), no matching position (SELL).

### 6.4 Webhook Mapping (JSONPath)

The `mapping_template` is applied to the raw webhook payload to produce a `StandardSignal`.

**Example payload:**
```json
{"action": "BUY", "qty": 2, "symbol": "NIFTY"}
```

**Example mapping_template:**
```json
{
  "exchange": "EXCHANGE1",
  "product_type": "FUTURES",
  "symbol": "$.symbol",
  "action": "$.action",
  "order_type": "MARKET",
  "quantity": "$.qty",
  "leverage": 10
}
```

**Resulting StandardSignal:**
```json
{
  "exchange": "EXCHANGE1",
  "product_type": "FUTURES",
  "symbol": "NIFTY",
  "action": "BUY",
  "order_type": "MARKET",
  "quantity": 2,
  "leverage": 10
}
```

**Numeric coercion:** Fields `leverage`, `quantity`, `price`, `take_profit`, `stop_loss` are coerced to `float` when extracted from signal.

### 6.5 Signal Rules Engine

Each rule is evaluated in sequence. First failure blocks execution.

| Rule | Config Key | Logic |
|------|-----------|-------|
| Symbol Whitelist | `rules.symbol_whitelist` | Block if symbol not in list |
| Symbol Blacklist | `rules.symbol_blacklist` | Block if symbol in list |
| Max Open Positions | `rules.max_positions` | Block if Redis counter ≥ max |
| Max Signals/Day | `rules.max_signals_per_day` | Block if Redis daily counter ≥ max |
| Trading Hours | `rules.trading_hours` | Block if current time outside start/end in timezone |

**Trading Hours Validation:**
```python
import pytz
from datetime import datetime

tz = pytz.timezone(trading_hours.timezone)
now = datetime.now(tz).time()
start = time.fromisoformat(trading_hours.start)
end = time.fromisoformat(trading_hours.end)
if not (start <= now <= end):
    block("Outside trading hours")
```

---

## 7. Background Jobs & Crons

**Worker:** ARQ (asyncio-based job queue backed by Redis)

**Entry point:** `backend/worker.py`

### Worker Settings
```python
redis_settings = RedisSettings(host=REDIS_HOST, port=6379)
max_jobs = 100
job_timeout = 3600   # 1 hour
result_ttl = 86400   # 24 hours
```

### Cron Tasks

| Task | Schedule | Description |
|------|----------|-------------|
| `daily_data_fetch` | Daily @ 06:00 IST | Fetch OHLCV data for tracked symbols from Binance |
| `recover_queued_signals` | Every 5 minutes | Find stuck WebhookSignals, re-enqueue as live order jobs |

### `recover_queued_signals` Logic

```
1. Find WebhookSignals where:
   - execution_result IN ("queued", "recovering")
   - received_at < NOW() - 3 minutes
   - strategy.mode = "live"
   - strategy.broker_connection_id IS NOT NULL
2. Atomically mark each as "recovering" (prevent double-enqueue)
3. For each signal:
   - Build job_payload from parsed_signal
   - Enqueue ARQ job: id = "live-order:{signal_id}" (idempotent)
4. Log recovered count
```

### Job: `execute_live_order_task`

**Triggered by:** recovery cron OR direct webhook execution on retry

**Payload:**
```json
{
  "strategy_id": "uuid",
  "broker_connection_id": "uuid",
  "tenant_id": "uuid",
  "signal": {StandardSignal},
  "webhook_signal_id": "uuid",
  "trace_id": "uuid"
}
```

**Actions:** Calls `_place_live_order()`, updates WebhookSignal execution_result in DB.

---

## 8. Broker Adapters

### Abstract Interface (`app/brokers/base.py`)

All brokers implement `BrokerAdapter`:

```python
class BrokerAdapter:
    # Auth
    async def authenticate(credentials: dict) -> bool
    async def verify_connection() -> bool

    # Orders
    async def place_order(order: OrderRequest) -> OrderResponse
    async def cancel_order(order_id: str) -> bool
    async def get_order_status(order_id: str) -> OrderStatus

    # Portfolio
    async def get_positions() -> list[Position]
    async def get_holdings() -> list[Holding]
    async def get_balance(product_type: str | None) -> AccountBalance

    # Market data
    async def get_quotes(symbols: list[str]) -> list[Quote]
    async def get_historical(symbol, interval, start, end) -> list[OHLCV]
```

### OrderRequest Schema

```python
@dataclass
class OrderRequest:
    symbol: str                        # e.g. "BTCUSDT"
    exchange: str                      # e.g. "BINANCE"
    action: Literal["BUY", "SELL"]
    quantity: Decimal
    order_type: Literal["MARKET", "LIMIT", "SL", "SL-M"]
    price: Decimal = 0
    product_type: str = "DELIVERY"     # INTRADAY, DELIVERY, CNC, MIS, FUTURES
    trigger_price: Decimal | None = None
    leverage: int | None = None
    position_model: str | None = None  # "isolated", "cross"
    position_side: str | None = None   # "long", "short"
    take_profit: Decimal | None = None
    stop_loss: Decimal | None = None
```

### OrderResponse Schema

```python
@dataclass
class OrderResponse:
    order_id: str
    status: Literal["filled", "open", "rejected", "cancelled"]
    fill_price: Decimal | None = None
    fill_quantity: Decimal | None = None
    message: str = ""
    placed_at: datetime = field(default_factory=datetime.utcnow)
```

### Supported Brokers

| Broker Type | `broker_type` value | Credential Fields | Notes |
|-------------|---------------------|-------------------|-------|
| Exchange1 | `exchange1` | `api_key`, `api_secret`, `user_id` | Primary live broker. Supports futures, dual-leg, error code 9012 |
| Binance Testnet | `binance_testnet` | `api_key`, `api_secret` | Testnet only |
| Simulated | `simulated` | — | In-memory simulation engine |

### Credential Encryption

**Algorithm:** AES-256-GCM with HKDF-SHA256 key derivation

**Encryption:**
```python
# 1. Derive 32-byte key
key = HKDF(
    algorithm=SHA256,
    length=32,
    salt=tenant_id.bytes,
    info=b"algomatter-credential-encryption",
).derive(MASTER_KEY.encode())

# 2. Encrypt
nonce = os.urandom(12)
aesgcm = AESGCM(key)
ciphertext = aesgcm.encrypt(nonce, json.dumps(credentials).encode(), None)

# 3. Store
stored = nonce + ciphertext  # saved as LargeBinary
```

**Decryption:**
```python
nonce = stored[:12]
ciphertext = stored[12:]
plaintext = aesgcm.decrypt(nonce, ciphertext, None)
credentials = json.loads(plaintext)
```

---

## 9. Security & Authentication

### JWT Tokens

**Access Token:**
- Algorithm: HS256
- Payload: `{sub: user_id, email, exp}`
- Lifetime: 15 minutes (configurable via `ALGOMATTER_JWT_ACCESS_TOKEN_EXPIRE_MINUTES`)
- Header: `Authorization: Bearer <token>`

**Refresh Token:**
- Format: URL-safe random 32 bytes
- Stored: SHA256 hash in `refresh_tokens` table
- Lifetime: 7 days (configurable)
- One-time use: new token issued on each refresh

### Row-Level Security (PostgreSQL RLS)

**Activation:**
```sql
-- Set per-transaction (in AsyncSession after_begin hook)
SET LOCAL app.current_tenant_id = '<user-uuid>';
```

**Policy example:**
```sql
CREATE POLICY tenant_isolation ON strategies
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

Applied to all tenant-scoped tables. Prevents cross-tenant data access even on raw queries.

### Rate Limiting

**Implementation:** Redis Sorted Set (Zset) rolling window

```
Key: ratelimit:{identifier}
Algorithm:
  1. ZREMRANGEBYSCORE key 0 (now - 60s)   # remove old
  2. ZADD key now now                       # add current
  3. ZCARD key                              # count in window
  4. If count > limit: return 429
  5. EXPIRE key 60                          # auto-cleanup
```

| Endpoint | Identifier | Limit |
|----------|-----------|-------|
| Webhooks | `webhook_token` | 60/min (configurable) |
| Auth (signup/login/refresh) | Client IP | 20/min |

### CORS

**Allowed Origins:**
- `http://localhost:3000`
- `http://localhost:5173`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:5173`

Production: Nginx handles CORS at proxy level.

### Password Hashing

- Algorithm: Bcrypt (work factor auto-selected)
- Minimum password length: 8 characters
- Verified via `bcrypt.checkpw()`

---

## 10. Configuration & Environment Variables

**File:** `backend/app/config.py` (Pydantic BaseSettings)

All variables prefixed with `ALGOMATTER_`.

| Variable | Type | Default | Required in Prod | Description |
|----------|------|---------|-----------------|-------------|
| `ALGOMATTER_DATABASE_URL` | str | `postgres://algomatter:algomatter@localhost:5432/algomatter` | Yes | AsyncPG DSN |
| `ALGOMATTER_REDIS_URL` | str | `redis://localhost:6379/0` | Yes | Redis connection string |
| `ALGOMATTER_JWT_SECRET` | str | `change-me` | Yes (≥32 chars) | HS256 signing key |
| `ALGOMATTER_JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | int | 15 | No | Access token lifetime |
| `ALGOMATTER_JWT_REFRESH_TOKEN_EXPIRE_DAYS` | int | 7 | No | Refresh token lifetime |
| `ALGOMATTER_MASTER_KEY` | str | `change-me` | Yes (≥32 chars hex) | AES-GCM master encryption key |
| `ALGOMATTER_RATE_LIMIT_PER_MINUTE` | int | 60 | No | Webhook rate limit |
| `ALGOMATTER_MAX_WEBHOOK_PAYLOAD_BYTES` | int | 65536 | No | Max webhook body (64KB) |
| `ALGOMATTER_ENABLE_PAPER_TRADING` | bool | True | No | Feature flag |
| `ALGOMATTER_ENABLE_BACKTESTING` | bool | True | No | Feature flag |
| `ALGOMATTER_SKIP_SECRET_CHECK` | bool | False | No | Bypass secret validation (dev only) |

**Startup Validation:** Server fails to start if `JWT_SECRET` or `MASTER_KEY` are defaults or <32 chars (unless `SKIP_SECRET_CHECK=1`).

**Frontend Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Backend API URL |

---

## 11. Frontend Structure

```
frontend/
├── app/                        # Next.js 14 App Router
│   ├── (auth)/                 # Public auth routes
│   │   ├── login/page.tsx
│   │   └── signup/page.tsx
│   ├── (dashboard)/            # Protected dashboard (requires login)
│   │   ├── layout.tsx          # Auth check, sidebar, topbar
│   │   ├── page.tsx            # Dashboard home
│   │   ├── strategies/         # Webhook strategies
│   │   ├── live-deployments/   # Live deployment management
│   │   ├── live-trading/       # Manual trading UI
│   │   ├── paper-trading/      # Paper trading sessions
│   │   ├── backtesting/        # Backtest runner
│   │   ├── backtest-deployments/
│   │   ├── analytics/
│   │   ├── brokers/
│   │   ├── webhooks/
│   │   └── settings/
│   ├── layout.tsx              # Root layout (fonts, metadata)
│   └── providers.tsx           # Client-side providers
├── components/
│   ├── layout/                 # Sidebar, TopBar, NavItem
│   ├── shared/                 # DataTable, StatusBadge, StatCard, etc.
│   ├── strategies/             # WebhookParameterBuilder, ParameterRow, TradingViewPreview
│   ├── charts/                 # EquityCurve, CandlestickChart, ChartContainer
│   ├── live-trading/           # LiveDeploymentCard, AggregateStats, etc.
│   ├── trade/                  # OrderForm, TradingChart, Watchlist
│   ├── brokers/                # BrokerPositionsTable, BrokerStatsBar, etc.
│   ├── deployments/            # DeploymentCard, PromoteModal
│   ├── backtest-deployments/   # BacktestOverviewTab
│   └── editor/                 # MonacoEditor
├── lib/
│   ├── api/
│   │   ├── client.ts           # HTTP client (auth, token refresh, error)
│   │   └── types.ts            # TypeScript interfaces
│   ├── contexts/
│   │   └── FeatureFlagsContext.tsx
│   ├── hooks/
│   │   ├── useAuth.tsx         # Auth context
│   │   ├── useApi.ts           # All SWR data-fetching hooks
│   │   ├── useBinanceWebSocket.ts
│   │   └── useManualTrades.ts
│   └── utils/
│       ├── constants.ts        # API_BASE_URL, polling intervals
│       ├── formatters.ts       # Currency, date, % formatters
│       ├── filterNavItems.ts   # Feature-flag nav filtering
│       └── brokerFields.ts     # Dynamic broker credential config
├── next.config.mjs             # basePath=/app, security headers, CSP
└── package.json
```

### Provider Stack (`app/providers.tsx`)

```tsx
<ChakraProvider>
  <AuthProvider>
    <FeatureFlagsProvider>
      {children}
    </FeatureFlagsProvider>
  </AuthProvider>
</ChakraProvider>
```

### Dashboard Layout (`(dashboard)/layout.tsx`)

```tsx
// Auth check
const { user, isLoading } = useAuth()
if (!isLoading && !user) redirect('/login')

// Render
<Flex>
  <Sidebar />
  <Box flex={1}>
    <TopBar />
    <Box p={6}>{children}</Box>
  </Box>
</Flex>
```

---

## 12. Frontend Pages & Routes

All routes are under `/app` (Next.js basePath).

### Auth Pages

| Route | File | Description |
|-------|------|-------------|
| `/login` | `(auth)/login/page.tsx` | Email/password login form |
| `/signup` | `(auth)/signup/page.tsx` | Registration with password confirmation |

### Dashboard Pages

| Route | File | Data Hooks | Polling |
|-------|------|-----------|---------|
| `/` | `(dashboard)/page.tsx` | `useAnalyticsOverview`, `useWebhookSignals`, `useStrategies`, `usePaperSessions`, `useActiveDeployments` | 10s, 5s |
| `/strategies` | `strategies/page.tsx` | `useStrategies` | — |
| `/strategies/new` | `strategies/new/page.tsx` | `useBrokers`, `useWebhookConfig` | — |
| `/strategies/[id]` | `strategies/[id]/page.tsx` | `useStrategy`, `useStrategySignals`, `useStrategyMetrics`, `useStrategyEquityCurve` | 5s |
| `/strategies/[id]/edit` | `strategies/[id]/edit/page.tsx` | `useBrokers`, `useStrategy`, `useWebhookConfig` | — |
| `/strategies/hosted` | `strategies/hosted/page.tsx` | `useHostedStrategies` | — |
| `/strategies/hosted/new` | `strategies/hosted/new/page.tsx` | — | — |
| `/strategies/hosted/[id]` | `strategies/hosted/[id]/page.tsx` | `useHostedStrategy`, `useStrategyVersions`, `useDeployments` | 10s |
| `/live-deployments` | `live-deployments/page.tsx` | `useActiveDeployments` | 5s |
| `/live-deployments/[id]` | `live-deployments/[id]/page.tsx` | `useDeployment`, `useDeploymentMetrics`, `useDeploymentTrades`, `useDeploymentPosition` | 2–5s |
| `/live-trading` | `live-trading/page.tsx` | `useActiveDeployments`, `useAggregateStats`, `useRecentTrades` | 5s |
| `/paper-trading` | `paper-trading/page.tsx` | `usePaperSessions` | — |
| `/paper-trading/[id]` | `paper-trading/[id]/page.tsx` | `usePaperSession` | 10s |
| `/backtesting` | `backtesting/page.tsx` | — | 2s (poll for completion) |
| `/backtest-deployments` | `backtest-deployments/page.tsx` | `useBacktestDeployments` | 2s |
| `/backtest-deployments/[id]` | `backtest-deployments/[id]/page.tsx` | `useDeploymentResults`, `useDeploymentTrades` | — |
| `/analytics` | `analytics/page.tsx` | `useAnalyticsOverview`, `useStrategies` | 10s |
| `/analytics/strategies/[id]` | `analytics/strategies/[id]/page.tsx` | `useStrategyMetrics`, `useStrategyTrades`, `useStrategyEquityCurve` | — |
| `/brokers` | `brokers/page.tsx` | `useBrokers` | — |
| `/brokers/new` | `brokers/new/page.tsx` | — | — |
| `/brokers/[id]` | `brokers/[id]/page.tsx` | `useBrokerStats`, `useBrokerPositions`, `useBrokerOrders`, `useBrokerBalance` | 5–30s |
| `/webhooks` | `webhooks/page.tsx` | `useWebhookConfig`, `useWebhookSignals` | 5s |
| `/settings` | `settings/page.tsx` | `useHealth` | 30s |

---

## 13. Frontend Components

### Layout

| Component | Purpose | Notes |
|-----------|---------|-------|
| `Sidebar` | Left navigation, collapsible | Filtered by feature flags |
| `NavItem` | Single nav link with icon | Active state via `usePathname` |
| `TopBar` | Header bar | Theme toggle, logout menu |

### Shared

| Component | Props | Purpose |
|-----------|-------|---------|
| `DataTable<T>` | `columns: Column<T>[]`, `data: T[]`, `onRowClick?`, `isLoading?` | Generic sortable table |
| `StatusBadge` | `variant`, `text` | Color-coded status indicator |
| `StatCard` | `label`, `value`, `change?` | KPI metric card |
| `EmptyState` | `title`, `description?`, `actionLabel?` | Empty-state placeholder |
| `ConfirmModal` | `isOpen`, `onClose`, `onConfirm`, `title`, `message` | Destructive action confirmation |
| `DeploymentBadge` | `mode`, `status` | Deployment mode + status badge |
| `Pagination` | `offset`, `pageSize`, `total`, `onPrev`, `onNext` | Page controls |
| `LogViewer` | `logs: string[]`, `height?` | Scrollable log display |
| `SymbolSelect` | `exchange`, `value`, `onChange` | Symbol search dropdown |

### Strategy Components

| Component | Purpose |
|-----------|---------|
| `WebhookParameterBuilder` | Maps webhook payload fields → order parameters. Tabs: Futures/Spot. Fixed vs. Signal source per field. Emits `mapping_template` object via `onChange`. Props: `initialValue`, `onChange`, `webhookUrl`. |
| `ParameterRow` | Single row in builder. Shows label, Fixed/Signal toggle, and value input. |
| `TradingViewPreview` | TradingView embedded chart widget. |

**WebhookParameterBuilder field mapping:**

| Field | Tab | Required | Input Type | Notes |
|-------|-----|----------|-----------|-------|
| symbol | Both | Yes | SymbolSelect (fixed) or text | |
| action | Both | Yes | Select: BUY/SELL | |
| order_type | Both | Yes | Select: MARKET/LIMIT | |
| quantity | Both | Yes | Number | Coerced to float |
| leverage | Futures | Yes | Select: 1x-100x | Coerced to number |
| position_model | Futures | Yes | Select: isolated/cross | |
| price | Both | Optional | Number | Required if LIMIT |
| position_side | Futures | Optional | Select: auto/long/short | |
| take_profit | Futures | Optional | Number | |
| stop_loss | Futures | Optional | Number | |

### Charts

| Component | Library | Props |
|-----------|---------|-------|
| `EquityCurve` | lightweight-charts | `data: {time, value}[]` |
| `CandlestickChart` | lightweight-charts | `data: OhlcvCandle[]` |
| `ChartContainer` | — | Wraps charts with timeframe selector (1W/1M/3M/ALL) |

### Trade / Manual Trading

| Component | Purpose |
|-----------|---------|
| `OrderForm` | Full order placement form (action, quantity, order type, leverage, SL/TP) |
| `Watchlist` | Symbol list with live Binance WebSocket ticker prices |
| `TradingChart` | TradingView advanced chart, theme-synced |
| `TradeHistory` | Manual trade execution history table |

---

## 14. Frontend Hooks & API Client

### API Client (`lib/api/client.ts`)

**Token Storage:**
- Access token: in-memory variable (cleared on reload)
- Refresh token: `localStorage` key `refresh_token`

**Request Flow:**
```typescript
async function apiClient<T>(path, options?): Promise<T> {
  1. Include Authorization: Bearer {accessToken} if set
  2. Make fetch to API_BASE_URL + path
  3. On 401:
     a. Try POST /auth/refresh with localStorage refresh token
     b. On success: update tokens, retry original request
     c. On failure: clearTokens(), redirect to /app/login
  4. On non-2xx: throw ApiError(status, detail)
  5. Return JSON response
}
```

**Auth Functions:**
```typescript
setAccessToken(token: string | null): void
getAccessToken(): string | null
setRefreshToken(token: string | null): void
getRefreshToken(): string | null
clearTokens(): void
```

### Auth Hook (`lib/hooks/useAuth.tsx`)

```typescript
interface AuthContext {
  user: User | null
  isLoading: boolean
  login(email: string, password: string): Promise<void>
  signup(email: string, password: string): Promise<void>
  logout(): Promise<void>
}
```

**On mount:** Checks localStorage for refresh token. If found, calls `/auth/refresh` immediately to restore session.

### Data Hooks (`lib/hooks/useApi.ts`)

All hooks use SWR with `apiClient` as fetcher.

**Polling Intervals (`lib/utils/constants.ts`):**
```typescript
DASHBOARD: 10000      // 10s
SIGNALS: 5000         // 5s
PAPER_TRADING: 10000  // 10s
HEALTH: 30000         // 30s
BACKTEST_STATUS: 2000 // 2s
MARKET_CHART: 30000   // 30s
DEPLOYMENT: 5000      // 5s
LIVE_TRADING: 5000    // 5s
```

**Key hooks:**

```typescript
useStrategies()                      // → Strategy[]
useStrategy(id)                      // → Strategy
useWebhookConfig()                   // → {webhook_url, token}
useWebhookSignals(offset, limit)     // → {signals, total, offset, limit}
useStrategySignals(id)               // → WebhookSignal[]
useBrokers()                         // → BrokerConnection[]
usePaperSessions()                   // → PaperSession[]
useActiveDeployments()               // → Deployment[] (running/paused only)
useDeployment(id)                    // → Deployment (2s polling for backtest)
useDeploymentTrades(id, offset, limit) // → TradesResponse
useDeploymentMetrics(id)             // → LiveMetrics (10s)
useDeploymentPosition(id)            // → PositionInfo (5s)
useAggregateStats()                  // → AggregateStats (5s)
useRecentTrades(limit)               // → RecentTradesResponse (5s)
useManualTrades(offset, limit, status?) // → ManualTradesListResponse (3s)
useBrokerBalance(id, productType?)   // → BrokerBalance (15s)
useBrokerPositions(id)               // → BrokerPosition[] (5s)
useOhlcv(symbol, interval, exchange, timeframe, isLive) // → OhlcvCandle[] (30s if live)
useAnalyticsOverview()               // → AnalyticsOverview (10s)
useHostedStrategies()                // → HostedStrategy[]
useStrategyVersions(id)              // → StrategyVersion[]
```

### WebSocket Hooks (`lib/hooks/useBinanceWebSocket.ts`)

```typescript
// Subscribe to 24h mini ticker for multiple symbols
useBinanceTickerStream(
  symbols: string[],
  onTicker: (ticker: BinanceMiniTicker) => void
): { connected: boolean }

// Subscribe to candlestick updates
useBinanceKlineStream(
  symbol: string,
  interval: string,
  onKline: (kline: KlineData) => void
): { connected: boolean }

// Fetch historical klines (REST)
fetchBinanceKlines(symbol, interval, limit): Promise<KlineData[]>
```

Features: Auto-reconnect with exponential backoff (max 30s delay).

---

## 15. Key Data Flows

### 15.1 Webhook Signal → Live Order

```
TradingView Alert / Custom Bot
  → POST https://algomatter.in/api/v1/webhook/{token}/{slug}
    Body: {"action": "BUY", "qty": 1, "symbol": "NIFTY"}

FastAPI Webhook Router
  → Auth: resolve user by webhook_token
  → Rate limit check (Redis)
  → Load strategy by slug
  → Map payload → StandardSignal (JSONPath)
  → Evaluate rules (whitelist, hours, position count)
  → mode="live" → _place_live_order()
    → Load broker_connection
    → Decrypt credentials (AES-GCM)
    → Call Exchange1 API (place order)
    → OrderResponse{order_id, status, fill_price}
  → Write WebhookSignal record (background)
  → Return {received: true, signals_processed: 1}
```

### 15.2 User Login → Dashboard

```
User enters email/password
  → POST /api/v1/auth/login
  → Verify bcrypt hash
  → Generate access_token (JWT, 15min)
  → Generate refresh_token (random), store SHA256 hash in DB
  → Return {access_token, refresh_token}

Frontend (useAuth)
  → setAccessToken(access_token)
  → setRefreshToken(refresh_token) in localStorage
  → GET /api/v1/auth/me → User object
  → Set user in AuthContext
  → Redirect to /

Dashboard Layout
  → useAuth() → user present
  → Render Sidebar + TopBar + Content
  → SWR hooks begin polling
```

### 15.3 Access Token Expiry → Transparent Refresh

```
SWR hook calls apiClient('/api/v1/strategies')
  → Sends Authorization: Bearer {expired_access_token}
  → API returns 401

apiClient auto-refresh:
  → GET refresh_token from localStorage
  → POST /api/v1/auth/refresh {refresh_token}
  → API: verify hash, issue new access + refresh tokens
  → setAccessToken(new_access_token)
  → setRefreshToken(new_refresh_token)
  → Retry original request with new token
  → Return data to SWR
```

### 15.4 Strategy Creation Flow

```
User fills New Strategy form
  → WebhookParameterBuilder builds mapping_template
  → Click Create Strategy

POST /api/v1/strategies {
  name, broker_connection_id, mode, mapping_template, rules
}

Backend:
  → Validate fields
  → Generate slug from name (lowercase, hyphenated)
  → UNIQUE check (tenant_id, slug)
  → Insert Strategy row
  → Return StrategyResponse

Frontend:
  → mutate('/api/v1/strategies') to refresh list
  → router.push('/strategies')
```

### 15.5 Backtest Deployment Flow

```
User selects hosted strategy, configures backtest params
  → POST /api/v1/hosted-strategies/{id}/deployments
    {mode: "backtest", symbol, interval, ...}

Backend:
  → Create StrategyDeployment (status="pending")
  → Enqueue backtest job in ARQ
  → Return deployment object

Frontend:
  → Poll GET /api/v1/deployments/{id} every 2s
  → status: pending → running → completed/failed

Strategy Runner:
  → Load strategy code, run backtest engine
  → Write DeploymentTrade records
  → Write StrategyResult (equity_curve, metrics)
  → Set status="completed"

Frontend:
  → status="completed" → load results
  → Show equity curve, metrics, trade log
```

### 15.6 Promote Paper → Live

```
User clicks "Promote to Live" on paper deployment
  → PromoteModal: select broker connection, confirm

POST /api/v1/deployments/{paper_id}/promote
  {target_mode: "live", broker_connection_id: "uuid"}

Backend:
  → Validate: paper deployment has ≥10 ticks
  → Create new StrategyDeployment (mode="live", promoted_from_id=paper_id)
  → Copy config, params, symbol, interval from paper deployment
  → Return new deployment

Frontend:
  → Show new live deployment
  → User sees comparison between backtest/paper and live
```

---

## 16. External Integrations

### Exchange1 Broker

- REST API (proprietary, India-based futures broker)
- Credentials: `api_key`, `api_secret`, `user_id`
- Supports: SPOT (CNC/MIS), FUTURES with leverage and position modes
- Error code `9012` = "position not found" (treated as success in dual-leg close)
- IP whitelist required on Exchange1 dashboard (VPS IP: `194.61.31.226`)

### Binance Testnet

- REST API: `https://testnet.binance.vision`
- Credentials: `api_key`, `api_secret` (from Binance testnet portal)
- Supports: Spot orders only

### Binance WebSocket (Frontend)

- Ticker stream: `wss://stream.binance.com:9443/ws/{symbol}@miniTicker`
- Kline stream: `wss://stream.binance.com:9443/ws/{symbol}@kline_{interval}`
- Used for live price updates in Watchlist and TradingChart

### TradingView

- Embedded via CDN script: `https://s3.tradingview.com/tv.js`
- Advanced chart widget embedded in `TradingChart` component
- Allowed via CSP in `next.config.mjs`

### yfinance / Binance Historical Data

- `yfinance` Python library fetches OHLCV for backtesting
- Also supports Binance REST API for historical candles
- Stored in `historical_ohlcv` table
- Daily cron job refreshes data for tracked symbols

---

## 17. Redis Key Reference

| Key Pattern | Type | TTL | Purpose |
|-------------|------|-----|---------|
| `strategies:active:{tenant_id}` | String (JSON) | 60s | Cached active strategy list for webhook routing |
| `wh:positions:{strategy_id}` | String (int) | None | Open position count (increment on order, decrement on close) |
| `wh:signals:{strategy_id}:{YYYY-MM-DD}` | String (int) | Until midnight IST | Daily signal counter per strategy |
| `dual_leg:{strategy_id}:position_side` | String | Until midnight IST | Current leg direction: "" \| "long" \| "short" |
| `dual_leg:{strategy_id}:trade_count` | String (int) | Until midnight IST | Number of leg trades placed today |
| `ratelimit:{token}` | Sorted Set | 60s | Webhook rate limit window |
| `ratelimit:auth:{ip}` | Sorted Set | 60s | Auth endpoint rate limit window |
| ARQ job queues | Various | Per job TTL | Background task queue (24h result TTL) |

---

## 18. Feature Flags & Limits

### Feature Flags

Served from `GET /api/v1/config`:

```json
{
  "paper_trading_enabled": true,
  "backtesting_enabled": true
}
```

Controlled by env vars: `ALGOMATTER_ENABLE_PAPER_TRADING`, `ALGOMATTER_ENABLE_BACKTESTING`.

Frontend: `useFeatureFlags()` context. Sidebar filters out nav items based on flags.

### Deployment Limits

| Mode | Limit | Scope |
|------|-------|-------|
| Backtest | 3 concurrent | pending + running per tenant |
| Paper | 5 active | running + paused per tenant |
| Live | 2 active | running + paused per tenant |

### Promotion Rules

| From | To | Prerequisite |
|------|----|-------------|
| Backtest (completed) | Paper | — |
| Paper | Live | ≥ 10 strategy ticks recorded |

### Cron Expression Validation

- Minimum interval: 5 minutes
- Format: 5-field standard cron (minute, hour, day, month, weekday)
- Example: `*/5 * * * *` (every 5 minutes)

### Hosted Strategy Upload

- Max file size: 100KB
- Format: Python (.py) file
- Entrypoint: configurable class name (default: `Strategy`)

---

## 19. Dependencies

### Backend (`backend/pyproject.toml`)

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | ≥0.115.0 | Web framework |
| `uvicorn[standard]` | — | ASGI server |
| `sqlalchemy[asyncio]` | ≥2.0 | ORM + async |
| `asyncpg` | ≥0.30 | PostgreSQL async driver |
| `alembic` | ≥1.13 | Database migrations |
| `pydantic` | ≥2.7 | Data validation |
| `pyjwt` | ≥2.8 | JWT tokens |
| `bcrypt` | ≥4.1 | Password hashing |
| `cryptography` | ≥42.0 | AES-GCM encryption |
| `redis` | ≥5.0 | Redis client |
| `arq` | ≥0.26 | Async job queue |
| `jsonpath-ng` | ≥1.6 | JSONPath parsing for webhook mapping |
| `structlog` | ≥24.1 | Structured logging |
| `httpx` | ≥0.27 | Async HTTP client (broker calls) |
| `yfinance` | ≥0.2 | Historical OHLCV data |
| `nautilus_trader` | ≥1.200 | Algo trading SDK (strategy runner) |
| `pytz` | — | Timezone handling |

### Frontend (`frontend/package.json`)

| Package | Version | Purpose |
|---------|---------|---------|
| `next` | 14.2 | React framework (App Router) |
| `react` | 18 | UI library |
| `@chakra-ui/react` | 2.10 | Component library |
| `@emotion/react` | — | CSS-in-JS (Chakra peer dep) |
| `framer-motion` | — | Animations (Chakra peer dep) |
| `swr` | 2.4 | Data fetching + caching |
| `lightweight-charts` | 5.1 | OHLCV candlestick charts |
| `@monaco-editor/react` | 4.7 | Code editor (hosted strategies) |
| `react-icons` | 5.6 | Icon library |
| `typescript` | 5 | Type system |
| `jest` | — | Unit testing |
| `@testing-library/react` | — | Component testing |

---

## Appendix: Alembic Migration History

| Revision | Date | Description |
|----------|------|-------------|
| `d0e36e5a6fdb` | 2026-03-25 | Initial schema: users, broker_connections, strategies, webhooks, paper trading |
| `aa8fa5c74ed6` | 2026-03-25 | PostgreSQL RLS policies |
| `5b35c717713d` | 2026-03-28 | Hosted strategies: StrategyCode, StrategyCodeVersion, StrategyDeployment, DeploymentState |
| `919540c9ed52` | 2026-03-28 | DeploymentTrade table |
| `b6e74168570e` | 2026-03-29 | Make PaperTradingSession.strategy_id nullable |
| `f1a2b3c4d5e6` | 2026-04-05 | ExchangeInstrument table |
| `c3f1a2b4d5e6` | 2026-04-05 | PaperTradingSession: add strategy_code_id FK |
| `a1b2c3d4e5f6` | 2026-04-06 | ManualTrade table |
| `e1f2a3b4c5d6` | 2026-04-06 | ManualTrade: add position_side column |
| `b7d4e9f1a2c3` | 2026-04-09 | ManualTrade: add error_message |
| `c8e1d2f3a4b5` | 2026-04-09 | BrokerConnection: add label + UNIQUE(tenant_id, label) |
| `f2a3b4c5d6e7` | 2026-04-09 | ManualTrade: BrokerConnection FK ondelete CASCADE |
| `d3e4f5a6b7c8` | 2026-04-09 | WebhookSignal: add composite index (tenant_id, strategy_id, received_at) |
| `e5f6a7b8c9d0` | 2026-04-10 | Add missing tenant_id indexes |
| `b2c3d4e5f6a7` | 2026-04-10 | Strategy: add slug column + UNIQUE(tenant_id, slug) |

---

*Last updated: 2026-04-11*
