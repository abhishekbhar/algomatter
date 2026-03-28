# AlgoMatter Phase 1 Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete Phase 1 backend — auth, broker connections, webhook engine, backtesting, paper trading, analytics, and event bus — as a testable, deployable FastAPI application.

**Architecture:** Multi-tenant FastAPI backend with PostgreSQL (RLS), Redis (Streams + cache), and ARQ task queue. All tenant-scoped data isolated via RLS policies activated per-request. Webhook signals flow through a JSONPath mapper and rules engine before reaching the SimulatedBroker for paper/backtest execution.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL 16, Redis, ARQ, Pydantic v2, PyJWT, bcrypt, jsonpath-ng, structlog, pytest, httpx

**Spec:** `docs/superpowers/specs/2026-03-25-algomatter-multiuser-algotrading-platform-design.md`

---

## File Map

```
backend/
├── pyproject.toml                      # Project metadata, dependencies
├── alembic.ini                         # Alembic config
├── Dockerfile                          # Backend container
├── docker-compose.yml                  # All services (api, worker, postgres, redis)
├── docker-compose.test.yml             # Test infrastructure
├── .env.example                        # Environment variable template
├── app/
│   ├── __init__.py
│   ├── main.py                         # FastAPI app, routers, middleware, lifespan
│   ├── config.py                       # pydantic-settings: Settings class
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py                     # SQLAlchemy DeclarativeBase
│   │   ├── models.py                   # All SQLAlchemy ORM models
│   │   ├── session.py                  # async engine, session factory, RLS hook
│   │   └── migrations/
│   │       ├── env.py                  # Alembic async env
│   │       └── versions/               # Migration files
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── router.py                   # POST signup, login, refresh; GET me
│   │   ├── deps.py                     # get_current_user, get_tenant_session
│   │   ├── service.py                  # hash_password, verify_password, create_jwt, refresh logic
│   │   └── schemas.py                  # Pydantic request/response models
│   ├── crypto/
│   │   ├── __init__.py
│   │   └── encryption.py               # HKDF key derivation, AES-256-GCM encrypt/decrypt
│   ├── brokers/
│   │   ├── __init__.py
│   │   ├── base.py                     # BrokerAdapter ABC, data models (OrderRequest, Position, etc.)
│   │   ├── simulated.py                # SimulatedBroker for paper/backtest
│   │   ├── router.py                   # GET/POST/DELETE broker connections
│   │   └── schemas.py                  # Pydantic schemas for broker API
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── router.py                   # Strategy CRUD
│   │   └── schemas.py
│   ├── webhooks/
│   │   ├── __init__.py
│   │   ├── router.py                   # POST webhook receiver, GET signals, config
│   │   ├── mapper.py                   # JSONPath mapping template engine
│   │   ├── processor.py                # Signal rules engine
│   │   └── schemas.py
│   ├── backtesting/
│   │   ├── __init__.py
│   │   ├── router.py                   # POST create, GET list/detail, DELETE
│   │   ├── engine.py                   # Backtest runner (processes CSV signals)
│   │   └── tasks.py                    # ARQ task wrappers
│   ├── paper_trading/
│   │   ├── __init__.py
│   │   ├── router.py                   # Session CRUD + stop
│   │   └── engine.py                   # Paper trade execution logic
│   ├── historical/
│   │   ├── __init__.py
│   │   ├── service.py                  # Fetch + cache OHLCV data
│   │   └── tasks.py                    # ARQ daily fetch job
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── router.py                   # Overview, metrics, equity curve, trades
│   │   ├── metrics.py                  # Sharpe, drawdown, win rate, profit factor
│   │   └── service.py                  # Aggregation queries
│   ├── events/
│   │   ├── __init__.py
│   │   └── bus.py                      # Redis Streams publish helper
│   └── middleware/
│       ├── __init__.py
│       ├── rate_limiter.py             # Redis sliding window
│       └── logging.py                  # structlog request logging
├── worker.py                           # ARQ worker entry point
└── tests/
    ├── __init__.py
    ├── conftest.py                     # Fixtures: async DB, test client, user factory
    ├── test_auth.py
    ├── test_crypto.py
    ├── test_brokers.py
    ├── test_strategies.py
    ├── test_webhooks.py
    ├── test_webhook_mapper.py
    ├── test_signal_processor.py
    ├── test_backtesting.py
    ├── test_paper_trading.py
    ├── test_analytics.py
    ├── test_metrics.py
    ├── test_events.py
    └── test_health.py
```

---

## Task 1: Project Scaffolding & Docker Infrastructure

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/Dockerfile`
- Create: `backend/docker-compose.yml`
- Create: `backend/docker-compose.test.yml`

- [ ] **Step 1: Create pyproject.toml with all dependencies**

```toml
[project]
name = "algomatter"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.30",
    "asyncpg>=0.30.0",
    "alembic>=1.13.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    "pyjwt>=2.8.0",
    "bcrypt>=4.1.0",
    "cryptography>=42.0.0",
    "redis>=5.0.0",
    "arq>=0.26.0",
    "jsonpath-ng>=1.6.0",
    "structlog>=24.1.0",
    "httpx>=0.27.0",
    "yfinance>=0.2.40",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
    "ruff>=0.5.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create .env.example**

```env
ALGOMATTER_DATABASE_URL=postgresql+asyncpg://algomatter:algomatter@localhost:5432/algomatter
ALGOMATTER_REDIS_URL=redis://localhost:6379/0
ALGOMATTER_JWT_SECRET=change-me-in-production
ALGOMATTER_MASTER_KEY=change-me-in-production-64-hex-chars
```

- [ ] **Step 3: Create app/config.py**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://algomatter:algomatter@localhost:5432/algomatter"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    master_key: str = "change-me"
    rate_limit_per_minute: int = 60
    max_webhook_payload_bytes: int = 65536

    model_config = {"env_prefix": "ALGOMATTER_", "env_file": ".env"}

settings = Settings()
```

- [ ] **Step 4: Create minimal app/main.py**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: init DB pool, Redis
    yield
    # shutdown: close pools

app = FastAPI(title="AlgoMatter", version="0.1.0", lifespan=lifespan)

@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Create docker-compose.yml**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: algomatter
      POSTGRES_PASSWORD: algomatter
      POSTGRES_DB: algomatter
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - postgres
      - redis
    volumes:
      - .:/app

  worker:
    build: .
    command: arq worker.WorkerSettings
    env_file: .env
    depends_on:
      - postgres
      - redis
    volumes:
      - .:/app

volumes:
  pgdata:
```

- [ ] **Step 6: Create Dockerfile**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 7: Create docker-compose.test.yml**

```yaml
services:
  test-postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: algomatter_test
      POSTGRES_PASSWORD: algomatter_test
      POSTGRES_DB: algomatter_test
    ports:
      - "5433:5432"

  test-redis:
    image: redis:7-alpine
    ports:
      - "6380:6379"
```

- [ ] **Step 8: Verify Docker infrastructure starts**

Run: `cd backend && docker compose up -d postgres redis`
Expected: Both containers running, Postgres accepting connections on 5432, Redis on 6379.

- [ ] **Step 9: Verify API starts**

Run: `cd backend && pip install -e ".[dev]" && uvicorn app.main:app --port 8000 &`
Run: `curl http://localhost:8000/api/v1/health`
Expected: `{"status":"ok"}`

- [ ] **Step 10: Commit**

```bash
git add backend/
git commit -m "feat: project scaffolding with Docker, FastAPI, config"
```

---

## Task 2: Database Models, Migrations & RLS

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/models.py`
- Create: `backend/app/db/session.py`
- Create: `backend/alembic.ini`
- Create: `backend/app/db/migrations/env.py`

- [ ] **Step 1: Create SQLAlchemy base**

```python
# app/db/base.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

- [ ] **Step 2: Create all ORM models**

Create `app/db/models.py` with all Phase 1 tables: `User`, `RefreshToken`, `BrokerConnection`, `Strategy`, `WebhookSignal`, `HistoricalOHLCV`, `StrategyResult`, `PaperTradingSession`, `PaperPosition`, `PaperTrade`.

Each model follows the spec's SQL schemas exactly. Key details:
- All tenant-scoped models have `tenant_id: Mapped[uuid.UUID]` as a FK to `User.id`
- `User` model includes `webhook_token: Mapped[str]` column — generated via `secrets.token_urlsafe(32)` as default
- `BrokerConnection.credentials` is `LargeBinary` (BYTEA for encrypted data)
- `Strategy.mapping_template` and `Strategy.rules` are `JSON` type
- `StrategyResult.trade_log`, `equity_curve`, `metrics`, `config`, `warnings` are `JSON` type
- `WebhookSignal` includes `processing_ms: Mapped[int | None]` for end-to-end timing
- All NUMERIC fields use `Numeric(20, 8)`

Full column list per model (implementer should match spec SQL exactly):
- **User**: id, email, password_hash, is_active, plan, webhook_token, created_at
- **RefreshToken**: id, user_id (FK), token_hash, expires_at, created_at
- **BrokerConnection**: id, tenant_id (FK), broker_type, credentials (BYTEA), is_active, connected_at
- **Strategy**: id, tenant_id (FK), name, broker_connection_id (FK nullable), mode, mapping_template (JSONB), rules (JSONB), is_active, created_at
- **WebhookSignal**: id, tenant_id (FK), strategy_id (FK nullable), received_at, raw_payload (JSONB), parsed_signal (JSONB nullable), rule_result, rule_detail, execution_result, execution_detail (JSONB nullable), processing_ms
- **HistoricalOHLCV**: symbol, exchange, interval, timestamp (composite PK), open, high, low, close, volume
- **StrategyResult**: id, tenant_id (FK), strategy_id (FK nullable), result_type, trade_log (JSONB), equity_curve (JSONB), metrics (JSONB), config (JSONB), warnings (JSONB nullable), status, error_message, created_at, completed_at
- **PaperTradingSession**: id, tenant_id (FK), strategy_id (FK), initial_capital, current_balance, status, started_at, stopped_at
- **PaperPosition**: id, session_id (FK), tenant_id (FK), symbol, exchange, side, quantity, avg_entry_price, current_price, unrealized_pnl, opened_at, closed_at
- **PaperTrade**: id, session_id (FK), tenant_id (FK), signal_id (FK nullable), symbol, exchange, action, quantity, fill_price, commission, slippage, realized_pnl, executed_at

- [ ] **Step 3: Create async session factory with RLS hook**

```python
# app/db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import event, text
from app.config import settings

engine = create_async_engine(settings.database_url, pool_size=20)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

def activate_rls(session: AsyncSession, tenant_id: str):
    """Register an after_begin hook that sets the RLS tenant context."""
    @event.listens_for(session.sync_session, "after_begin")
    def set_tenant(session, transaction, connection):
        connection.execute(
            text("SET LOCAL app.current_tenant_id = :tid"),
            {"tid": str(tenant_id)}
        )
```

- [ ] **Step 4: Configure Alembic for async**

Create `alembic.ini` pointing to `app/db/migrations`. Create `app/db/migrations/env.py` with async migration support using `run_async` and importing `Base.metadata` from `app.db.base` plus all models from `app.db.models`.

- [ ] **Step 5: Generate initial migration**

Run: `cd backend && alembic revision --autogenerate -m "initial schema"`
Expected: Migration file created in `app/db/migrations/versions/`

- [ ] **Step 6: Run migration and verify tables**

Run: `cd backend && alembic upgrade head`
Run: `psql postgresql://algomatter:algomatter@localhost:5432/algomatter -c "\dt"`
Expected: All 10 tables listed.

- [ ] **Step 7: Add RLS policies via manual migration**

Run: `alembic revision -m "add RLS policies"`

Create migration that:
1. Creates a restricted app user: `CREATE USER algomatter_app WITH PASSWORD 'algomatter_app'`
2. Grants necessary permissions to `algomatter_app`
3. Enables RLS on all tenant-scoped tables (all except `users` and `historical_ohlcv`)
4. Creates `tenant_isolation` policy on each: `USING (tenant_id = current_setting('app.current_tenant_id')::UUID)`

Run: `alembic upgrade head`

- [ ] **Step 8: Commit**

```bash
git add backend/app/db/ backend/alembic.ini
git commit -m "feat: database models, async migrations, RLS policies"
```

---

## Task 3: Encryption Service

**Files:**
- Create: `backend/app/crypto/__init__.py`
- Create: `backend/app/crypto/encryption.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_crypto.py`

- [ ] **Step 1: Write failing tests for encryption**

```python
# tests/test_crypto.py
import uuid
import pytest
from app.crypto.encryption import derive_tenant_key, encrypt_credentials, decrypt_credentials

def test_derive_tenant_key_deterministic():
    tenant_id = uuid.uuid4()
    key1 = derive_tenant_key(tenant_id)
    key2 = derive_tenant_key(tenant_id)
    assert key1 == key2

def test_derive_tenant_key_unique_per_tenant():
    key1 = derive_tenant_key(uuid.uuid4())
    key2 = derive_tenant_key(uuid.uuid4())
    assert key1 != key2

def test_encrypt_decrypt_roundtrip():
    tenant_id = uuid.uuid4()
    credentials = {"api_key": "abc123", "secret": "xyz789"}
    encrypted = encrypt_credentials(tenant_id, credentials)
    assert isinstance(encrypted, bytes)
    decrypted = decrypt_credentials(tenant_id, encrypted)
    assert decrypted == credentials

def test_decrypt_with_wrong_tenant_fails():
    tenant_id_a = uuid.uuid4()
    tenant_id_b = uuid.uuid4()
    encrypted = encrypt_credentials(tenant_id_a, {"key": "val"})
    with pytest.raises(Exception):
        decrypt_credentials(tenant_id_b, encrypted)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_crypto.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement encryption module**

```python
# app/crypto/encryption.py
import json
import os
import uuid
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from app.config import settings

def derive_tenant_key(tenant_id: uuid.UUID) -> bytes:
    master_key = bytes.fromhex(settings.master_key)
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=tenant_id.bytes,
        info=b"algomatter-credential-encryption",
    )
    return hkdf.derive(master_key)

def encrypt_credentials(tenant_id: uuid.UUID, credentials: dict) -> bytes:
    key = derive_tenant_key(tenant_id)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    plaintext = json.dumps(credentials).encode()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext  # 12-byte nonce prepended

def decrypt_credentials(tenant_id: uuid.UUID, data: bytes) -> dict:
    key = derive_tenant_key(tenant_id)
    nonce = data[:12]
    ciphertext = data[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ALGOMATTER_MASTER_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") pytest tests/test_crypto.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/crypto/ backend/tests/test_crypto.py
git commit -m "feat: AES-256-GCM encryption with HKDF per-tenant key derivation"
```

---

## Task 4: Auth Service & API

**Files:**
- Create: `backend/app/auth/__init__.py`
- Create: `backend/app/auth/service.py`
- Create: `backend/app/auth/schemas.py`
- Create: `backend/app/auth/router.py`
- Create: `backend/app/auth/deps.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Create auth Pydantic schemas**

```python
# app/auth/schemas.py
from pydantic import BaseModel, EmailStr
import uuid
from datetime import datetime

class SignupRequest(BaseModel):
    email: EmailStr
    password: str  # min 8 chars validated in service

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    is_active: bool
    plan: str
    created_at: datetime
```

- [ ] **Step 2: Implement auth service**

`app/auth/service.py` — functions:
- `hash_password(password: str) -> str` — bcrypt hash
- `verify_password(password: str, hash: str) -> bool` — bcrypt verify
- `create_access_token(user_id: UUID, email: str) -> str` — PyJWT encode with exp=15min
- `decode_access_token(token: str) -> dict` — PyJWT decode, raises on invalid/expired
- `create_refresh_token() -> str` — `secrets.token_urlsafe(32)`
- `hash_refresh_token(token: str) -> str` — SHA-256 hex digest

- [ ] **Step 3: Create test fixtures in conftest.py**

```python
# tests/conftest.py
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.main import app
from app.db.base import Base
from app.db.session import engine

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture
async def db_session():
    """Create tables, yield session, drop tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def client():
    """Async test client for FastAPI."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def create_authenticated_user(client: AsyncClient, email: str = "test@example.com") -> dict:
    """Helper — not a fixture. Call from tests as: tokens = await create_authenticated_user(client)"""
    resp = await client.post("/api/v1/auth/signup", json={
        "email": email, "password": "securepass123"
    })
    return resp.json()  # {access_token, refresh_token}
```

- [ ] **Step 4: Write failing auth integration tests**

```python
# tests/test_auth.py
import pytest

@pytest.mark.asyncio
async def test_signup_success(client):
    resp = await client.post("/api/v1/auth/signup", json={
        "email": "test@example.com", "password": "securepass123"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data

@pytest.mark.asyncio
async def test_signup_duplicate_email(client):
    await client.post("/api/v1/auth/signup", json={
        "email": "test@example.com", "password": "securepass123"
    })
    resp = await client.post("/api/v1/auth/signup", json={
        "email": "test@example.com", "password": "otherpass123"
    })
    assert resp.status_code == 409

@pytest.mark.asyncio
async def test_login_success(client):
    await client.post("/api/v1/auth/signup", json={
        "email": "test@example.com", "password": "securepass123"
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com", "password": "securepass123"
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()

@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/signup", json={
        "email": "test@example.com", "password": "securepass123"
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com", "password": "wrongpass"
    })
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_me_requires_auth(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_me_returns_user(client):
    signup = await client.post("/api/v1/auth/signup", json={
        "email": "test@example.com", "password": "securepass123"
    })
    token = signup.json()["access_token"]
    resp = await client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {token}"
    })
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"

@pytest.mark.asyncio
async def test_refresh_token_rotation(client):
    signup = await client.post("/api/v1/auth/signup", json={
        "email": "test@example.com", "password": "securepass123"
    })
    refresh = signup.json()["refresh_token"]
    resp = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh
    })
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert new_tokens["refresh_token"] != refresh  # rotated

@pytest.mark.asyncio
async def test_rls_isolation(client):
    """User A's profile is invisible to User B's scoped queries."""
    a = (await client.post("/api/v1/auth/signup", json={
        "email": "a@test.com", "password": "securepass123"
    })).json()
    b = (await client.post("/api/v1/auth/signup", json={
        "email": "b@test.com", "password": "securepass123"
    })).json()
    # User A should only see their own data via /me
    a_me = (await client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {a['access_token']}"
    })).json()
    assert a_me["email"] == "a@test.com"
    b_me = (await client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {b['access_token']}"
    })).json()
    assert b_me["email"] == "b@test.com"
    # Full RLS isolation of tenant-scoped data (strategies, signals, etc.)
    # is verified in Task 7 (broker connections) and Task 19 (E2E integration test)
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: FAIL — routes not registered

- [ ] **Step 6: Implement auth deps (get_current_user, get_tenant_session)**

```python
# app/auth/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.service import decode_access_token
from app.db.session import async_session_factory, activate_rls
from app.db.models import User

bearer_scheme = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    try:
        payload = decode_access_token(credentials.credentials)
        return payload  # {"user_id": "...", "email": "..."}
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

async def get_tenant_session(
    current_user: dict = Depends(get_current_user),
) -> AsyncSession:
    session = async_session_factory()
    activate_rls(session, current_user["user_id"])
    try:
        yield session
    finally:
        await session.close()

async def get_session() -> AsyncSession:
    """Non-RLS session for auth endpoints (signup/login)."""
    async with async_session_factory() as session:
        yield session
```

- [ ] **Step 7: Implement auth router**

`app/auth/router.py` — FastAPI APIRouter with prefix `/api/v1/auth`:
- `POST /signup` — validate password >= 8 chars, hash password, generate `webhook_token` via `secrets.token_urlsafe(32)`, create User, create refresh token, return tokens. 201 on success, 409 on duplicate email.
- `POST /login` — find user by email, verify password, create new tokens. 200 on success, 401 on failure.
- `POST /refresh` — hash incoming token, find in DB, verify not expired, delete old token, create new pair. 200 on success, 401 on invalid.
- `GET /me` — return current user from JWT (requires `get_current_user`).

- [ ] **Step 8: Wire auth router into main.py**

Add `from app.auth.router import router as auth_router` and `app.include_router(auth_router)` in `main.py`. Add DB pool initialization in lifespan.

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: All 8 tests pass

- [ ] **Step 10: Commit**

```bash
git add backend/app/auth/ backend/tests/conftest.py backend/tests/test_auth.py backend/app/main.py
git commit -m "feat: auth system with signup, login, JWT, refresh tokens, RLS deps"
```

---

## Task 5: Structured Logging & Rate Limiting Middleware

**Files:**
- Create: `backend/app/middleware/__init__.py`
- Create: `backend/app/middleware/logging.py`
- Create: `backend/app/middleware/rate_limiter.py`

- [ ] **Step 1: Implement structured logging middleware**

```python
# app/middleware/logging.py
import time
import uuid
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = structlog.get_logger()

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )
        return response
```

- [ ] **Step 2: Implement rate limiter middleware**

```python
# app/middleware/rate_limiter.py
import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from redis.asyncio import Redis
from app.config import settings

class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis: Redis):
        super().__init__(app)
        self.redis = redis
        self.limit = settings.rate_limit_per_minute
        self.window = 60  # seconds

    async def dispatch(self, request: Request, call_next):
        # Only rate-limit webhook endpoints
        if not request.url.path.startswith("/api/v1/webhook/"):
            return await call_next(request)

        # Extract token from path as rate-limit key
        token = request.url.path.split("/api/v1/webhook/")[-1]
        key = f"ratelimit:{token}"
        now = time.time()
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - self.window)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, self.window)
        results = await pipe.execute()
        count = results[2]

        if count > self.limit:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(self.window)},
            )
        return await call_next(request)
```

- [ ] **Step 3: Wire middleware into main.py**

Add both middleware classes to the app in `main.py`. Initialize Redis in lifespan and pass to rate limiter.

- [ ] **Step 4: Write rate limiter tests**

```python
# tests/test_rate_limiter.py
import pytest

@pytest.mark.asyncio
async def test_non_webhook_not_rate_limited(client):
    """Non-webhook paths should not be rate-limited."""
    for _ in range(100):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200

@pytest.mark.asyncio
async def test_webhook_under_limit_passes(client, redis_client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    config = (await client.get("/api/v1/webhooks/config", headers=headers)).json()
    wt = config["webhook_token"]
    resp = await client.post(f"/api/v1/webhook/{wt}", json={"test": 1})
    assert resp.status_code != 429

@pytest.mark.asyncio
async def test_webhook_over_limit_returns_429(client, redis_client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    config = (await client.get("/api/v1/webhooks/config", headers=headers)).json()
    wt = config["webhook_token"]
    # Exceed rate limit (60/min)
    for _ in range(61):
        await client.post(f"/api/v1/webhook/{wt}", json={"test": 1})
    resp = await client.post(f"/api/v1/webhook/{wt}", json={"test": 1})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
```

- [ ] **Step 5: Verify logging output**

Run: `curl http://localhost:8000/api/v1/health`
Expected: structlog JSON output in server logs with method, path, status, duration_ms.

- [ ] **Step 6: Run rate limiter tests**

Run: `cd backend && pytest tests/test_rate_limiter.py -v`
Expected: All 3 pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/middleware/ backend/app/main.py
git commit -m "feat: structured logging and Redis sliding-window rate limiter middleware"
```

---

## Task 6: Broker Adapter Base & SimulatedBroker

**Files:**
- Create: `backend/app/brokers/__init__.py`
- Create: `backend/app/brokers/base.py`
- Create: `backend/app/brokers/simulated.py`
- Create: `backend/tests/test_brokers.py`

- [ ] **Step 1: Write failing tests for SimulatedBroker**

```python
# tests/test_brokers.py
import pytest
from decimal import Decimal
from app.brokers.base import OrderRequest, OrderResponse, Position, AccountBalance
from app.brokers.simulated import SimulatedBroker

@pytest.mark.asyncio
async def test_simulated_initial_balance():
    broker = SimulatedBroker(initial_capital=Decimal("1000000"))
    balance = await broker.get_balance()
    assert balance.available == Decimal("1000000")

@pytest.mark.asyncio
async def test_simulated_place_buy_order():
    broker = SimulatedBroker(initial_capital=Decimal("1000000"))
    order = OrderRequest(
        symbol="RELIANCE", exchange="NSE", action="BUY",
        quantity=Decimal("10"), order_type="MARKET",
        price=Decimal("2500"), product_type="INTRADAY",
    )
    resp = await broker.place_order(order)
    assert resp.status == "filled"
    assert resp.fill_price == Decimal("2500")  # no slippage configured
    positions = await broker.get_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "RELIANCE"
    assert positions[0].quantity == Decimal("10")

@pytest.mark.asyncio
async def test_simulated_slippage():
    broker = SimulatedBroker(
        initial_capital=Decimal("1000000"),
        slippage_pct=Decimal("0.1"),  # 0.1%
    )
    order = OrderRequest(
        symbol="TCS", exchange="NSE", action="BUY",
        quantity=Decimal("5"), order_type="MARKET",
        price=Decimal("1000"), product_type="INTRADAY",
    )
    resp = await broker.place_order(order)
    assert resp.fill_price == Decimal("1001")  # 1000 + 0.1%

@pytest.mark.asyncio
async def test_simulated_sell_reduces_position():
    broker = SimulatedBroker(initial_capital=Decimal("1000000"))
    await broker.place_order(OrderRequest(
        symbol="INFY", exchange="NSE", action="BUY",
        quantity=Decimal("20"), order_type="MARKET",
        price=Decimal("1500"), product_type="INTRADAY",
    ))
    await broker.place_order(OrderRequest(
        symbol="INFY", exchange="NSE", action="SELL",
        quantity=Decimal("20"), order_type="MARKET",
        price=Decimal("1600"), product_type="INTRADAY",
    ))
    positions = await broker.get_positions()
    open_positions = [p for p in positions if p.closed_at is None]
    assert len(open_positions) == 0

@pytest.mark.asyncio
async def test_simulated_insufficient_balance():
    broker = SimulatedBroker(initial_capital=Decimal("100"))
    order = OrderRequest(
        symbol="RELIANCE", exchange="NSE", action="BUY",
        quantity=Decimal("10"), order_type="MARKET",
        price=Decimal("2500"), product_type="INTRADAY",
    )
    resp = await broker.place_order(order)
    assert resp.status == "rejected"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_brokers.py -v`
Expected: FAIL — import errors

- [ ] **Step 3: Implement BrokerAdapter ABC and data models in base.py**

Define in `app/brokers/base.py`:
- Data models as Pydantic BaseModel: `OrderRequest`, `OrderResponse`, `Position`, `Holding`, `AccountBalance`, `Quote`, `OHLCV` — all with fields matching the spec.
- `BrokerAdapter` ABC with all abstract methods from the spec.

- [ ] **Step 4: Implement SimulatedBroker**

`app/brokers/simulated.py` — implements `BrokerAdapter`:
- Constructor takes `initial_capital`, `slippage_pct` (default 0), `commission_pct` (default 0)
- Maintains in-memory state: `balance`, `positions: list[Position]`, `orders: list[OrderResponse]`
- `place_order`: calculates fill price (price + slippage for BUY, price - slippage for SELL), checks sufficient balance, updates positions and balance, returns `OrderResponse`
- `get_positions`, `get_balance`, `get_holdings`: return current state
- `verify_connection`: always returns True
- `get_quotes`: returns empty (no live data in Phase 1)
- `get_historical`: returns empty (data comes from historical service)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_brokers.py -v`
Expected: All 5 tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/brokers/base.py backend/app/brokers/simulated.py backend/tests/test_brokers.py
git commit -m "feat: BrokerAdapter ABC and SimulatedBroker with slippage/commission"
```

---

## Task 7: Broker Connections API

**Files:**
- Create: `backend/app/brokers/schemas.py`
- Create: `backend/app/brokers/router.py`
- Modify: `backend/app/main.py` (add router)
- Modify: `backend/tests/conftest.py` (add auth helper fixture)
- Create: `backend/tests/test_broker_connections.py`

- [ ] **Step 1: Write failing tests**

Tests for:
- `POST /api/v1/brokers` — create broker connection, verify credentials are encrypted in DB
- `GET /api/v1/brokers` — list connections (only current user's)
- `DELETE /api/v1/brokers/{id}` — remove connection
- RLS isolation: User A creates connection, User B cannot see it via `GET /api/v1/brokers`

Add a helper fixture in `conftest.py`:
```python
async def create_authenticated_user(client, email="test@example.com"):
    resp = await client.post("/api/v1/auth/signup", json={
        "email": email, "password": "securepass123"
    })
    return resp.json()  # {access_token, refresh_token}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_broker_connections.py -v`
Expected: FAIL

- [ ] **Step 3: Implement broker schemas**

`app/brokers/schemas.py`:
- `CreateBrokerConnectionRequest`: `broker_type: str`, `credentials: dict`
- `BrokerConnectionResponse`: `id, broker_type, is_active, connected_at` (no credentials in response)

- [ ] **Step 4: Implement broker router**

`app/brokers/router.py` — APIRouter prefix `/api/v1/brokers`:
- `POST /` — encrypt credentials with `encrypt_credentials(tenant_id, creds)`, store in DB, return 201
- `GET /` — query `BrokerConnection` (RLS filters automatically), return list
- `DELETE /{id}` — find by id (RLS ensures tenant scope), delete, return 204
- `POST /{id}/verify` — decrypt credentials, instantiate adapter, call `verify_connection()`, return result

- [ ] **Step 5: Wire router into main.py**

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_broker_connections.py -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/brokers/schemas.py backend/app/brokers/router.py backend/tests/test_broker_connections.py
git commit -m "feat: broker connections API with encrypted credential storage and RLS"
```

---

## Task 8: Webhook Mapper (JSONPath Engine)

**Files:**
- Create: `backend/app/webhooks/__init__.py`
- Create: `backend/app/webhooks/mapper.py`
- Create: `backend/app/webhooks/schemas.py`
- Create: `backend/tests/test_webhook_mapper.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_webhook_mapper.py
import pytest
from app.webhooks.mapper import apply_mapping
from app.webhooks.schemas import StandardSignal

def test_mapping_with_jsonpath():
    payload = {
        "ticker": "RELIANCE",
        "exchange": "NSE",
        "strategy": {"order_action": "buy", "order_contracts": "10"}
    }
    template = {
        "symbol": "$.ticker",
        "exchange": "$.exchange",
        "action": "$.strategy.order_action",
        "quantity": "$.strategy.order_contracts",
        "order_type": "MARKET",
        "product_type": "INTRADAY",
    }
    signal = apply_mapping(payload, template)
    assert isinstance(signal, StandardSignal)
    assert signal.symbol == "RELIANCE"
    assert signal.action == "BUY"  # normalized to uppercase
    assert signal.quantity == 10
    assert signal.order_type == "MARKET"

def test_mapping_with_literal_values():
    payload = {"sym": "TCS"}
    template = {
        "symbol": "$.sym",
        "exchange": "NSE",
        "action": "BUY",
        "quantity": "5",
        "order_type": "MARKET",
        "product_type": "INTRADAY",
    }
    signal = apply_mapping(payload, template)
    assert signal.symbol == "TCS"
    assert signal.exchange == "NSE"

def test_mapping_missing_jsonpath_raises():
    payload = {"foo": "bar"}
    template = {"symbol": "$.nonexistent", "exchange": "NSE", "action": "BUY",
                "quantity": "1", "order_type": "MARKET", "product_type": "INTRADAY"}
    with pytest.raises(ValueError, match="Failed to resolve"):
        apply_mapping(payload, template)

def test_mapping_tradingview_format():
    """Real TradingView webhook payload."""
    payload = {
        "ticker": "NIFTY",
        "exchange": "NSE",
        "close": 22500.50,
        "strategy": {
            "order_action": "sell",
            "order_contracts": "50",
            "order_price": "22500.50",
            "order_id": "Long Entry"
        }
    }
    template = {
        "symbol": "$.ticker",
        "exchange": "$.exchange",
        "action": "$.strategy.order_action",
        "quantity": "$.strategy.order_contracts",
        "order_type": "MARKET",
        "price": "$.strategy.order_price",
        "product_type": "INTRADAY",
    }
    signal = apply_mapping(payload, template)
    assert signal.symbol == "NIFTY"
    assert signal.action == "SELL"
    assert signal.quantity == 50
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_webhook_mapper.py -v`

- [ ] **Step 3: Implement StandardSignal schema and mapper**

`app/webhooks/schemas.py`:
```python
from pydantic import BaseModel
from decimal import Decimal
from typing import Optional

class StandardSignal(BaseModel):
    symbol: str
    exchange: str
    action: str  # BUY, SELL
    quantity: Decimal
    order_type: str  # MARKET, LIMIT, SL
    price: Optional[Decimal] = None
    trigger_price: Optional[Decimal] = None
    product_type: str  # INTRADAY, DELIVERY
```

`app/webhooks/mapper.py`:
```python
from decimal import Decimal
from jsonpath_ng import parse
from app.webhooks.schemas import StandardSignal

def apply_mapping(payload: dict, template: dict) -> StandardSignal:
    resolved = {}
    for field, expr in template.items():
        if isinstance(expr, str) and expr.startswith("$."):
            matches = parse(expr).find(payload)
            if not matches:
                raise ValueError(f"Failed to resolve JSONPath '{expr}' for field '{field}'")
            resolved[field] = matches[0].value
        else:
            resolved[field] = expr
    # Normalize
    resolved["action"] = str(resolved["action"]).upper()
    resolved["quantity"] = Decimal(str(resolved["quantity"])) if resolved.get("quantity") else Decimal("0")
    if resolved.get("price"):
        resolved["price"] = float(resolved["price"])
    return StandardSignal(**resolved)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_webhook_mapper.py -v`
Expected: All 4 tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/webhooks/ backend/tests/test_webhook_mapper.py
git commit -m "feat: JSONPath webhook mapping engine with standard signal format"
```

---

## Task 9: Signal Processor (Rules Engine)

**Files:**
- Create: `backend/app/webhooks/processor.py`
- Create: `backend/tests/test_signal_processor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_signal_processor.py
import pytest
from decimal import Decimal
from app.webhooks.processor import evaluate_rules, RuleResult
from app.webhooks.schemas import StandardSignal

def make_signal(**overrides) -> StandardSignal:
    defaults = dict(symbol="RELIANCE", exchange="NSE", action="BUY",
                    quantity=Decimal("10"), order_type="MARKET", product_type="INTRADAY")
    defaults.update(overrides)
    return StandardSignal(**defaults)

def test_no_rules_passes():
    result = evaluate_rules(make_signal(), {}, open_positions=0, signals_today=0)
    assert result.passed is True

def test_symbol_whitelist_pass():
    rules = {"symbol_whitelist": ["RELIANCE", "TCS"]}
    result = evaluate_rules(make_signal(symbol="RELIANCE"), rules, 0, 0)
    assert result.passed is True

def test_symbol_whitelist_block():
    rules = {"symbol_whitelist": ["TCS", "INFY"]}
    result = evaluate_rules(make_signal(symbol="RELIANCE"), rules, 0, 0)
    assert result.passed is False
    assert "whitelist" in result.reason

def test_symbol_blacklist_block():
    rules = {"symbol_blacklist": ["RELIANCE"]}
    result = evaluate_rules(make_signal(symbol="RELIANCE"), rules, 0, 0)
    assert result.passed is False

def test_max_open_positions_block():
    rules = {"max_open_positions": 5}
    result = evaluate_rules(make_signal(), rules, open_positions=5, signals_today=0)
    assert result.passed is False

def test_max_position_size_block():
    rules = {"max_position_size": 100}
    signal = make_signal(quantity=Decimal("200"))
    result = evaluate_rules(signal, rules, 0, 0)
    assert result.passed is False

def test_max_signals_per_day_block():
    rules = {"max_signals_per_day": 10}
    result = evaluate_rules(make_signal(), rules, 0, signals_today=10)
    assert result.passed is False

def test_trading_hours_block():
    rules = {"trading_hours": {"start": "09:15", "end": "15:30", "timezone": "Asia/Kolkata"}}
    # This test is time-dependent; use a fixed time via parameter
    result = evaluate_rules(
        make_signal(), rules, 0, 0,
        current_time_str="03:00"  # 3 AM IST — outside hours
    )
    assert result.passed is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_signal_processor.py -v`

- [ ] **Step 3: Implement rules engine**

```python
# app/webhooks/processor.py
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo
from app.webhooks.schemas import StandardSignal

@dataclass
class RuleResult:
    passed: bool
    reason: str = ""

def evaluate_rules(
    signal: StandardSignal,
    rules: dict,
    open_positions: int,
    signals_today: int,
    current_time_str: str | None = None,
) -> RuleResult:
    if not rules:
        return RuleResult(passed=True)

    # Symbol whitelist
    if wl := rules.get("symbol_whitelist"):
        if wl and signal.symbol not in wl:
            return RuleResult(False, f"Symbol {signal.symbol} not in whitelist")

    # Symbol blacklist
    if bl := rules.get("symbol_blacklist"):
        if signal.symbol in bl:
            return RuleResult(False, f"Symbol {signal.symbol} in blacklist")

    # Max open positions
    if max_pos := rules.get("max_open_positions"):
        if open_positions >= max_pos:
            return RuleResult(False, f"Max open positions ({max_pos}) reached")

    # Max position size
    if max_size := rules.get("max_position_size"):
        if signal.quantity > Decimal(str(max_size)):
            return RuleResult(False, f"Quantity {signal.quantity} exceeds max {max_size}")

    # Max signals per day
    if max_sig := rules.get("max_signals_per_day"):
        if signals_today >= max_sig:
            return RuleResult(False, f"Max signals per day ({max_sig}) reached")

    # Trading hours
    if hours := rules.get("trading_hours"):
        tz = ZoneInfo(hours.get("timezone", "Asia/Kolkata"))
        if current_time_str:
            now_time = datetime.strptime(current_time_str, "%H:%M").time()
        else:
            now_time = datetime.now(tz).time()
        start = datetime.strptime(hours["start"], "%H:%M").time()
        end = datetime.strptime(hours["end"], "%H:%M").time()
        if not (start <= now_time <= end):
            return RuleResult(False, f"Outside trading hours ({hours['start']}-{hours['end']})")

    return RuleResult(passed=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_signal_processor.py -v`
Expected: All 8 tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/webhooks/processor.py backend/tests/test_signal_processor.py
git commit -m "feat: signal processing rules engine (whitelist, blacklist, limits, hours)"
```

---

## Task 10: Strategies CRUD API

**Files:**
- Create: `backend/app/strategies/__init__.py`
- Create: `backend/app/strategies/schemas.py`
- Create: `backend/app/strategies/router.py`
- Create: `backend/tests/test_strategies.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests**

Tests for:
- `POST /api/v1/strategies` — create with name, mapping template, rules. Returns 201.
- `GET /api/v1/strategies` — list user's strategies
- `PUT /api/v1/strategies/{id}` — update name, rules, mapping template
- `DELETE /api/v1/strategies/{id}` — remove strategy, returns 204
- RLS isolation: User A's strategies invisible to User B

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_strategies.py -v`

- [ ] **Step 3: Implement schemas**

`app/strategies/schemas.py`:
- `CreateStrategyRequest`: `name: str`, `broker_connection_id: UUID | None`, `mode: str = "paper"`, `mapping_template: dict`, `rules: dict = {}`
- `UpdateStrategyRequest`: all fields optional
- `StrategyResponse`: full strategy with id, tenant_id, created_at, is_active

- [ ] **Step 4: Implement router**

Standard CRUD on `Strategy` model. All queries go through tenant-scoped session (`get_tenant_session`). Generates a `webhook_token` via `secrets.token_urlsafe(32)` on strategy creation (add `webhook_token` column to Strategy model if not already present — or use the user-level token from the spec).

Note: Per the spec, the webhook token is per-user, not per-strategy. The strategy determines how to process the signal. So webhook_token lives on the User model. Add a `webhook_token` column to User (generated on signup).

- [ ] **Step 5: Wire router, run tests**

Run: `cd backend && pytest tests/test_strategies.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/strategies/ backend/tests/test_strategies.py
git commit -m "feat: strategies CRUD API with mapping templates and rules config"
```

---

## Task 11: Webhook Receiver API & Integration Test

**Files:**
- Create: `backend/app/webhooks/router.py`
- Create: `backend/tests/test_webhooks.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing integration tests**

```python
# tests/test_webhooks.py
import pytest

@pytest.mark.asyncio
async def test_webhook_invalid_token(client):
    resp = await client.post("/api/v1/webhook/invalid-token", json={
        "ticker": "RELIANCE", "exchange": "NSE",
        "strategy": {"order_action": "buy", "order_contracts": "10"}
    })
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_webhook_receives_and_logs_signal(client):
    # Setup: create user, create strategy
    tokens = await create_authenticated_user(client)
    token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get user's webhook token
    config = await client.get("/api/v1/webhooks/config", headers=headers)
    webhook_token = config.json()["webhook_token"]

    # Create a strategy with mapping template
    await client.post("/api/v1/strategies", json={
        "name": "test-strategy",
        "mode": "paper",
        "mapping_template": {
            "symbol": "$.ticker", "exchange": "$.exchange",
            "action": "$.strategy.order_action",
            "quantity": "$.strategy.order_contracts",
            "order_type": "MARKET", "product_type": "INTRADAY",
        },
        "rules": {},
    }, headers=headers)

    # Send webhook
    resp = await client.post(f"/api/v1/webhook/{webhook_token}", json={
        "ticker": "RELIANCE", "exchange": "NSE",
        "strategy": {"order_action": "buy", "order_contracts": "10"}
    })
    assert resp.status_code == 200

    # Verify signal logged
    signals = await client.get("/api/v1/webhooks/signals", headers=headers)
    assert len(signals.json()) >= 1
    assert signals.json()[0]["parsed_signal"]["symbol"] == "RELIANCE"

@pytest.mark.asyncio
async def test_webhook_blocked_by_rule(client):
    tokens = await create_authenticated_user(client)
    token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    config = await client.get("/api/v1/webhooks/config", headers=headers)
    webhook_token = config.json()["webhook_token"]

    await client.post("/api/v1/strategies", json={
        "name": "restricted",
        "mode": "paper",
        "mapping_template": {
            "symbol": "$.ticker", "exchange": "NSE", "action": "$.action",
            "quantity": "$.qty", "order_type": "MARKET", "product_type": "INTRADAY",
        },
        "rules": {"symbol_whitelist": ["TCS"]},
    }, headers=headers)

    resp = await client.post(f"/api/v1/webhook/{webhook_token}", json={
        "ticker": "RELIANCE", "action": "buy", "qty": "10"
    })
    assert resp.status_code == 200  # webhook accepted but signal blocked

    signals = await client.get("/api/v1/webhooks/signals", headers=headers)
    blocked = [s for s in signals.json() if s["rule_result"] == "blocked_by_rule"]
    assert len(blocked) >= 1

@pytest.mark.asyncio
async def test_webhook_payload_too_large(client):
    # Create user and get webhook token
    tokens = await create_authenticated_user(client)
    token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    config = await client.get("/api/v1/webhooks/config", headers=headers)
    webhook_token = config.json()["webhook_token"]

    # Send oversized payload (>64KB)
    big_payload = {"data": "x" * 70000}
    resp = await client.post(f"/api/v1/webhook/{webhook_token}", json=big_payload)
    assert resp.status_code == 413

@pytest.mark.asyncio
async def test_webhook_config_regenerate_token(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    config1 = await client.get("/api/v1/webhooks/config", headers=headers)
    old_token = config1.json()["webhook_token"]

    await client.post("/api/v1/webhooks/config/regenerate-token", headers=headers)
    config2 = await client.get("/api/v1/webhooks/config", headers=headers)
    new_token = config2.json()["webhook_token"]

    assert old_token != new_token

    # Old token no longer works
    resp = await client.post(f"/api/v1/webhook/{old_token}", json={"test": 1})
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_webhooks.py -v`

- [ ] **Step 3: Implement webhook router**

`app/webhooks/router.py`:
- `POST /api/v1/webhook/{token}` (public, no JWT required):
  1. Look up user by webhook_token (401 if not found)
  2. Validate payload size (413 if >64KB)
  3. Validate payload structure: reject nesting deeper than 3 levels, strip and length-cap all string values (max 1000 chars)
  4. Record `start_time` for `processing_ms` tracking
  5. For each active strategy of that user, apply mapping template → get StandardSignal
  6. Evaluate rules → get RuleResult
  7. If passed and mode=paper: route to paper trading engine (stubbed in this task — actual wiring happens in Task 16 Step 5; for now, log `execution_result = "pending"`)
  8. Log everything to `webhook_signals` table including `processing_ms = time.perf_counter() - start_time`
  9. Publish event to Redis Streams
  10. Return 200 with `{received: true, signals_processed: N}`

**Note:** The paper trading integration (step 7) is a forward dependency on Task 16. In this task, the webhook receiver logs the signal and marks execution as "pending". Task 16 Step 5 wires the actual paper trade execution.

- `GET /api/v1/webhooks/config` (requires auth): return user's webhook_token and active strategies
- `POST /api/v1/webhooks/config/regenerate-token` (requires auth): generate new token, update user
- `GET /api/v1/webhooks/signals` (requires auth): paginated list of webhook_signals for tenant

- [ ] **Step 4: Wire router, run tests**

Run: `cd backend && pytest tests/test_webhooks.py -v`
Expected: All 5 tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/webhooks/router.py backend/tests/test_webhooks.py
git commit -m "feat: webhook receiver with mapping, rules, signal logging, token management"
```

---

## Task 12: Event Bus (Redis Streams)

**Files:**
- Create: `backend/app/events/__init__.py`
- Create: `backend/app/events/bus.py`
- Create: `backend/tests/test_events.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_events.py
import pytest
from app.events.bus import EventBus

@pytest.mark.asyncio
async def test_publish_and_read_event(redis_client):
    bus = EventBus(redis_client)
    await bus.publish("webhook.received", {
        "tenant_id": "abc", "signal_id": "123", "symbol": "RELIANCE"
    })
    events = await bus.read_recent("webhook.received", count=1)
    assert len(events) == 1
    assert events[0]["symbol"] == "RELIANCE"

@pytest.mark.asyncio
async def test_stream_max_length(redis_client):
    bus = EventBus(redis_client, max_length=5)
    for i in range(10):
        await bus.publish("test.stream", {"i": str(i)})
    events = await bus.read_recent("test.stream", count=100)
    assert len(events) <= 6  # approximate trimming
```

- [ ] **Step 2: Implement EventBus**

```python
# app/events/bus.py
import json
from redis.asyncio import Redis

class EventBus:
    def __init__(self, redis: Redis, max_length: int = 100_000):
        self.redis = redis
        self.max_length = max_length

    async def publish(self, stream: str, data: dict) -> str:
        entry = {k: json.dumps(v) if not isinstance(v, str) else v for k, v in data.items()}
        msg_id = await self.redis.xadd(
            f"algomatter:{stream}", entry, maxlen=self.max_length, approximate=True
        )
        return msg_id

    async def read_recent(self, stream: str, count: int = 10) -> list[dict]:
        messages = await self.redis.xrevrange(f"algomatter:{stream}", count=count)
        results = []
        for msg_id, data in messages:
            parsed = {}
            for k, v in data.items():
                key = k.decode() if isinstance(k, bytes) else k
                val = v.decode() if isinstance(v, bytes) else v
                try:
                    parsed[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    parsed[key] = val
            results.append(parsed)
        return results
```

- [ ] **Step 3: Add redis_client fixture to conftest.py**

```python
@pytest_asyncio.fixture
async def redis_client():
    from redis.asyncio import Redis
    client = Redis.from_url("redis://localhost:6379/1")  # test DB
    yield client
    await client.flushdb()
    await client.aclose()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_events.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/events/ backend/tests/test_events.py
git commit -m "feat: Redis Streams event bus for durable event publishing"
```

---

## Task 13: Historical Data Service

**Files:**
- Create: `backend/app/historical/__init__.py`
- Create: `backend/app/historical/service.py`
- Create: `backend/app/historical/tasks.py`
- Create: `backend/tests/test_historical.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_historical.py
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_get_ohlcv_returns_cached_data(db_session):
    """Data already in DB is returned without external fetch."""
    from app.historical.service import get_ohlcv
    from app.db.models import HistoricalOHLCV
    # Insert test data
    row = HistoricalOHLCV(
        symbol="RELIANCE", exchange="NSE", interval="1d",
        timestamp=datetime(2025, 1, 2), open=Decimal("2500"),
        high=Decimal("2550"), low=Decimal("2480"),
        close=Decimal("2530"), volume=Decimal("1000000"),
    )
    db_session.add(row)
    await db_session.commit()
    result = await get_ohlcv(db_session, "RELIANCE", "NSE", "1d",
                             datetime(2025, 1, 1), datetime(2025, 1, 3))
    assert len(result) == 1
    assert result[0].close == Decimal("2530")

@pytest.mark.asyncio
async def test_get_latest_price(db_session):
    from app.historical.service import get_latest_price
    from app.db.models import HistoricalOHLCV
    for i, price in enumerate([2500, 2530, 2510]):
        db_session.add(HistoricalOHLCV(
            symbol="TCS", exchange="NSE", interval="1d",
            timestamp=datetime(2025, 1, i+1), open=Decimal(str(price)),
            high=Decimal(str(price+50)), low=Decimal(str(price-20)),
            close=Decimal(str(price)), volume=Decimal("500000"),
        ))
    await db_session.commit()
    price = await get_latest_price(db_session, "TCS", "NSE")
    assert price == Decimal("2510")  # most recent

@pytest.mark.asyncio
async def test_fetch_and_cache_calls_yfinance_for_nse(db_session):
    """Verify yfinance is called when data is missing."""
    from app.historical.service import fetch_and_cache_ohlcv
    import pandas as pd
    mock_df = pd.DataFrame({
        "Open": [2500.0], "High": [2550.0], "Low": [2480.0],
        "Close": [2530.0], "Volume": [1000000],
    }, index=pd.DatetimeIndex([datetime(2025, 1, 2)]))
    with patch("app.historical.service.yfinance_download", return_value=mock_df):
        result = await fetch_and_cache_ohlcv(
            db_session, "RELIANCE", "NSE", "1d",
            datetime(2025, 1, 1), datetime(2025, 1, 3),
        )
    assert len(result) >= 1
    assert result[0].symbol == "RELIANCE"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_historical.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement historical data service**

`app/historical/service.py`:
- `async def fetch_and_cache_ohlcv(session, symbol, exchange, interval, start, end)`:
  - Check DB for existing data in range
  - If stale (>24h old) or missing, fetch from source:
    - NSE/BSE: use `yfinance_download(symbol + ".NS", start, end, interval)` (wrapper around `yfinance.download`)
    - EXCHANGE1: HTTP GET to Exchange1 kline endpoint
  - Upsert into `historical_ohlcv` table (ON CONFLICT DO NOTHING)
  - Return list of OHLCV rows

- `async def get_ohlcv(session, symbol, exchange, interval, start, end) -> list[OHLCV]`:
  - Query `historical_ohlcv` for the range
  - Return as list of broker base OHLCV models

- `async def get_latest_price(session, symbol, exchange) -> Decimal`:
  - Query most recent close price from `historical_ohlcv`
  - Used by SimulatedBroker for paper trading fills

- `def yfinance_download(symbol, start, end, interval)`:
  - Thin wrapper around `yfinance.download()` for easy mocking in tests

- [ ] **Step 4: Implement ARQ task for daily fetch**

`app/historical/tasks.py`:
```python
async def daily_data_fetch(ctx):
    """Fetch daily OHLCV for all symbols that have active strategies."""
    # Query distinct symbols from active strategies
    # For each, call fetch_and_cache_ohlcv for last 2 days
    pass
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_historical.py -v`
Expected: All 3 pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/historical/ backend/tests/test_historical.py
git commit -m "feat: historical data service with yfinance fetch and DB caching"
```

---

## Task 14: Analytics Metrics Module

**Files:**
- Create: `backend/app/analytics/__init__.py`
- Create: `backend/app/analytics/metrics.py`
- Create: `backend/tests/test_metrics.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_metrics.py
import pytest
from decimal import Decimal
from app.analytics.metrics import compute_metrics

def test_compute_metrics_basic():
    trades = [
        {"pnl": 100, "entry_price": 1000, "exit_price": 1100, "quantity": 1},
        {"pnl": -50, "entry_price": 2000, "exit_price": 1950, "quantity": 1},
        {"pnl": 200, "entry_price": 500, "exit_price": 700, "quantity": 1},
    ]
    equity_curve = [
        {"timestamp": "2025-01-01", "equity": 100000},
        {"timestamp": "2025-01-02", "equity": 100100},
        {"timestamp": "2025-01-03", "equity": 100050},
        {"timestamp": "2025-01-04", "equity": 100250},
    ]
    metrics = compute_metrics(trades, equity_curve, initial_capital=100000)
    assert metrics["total_return"] == pytest.approx(0.25, rel=0.01)  # 250/100000 as %
    assert metrics["win_rate"] == pytest.approx(66.67, rel=0.1)  # 2/3
    assert metrics["profit_factor"] > 1  # winners > losers
    assert "sharpe_ratio" in metrics
    assert "max_drawdown" in metrics

def test_compute_metrics_no_trades():
    metrics = compute_metrics([], [{"timestamp": "2025-01-01", "equity": 100000}], 100000)
    assert metrics["total_return"] == 0
    assert metrics["win_rate"] == 0
    assert metrics["max_drawdown"] == 0

def test_max_drawdown():
    equity_curve = [
        {"timestamp": "2025-01-01", "equity": 100000},
        {"timestamp": "2025-01-02", "equity": 110000},
        {"timestamp": "2025-01-03", "equity": 88000},  # 20% drawdown from peak
        {"timestamp": "2025-01-04", "equity": 95000},
    ]
    metrics = compute_metrics([], equity_curve, 100000)
    assert metrics["max_drawdown"] == pytest.approx(20.0, rel=0.1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_metrics.py -v`

- [ ] **Step 3: Implement metrics module**

`app/analytics/metrics.py`:
- `compute_metrics(trades, equity_curve, initial_capital) -> dict`:
  - `total_return`: (final_equity - initial) / initial * 100
  - `win_rate`: winning trades / total trades * 100
  - `profit_factor`: sum of profits / abs(sum of losses)
  - `avg_trade_pnl`: mean of all trade PnLs
  - `max_drawdown`: max peak-to-trough decline as percentage
  - `sharpe_ratio`: annualized (mean daily return / std daily return * sqrt(252))

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_metrics.py -v`
Expected: All 3 tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/analytics/metrics.py backend/tests/test_metrics.py
git commit -m "feat: analytics metrics (Sharpe, drawdown, win rate, profit factor)"
```

---

## Task 15: Backtesting Engine & API

**Files:**
- Create: `backend/app/backtesting/__init__.py`
- Create: `backend/app/backtesting/engine.py`
- Create: `backend/app/backtesting/tasks.py`
- Create: `backend/app/backtesting/router.py`
- Create: `backend/tests/test_backtesting.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_backtesting.py
import pytest
from decimal import Decimal

@pytest.mark.asyncio
async def test_backtest_engine_processes_signals():
    from app.backtesting.engine import run_backtest
    from app.brokers.simulated import SimulatedBroker

    signals = [
        {"timestamp": "2025-01-02T09:30:00", "symbol": "RELIANCE", "exchange": "NSE",
         "action": "BUY", "quantity": 10, "order_type": "MARKET", "price": 2500},
        {"timestamp": "2025-01-03T09:30:00", "symbol": "RELIANCE", "exchange": "NSE",
         "action": "SELL", "quantity": 10, "order_type": "MARKET", "price": 2600},
    ]
    result = await run_backtest(
        signals=signals,
        initial_capital=Decimal("1000000"),
        slippage_pct=Decimal("0"),
        commission_pct=Decimal("0"),
    )
    assert result["status"] == "completed"
    assert len(result["trade_log"]) == 2
    assert result["metrics"]["total_return"] > 0
    assert len(result["equity_curve"]) >= 2

@pytest.mark.asyncio
async def test_backtest_api_creates_and_returns(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Create strategy
    strat = await client.post("/api/v1/strategies", json={
        "name": "backtest-strat", "mode": "backtest",
        "mapping_template": {"symbol": "$.symbol", "exchange": "NSE",
                             "action": "$.action", "quantity": "$.quantity",
                             "order_type": "MARKET", "product_type": "INTRADAY"},
        "rules": {},
    }, headers=headers)
    strategy_id = strat.json()["id"]

    # Start backtest
    resp = await client.post("/api/v1/backtests", json={
        "strategy_id": strategy_id,
        "start_date": "2025-01-01",
        "end_date": "2025-01-31",
        "capital": 1000000,
        "slippage_pct": 0,
        "commission_pct": 0,
        "signals_csv": "timestamp,symbol,action,quantity,order_type,price\n2025-01-02T09:30:00,RELIANCE,BUY,10,MARKET,2500\n2025-01-03T09:30:00,RELIANCE,SELL,10,MARKET,2600"
    }, headers=headers)
    assert resp.status_code == 201
    backtest_id = resp.json()["id"]

    # Poll for completion (in tests, backtest runs synchronously)
    result = await client.get(f"/api/v1/backtests/{backtest_id}", headers=headers)
    assert result.json()["status"] == "completed"
    assert result.json()["metrics"]["total_return"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_backtesting.py -v`

- [ ] **Step 3: Implement backtest engine**

`app/backtesting/engine.py`:
- `async def run_backtest(signals, initial_capital, slippage_pct, commission_pct) -> dict`:
  1. Create `SimulatedBroker(initial_capital, slippage_pct, commission_pct)`
  2. Sort signals by timestamp
  3. For each signal, create `OrderRequest` and call `broker.place_order()`
  4. Track equity curve (balance + positions value after each trade)
  5. Collect trade log from broker responses
  6. Call `compute_metrics(trade_log, equity_curve, initial_capital)`
  7. Return `{status, trade_log, equity_curve, metrics, warnings}`

- [ ] **Step 4: Implement ARQ task wrapper**

`app/backtesting/tasks.py`:
```python
async def run_backtest_task(ctx, backtest_id: str):
    """ARQ task: load backtest config from DB, run engine, save results."""
    # 1. Load StrategyResult row by id
    # 2. Parse config (signals, capital, slippage, commission)
    # 3. Update status to 'running'
    # 4. Call run_backtest()
    # 5. Update StrategyResult with trade_log, equity_curve, metrics, status='completed'
    # 6. Publish event to bus
```

- [ ] **Step 5: Implement backtest router**

`app/backtesting/router.py` — APIRouter prefix `/api/v1/backtests`:
- `POST /` — parse CSV signals, create `StrategyResult` row with status='queued', enqueue ARQ task (or run synchronously in tests), return 201 with id
- `GET /` — list backtests for tenant (paginated)
- `GET /{id}` — get backtest detail (status, metrics, trade_log, equity_curve)
- `DELETE /{id}` — delete backtest result

- [ ] **Step 6: Wire router, run tests**

Run: `cd backend && pytest tests/test_backtesting.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/backtesting/ backend/tests/test_backtesting.py
git commit -m "feat: backtesting engine with CSV signal replay, metrics, and API"
```

---

## Task 16: Paper Trading Engine & API

**Files:**
- Create: `backend/app/paper_trading/__init__.py`
- Create: `backend/app/paper_trading/engine.py`
- Create: `backend/app/paper_trading/router.py`
- Create: `backend/tests/test_paper_trading.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_paper_trading.py
import pytest

@pytest.mark.asyncio
async def test_create_paper_session(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    strat = await client.post("/api/v1/strategies", json={
        "name": "paper-strat", "mode": "paper",
        "mapping_template": {"symbol": "$.ticker", "exchange": "NSE",
                             "action": "$.action", "quantity": "$.qty",
                             "order_type": "MARKET", "product_type": "INTRADAY"},
        "rules": {},
    }, headers=headers)
    strategy_id = strat.json()["id"]

    resp = await client.post("/api/v1/paper-trading/sessions", json={
        "strategy_id": strategy_id, "capital": 1000000
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["status"] == "active"
    assert float(resp.json()["current_balance"]) == 1000000

@pytest.mark.asyncio
async def test_webhook_executes_paper_trade(client):
    """Full pipeline: webhook → mapper → rules → paper trade execution."""
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Get webhook token
    config = await client.get("/api/v1/webhooks/config", headers=headers)
    webhook_token = config.json()["webhook_token"]

    # Create strategy
    strat = await client.post("/api/v1/strategies", json={
        "name": "paper-live", "mode": "paper",
        "mapping_template": {"symbol": "$.ticker", "exchange": "NSE",
                             "action": "$.action", "quantity": "$.qty",
                             "order_type": "MARKET", "product_type": "INTRADAY"},
        "rules": {},
    }, headers=headers)
    strategy_id = strat.json()["id"]

    # Start paper session
    session = await client.post("/api/v1/paper-trading/sessions", json={
        "strategy_id": strategy_id, "capital": 1000000
    }, headers=headers)
    session_id = session.json()["id"]

    # Send webhook
    await client.post(f"/api/v1/webhook/{webhook_token}", json={
        "ticker": "RELIANCE", "action": "buy", "qty": "10"
    })

    # Check session state
    state = await client.get(f"/api/v1/paper-trading/sessions/{session_id}", headers=headers)
    data = state.json()
    assert len(data["positions"]) >= 1
    assert data["positions"][0]["symbol"] == "RELIANCE"

@pytest.mark.asyncio
async def test_stop_paper_session(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    strat = await client.post("/api/v1/strategies", json={
        "name": "stop-test", "mode": "paper",
        "mapping_template": {"symbol": "$.s", "exchange": "NSE", "action": "$.a",
                             "quantity": "$.q", "order_type": "MARKET", "product_type": "INTRADAY"},
        "rules": {},
    }, headers=headers)

    session = await client.post("/api/v1/paper-trading/sessions", json={
        "strategy_id": strat.json()["id"], "capital": 500000
    }, headers=headers)
    session_id = session.json()["id"]

    resp = await client.post(f"/api/v1/paper-trading/sessions/{session_id}/stop", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "stopped"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_paper_trading.py -v`

- [ ] **Step 3: Implement paper trading engine**

`app/paper_trading/engine.py`:
- `async def execute_paper_trade(session: AsyncSession, paper_session_id, signal: StandardSignal)`:
  1. Load paper trading session from DB
  2. Get latest price from `historical_ohlcv` (or use signal price if provided)
  3. Apply slippage
  4. For BUY: check balance sufficient, create `PaperPosition`, create `PaperTrade`, deduct balance
  5. For SELL: find matching open position, close it, compute realized PnL, create `PaperTrade`, add to balance
  6. Update `paper_trading_sessions.current_balance`
  7. Publish event to bus

- [ ] **Step 4: Implement paper trading router**

`app/paper_trading/router.py` — APIRouter prefix `/api/v1/paper-trading`:
- `POST /sessions` — create session with initial capital, return 201
- `GET /sessions` — list sessions for tenant
- `GET /sessions/{id}` — return session with positions and recent trades
- `POST /sessions/{id}/stop` — set status to stopped, record stopped_at

- [ ] **Step 5: Wire webhook → paper trading**

In `app/webhooks/router.py`, after signal passes rules and strategy mode is "paper":
- Find active paper session for that strategy
- Call `execute_paper_trade(session, paper_session_id, signal)`
- Update `webhook_signals.execution_result` to "filled" or "failed"

- [ ] **Step 6: Wire router, run tests**

Run: `cd backend && pytest tests/test_paper_trading.py -v`
Expected: All 3 pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/paper_trading/ backend/tests/test_paper_trading.py
git commit -m "feat: paper trading engine with webhook integration and session management"
```

---

## Task 17: Analytics API

**Files:**
- Create: `backend/app/analytics/service.py`
- Create: `backend/app/analytics/router.py`
- Create: `backend/tests/test_analytics.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_analytics.py
import pytest

@pytest.mark.asyncio
async def test_overview_empty(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.get("/api/v1/analytics/overview", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_pnl"] == 0
    assert data["active_strategies"] == 0

@pytest.mark.asyncio
async def test_strategy_metrics_after_backtest(client):
    """Run a backtest, then verify metrics are available via analytics."""
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Create strategy + run backtest (reuse pattern from Task 15)
    strat = await client.post("/api/v1/strategies", json={
        "name": "analytics-test", "mode": "backtest",
        "mapping_template": {"symbol": "$.symbol", "exchange": "NSE",
                             "action": "$.action", "quantity": "$.quantity",
                             "order_type": "MARKET", "product_type": "INTRADAY"},
        "rules": {},
    }, headers=headers)
    strategy_id = strat.json()["id"]

    await client.post("/api/v1/backtests", json={
        "strategy_id": strategy_id,
        "start_date": "2025-01-01", "end_date": "2025-01-31",
        "capital": 1000000, "slippage_pct": 0, "commission_pct": 0,
        "signals_csv": "timestamp,symbol,action,quantity,order_type,price\n2025-01-02,RELIANCE,BUY,10,MARKET,2500\n2025-01-03,RELIANCE,SELL,10,MARKET,2600"
    }, headers=headers)

    resp = await client.get(f"/api/v1/analytics/strategies/{strategy_id}/metrics", headers=headers)
    assert resp.status_code == 200
    assert "total_return" in resp.json()

@pytest.mark.asyncio
async def test_trades_csv_export(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    strat = await client.post("/api/v1/strategies", json={
        "name": "csv-test", "mode": "backtest",
        "mapping_template": {"symbol": "$.symbol", "exchange": "NSE",
                             "action": "$.action", "quantity": "$.quantity",
                             "order_type": "MARKET", "product_type": "INTRADAY"},
        "rules": {},
    }, headers=headers)
    strategy_id = strat.json()["id"]

    await client.post("/api/v1/backtests", json={
        "strategy_id": strategy_id,
        "start_date": "2025-01-01", "end_date": "2025-01-31",
        "capital": 1000000, "slippage_pct": 0, "commission_pct": 0,
        "signals_csv": "timestamp,symbol,action,quantity,order_type,price\n2025-01-02,RELIANCE,BUY,10,MARKET,2500\n2025-01-03,RELIANCE,SELL,10,MARKET,2600"
    }, headers=headers)

    resp = await client.get(
        f"/api/v1/analytics/strategies/{strategy_id}/trades?format=csv",
        headers=headers
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_analytics.py -v`

- [ ] **Step 3: Implement analytics service**

`app/analytics/service.py`:
- `async def get_overview(session, tenant_id)` — aggregates: total PnL (sum across all results), active strategies count, open paper positions count, today's trade count
- `async def get_strategy_metrics(session, strategy_id)` — returns latest backtest or computed paper trade metrics
- `async def get_equity_curve(session, strategy_id)` — returns equity curve data from latest result
- `async def get_trades(session, strategy_id, format)` — returns trade log, optionally as CSV

- [ ] **Step 4: Implement analytics router**

`app/analytics/router.py` — APIRouter prefix `/api/v1/analytics`:
- `GET /overview` — calls `get_overview`, returns JSON
- `GET /strategies/{id}/metrics` — returns pre-computed metrics
- `GET /strategies/{id}/equity-curve` — returns equity curve array
- `GET /strategies/{id}/trades` — returns trade log; if `?format=csv`, returns `StreamingResponse` with CSV content-type

- [ ] **Step 5: Wire router, run tests**

Run: `cd backend && pytest tests/test_analytics.py -v`
Expected: All 3 pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/analytics/ backend/tests/test_analytics.py
git commit -m "feat: analytics API with overview, strategy metrics, equity curve, CSV export"
```

---

## Task 18: Health Check & ARQ Worker

**Files:**
- Create: `backend/worker.py`
- Create: `backend/tests/test_health.py`
- Modify: `backend/app/main.py` (enhance health endpoint)

- [ ] **Step 1: Write failing health check test**

```python
# tests/test_health.py
import pytest

@pytest.mark.asyncio
async def test_health_check(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "database" in data
    assert "redis" in data
    assert data["database"] == "ok"
    assert data["redis"] == "ok"
```

- [ ] **Step 2: Implement enhanced health check**

Update health endpoint in `main.py`:
```python
@app.get("/api/v1/health")
async def health():
    db_status = "ok"
    redis_status = "ok"
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    try:
        await redis_pool.ping()
    except Exception:
        redis_status = "error"
    status_code = 200 if db_status == "ok" and redis_status == "ok" else 503
    return JSONResponse(
        status_code=status_code,
        content={"database": db_status, "redis": redis_status}
    )
```

- [ ] **Step 3: Create ARQ worker entry point**

```python
# worker.py
from arq import cron
from arq.connections import RedisSettings
from app.config import settings
from app.backtesting.tasks import run_backtest_task
from app.historical.tasks import daily_data_fetch

class WorkerSettings:
    functions = [run_backtest_task]
    cron_jobs = [cron(daily_data_fetch, hour=6, minute=0)]  # 6 AM daily
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: Pass

- [ ] **Step 5: Commit**

```bash
git add backend/worker.py backend/tests/test_health.py backend/app/main.py
git commit -m "feat: health check endpoint (DB + Redis) and ARQ worker config"
```

---

## Task 19: Full Integration Test & Final Wiring

**Files:**
- Create: `backend/tests/test_integration.py`
- Modify: `backend/app/main.py` (ensure all routers wired)

- [ ] **Step 1: Write end-to-end integration test**

```python
# tests/test_integration.py
import pytest

@pytest.mark.asyncio
async def test_full_pipeline(client):
    """
    End-to-end: signup → create strategy → start paper session →
    send webhook → verify trade → check analytics
    """
    # 1. Signup
    tokens = (await client.post("/api/v1/auth/signup", json={
        "email": "e2e@test.com", "password": "securepass123"
    })).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # 2. Get webhook token
    config = (await client.get("/api/v1/webhooks/config", headers=headers)).json()
    webhook_token = config["webhook_token"]

    # 3. Create strategy
    strat = (await client.post("/api/v1/strategies", json={
        "name": "e2e-strategy", "mode": "paper",
        "mapping_template": {
            "symbol": "$.ticker", "exchange": "NSE",
            "action": "$.strategy.order_action",
            "quantity": "$.strategy.order_contracts",
            "order_type": "MARKET", "product_type": "INTRADAY",
        },
        "rules": {"symbol_whitelist": ["RELIANCE", "TCS"]},
    }, headers=headers)).json()

    # 4. Start paper trading session
    session = (await client.post("/api/v1/paper-trading/sessions", json={
        "strategy_id": strat["id"], "capital": 1000000
    }, headers=headers)).json()

    # 5. Send webhook (BUY)
    resp = await client.post(f"/api/v1/webhook/{webhook_token}", json={
        "ticker": "RELIANCE", "strategy": {"order_action": "buy", "order_contracts": "10"}
    })
    assert resp.status_code == 200

    # 6. Verify paper position created
    state = (await client.get(
        f"/api/v1/paper-trading/sessions/{session['id']}", headers=headers
    )).json()
    assert len(state["positions"]) == 1
    assert state["positions"][0]["symbol"] == "RELIANCE"

    # 7. Send webhook (SELL)
    await client.post(f"/api/v1/webhook/{webhook_token}", json={
        "ticker": "RELIANCE", "strategy": {"order_action": "sell", "order_contracts": "10"}
    })

    # 8. Verify position closed
    state = (await client.get(
        f"/api/v1/paper-trading/sessions/{session['id']}", headers=headers
    )).json()
    open_positions = [p for p in state["positions"] if p.get("closed_at") is None]
    assert len(open_positions) == 0

    # 9. Check signal log
    signals = (await client.get("/api/v1/webhooks/signals", headers=headers)).json()
    assert len(signals) == 2

    # 10. Check analytics overview
    overview = (await client.get("/api/v1/analytics/overview", headers=headers)).json()
    assert overview["active_strategies"] >= 1

    # 11. Verify RLS — second user sees nothing
    tokens_b = (await client.post("/api/v1/auth/signup", json={
        "email": "other@test.com", "password": "securepass123"
    })).json()
    headers_b = {"Authorization": f"Bearer {tokens_b['access_token']}"}
    strats_b = (await client.get("/api/v1/strategies", headers=headers_b)).json()
    assert len(strats_b) == 0
    signals_b = (await client.get("/api/v1/webhooks/signals", headers=headers_b)).json()
    assert len(signals_b) == 0
```

- [ ] **Step 2: Verify all routers are wired in main.py**

Ensure `main.py` includes:
```python
app.include_router(auth_router)
app.include_router(broker_router)
app.include_router(strategy_router)
app.include_router(webhook_router)
app.include_router(backtest_router)
app.include_router(paper_trading_router)
app.include_router(analytics_router)
```

- [ ] **Step 3: Run full test suite**

Run: `cd backend && pytest tests/ -v`
Expected: All tests across all test files pass

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_integration.py backend/app/main.py
git commit -m "feat: end-to-end integration test covering full webhook-to-analytics pipeline"
```

---

## Task 20: Docker Compose Finalization & Smoke Test

**Files:**
- Modify: `backend/docker-compose.yml` (finalize all services)
- Modify: `backend/Dockerfile` (production-ready)

- [ ] **Step 1: Finalize Dockerfile**

```dockerfile
FROM python:3.12-slim AS base
WORKDIR /app

FROM base AS deps
COPY pyproject.toml .
RUN pip install --no-cache-dir .

FROM deps AS app
COPY . .
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

- [ ] **Step 2: Finalize docker-compose.yml**

Ensure all 4 services defined (postgres, redis, api, worker) with proper health checks:
```yaml
postgres:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U algomatter"]
    interval: 5s
    retries: 5

redis:
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s
    retries: 5

api:
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
```

- [ ] **Step 3: Build and start all services**

Run: `cd backend && docker compose up --build -d`
Expected: All 4 services running and healthy

- [ ] **Step 4: Smoke test**

Run: `curl http://localhost:8000/api/v1/health`
Expected: `{"database": "ok", "redis": "ok"}`

Run: `curl -X POST http://localhost:8000/api/v1/auth/signup -H "Content-Type: application/json" -d '{"email":"smoke@test.com","password":"securepass123"}'`
Expected: 201 with tokens

- [ ] **Step 5: Commit**

```bash
git add backend/Dockerfile backend/docker-compose.yml
git commit -m "feat: production Docker Compose with health checks and migration on startup"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | Project scaffolding, Docker, config | Manual verification |
| 2 | DB models, Alembic migrations, RLS | Migration run |
| 3 | Encryption (HKDF + AES-256-GCM) | 4 unit tests |
| 4 | Auth (signup, login, refresh, JWT, RLS) | 8 integration tests |
| 5 | Logging + rate limiter middleware | 3 tests + manual verification |
| 6 | BrokerAdapter ABC + SimulatedBroker | 5 unit tests |
| 7 | Broker connections API | 4+ integration tests |
| 8 | Webhook JSONPath mapper | 4 unit tests |
| 9 | Signal processor rules engine | 8 unit tests |
| 10 | Strategies CRUD API | 5+ integration tests |
| 11 | Webhook receiver API | 5 integration tests |
| 12 | Event bus (Redis Streams) | 2 unit tests |
| 13 | Historical data service | 3 unit tests |
| 14 | Analytics metrics module | 3 unit tests |
| 15 | Backtesting engine + API | 2+ tests |
| 16 | Paper trading engine + API | 3 integration tests |
| 17 | Analytics API | 3 integration tests |
| 18 | Health check + ARQ worker | 1 test |
| 19 | Full integration test | 1 E2E test |
| 20 | Docker finalization + smoke test | Manual verification |

**Spec endpoint note:** `PUT /api/v1/webhooks/rules` from the spec is intentionally handled via `PUT /api/v1/strategies/{id}` (Task 10) — rules are a property of each strategy, not a global webhook setting.

**Total: ~64+ automated tests across 20 tasks**
