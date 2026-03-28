# Strategy Deployment & Backtesting — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hosted Python strategies with Nautilus-powered backtesting, cron-based live/paper execution, and a backtest→paper→live promotion pipeline.

**Architecture:** Hybrid approach — Nautilus Trader for backtesting, custom cron-based runner for live/paper. Dedicated strategy-runner Docker service with per-strategy subprocess isolation via nsjail. AlgoMatterStrategy wrapper simplifies the user-facing API.

**Tech Stack:** FastAPI, SQLAlchemy, Nautilus Trader, APScheduler 4, nsjail, ARQ, Monaco Editor (React), Next.js 14, Chakra UI

**Spec:** `docs/superpowers/specs/2026-03-28-strategy-deploy-backtest-design.md`

---

## File Structure

### Backend — New Files

```
backend/app/
├── hosted_strategies/
│   ├── __init__.py
│   ├── router.py              # CRUD for StrategyCode + versions + upload
│   ├── schemas.py             # Pydantic request/response models
│   └── templates.py           # Starter strategy templates (SMA, RSI, etc.)
├── deployments/
│   ├── __init__.py
│   ├── router.py              # Deployment CRUD + pause/resume/stop/promote
│   ├── schemas.py             # Deployment request/response models
│   └── service.py             # Promotion logic, validation, deployment limits
├── strategy_runner/
│   ├── __init__.py
│   ├── main.py                # Service entrypoint (scheduler + ARQ consumer)
│   ├── scheduler.py           # APScheduler cron management
│   ├── executor.py            # Subprocess spawning + nsjail wrapper
│   ├── tick_runner.py         # Live/paper tick: fetch candle → run subprocess → process orders
│   ├── backtest_runner.py     # Backtest: fetch history → run Nautilus subprocess → store results
│   ├── order_router.py        # Translate + dispatch orders to brokers/SimulatedBroker
│   └── health.py              # Health monitor, failure tracking, auto-pause
├── strategy_sdk/
│   ├── __init__.py            # Exports: AlgoMatterStrategy, Candle
│   ├── base.py                # AlgoMatterStrategy base class
│   ├── models.py              # Candle, Position, Portfolio, Order dataclasses
│   ├── sandbox.py             # Import allowlist enforcement
│   └── subprocess_entry.py    # Subprocess stdin→exec→stdout protocol handler
├── nautilus_integration/
│   ├── __init__.py
│   ├── adapter.py             # NautilusAdapter: translates AlgoMatterStrategy ↔ Nautilus Strategy
│   ├── instrument.py          # CryptoSpot instrument builder from symbol config
│   ├── data.py                # OHLCV → Nautilus Bar conversion
│   └── results.py             # Extract trade_log, equity_curve, metrics from engine
```

### Backend — Modified Files

```
backend/app/db/models.py           # Add StrategyCode, StrategyCodeVersion, StrategyDeployment,
                                   #     DeploymentState, DeploymentLog; modify StrategyResult
backend/app/main.py                # Register hosted_strategies + deployments routers
backend/pyproject.toml             # Add nautilus_trader, apscheduler
backend/docker-compose.yml         # Add strategy-runner service
backend/docker-compose.test.yml    # No changes needed (uses same test DB)
```

### Frontend — New Files

```
frontend/
├── app/(dashboard)/strategies/hosted/
│   ├── page.tsx                    # Hosted strategies list
│   ├── new/page.tsx                # New strategy with template picker
│   └── [id]/
│       ├── page.tsx                # Strategy editor (Monaco + config + results)
│       └── deployments/page.tsx    # Deployment timeline + cards
├── components/
│   ├── editor/
│   │   └── MonacoEditor.tsx        # Python Monaco editor wrapper
│   ├── deployments/
│   │   ├── DeploymentCard.tsx      # Mode badge + status + metrics
│   │   ├── DeploymentTimeline.tsx  # Backtest→Paper→Live visual flow
│   │   ├── MetricsComparison.tsx   # Side-by-side metrics for promotion
│   │   └── PromoteModal.tsx        # Confirm promotion with broker selection
│   └── shared/
│       ├── DeploymentBadge.tsx     # Mode × Status colored badge
│       └── LogViewer.tsx           # Paginated strategy log display
```

### Frontend — Modified Files

```
frontend/lib/api/types.ts           # Add hosted strategy + deployment types
frontend/lib/hooks/useApi.ts        # Add hooks for hosted strategies, deployments, templates
frontend/components/layout/Sidebar.tsx  # Split Strategies into Webhook / Hosted
frontend/app/(dashboard)/page.tsx       # Add Active Strategies section
```

---

## Phase 1: Backend Foundation

### Task 1: Database Models & Migration

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/app/db/migrations/versions/<auto>_add_hosted_strategy_models.py`

- [ ] **Step 1: Write the new SQLAlchemy models**

Add to `backend/app/db/models.py` after the existing `PaperTrade` model:

```python
class StrategyCode(Base):
    __tablename__ = "strategy_codes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    code: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    entrypoint: Mapped[str] = mapped_column(String(100), default="Strategy")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    versions: Mapped[list["StrategyCodeVersion"]] = relationship(back_populates="strategy_code", cascade="all, delete-orphan")
    deployments: Mapped[list["StrategyDeployment"]] = relationship(back_populates="strategy_code")


class StrategyCodeVersion(Base):
    __tablename__ = "strategy_code_versions"
    __table_args__ = (UniqueConstraint("strategy_code_id", "version", name="uq_code_version"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    strategy_code_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategy_codes.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    strategy_code: Mapped["StrategyCode"] = relationship(back_populates="versions")


class StrategyDeployment(Base):
    __tablename__ = "strategy_deployments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    strategy_code_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategy_codes.id"), index=True)
    strategy_code_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategy_code_versions.id"))
    mode: Mapped[str] = mapped_column(String(20))  # backtest, paper, live
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, paused, stopped, completed, failed
    symbol: Mapped[str] = mapped_column(String(20))
    exchange: Mapped[str] = mapped_column(String(20))
    product_type: Mapped[str] = mapped_column(String(20), default="DELIVERY")
    interval: Mapped[str] = mapped_column(String(10))
    broker_connection_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("broker_connections.id"), nullable=True)
    cron_expression: Mapped[str | None] = mapped_column(String(50), nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    promoted_from_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("strategy_deployments.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    strategy_code: Mapped["StrategyCode"] = relationship(back_populates="deployments")
    code_version: Mapped["StrategyCodeVersion"] = relationship()
    state: Mapped["DeploymentState | None"] = relationship(back_populates="deployment", uselist=False)


class DeploymentState(Base):
    __tablename__ = "deployment_states"

    deployment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategy_deployments.id"), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    position: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    open_orders: Mapped[list] = mapped_column(JSON, default=list)
    portfolio: Mapped[dict] = mapped_column(JSON, default=dict)
    user_state: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    deployment: Mapped["StrategyDeployment"] = relationship(back_populates="state")


class DeploymentLog(Base):
    __tablename__ = "deployment_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    deployment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategy_deployments.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    level: Mapped[str] = mapped_column(String(10), default="info")
    message: Mapped[str] = mapped_column(Text)
```

- [ ] **Step 2: Add nullable columns to existing StrategyResult model**

In the existing `StrategyResult` class in `models.py`, add:

```python
    deployment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("strategy_deployments.id"), nullable=True)
    strategy_code_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("strategy_code_versions.id"), nullable=True)
```

- [ ] **Step 3: Add missing imports to models.py**

Ensure these imports are at the top of `models.py` (add to existing import lines — `Text` is already imported, `relationship` must be added to the `sqlalchemy.orm` import):

```python
from sqlalchemy import UniqueConstraint, Integer  # add to existing sqlalchemy import
from sqlalchemy.orm import Mapped, mapped_column, relationship  # add relationship to existing orm import
```

- [ ] **Step 4: Generate and run migration**

```bash
cd backend && alembic revision --autogenerate -m "add hosted strategy models"
cd backend && alembic upgrade head
```

- [ ] **Step 4b: Add RLS policies for new tables**

Create a manual migration or add to the autogenerated migration. The new tenant-scoped tables need RLS policies matching the existing pattern. Add these SQL statements to the migration's `upgrade()` function:

```python
for table in ["strategy_codes", "strategy_code_versions", "strategy_deployments", "deployment_states", "deployment_logs"]:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY tenant_isolation ON {table}
        USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    """)
```

And in `downgrade()`:
```python
for table in ["strategy_codes", "strategy_code_versions", "strategy_deployments", "deployment_states", "deployment_logs"]:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
```

- [ ] **Step 5: Verify migration**

```bash
cd backend && python -c "from app.db.models import StrategyCode, StrategyCodeVersion, StrategyDeployment, DeploymentState, DeploymentLog; print('Models imported OK')"
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/models.py backend/app/db/migrations/versions/
git commit -m "feat: add hosted strategy database models and migration"
```

---

### Task 2: AlgoMatterStrategy SDK

**Files:**
- Create: `backend/app/strategy_sdk/__init__.py`
- Create: `backend/app/strategy_sdk/models.py`
- Create: `backend/app/strategy_sdk/base.py`
- Test: `backend/tests/test_strategy_sdk.py`

- [ ] **Step 1: Write failing tests for the SDK**

Create `backend/tests/test_strategy_sdk.py`:

```python
import pytest
from app.strategy_sdk import AlgoMatterStrategy, Candle
from app.strategy_sdk.models import Position, Portfolio, PendingOrder


class SMAStrategy(AlgoMatterStrategy):
    def on_init(self):
        self.state.setdefault("prices", [])

    def on_candle(self, candle: Candle):
        self.state["prices"].append(candle.close)
        period = self.params.get("sma_period", 3)
        if len(self.state["prices"]) >= period:
            sma = sum(self.state["prices"][-period:]) / period
            if candle.close > sma and not self.position:
                self.buy(quantity=1)
            elif candle.close < sma and self.position:
                self.sell(quantity=1)

    def on_order_update(self, order_id, status, fill_price, fill_quantity):
        self.log(f"Order {order_id} {status}")


def make_candle(close, ts="2026-01-01T00:00:00Z"):
    from datetime import datetime
    return Candle(
        timestamp=datetime.fromisoformat(ts.replace("Z", "+00:00")),
        open=close, high=close + 1, low=close - 1, close=close, volume=100
    )


class TestAlgoMatterStrategy:
    def test_instantiation_with_params(self):
        s = SMAStrategy(params={"sma_period": 5})
        assert s.params["sma_period"] == 5

    def test_on_init_called(self):
        s = SMAStrategy(params={})
        s.on_init()
        assert s.state == {"prices": []}

    def test_buy_returns_order_id(self):
        s = SMAStrategy(params={}, portfolio=Portfolio(balance=10000, equity=10000, available_margin=10000))
        oid = s.buy(quantity=1)
        assert isinstance(oid, str)
        assert len(s._pending_orders) == 1

    def test_sell_returns_order_id(self):
        s = SMAStrategy(
            params={},
            position=Position(quantity=1, avg_entry_price=100, unrealized_pnl=0),
            portfolio=Portfolio(balance=10000, equity=10000, available_margin=10000),
        )
        oid = s.sell(quantity=1)
        assert isinstance(oid, str)
        assert len(s._pending_orders) == 1

    def test_cancel_order(self):
        s = SMAStrategy(params={}, portfolio=Portfolio(balance=10000, equity=10000, available_margin=10000))
        oid = s.buy(quantity=1)
        s.cancel_order(oid)
        assert oid in s._cancelled_orders

    def test_limit_order(self):
        s = SMAStrategy(params={}, portfolio=Portfolio(balance=10000, equity=10000, available_margin=10000))
        oid = s.buy(quantity=1, order_type="limit", price=99.5)
        order = s._pending_orders[0]
        assert order["order_type"] == "limit"
        assert order["price"] == 99.5

    def test_stop_order(self):
        s = SMAStrategy(
            params={},
            position=Position(quantity=1, avg_entry_price=100, unrealized_pnl=0),
            portfolio=Portfolio(balance=10000, equity=10000, available_margin=10000),
        )
        oid = s.sell(quantity=1, order_type="stop", trigger_price=95.0)
        order = s._pending_orders[0]
        assert order["order_type"] == "stop"
        assert order["trigger_price"] == 95.0

    def test_history_returns_candles(self):
        candles = [make_candle(100 + i) for i in range(5)]
        s = SMAStrategy(params={}, history=candles)
        assert len(s.history(3)) == 3
        assert s.history(3)[-1].close == 104

    def test_log_captures_messages(self):
        s = SMAStrategy(params={})
        s.log("test message")
        s.log("warning", level="warn")
        assert len(s._logs) == 2
        assert s._logs[0] == {"level": "info", "message": "test message"}

    def test_on_candle_generates_orders(self):
        s = SMAStrategy(
            params={"sma_period": 3},
            portfolio=Portfolio(balance=10000, equity=10000, available_margin=10000),
        )
        s.on_init()
        for price in [100, 101, 102, 105]:  # 105 > sma(101,102,105)=102.67 → buy
            s.on_candle(make_candle(price))
        assert len(s._pending_orders) == 1
        assert s._pending_orders[0]["action"] == "buy"

    def test_collect_output(self):
        s = SMAStrategy(
            params={},
            portfolio=Portfolio(balance=10000, equity=10000, available_margin=10000),
        )
        s.on_init()
        s.buy(quantity=1)
        s.log("hello")
        output = s.collect_output()
        assert "orders" in output
        assert "state" in output
        assert "logs" in output
        assert output["error"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_strategy_sdk.py -v
```

Expected: FAIL — modules don't exist yet.

- [ ] **Step 3: Implement SDK models**

Create `backend/app/strategy_sdk/__init__.py`:

```python
from app.strategy_sdk.base import AlgoMatterStrategy
from app.strategy_sdk.models import Candle

__all__ = ["AlgoMatterStrategy", "Candle"]
```

Create `backend/app/strategy_sdk/models.py`:

```python
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Position:
    quantity: float
    avg_entry_price: float
    unrealized_pnl: float


@dataclass
class Portfolio:
    balance: float
    equity: float
    available_margin: float


@dataclass
class PendingOrder:
    id: str
    action: str
    quantity: float
    order_type: str
    price: float | None = None
    trigger_price: float | None = None
    age_candles: int = 0
```

- [ ] **Step 4: Implement AlgoMatterStrategy base class**

Create `backend/app/strategy_sdk/base.py`:

```python
import uuid
from app.strategy_sdk.models import Candle, Position, Portfolio, PendingOrder


class AlgoMatterStrategy:
    def __init__(
        self,
        params: dict | None = None,
        state: dict | None = None,
        position: Position | None = None,
        portfolio: Portfolio | None = None,
        open_orders: list[PendingOrder] | None = None,
        history: list[Candle] | None = None,
    ):
        self.params: dict = params or {}
        self.state: dict = state if state is not None else {}
        self._position: Position | None = position
        self._portfolio: Portfolio = portfolio or Portfolio(balance=0, equity=0, available_margin=0)
        self._open_orders: list[PendingOrder] = open_orders or []
        self._history: list[Candle] = history or []
        self._pending_orders: list[dict] = []
        self._cancelled_orders: list[str] = []
        self._logs: list[dict] = []
        self.nautilus_strategy = None

    @property
    def position(self) -> Position | None:
        return self._position

    @property
    def portfolio(self) -> Portfolio:
        return self._portfolio

    @property
    def open_orders(self) -> list[PendingOrder]:
        return self._open_orders

    def history(self, periods: int | None = None) -> list[Candle]:
        if periods is None:
            return list(self._history)
        return list(self._history[-periods:])

    def buy(
        self,
        quantity: float,
        order_type: str = "market",
        price: float | None = None,
        trigger_price: float | None = None,
    ) -> str:
        order_id = str(uuid.uuid4())
        self._pending_orders.append({
            "id": order_id,
            "action": "buy",
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
            "trigger_price": trigger_price,
        })
        return order_id

    def sell(
        self,
        quantity: float,
        order_type: str = "market",
        price: float | None = None,
        trigger_price: float | None = None,
    ) -> str:
        order_id = str(uuid.uuid4())
        self._pending_orders.append({
            "id": order_id,
            "action": "sell",
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
            "trigger_price": trigger_price,
        })
        return order_id

    def cancel_order(self, order_id: str) -> None:
        self._cancelled_orders.append(order_id)

    def log(self, message: str, level: str = "info") -> None:
        self._logs.append({"level": level, "message": message})

    def on_init(self) -> None:
        pass

    def on_candle(self, candle: Candle) -> None:
        pass

    def on_order_update(self, order_id: str, status: str, fill_price: float | None, fill_quantity: float | None) -> None:
        pass

    def on_stop(self) -> None:
        pass

    def collect_output(self) -> dict:
        return {
            "orders": self._pending_orders,
            "cancelled_orders": self._cancelled_orders,
            "state": {"user_state": self.state},
            "logs": self._logs,
            "error": None,
        }
```

- [ ] **Step 5: Run tests**

```bash
cd backend && python -m pytest tests/test_strategy_sdk.py -v
```

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/strategy_sdk/ backend/tests/test_strategy_sdk.py
git commit -m "feat: implement AlgoMatterStrategy SDK with Candle, Position, Portfolio models"
```

---

### Task 3: Subprocess Entry Point & Sandbox

**Files:**
- Create: `backend/app/strategy_sdk/sandbox.py`
- Create: `backend/app/strategy_sdk/subprocess_entry.py`
- Test: `backend/tests/test_subprocess_entry.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_subprocess_entry.py`:

```python
import json
import pytest
from app.strategy_sdk.subprocess_entry import run_tick, run_from_stdin_payload
from app.strategy_sdk.sandbox import SafeImporter


class TestSafeImporter:
    def test_allows_math(self):
        importer = SafeImporter()
        mod = importer("math")
        assert hasattr(mod, "sqrt")

    def test_allows_datetime(self):
        importer = SafeImporter()
        mod = importer("datetime")
        assert hasattr(mod, "datetime")

    def test_blocks_os(self):
        importer = SafeImporter()
        with pytest.raises(ImportError, match="not allowed"):
            importer("os")

    def test_blocks_subprocess(self):
        importer = SafeImporter()
        with pytest.raises(ImportError, match="not allowed"):
            importer("subprocess")

    def test_blocks_socket(self):
        importer = SafeImporter()
        with pytest.raises(ImportError, match="not allowed"):
            importer("socket")


class TestRunTick:
    def test_basic_strategy_execution(self):
        code = '''
class Strategy(AlgoMatterStrategy):
    def on_init(self):
        self.state.setdefault("count", 0)

    def on_candle(self, candle):
        self.state["count"] += 1
        if candle.close > 100:
            self.buy(quantity=1)
        self.log(f"Processed candle {self.state['count']}")
'''
        payload = {
            "code": code,
            "entrypoint": "Strategy",
            "candle": {"timestamp": "2026-01-01T00:00:00Z", "open": 105, "high": 106, "low": 104, "close": 105, "volume": 1000},
            "history": [],
            "state": {"position": None, "open_orders": [], "portfolio": {"balance": 10000, "equity": 10000, "available_margin": 10000}, "user_state": {}},
            "order_updates": [],
            "params": {},
            "mode": "paper",
        }
        result = run_tick(payload)
        assert result["error"] is None
        assert len(result["orders"]) == 1
        assert result["orders"][0]["action"] == "buy"
        assert result["state"]["user_state"]["count"] == 1
        assert len(result["logs"]) == 1

    def test_syntax_error_in_code(self):
        payload = {
            "code": "class Strategy(AlgoMatterStrategy):\n    def on_candle(self, candle)\n        pass",
            "entrypoint": "Strategy",
            "candle": {"timestamp": "2026-01-01T00:00:00Z", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 100},
            "history": [],
            "state": {"position": None, "open_orders": [], "portfolio": {"balance": 10000, "equity": 10000, "available_margin": 10000}, "user_state": {}},
            "order_updates": [],
            "params": {},
            "mode": "paper",
        }
        result = run_tick(payload)
        assert result["error"] is not None
        assert result["error"]["type"] == "syntax"

    def test_runtime_error_in_code(self):
        code = '''
class Strategy(AlgoMatterStrategy):
    def on_candle(self, candle):
        x = 1 / 0
'''
        payload = {
            "code": code,
            "entrypoint": "Strategy",
            "candle": {"timestamp": "2026-01-01T00:00:00Z", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 100},
            "history": [],
            "state": {"position": None, "open_orders": [], "portfolio": {"balance": 10000, "equity": 10000, "available_margin": 10000}, "user_state": {}},
            "order_updates": [],
            "params": {},
            "mode": "paper",
        }
        result = run_tick(payload)
        assert result["error"] is not None
        assert result["error"]["type"] == "runtime"
        assert "ZeroDivisionError" in result["error"]["message"]

    def test_order_updates_trigger_callback(self):
        code = '''
class Strategy(AlgoMatterStrategy):
    def on_order_update(self, order_id, status, fill_price, fill_quantity):
        self.log(f"Order {order_id} was {status}")

    def on_candle(self, candle):
        pass
'''
        payload = {
            "code": code,
            "entrypoint": "Strategy",
            "candle": {"timestamp": "2026-01-01T00:00:00Z", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 100},
            "history": [],
            "state": {"position": None, "open_orders": [], "portfolio": {"balance": 10000, "equity": 10000, "available_margin": 10000}, "user_state": {}},
            "order_updates": [{"order_id": "abc-123", "status": "filled", "fill_price": 100.5, "fill_quantity": 1}],
            "params": {},
            "mode": "paper",
        }
        result = run_tick(payload)
        assert result["error"] is None
        assert len(result["logs"]) == 1
        assert "filled" in result["logs"][0]["message"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_subprocess_entry.py -v
```

- [ ] **Step 3: Implement sandbox.py**

Create `backend/app/strategy_sdk/sandbox.py`:

```python
import importlib

ALLOWED_MODULES = {
    "math", "statistics", "datetime", "collections", "itertools",
    "functools", "decimal", "json", "dataclasses", "typing",
    "enum", "abc", "copy", "operator", "bisect", "heapq", "random",
    # Third-party (pre-installed)
    "numpy", "pandas", "ta", "pandas_ta",
}

BLOCKED_MODULES = {
    "os", "sys", "subprocess", "socket", "http", "urllib", "requests",
    "ctypes", "importlib", "pickle", "shelve", "multiprocessing",
    "threading", "signal", "shutil", "pathlib", "io", "builtins",
}


class SafeImporter:
    def __call__(self, name: str, *args, **kwargs):
        top_level = name.split(".")[0]
        if top_level in BLOCKED_MODULES:
            raise ImportError(f"Module '{name}' is not allowed in strategy code")
        if top_level in ALLOWED_MODULES or top_level.startswith("app.strategy_sdk"):
            return importlib.import_module(name)
        raise ImportError(f"Module '{name}' is not allowed in strategy code")
```

- [ ] **Step 4: Implement subprocess_entry.py**

Create `backend/app/strategy_sdk/subprocess_entry.py`:

```python
import ast
import json
import sys
import traceback
from datetime import datetime, timezone

from app.strategy_sdk.base import AlgoMatterStrategy
from app.strategy_sdk.models import Candle, Position, Portfolio, PendingOrder


def _parse_candle(data: dict) -> Candle:
    ts = data["timestamp"]
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return Candle(
        timestamp=ts,
        open=float(data["open"]),
        high=float(data["high"]),
        low=float(data["low"]),
        close=float(data["close"]),
        volume=float(data["volume"]),
    )


def _restore_state(state: dict) -> tuple[Position | None, list[PendingOrder], Portfolio, dict]:
    position = None
    if state.get("position"):
        p = state["position"]
        position = Position(
            quantity=float(p["quantity"]),
            avg_entry_price=float(p["avg_entry_price"]),
            unrealized_pnl=float(p.get("unrealized_pnl", 0)),
        )

    open_orders = []
    for o in state.get("open_orders", []):
        open_orders.append(PendingOrder(
            id=o["id"], action=o["action"], quantity=float(o["quantity"]),
            order_type=o["order_type"], price=o.get("price"),
            trigger_price=o.get("trigger_price"), age_candles=o.get("age_candles", 0),
        ))

    pf = state.get("portfolio", {})
    portfolio = Portfolio(
        balance=float(pf.get("balance", 0)),
        equity=float(pf.get("equity", 0)),
        available_margin=float(pf.get("available_margin", 0)),
    )

    user_state = state.get("user_state", {})
    return position, open_orders, portfolio, user_state


def run_tick(payload: dict) -> dict:
    code = payload["code"]
    entrypoint = payload.get("entrypoint", "Strategy")

    # Parse code — catch syntax errors
    try:
        ast.parse(code)
    except SyntaxError as e:
        return {
            "orders": [], "cancelled_orders": [], "state": {"user_state": {}},
            "logs": [],
            "error": {"type": "syntax", "message": str(e), "traceback": ""},
        }

    # Restore state
    position, open_orders, portfolio, user_state = _restore_state(payload.get("state", {}))
    history = [_parse_candle(c) for c in payload.get("history", [])]
    candle = _parse_candle(payload["candle"])
    params = payload.get("params", {})

    # Execute user code in sandboxed namespace
    try:
        from app.strategy_sdk.sandbox import SafeImporter
        from app.strategy_sdk import models as sdk_models
        safe_builtins = {**__builtins__.__dict__, "__import__": SafeImporter()} if isinstance(__builtins__, dict) else {**vars(__builtins__), "__import__": SafeImporter()}
        # Create a fake 'strategy_sdk' module so `from strategy_sdk import ...` works
        import types
        strategy_sdk_module = types.ModuleType("strategy_sdk")
        strategy_sdk_module.AlgoMatterStrategy = AlgoMatterStrategy
        strategy_sdk_module.Candle = Candle
        import sys as _sys
        _sys.modules["strategy_sdk"] = strategy_sdk_module

        namespace = {
            "__builtins__": safe_builtins,
            "AlgoMatterStrategy": AlgoMatterStrategy,
            "Candle": Candle,
        }
        exec(code, namespace)

        strategy_cls = namespace.get(entrypoint)
        if strategy_cls is None:
            return {
                "orders": [], "cancelled_orders": [], "state": {"user_state": user_state},
                "logs": [],
                "error": {"type": "runtime", "message": f"Class '{entrypoint}' not found in strategy code", "traceback": ""},
            }

        strategy = strategy_cls(
            params=params,
            state=user_state,
            position=position,
            portfolio=portfolio,
            open_orders=open_orders,
            history=history,
        )

        strategy.on_init()

        # Process order updates before candle
        for update in payload.get("order_updates", []):
            strategy.on_order_update(
                order_id=update["order_id"],
                status=update["status"],
                fill_price=update.get("fill_price"),
                fill_quantity=update.get("fill_quantity"),
            )

        strategy.on_candle(candle)
        return strategy.collect_output()

    except Exception as e:
        tb = traceback.format_exc()
        return {
            "orders": [], "cancelled_orders": [],
            "state": {"user_state": user_state},
            "logs": [],
            "error": {"type": "runtime", "message": f"{type(e).__name__}: {e}", "traceback": tb},
        }


def run_from_stdin_payload():
    """Entry point for subprocess: read JSON from stdin, write result to stdout."""
    payload = json.loads(sys.stdin.read())
    result = run_tick(payload)
    sys.stdout.write(json.dumps(result))
    sys.stdout.flush()


if __name__ == "__main__":
    run_from_stdin_payload()
```

- [ ] **Step 5: Run tests**

```bash
cd backend && python -m pytest tests/test_subprocess_entry.py -v
```

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/strategy_sdk/sandbox.py backend/app/strategy_sdk/subprocess_entry.py backend/tests/test_subprocess_entry.py
git commit -m "feat: implement subprocess entry point and import sandbox for strategy execution"
```

---

### Task 4: Hosted Strategy CRUD API

**Files:**
- Create: `backend/app/hosted_strategies/__init__.py`
- Create: `backend/app/hosted_strategies/schemas.py`
- Create: `backend/app/hosted_strategies/router.py`
- Create: `backend/app/hosted_strategies/templates.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_hosted_strategies_router.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_hosted_strategies_router.py`. **IMPORTANT:** Use the existing `conftest.py` fixtures (`client`, `db_session`, `create_authenticated_user`) that handle test DB setup, RLS activation, and JWT auth. Do NOT use `dependency_overrides` — follow the existing test patterns in the codebase.

```python
import pytest


@pytest.mark.asyncio
class TestHostedStrategiesRouter:
    async def test_create_strategy(self, client, auth_headers):
        resp = await client.post("/api/v1/hosted-strategies", json={
            "name": "Test SMA",
            "code": "class Strategy(AlgoMatterStrategy):\n    def on_candle(self, candle): pass",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test SMA"
        assert data["version"] == 1

    async def test_list_strategies(self, client, auth_headers):
        resp = await client.get("/api/v1/hosted-strategies", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_templates(self, client):
        resp = await client.get("/api/v1/strategy-templates")
        assert resp.status_code == 200
        templates = resp.json()
        assert len(templates) >= 4
        assert any(t["name"] == "SMA Crossover" for t in templates)
```

**Note:** The `client` and `auth_headers` fixtures come from the existing `conftest.py`. If these fixture names differ, check `backend/tests/conftest.py` and adapt. The key requirement is using the test database with proper table creation and RLS policies.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_hosted_strategies_router.py -v
```

- [ ] **Step 3: Implement schemas**

Create `backend/app/hosted_strategies/__init__.py` (empty file).

Create `backend/app/hosted_strategies/schemas.py`:

```python
from pydantic import BaseModel, Field


class CreateStrategyRequest(BaseModel):
    name: str = Field(max_length=255)
    description: str | None = None
    code: str
    entrypoint: str = "Strategy"


class UpdateStrategyRequest(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    code: str | None = None
    entrypoint: str | None = None


class StrategyResponse(BaseModel):
    id: str
    name: str
    description: str | None
    code: str
    version: int
    entrypoint: str
    created_at: str
    updated_at: str


class StrategyVersionResponse(BaseModel):
    id: str
    version: int
    code: str
    created_at: str


class TemplateResponse(BaseModel):
    name: str
    description: str
    code: str
    params: dict
```

- [ ] **Step 4: Implement templates**

Create `backend/app/hosted_strategies/templates.py`:

```python
TEMPLATES = [
    {
        "name": "SMA Crossover",
        "description": "Buy when price crosses above SMA, sell when below.",
        "params": {"sma_period": 20},
        "code": '''from strategy_sdk import AlgoMatterStrategy, Candle


class Strategy(AlgoMatterStrategy):
    """Simple Moving Average Crossover Strategy.

    Buys when price crosses above the SMA, sells when it crosses below.
    Params: sma_period (default 20)
    """

    def on_init(self):
        self.state.setdefault("prices", [])

    def on_candle(self, candle: Candle):
        self.state["prices"].append(candle.close)
        period = self.params.get("sma_period", 20)

        if len(self.state["prices"]) < period:
            return

        sma = sum(self.state["prices"][-period:]) / period

        if candle.close > sma and not self.position:
            self.buy(quantity=1)
            self.log(f"BUY signal: price {candle.close:.2f} > SMA {sma:.2f}")
        elif candle.close < sma and self.position:
            self.sell(quantity=self.position.quantity)
            self.log(f"SELL signal: price {candle.close:.2f} < SMA {sma:.2f}")
''',
    },
    {
        "name": "RSI Mean Reversion",
        "description": "Buy when RSI < oversold, sell when RSI > overbought.",
        "params": {"rsi_period": 14, "oversold": 30, "overbought": 70},
        "code": '''from strategy_sdk import AlgoMatterStrategy, Candle


class Strategy(AlgoMatterStrategy):
    """RSI Mean Reversion Strategy.

    Buys when RSI drops below oversold threshold, sells when above overbought.
    Params: rsi_period (14), oversold (30), overbought (70)
    """

    def on_init(self):
        self.state.setdefault("prices", [])

    def on_candle(self, candle: Candle):
        self.state["prices"].append(candle.close)
        period = self.params.get("rsi_period", 14)

        if len(self.state["prices"]) < period + 1:
            return

        # Compute RSI
        prices = self.state["prices"][-(period + 1):]
        deltas = [prices[i + 1] - prices[i] for i in range(len(prices) - 1)]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0.001
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        oversold = self.params.get("oversold", 30)
        overbought = self.params.get("overbought", 70)

        if rsi < oversold and not self.position:
            self.buy(quantity=1)
            self.log(f"BUY: RSI {rsi:.1f} < {oversold}")
        elif rsi > overbought and self.position:
            self.sell(quantity=self.position.quantity)
            self.log(f"SELL: RSI {rsi:.1f} > {overbought}")
''',
    },
    {
        "name": "MACD Momentum",
        "description": "Buy on MACD line crossing above signal, sell on cross below.",
        "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
        "code": '''from strategy_sdk import AlgoMatterStrategy, Candle


class Strategy(AlgoMatterStrategy):
    """MACD Momentum Strategy.

    Uses MACD line crossover with signal line for entry/exit.
    Params: fast_period (12), slow_period (26), signal_period (9)
    """

    def on_init(self):
        self.state.setdefault("prices", [])
        self.state.setdefault("prev_histogram", None)

    def on_candle(self, candle: Candle):
        self.state["prices"].append(candle.close)
        fast = self.params.get("fast_period", 12)
        slow = self.params.get("slow_period", 26)
        sig = self.params.get("signal_period", 9)

        if len(self.state["prices"]) < slow + sig:
            return

        prices = self.state["prices"]

        def ema(data, period):
            k = 2 / (period + 1)
            result = [data[0]]
            for price in data[1:]:
                result.append(price * k + result[-1] * (1 - k))
            return result

        fast_ema = ema(prices, fast)
        slow_ema = ema(prices, slow)
        macd_line = [f - s for f, s in zip(fast_ema, slow_ema)]
        signal_line = ema(macd_line, sig)
        histogram = macd_line[-1] - signal_line[-1]

        prev = self.state["prev_histogram"]
        self.state["prev_histogram"] = histogram

        if prev is not None:
            if prev <= 0 < histogram and not self.position:
                self.buy(quantity=1)
                self.log("BUY: MACD crossed above signal")
            elif prev >= 0 > histogram and self.position:
                self.sell(quantity=self.position.quantity)
                self.log("SELL: MACD crossed below signal")
''',
    },
    {
        "name": "Bollinger Band Breakout",
        "description": "Buy on upper band breakout, sell on lower band break.",
        "params": {"bb_period": 20, "bb_std": 2.0},
        "code": '''from strategy_sdk import AlgoMatterStrategy, Candle
import math


class Strategy(AlgoMatterStrategy):
    """Bollinger Band Breakout Strategy.

    Buys when price breaks above upper band, sells below lower band.
    Params: bb_period (20), bb_std (2.0)
    """

    def on_init(self):
        self.state.setdefault("prices", [])

    def on_candle(self, candle: Candle):
        self.state["prices"].append(candle.close)
        period = self.params.get("bb_period", 20)
        num_std = self.params.get("bb_std", 2.0)

        if len(self.state["prices"]) < period:
            return

        window = self.state["prices"][-period:]
        sma = sum(window) / period
        variance = sum((p - sma) ** 2 for p in window) / period
        std = math.sqrt(variance)
        upper = sma + num_std * std
        lower = sma - num_std * std

        if candle.close > upper and not self.position:
            self.buy(quantity=1)
            self.log(f"BUY: price {candle.close:.2f} > upper band {upper:.2f}")
        elif candle.close < lower and self.position:
            self.sell(quantity=self.position.quantity)
            self.log(f"SELL: price {candle.close:.2f} < lower band {lower:.2f}")
''',
    },
    {
        "name": "Blank Template",
        "description": "Minimal skeleton to build your own strategy.",
        "params": {},
        "code": '''from strategy_sdk import AlgoMatterStrategy, Candle


class Strategy(AlgoMatterStrategy):
    """Your strategy description here."""

    def on_init(self):
        # Initialize state that persists between ticks
        # Use self.state (dict) for persistence, not instance variables
        pass

    def on_candle(self, candle: Candle):
        # Called on each new candle
        # candle.timestamp, candle.open, candle.high, candle.low, candle.close, candle.volume
        #
        # Available methods:
        #   self.buy(quantity, order_type="market", price=None, trigger_price=None)
        #   self.sell(quantity, order_type="market", price=None, trigger_price=None)
        #   self.cancel_order(order_id)
        #   self.log(message, level="info")
        #   self.history(periods=N) -> list[Candle]
        #
        # Available properties:
        #   self.position -> Position or None (quantity, avg_entry_price, unrealized_pnl)
        #   self.portfolio -> Portfolio (balance, equity, available_margin)
        #   self.open_orders -> list[PendingOrder]
        #   self.params -> dict (user-configurable parameters)
        #   self.state -> dict (persistent state between ticks)
        pass

    def on_order_update(self, order_id, status, fill_price, fill_quantity):
        # Optional: called when an order fills, cancels, or is rejected
        pass
''',
    },
]
```

- [ ] **Step 5: Implement router**

Create `backend/app/hosted_strategies/router.py`:

```python
import ast
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_tenant_session
from app.db.models import StrategyCode, StrategyCodeVersion
from app.hosted_strategies.schemas import (
    CreateStrategyRequest, UpdateStrategyRequest,
    StrategyResponse, StrategyVersionResponse, TemplateResponse,
)
from app.hosted_strategies.templates import TEMPLATES

router = APIRouter(prefix="/api/v1/hosted-strategies", tags=["hosted-strategies"])
template_router = APIRouter(prefix="/api/v1/strategy-templates", tags=["templates"])


def _to_response(sc: StrategyCode) -> StrategyResponse:
    return StrategyResponse(
        id=str(sc.id),
        name=sc.name,
        description=sc.description,
        code=sc.code,
        version=sc.version,
        entrypoint=sc.entrypoint,
        created_at=sc.created_at.isoformat(),
        updated_at=sc.updated_at.isoformat(),
    )


def _create_version(sc: StrategyCode) -> StrategyCodeVersion:
    return StrategyCodeVersion(
        id=uuid.uuid4(),
        tenant_id=sc.tenant_id,
        strategy_code_id=sc.id,
        version=sc.version,
        code=sc.code,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=StrategyResponse)
async def create_strategy(
    body: CreateStrategyRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    sc = StrategyCode(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(current_user["user_id"]),
        name=body.name,
        description=body.description,
        code=body.code,
        version=1,
        entrypoint=body.entrypoint,
    )
    session.add(sc)
    session.add(_create_version(sc))
    await session.commit()
    await session.refresh(sc)
    return _to_response(sc)


@router.get("", response_model=list[StrategyResponse])
async def list_strategies(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    result = await session.execute(
        select(StrategyCode)
        .where(StrategyCode.tenant_id == uuid.UUID(current_user["user_id"]))
        .order_by(StrategyCode.updated_at.desc())
    )
    return [_to_response(sc) for sc in result.scalars().all()]


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    sc = await session.get(StrategyCode, strategy_id)
    if not sc or sc.tenant_id != uuid.UUID(current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Strategy not found")
    return _to_response(sc)


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: uuid.UUID,
    body: UpdateStrategyRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    sc = await session.get(StrategyCode, strategy_id)
    if not sc or sc.tenant_id != uuid.UUID(current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Strategy not found")

    updates = body.model_dump(exclude_unset=True)
    code_changed = "code" in updates and updates["code"] != sc.code

    for field, value in updates.items():
        setattr(sc, field, value)

    if code_changed:
        sc.version += 1
        session.add(_create_version(sc))

    await session.commit()
    await session.refresh(sc)
    return _to_response(sc)


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    strategy_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    sc = await session.get(StrategyCode, strategy_id)
    if not sc or sc.tenant_id != uuid.UUID(current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Strategy not found")
    await session.delete(sc)
    await session.commit()


@router.post("/{strategy_id}/upload", response_model=StrategyResponse)
async def upload_strategy_file(
    strategy_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    sc = await session.get(StrategyCode, strategy_id)
    if not sc or sc.tenant_id != uuid.UUID(current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Strategy not found")

    content = await file.read()
    if len(content) > 100_000:
        raise HTTPException(status_code=400, detail="File too large (max 100KB)")

    code = content.decode("utf-8")
    try:
        ast.parse(code)
    except SyntaxError as e:
        raise HTTPException(status_code=422, detail=f"Invalid Python: {e}")

    sc.code = code
    sc.version += 1
    session.add(_create_version(sc))
    await session.commit()
    await session.refresh(sc)
    return _to_response(sc)


@router.get("/{strategy_id}/versions", response_model=list[StrategyVersionResponse])
async def list_versions(
    strategy_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    result = await session.execute(
        select(StrategyCodeVersion)
        .where(
            StrategyCodeVersion.strategy_code_id == strategy_id,
            StrategyCodeVersion.tenant_id == uuid.UUID(current_user["user_id"]),
        )
        .order_by(StrategyCodeVersion.version.desc())
    )
    return [
        StrategyVersionResponse(
            id=str(v.id), version=v.version, code=v.code, created_at=v.created_at.isoformat()
        )
        for v in result.scalars().all()
    ]


@router.get("/{strategy_id}/versions/{version}", response_model=StrategyVersionResponse)
async def get_version(
    strategy_id: uuid.UUID,
    version: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    result = await session.execute(
        select(StrategyCodeVersion).where(
            StrategyCodeVersion.strategy_code_id == strategy_id,
            StrategyCodeVersion.version == version,
            StrategyCodeVersion.tenant_id == uuid.UUID(current_user["user_id"]),
        )
    )
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    return StrategyVersionResponse(
        id=str(v.id), version=v.version, code=v.code, created_at=v.created_at.isoformat()
    )


@router.post("/{strategy_id}/versions/{version}/restore", response_model=StrategyResponse)
async def restore_version(
    strategy_id: uuid.UUID,
    version: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    sc = await session.get(StrategyCode, strategy_id)
    if not sc or sc.tenant_id != uuid.UUID(current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Strategy not found")

    result = await session.execute(
        select(StrategyCodeVersion).where(
            StrategyCodeVersion.strategy_code_id == strategy_id,
            StrategyCodeVersion.version == version,
        )
    )
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")

    sc.code = v.code
    sc.version += 1
    session.add(_create_version(sc))
    await session.commit()
    await session.refresh(sc)
    return _to_response(sc)


# Templates — no auth required
@template_router.get("", response_model=list[TemplateResponse])
async def list_templates():
    return [
        TemplateResponse(name=t["name"], description=t["description"], code=t["code"], params=t["params"])
        for t in TEMPLATES
    ]
```

- [ ] **Step 6: Register routers in main.py**

In `backend/app/main.py`, add imports and include_router calls:

```python
from app.hosted_strategies.router import router as hosted_strategy_router, template_router
# ... in the router registration section:
app.include_router(hosted_strategy_router)
app.include_router(template_router)
```

- [ ] **Step 7: Run tests**

```bash
cd backend && python -m pytest tests/test_hosted_strategies_router.py -v
```

Expected: All PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/hosted_strategies/ backend/app/main.py backend/tests/test_hosted_strategies_router.py
git commit -m "feat: add hosted strategy CRUD API with templates, versioning, and file upload"
```

---

### Task 5: Deployment CRUD & Status API

**Files:**
- Create: `backend/app/deployments/__init__.py`
- Create: `backend/app/deployments/schemas.py`
- Create: `backend/app/deployments/service.py`
- Create: `backend/app/deployments/router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_deployments_router.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_deployments_router.py` with tests for:
- Create backtest deployment (POST)
- Create paper deployment (POST)
- Get deployment detail (GET)
- List deployments for strategy (GET)
- Pause deployment (POST)
- Resume deployment (POST)
- Stop deployment (POST)
- Stop all deployments (POST)
- Promote deployment backtest→paper (POST)
- Promote paper→live requires min ticks (422 validation)
- Get deployment results (GET)
- Get deployment logs (GET, paginated)

Follow the same auth_override fixture pattern from Task 4 tests. Each test creates prerequisite data (strategy code, deployment) as needed.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_deployments_router.py -v
```

- [ ] **Step 3: Implement schemas**

Create `backend/app/deployments/__init__.py` (empty).

Create `backend/app/deployments/schemas.py`:

```python
from pydantic import BaseModel, Field


class CreateDeploymentRequest(BaseModel):
    mode: str  # backtest, paper, live
    symbol: str
    exchange: str
    product_type: str = "DELIVERY"
    interval: str
    broker_connection_id: str | None = None
    cron_expression: str | None = None
    config: dict = Field(default_factory=dict)
    params: dict = Field(default_factory=dict)
    strategy_code_version: int | None = None  # null = latest


class PromoteRequest(BaseModel):
    broker_connection_id: str | None = None
    cron_expression: str | None = None
    config_overrides: dict = Field(default_factory=dict)


class DeploymentResponse(BaseModel):
    id: str
    strategy_code_id: str
    strategy_code_version_id: str
    mode: str
    status: str
    symbol: str
    exchange: str
    product_type: str
    interval: str
    broker_connection_id: str | None
    cron_expression: str | None
    config: dict
    params: dict
    promoted_from_id: str | None
    created_at: str
    started_at: str | None
    stopped_at: str | None


class DeploymentResultResponse(BaseModel):
    id: str
    deployment_id: str
    trade_log: list | None
    equity_curve: list | None
    metrics: dict | None
    status: str
    created_at: str
    completed_at: str | None


class DeploymentLogEntry(BaseModel):
    id: str
    timestamp: str
    level: str
    message: str


class DeploymentLogsResponse(BaseModel):
    logs: list[DeploymentLogEntry]
    total: int
    offset: int
    limit: int
```

- [ ] **Step 4: Implement service.py**

Create `backend/app/deployments/service.py`:

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.db.models import (
    StrategyCode, StrategyCodeVersion, StrategyDeployment,
    DeploymentState, DeploymentLog, StrategyResult,
)

MAX_PAPER_DEPLOYMENTS = 5
MAX_LIVE_DEPLOYMENTS = 2
MAX_CONCURRENT_BACKTESTS = 3
MIN_PAPER_TICKS_FOR_LIVE = 10

CRON_MIN_INTERVAL_MINUTES = 5

ORDER_TYPE_MAP = {
    "market": "MARKET",
    "limit": "LIMIT",
    "stop": "SL-M",
    "stop_limit": "SL",
}


def validate_cron_expression(cron_expr: str) -> None:
    """Basic validation — reject sub-5-minute intervals."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise HTTPException(status_code=400, detail="Invalid cron expression (need 5 fields)")
    minute_field = parts[0]
    if minute_field.startswith("*/"):
        try:
            interval = int(minute_field[2:])
            if interval < CRON_MIN_INTERVAL_MINUTES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Minimum cron interval is {CRON_MIN_INTERVAL_MINUTES} minutes",
                )
        except ValueError:
            pass


async def check_deployment_limits(
    session: AsyncSession, tenant_id: uuid.UUID, mode: str
) -> None:
    """Enforce per-user deployment limits."""
    if mode == "backtest":
        count = await session.scalar(
            select(func.count(StrategyDeployment.id)).where(
                StrategyDeployment.tenant_id == tenant_id,
                StrategyDeployment.mode == "backtest",
                StrategyDeployment.status.in_(["pending", "running"]),
            )
        )
        if count >= MAX_CONCURRENT_BACKTESTS:
            raise HTTPException(status_code=429, detail=f"Max {MAX_CONCURRENT_BACKTESTS} concurrent backtests")
    elif mode == "paper":
        count = await session.scalar(
            select(func.count(StrategyDeployment.id)).where(
                StrategyDeployment.tenant_id == tenant_id,
                StrategyDeployment.mode == "paper",
                StrategyDeployment.status.in_(["running", "paused"]),
            )
        )
        if count >= MAX_PAPER_DEPLOYMENTS:
            raise HTTPException(status_code=429, detail=f"Max {MAX_PAPER_DEPLOYMENTS} paper deployments")
    elif mode == "live":
        count = await session.scalar(
            select(func.count(StrategyDeployment.id)).where(
                StrategyDeployment.tenant_id == tenant_id,
                StrategyDeployment.mode == "live",
                StrategyDeployment.status.in_(["running", "paused"]),
            )
        )
        if count >= MAX_LIVE_DEPLOYMENTS:
            raise HTTPException(status_code=429, detail=f"Max {MAX_LIVE_DEPLOYMENTS} live deployments")


async def resolve_code_version(
    session: AsyncSession, strategy_code_id: uuid.UUID, version: int | None
) -> StrategyCodeVersion:
    """Get specific version or latest."""
    if version is not None:
        result = await session.execute(
            select(StrategyCodeVersion).where(
                StrategyCodeVersion.strategy_code_id == strategy_code_id,
                StrategyCodeVersion.version == version,
            )
        )
    else:
        result = await session.execute(
            select(StrategyCodeVersion)
            .where(StrategyCodeVersion.strategy_code_id == strategy_code_id)
            .order_by(StrategyCodeVersion.version.desc())
            .limit(1)
        )
    cv = result.scalar_one_or_none()
    if not cv:
        raise HTTPException(status_code=404, detail="Strategy code version not found")
    return cv


async def validate_promotion(
    session: AsyncSession, deployment: StrategyDeployment
) -> str:
    """Validate that a deployment can be promoted. Returns the target mode."""
    if deployment.mode == "backtest" and deployment.status == "completed":
        return "paper"
    elif deployment.mode == "paper" and deployment.status in ("running", "paused"):
        tick_count = await session.scalar(
            select(func.count(DeploymentLog.id)).where(
                DeploymentLog.deployment_id == deployment.id,
                DeploymentLog.level == "info",
            )
        )
        if (tick_count or 0) < MIN_PAPER_TICKS_FOR_LIVE:
            raise HTTPException(
                status_code=422,
                detail=f"Paper deployment needs at least {MIN_PAPER_TICKS_FOR_LIVE} ticks before promotion (has {tick_count})",
            )
        return "live"
    else:
        raise HTTPException(
            status_code=409,
            detail=f"Deployment in mode={deployment.mode} status={deployment.status} cannot be promoted",
        )
```

- [ ] **Step 5: Implement router**

Create `backend/app/deployments/router.py`:

```python
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_tenant_session
from app.db.models import (
    StrategyCode, StrategyDeployment, DeploymentState,
    DeploymentLog, StrategyResult,
)
from app.deployments.schemas import (
    CreateDeploymentRequest, PromoteRequest,
    DeploymentResponse, DeploymentResultResponse,
    DeploymentLogsResponse, DeploymentLogEntry,
)
from app.deployments.service import (
    check_deployment_limits, resolve_code_version,
    validate_cron_expression, validate_promotion,
)

router = APIRouter(tags=["deployments"])


def _to_response(d: StrategyDeployment) -> DeploymentResponse:
    return DeploymentResponse(
        id=str(d.id),
        strategy_code_id=str(d.strategy_code_id),
        strategy_code_version_id=str(d.strategy_code_version_id),
        mode=d.mode,
        status=d.status,
        symbol=d.symbol,
        exchange=d.exchange,
        product_type=d.product_type,
        interval=d.interval,
        broker_connection_id=str(d.broker_connection_id) if d.broker_connection_id else None,
        cron_expression=d.cron_expression,
        config=d.config,
        params=d.params,
        promoted_from_id=str(d.promoted_from_id) if d.promoted_from_id else None,
        created_at=d.created_at.isoformat(),
        started_at=d.started_at.isoformat() if d.started_at else None,
        stopped_at=d.stopped_at.isoformat() if d.stopped_at else None,
    )


@router.post(
    "/api/v1/hosted-strategies/{strategy_id}/deployments",
    status_code=status.HTTP_201_CREATED,
    response_model=DeploymentResponse,
)
async def create_deployment(
    strategy_id: uuid.UUID,
    body: CreateDeploymentRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])

    sc = await session.get(StrategyCode, strategy_id)
    if not sc or sc.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Strategy not found")

    await check_deployment_limits(session, tenant_id, body.mode)

    if body.mode in ("paper", "live") and body.cron_expression:
        validate_cron_expression(body.cron_expression)

    if body.mode == "live" and not body.broker_connection_id:
        raise HTTPException(status_code=400, detail="Broker connection required for live deployment")

    cv = await resolve_code_version(session, strategy_id, body.strategy_code_version)

    deployment = StrategyDeployment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        strategy_code_id=strategy_id,
        strategy_code_version_id=cv.id,
        mode=body.mode,
        status="pending",
        symbol=body.symbol,
        exchange=body.exchange,
        product_type=body.product_type,
        interval=body.interval,
        broker_connection_id=uuid.UUID(body.broker_connection_id) if body.broker_connection_id else None,
        cron_expression=body.cron_expression,
        config=body.config,
        params=body.params,
    )
    session.add(deployment)

    # Create initial state for paper/live
    if body.mode in ("paper", "live"):
        initial_capital = body.config.get("initial_capital", 10000)
        state = DeploymentState(
            deployment_id=deployment.id,
            tenant_id=tenant_id,
            position=None,
            open_orders=[],
            portfolio={"balance": initial_capital, "equity": initial_capital, "available_margin": initial_capital},
            user_state={},
        )
        session.add(state)

    await session.commit()
    await session.refresh(deployment)

    # TODO: Enqueue backtest task or register cron schedule via Redis pub/sub
    return _to_response(deployment)


@router.get(
    "/api/v1/hosted-strategies/{strategy_id}/deployments",
    response_model=list[DeploymentResponse],
)
async def list_deployments(
    strategy_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment)
        .where(
            StrategyDeployment.strategy_code_id == strategy_id,
            StrategyDeployment.tenant_id == tenant_id,
        )
        .order_by(StrategyDeployment.created_at.desc())
    )
    return [_to_response(d) for d in result.scalars().all()]


@router.get("/api/v1/deployments", response_model=list[DeploymentResponse])
async def list_all_deployments(
    status: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    q = select(StrategyDeployment).where(StrategyDeployment.tenant_id == tenant_id)
    if status:
        q = q.where(StrategyDeployment.status == status)
    result = await session.execute(q.order_by(StrategyDeployment.created_at.desc()))
    return [_to_response(d) for d in result.scalars().all()]


@router.get("/api/v1/deployments/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    d = await session.get(StrategyDeployment, deployment_id)
    if not d or d.tenant_id != uuid.UUID(current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Deployment not found")
    return _to_response(d)


@router.post("/api/v1/deployments/{deployment_id}/pause", response_model=DeploymentResponse)
async def pause_deployment(
    deployment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    d = await session.get(StrategyDeployment, deployment_id)
    if not d or d.tenant_id != uuid.UUID(current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Deployment not found")
    if d.status != "running":
        raise HTTPException(status_code=409, detail="Only running deployments can be paused")
    d.status = "paused"
    await session.commit()
    await session.refresh(d)
    # TODO: Notify strategy-runner to remove cron job
    return _to_response(d)


@router.post("/api/v1/deployments/{deployment_id}/resume", response_model=DeploymentResponse)
async def resume_deployment(
    deployment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    d = await session.get(StrategyDeployment, deployment_id)
    if not d or d.tenant_id != uuid.UUID(current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Deployment not found")
    if d.status != "paused":
        raise HTTPException(status_code=409, detail="Only paused deployments can be resumed")
    d.status = "running"
    await session.commit()
    await session.refresh(d)
    # TODO: Notify strategy-runner to re-register cron job
    return _to_response(d)


@router.post("/api/v1/deployments/{deployment_id}/stop", response_model=DeploymentResponse)
async def stop_deployment(
    deployment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    d = await session.get(StrategyDeployment, deployment_id)
    if not d or d.tenant_id != uuid.UUID(current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Deployment not found")
    if d.status in ("stopped", "completed", "failed"):
        raise HTTPException(status_code=409, detail="Deployment is already in a terminal state")
    d.status = "stopped"
    d.stopped_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(d)
    # TODO: Notify strategy-runner to remove cron job
    return _to_response(d)


@router.post("/api/v1/deployments/stop-all", status_code=status.HTTP_200_OK)
async def stop_all_deployments(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment).where(
            StrategyDeployment.tenant_id == tenant_id,
            StrategyDeployment.status.in_(["running", "paused", "pending"]),
        )
    )
    count = 0
    for d in result.scalars().all():
        d.status = "stopped"
        d.stopped_at = datetime.now(timezone.utc)
        count += 1
    await session.commit()
    # TODO: Notify strategy-runner to remove all cron jobs for this tenant
    return {"stopped": count}


@router.post("/api/v1/deployments/{deployment_id}/promote", response_model=DeploymentResponse)
async def promote_deployment(
    deployment_id: uuid.UUID,
    body: PromoteRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    d = await session.get(StrategyDeployment, deployment_id)
    if not d or d.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Deployment not found")

    target_mode = await validate_promotion(session, d)

    if target_mode == "live" and not body.broker_connection_id:
        raise HTTPException(status_code=400, detail="Broker connection required for live promotion")

    await check_deployment_limits(session, tenant_id, target_mode)

    if body.cron_expression:
        validate_cron_expression(body.cron_expression)

    config = {**d.config, **body.config_overrides}
    cron = body.cron_expression or d.cron_expression

    new_deployment = StrategyDeployment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        strategy_code_id=d.strategy_code_id,
        strategy_code_version_id=d.strategy_code_version_id,
        mode=target_mode,
        status="pending",
        symbol=d.symbol,
        exchange=d.exchange,
        product_type=d.product_type,
        interval=d.interval,
        broker_connection_id=uuid.UUID(body.broker_connection_id) if body.broker_connection_id else d.broker_connection_id,
        cron_expression=cron,
        config=config,
        params=d.params,
        promoted_from_id=d.id,
    )
    session.add(new_deployment)

    initial_capital = config.get("initial_capital", 10000)
    state = DeploymentState(
        deployment_id=new_deployment.id,
        tenant_id=tenant_id,
        position=None,
        open_orders=[],
        portfolio={"balance": initial_capital, "equity": initial_capital, "available_margin": initial_capital},
        user_state={},
    )
    session.add(state)

    await session.commit()
    await session.refresh(new_deployment)
    return _to_response(new_deployment)


@router.get("/api/v1/deployments/{deployment_id}/results", response_model=DeploymentResultResponse | None)
async def get_deployment_results(
    deployment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    d = await session.get(StrategyDeployment, deployment_id)
    if not d or d.tenant_id != uuid.UUID(current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Deployment not found")

    result = await session.execute(
        select(StrategyResult).where(StrategyResult.deployment_id == deployment_id)
    )
    sr = result.scalar_one_or_none()
    if not sr:
        return None
    return DeploymentResultResponse(
        id=str(sr.id),
        deployment_id=str(deployment_id),
        trade_log=sr.trade_log,
        equity_curve=sr.equity_curve,
        metrics=sr.metrics,
        status=sr.status,
        created_at=sr.created_at.isoformat(),
        completed_at=sr.completed_at.isoformat() if sr.completed_at else None,
    )


@router.get("/api/v1/deployments/{deployment_id}/orders")
async def get_deployment_orders(
    deployment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    d = await session.get(StrategyDeployment, deployment_id)
    if not d or d.tenant_id != uuid.UUID(current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Deployment not found")
    state = await session.get(DeploymentState, deployment_id)
    return {"open_orders": state.open_orders if state else [], "deployment_id": str(deployment_id)}


@router.get("/api/v1/deployments/{deployment_id}/logs", response_model=DeploymentLogsResponse)
async def get_deployment_logs(
    deployment_id: uuid.UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    d = await session.get(StrategyDeployment, deployment_id)
    if not d or d.tenant_id != uuid.UUID(current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Deployment not found")

    total = await session.scalar(
        select(func.count(DeploymentLog.id)).where(DeploymentLog.deployment_id == deployment_id)
    )
    result = await session.execute(
        select(DeploymentLog)
        .where(DeploymentLog.deployment_id == deployment_id)
        .order_by(DeploymentLog.timestamp.desc())
        .offset(offset)
        .limit(limit)
    )
    logs = [
        DeploymentLogEntry(
            id=str(log.id), timestamp=log.timestamp.isoformat(),
            level=log.level, message=log.message,
        )
        for log in result.scalars().all()
    ]
    return DeploymentLogsResponse(logs=logs, total=total or 0, offset=offset, limit=limit)
```

- [ ] **Step 6: Register deployment router in main.py**

In `backend/app/main.py`:

```python
from app.deployments.router import router as deployment_router
# ...
app.include_router(deployment_router)
```

- [ ] **Step 7: Run tests**

```bash
cd backend && python -m pytest tests/test_deployments_router.py -v
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/deployments/ backend/app/main.py backend/tests/test_deployments_router.py
git commit -m "feat: add deployment CRUD, promotion pipeline, and status management API"
```

---

## Phase 2: Execution Engine

### Task 6: Nautilus Backtest Integration

**Files:**
- Create: `backend/app/nautilus_integration/__init__.py`
- Create: `backend/app/nautilus_integration/instrument.py`
- Create: `backend/app/nautilus_integration/data.py`
- Create: `backend/app/nautilus_integration/adapter.py`
- Create: `backend/app/nautilus_integration/results.py`
- Test: `backend/tests/test_nautilus_integration.py`

- [ ] **Step 1: Add nautilus_trader to pyproject.toml**

In `backend/pyproject.toml`, add to dependencies:

```toml
"nautilus_trader>=1.200.0",
```

```bash
cd backend && pip install -e ".[dev]"
```

- [ ] **Step 2: Write failing tests**

Create `backend/tests/test_nautilus_integration.py` with tests for:
- `build_instrument("BTCUSDT", "BINANCE", ...)` returns a CryptoSpot
- `ohlcv_to_bars(candles, instrument_id, bar_spec)` returns Nautilus Bar list
- `NautilusAdapter` wraps an `AlgoMatterStrategy` and translates on_bar → on_candle
- Full backtest run: feed 100 candles through SMA strategy, get trade_log + equity_curve + metrics

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_nautilus_integration.py -v
```

- [ ] **Step 4: Implement instrument.py**

Create `backend/app/nautilus_integration/instrument.py` — builds `CryptoSpot` from symbol string + exchange config. Parses base/quote from symbol (e.g., "BTCUSDT" → "BTC"/"USDT"). Uses sensible defaults for precision/tick/lot sizes.

- [ ] **Step 5: Implement data.py**

Create `backend/app/nautilus_integration/data.py` — converts list of OHLCV dicts to Nautilus `Bar` objects with proper `BarType` and timestamps.

- [ ] **Step 6: Implement adapter.py**

Create `backend/app/nautilus_integration/adapter.py` — `NautilusAdapter(nautilus_trader.trading.Strategy)` that wraps `AlgoMatterStrategy`. Translates `on_bar()` → `on_candle()`, order methods → Nautilus order submission, and order events → `on_order_update()`.

- [ ] **Step 7: Implement results.py**

Create `backend/app/nautilus_integration/results.py` — extracts trade_log, equity_curve, and metrics from a completed `BacktestEngine`. Reuses existing `compute_metrics()` from `app/analytics/metrics.py`.

- [ ] **Step 8: Run tests**

```bash
cd backend && python -m pytest tests/test_nautilus_integration.py -v
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/nautilus_integration/ backend/tests/test_nautilus_integration.py backend/pyproject.toml
git commit -m "feat: implement Nautilus Trader integration - adapter, instrument builder, data conversion, results extraction"
```

---

### Task 7: Strategy-Runner Service

**Files:**
- Create: `backend/app/strategy_runner/__init__.py`
- Create: `backend/app/strategy_runner/main.py`
- Create: `backend/app/strategy_runner/executor.py`
- Create: `backend/app/strategy_runner/backtest_runner.py`
- Create: `backend/app/strategy_runner/tick_runner.py`
- Create: `backend/app/strategy_runner/order_router.py`
- Create: `backend/app/strategy_runner/scheduler.py`
- Create: `backend/app/strategy_runner/health.py`
- Modify: `backend/pyproject.toml` (add apscheduler)
- Test: `backend/tests/test_strategy_runner.py`

- [ ] **Step 1: Add apscheduler to pyproject.toml**

```toml
"apscheduler>=4.0.0a5",
```

```bash
cd backend && pip install -e ".[dev]"
```

- [ ] **Step 2: Write failing tests**

Create `backend/tests/test_strategy_runner.py` with tests for:
- `executor.run_subprocess(payload)` returns parsed JSON output
- `order_router.translate_order(order_dict, deployment)` maps order types correctly
- `backtest_runner.run_backtest_job(deployment_id)` creates StrategyResult with metrics
- `tick_runner.run_tick(deployment_id)` processes one candle, updates DeploymentState
- `health.FailureTracker` auto-pauses after 3 consecutive failures

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_strategy_runner.py -v
```

- [ ] **Step 4: Implement executor.py**

Create `backend/app/strategy_runner/executor.py`:
- `async def run_subprocess(payload: dict, timeout: int = 60) -> dict` — serializes payload to JSON, spawns subprocess via `asyncio.create_subprocess_exec`, writes to stdin, reads stdout, parses JSON result. Handles timeout (returns error type "timeout") and OOM.
- Uses `asyncio.Semaphore` for max concurrent workers.

- [ ] **Step 5: Implement order_router.py**

Create `backend/app/strategy_runner/order_router.py`:
- `translate_order(order: dict, deployment: StrategyDeployment) -> OrderRequest` — maps strategy API order types to BrokerAdapter types using `ORDER_TYPE_MAP`, injects `exchange`, `product_type`, `symbol` from deployment.
- `async def dispatch_orders(orders: list, deployment, session)` — for paper: use SimulatedBroker; for live: decrypt credentials, get broker from factory, place_order.
- Exchange1 stop/stop_limit rejection with error logging.

- [ ] **Step 6: Implement tick_runner.py**

Create `backend/app/strategy_runner/tick_runner.py`:
- `async def run_tick(deployment_id: UUID, session: AsyncSession)` — loads deployment + state from DB, fetches latest candle + history via broker adapter's `get_historical()`, builds subprocess payload, calls `executor.run_subprocess()`, processes returned orders via `order_router.dispatch_orders()`, updates `DeploymentState`, writes `DeploymentLog` entries.

- [ ] **Step 7: Implement backtest_runner.py**

Create `backend/app/strategy_runner/backtest_runner.py`:
- `async def run_backtest_job(deployment_id: UUID)` — loads deployment + code version from DB, fetches historical OHLCV (cache + broker API), runs Nautilus backtest via the integration module, writes `StrategyResult`, updates deployment status to "completed" or "failed".

- [ ] **Step 8: Implement scheduler.py**

Create `backend/app/strategy_runner/scheduler.py`:
- Uses APScheduler `AsyncScheduler` with `CronTrigger`
- `async def load_active_deployments(session)` — on startup, reads all running deployments, registers cron jobs
- `async def register_deployment(deployment_id, cron_expression)` — add job
- `async def unregister_deployment(deployment_id)` — remove job
- Redis distributed lock to prevent duplicate ticks across replicas

- [ ] **Step 9: Implement health.py**

Create `backend/app/strategy_runner/health.py`:
- `FailureTracker` class — tracks consecutive failures per deployment_id
- `record_failure(deployment_id)` — increment, auto-pause at threshold (3)
- `record_success(deployment_id)` — reset counter
- Reports health to Redis key

- [ ] **Step 10: Implement main.py**

Create `backend/app/strategy_runner/main.py`:
- Async entrypoint: initializes DB session, Redis, scheduler, ARQ consumer
- Starts APScheduler + ARQ worker loop
- Listens on `strategy-runner:queue` for backtest jobs
- Graceful shutdown: stop scheduler, drain running tasks

- [ ] **Step 11: Run tests**

```bash
cd backend && python -m pytest tests/test_strategy_runner.py -v
```

- [ ] **Step 12: Commit**

```bash
git add backend/app/strategy_runner/ backend/tests/test_strategy_runner.py backend/pyproject.toml
git commit -m "feat: implement strategy-runner service with cron scheduler, subprocess executor, tick runner, and backtest runner"
```

---

### Task 8: Docker Compose & Infrastructure

**Files:**
- Modify: `backend/docker-compose.yml`
- Modify: `backend/Dockerfile` (if separate runner image needed)

- [ ] **Step 1: Add strategy-runner service to docker-compose.yml**

Add after the `worker` service:

```yaml
  strategy-runner:
    build: .
    command: python -m app.strategy_runner.main
    environment:
      - ALGOMATTER_DATABASE_URL=postgresql+asyncpg://algomatter:algomatter@postgres:5432/algomatter
      - ALGOMATTER_REDIS_URL=redis://redis:6379/0
      - ALGOMATTER_JWT_SECRET=${ALGOMATTER_JWT_SECRET:-dev-secret-change-in-production}
      - ALGOMATTER_MASTER_KEY=${ALGOMATTER_MASTER_KEY:-0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

- [ ] **Step 2: Verify compose is valid**

```bash
cd backend && docker compose config
```

- [ ] **Step 3: Commit**

```bash
git add backend/docker-compose.yml
git commit -m "feat: add strategy-runner service to Docker Compose"
```

---

## Phase 3: Frontend

### Task 9: Frontend Types & API Hooks

**Files:**
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/lib/hooks/useApi.ts`

- [ ] **Step 1: Add TypeScript types**

Add to `frontend/lib/api/types.ts`:

```typescript
// Hosted Strategies
export interface HostedStrategy {
  id: string;
  name: string;
  description: string | null;
  code: string;
  version: number;
  entrypoint: string;
  created_at: string;
  updated_at: string;
}

export interface StrategyVersion {
  id: string;
  version: number;
  code: string;
  created_at: string;
}

export interface StrategyTemplate {
  name: string;
  description: string;
  code: string;
  params: Record<string, unknown>;
}

// Deployments
export interface Deployment {
  id: string;
  strategy_code_id: string;
  strategy_code_version_id: string;
  mode: "backtest" | "paper" | "live";
  status: "pending" | "running" | "paused" | "stopped" | "completed" | "failed";
  symbol: string;
  exchange: string;
  product_type: string;
  interval: string;
  broker_connection_id: string | null;
  cron_expression: string | null;
  config: Record<string, unknown>;
  params: Record<string, unknown>;
  promoted_from_id: string | null;
  created_at: string;
  started_at: string | null;
  stopped_at: string | null;
}

export interface DeploymentResult {
  id: string;
  deployment_id: string;
  trade_log: unknown[] | null;
  equity_curve: { timestamp: string; equity: number }[] | null;
  metrics: StrategyMetrics | null;
  status: string;
  created_at: string;
  completed_at: string | null;
}

export interface DeploymentLogEntry {
  id: string;
  timestamp: string;
  level: string;
  message: string;
}

export interface DeploymentLogsResponse {
  logs: DeploymentLogEntry[];
  total: number;
  offset: number;
  limit: number;
}
```

- [ ] **Step 2: Add SWR hooks**

Add to `frontend/lib/hooks/useApi.ts`:

```typescript
// Hosted Strategies
export function useHostedStrategies() {
  return useSWR<HostedStrategy[]>("/api/v1/hosted-strategies", fetcher);
}

export function useHostedStrategy(id: string | undefined) {
  return useSWR<HostedStrategy>(id ? `/api/v1/hosted-strategies/${id}` : null, fetcher);
}

export function useStrategyVersions(id: string | undefined) {
  return useSWR<StrategyVersion[]>(id ? `/api/v1/hosted-strategies/${id}/versions` : null, fetcher);
}

export function useStrategyTemplates() {
  return useSWR<StrategyTemplate[]>("/api/v1/strategy-templates", fetcher);
}

// Deployments
export function useDeployments(strategyId: string | undefined) {
  return useSWR<Deployment[]>(
    strategyId ? `/api/v1/hosted-strategies/${strategyId}/deployments` : null,
    fetcher, { refreshInterval: POLLING_INTERVALS.PAPER_TRADING }
  );
}

export function useDeployment(id: string | undefined) {
  return useSWR<Deployment>(id ? `/api/v1/deployments/${id}` : null, fetcher, { refreshInterval: 2000 });
}

export function useDeploymentResults(id: string | undefined) {
  return useSWR<DeploymentResult | null>(id ? `/api/v1/deployments/${id}/results` : null, fetcher);
}

export function useActiveDeployments() {
  return useSWR<Deployment[]>(
    "/api/v1/deployments?status=running",
    fetcher, { refreshInterval: POLLING_INTERVALS.PAPER_TRADING }
  );
}

export function useDeploymentLogs(id: string | undefined, offset = 0, limit = 50) {
  return useSWR<DeploymentLogsResponse>(
    id ? `/api/v1/deployments/${id}/logs?offset=${offset}&limit=${limit}` : null, fetcher
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api/types.ts frontend/lib/hooks/useApi.ts
git commit -m "feat: add TypeScript types and SWR hooks for hosted strategies and deployments"
```

---

### Task 10: Monaco Editor Component

**Files:**
- Create: `frontend/components/editor/MonacoEditor.tsx`

- [ ] **Step 1: Install Monaco editor package**

```bash
cd frontend && npm install @monaco-editor/react
```

- [ ] **Step 2: Create MonacoEditor component**

Create `frontend/components/editor/MonacoEditor.tsx`:

```tsx
"use client";

import { useRef, useCallback } from "react";
import Editor, { OnMount } from "@monaco-editor/react";
import { useColorMode } from "@chakra-ui/react";

interface MonacoEditorProps {
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
  height?: string;
}

export default function MonacoEditor({ value, onChange, readOnly = false, height = "100%" }: MonacoEditorProps) {
  const { colorMode } = useColorMode();
  const editorRef = useRef<any>(null);

  const handleMount: OnMount = useCallback((editor, monaco) => {
    editorRef.current = editor;

    // Register AlgoMatterStrategy completions
    monaco.languages.registerCompletionItemProvider("python", {
      provideCompletionItems: (model, position) => {
        const word = model.getWordUntilPosition(position);
        const range = {
          startLineNumber: position.lineNumber,
          endLineNumber: position.lineNumber,
          startColumn: word.startColumn,
          endColumn: word.endColumn,
        };
        return {
          suggestions: [
            { label: "self.buy", kind: monaco.languages.CompletionItemKind.Method, insertText: 'self.buy(quantity=${1:1}, order_type="${2:market}")', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range, detail: "Place a buy order" },
            { label: "self.sell", kind: monaco.languages.CompletionItemKind.Method, insertText: 'self.sell(quantity=${1:1}, order_type="${2:market}")', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range, detail: "Place a sell order" },
            { label: "self.cancel_order", kind: monaco.languages.CompletionItemKind.Method, insertText: "self.cancel_order(${1:order_id})", insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range, detail: "Cancel a pending order" },
            { label: "self.position", kind: monaco.languages.CompletionItemKind.Property, insertText: "self.position", range, detail: "Current position or None" },
            { label: "self.portfolio", kind: monaco.languages.CompletionItemKind.Property, insertText: "self.portfolio", range, detail: "Portfolio (balance, equity, margin)" },
            { label: "self.open_orders", kind: monaco.languages.CompletionItemKind.Property, insertText: "self.open_orders", range, detail: "List of pending orders" },
            { label: "self.params", kind: monaco.languages.CompletionItemKind.Property, insertText: "self.params", range, detail: "User-configurable parameters" },
            { label: "self.state", kind: monaco.languages.CompletionItemKind.Property, insertText: "self.state", range, detail: "Persistent state dict" },
            { label: "self.history", kind: monaco.languages.CompletionItemKind.Method, insertText: "self.history(${1:20})", insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range, detail: "Last N candles" },
            { label: "self.log", kind: monaco.languages.CompletionItemKind.Method, insertText: 'self.log("${1:message}")', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range, detail: "Log message to UI" },
          ],
        };
      },
    });
  }, []);

  return (
    <Editor
      height={height}
      language="python"
      theme={colorMode === "dark" ? "vs-dark" : "vs"}
      value={value}
      onChange={(v) => onChange(v || "")}
      onMount={handleMount}
      options={{
        readOnly,
        minimap: { enabled: false },
        fontSize: 14,
        lineNumbers: "on",
        scrollBeyondLastLine: false,
        automaticLayout: true,
        tabSize: 4,
        insertSpaces: true,
      }}
    />
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/editor/ frontend/package.json frontend/package-lock.json
git commit -m "feat: add Monaco editor component with Python language support and AlgoMatterStrategy autocomplete"
```

---

### Task 11: Strategy Editor Page

**Files:**
- Create: `frontend/app/(dashboard)/strategies/hosted/page.tsx`
- Create: `frontend/app/(dashboard)/strategies/hosted/new/page.tsx`
- Create: `frontend/app/(dashboard)/strategies/hosted/[id]/page.tsx`

- [ ] **Step 1: Create hosted strategies list page**

Create `frontend/app/(dashboard)/strategies/hosted/page.tsx` — lists all hosted strategies with name, version, updated_at. "New Strategy" button links to `/strategies/hosted/new`. Each row links to `/strategies/hosted/[id]`.

Pattern: Follow existing `frontend/app/(dashboard)/strategies/page.tsx` structure (DataTable, Chakra UI, useHostedStrategies hook).

- [ ] **Step 2: Create new strategy page**

Create `frontend/app/(dashboard)/strategies/hosted/new/page.tsx` — template picker (grid of cards from `useStrategyTemplates()`), name input. On select: creates strategy via `POST /api/v1/hosted-strategies` with template code, redirects to editor page.

- [ ] **Step 3: Create strategy editor page**

Create `frontend/app/(dashboard)/strategies/hosted/[id]/page.tsx`:
- Layout: `Flex` with left panel (MonacoEditor, 60% width) and right panel (tabs, 40% width)
- Top bar: strategy name, Save button, Upload .py button, version dropdown, Run Backtest button, Deploy button
- Right panel tabs:
  - **Config**: symbol input, interval select, params as key-value pairs (JSON editor or dynamic form)
  - **Backtest Results**: shows latest backtest deployment's results (metrics, equity curve, trade log) — reuse existing EquityCurve and DataTable components
  - **Deployments**: list of deployments for this strategy with status badges, links to deployment detail

State management:
- `code` state synced with Monaco editor
- Save: `PUT /api/v1/hosted-strategies/{id}` with updated code
- Upload: file input → `POST /api/v1/hosted-strategies/{id}/upload`
- Version dropdown: `useStrategyVersions(id)`, selecting a version shows read-only code, "Restore" button calls restore endpoint
- Run Backtest: opens modal with date range + capital inputs, submits `POST /api/v1/hosted-strategies/{id}/deployments` with mode="backtest", polls deployment status
- Deploy: opens modal with mode (paper/live), broker selector, cron expression, submits deployment

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(dashboard\)/strategies/hosted/
git commit -m "feat: add hosted strategy list, new strategy, and editor pages with Monaco editor"
```

---

### Task 12: Deployment Components & Page

**Files:**
- Create: `frontend/components/deployments/DeploymentCard.tsx`
- Create: `frontend/components/deployments/DeploymentTimeline.tsx`
- Create: `frontend/components/deployments/MetricsComparison.tsx`
- Create: `frontend/components/deployments/PromoteModal.tsx`
- Create: `frontend/components/shared/DeploymentBadge.tsx`
- Create: `frontend/components/shared/LogViewer.tsx`
- Create: `frontend/app/(dashboard)/strategies/hosted/[id]/deployments/page.tsx`

- [ ] **Step 1: Create DeploymentBadge**

`frontend/components/shared/DeploymentBadge.tsx` — colored badge showing mode (backtest/paper/live) and status. Uses Chakra `Badge` with color schemes: backtest=blue, paper=yellow, live=green. Status colors: running=green, paused=orange, stopped=red, completed=blue, failed=red, pending=gray.

- [ ] **Step 2: Create LogViewer**

`frontend/components/shared/LogViewer.tsx` — paginated log display using `useDeploymentLogs()`. Shows timestamp, level (color-coded), message. Load More button for pagination.

- [ ] **Step 3: Create DeploymentCard**

`frontend/components/deployments/DeploymentCard.tsx` — card showing DeploymentBadge, symbol, interval, duration, key metrics (if available from results). Action buttons: Pause/Resume, Stop, Promote (if eligible).

- [ ] **Step 4: Create MetricsComparison**

`frontend/components/deployments/MetricsComparison.tsx` — two-column card comparing metrics from two deployments (e.g., backtest vs paper). Highlights deltas with green/red arrows.

- [ ] **Step 5: Create PromoteModal**

`frontend/components/deployments/PromoteModal.tsx` — Chakra Modal for promoting a deployment. Shows MetricsComparison (current stage vs target). Broker selector dropdown (for live). Cron expression input. Confirm button calls promote API.

- [ ] **Step 6: Create DeploymentTimeline**

`frontend/components/deployments/DeploymentTimeline.tsx` — visual timeline showing promotion chain (backtest → paper → live) using `promoted_from_id` links. Each node is a DeploymentCard. Arrows between stages.

- [ ] **Step 7: Create deployments page**

`frontend/app/(dashboard)/strategies/hosted/[id]/deployments/page.tsx` — uses `useDeployments(strategyId)`. Groups by promotion chain using `promoted_from_id`. Shows DeploymentTimeline for each chain. Individual deployment details expandable with LogViewer and results.

- [ ] **Step 8: Commit**

```bash
git add frontend/components/deployments/ frontend/components/shared/DeploymentBadge.tsx frontend/components/shared/LogViewer.tsx frontend/app/\(dashboard\)/strategies/hosted/\[id\]/deployments/
git commit -m "feat: add deployment components - timeline, cards, metrics comparison, promote modal, log viewer"
```

---

### Task 13: Dashboard & Sidebar Updates

**Files:**
- Modify: `frontend/components/layout/Sidebar.tsx`
- Modify: `frontend/app/(dashboard)/page.tsx`

- [ ] **Step 1: Update Sidebar**

In `frontend/components/layout/Sidebar.tsx`, replace the single "Strategies" nav item with two items:

```typescript
{ icon: MdShowChart, label: "Webhook Strategies", href: "/strategies" },
{ icon: MdCode, label: "Hosted Strategies", href: "/strategies/hosted" },
```

Import `MdCode` from `react-icons/md`.

- [ ] **Step 2: Add Active Strategies section to Dashboard**

In `frontend/app/(dashboard)/page.tsx`, add a new section after existing stat cards:

- Heading: "Active Strategies"
- Fetch running deployments: create a new hook `useActiveDeployments()` that calls `GET /api/v1/deployments?status=running` (or filter client-side from all deployments)
- Display as a SimpleGrid of compact DeploymentCards showing: strategy name, symbol, mode, status, last tick time, current P&L
- Empty state: "No active strategies. Create one to get started." with link to `/strategies/hosted/new`

- [ ] **Step 3: Commit**

```bash
git add frontend/components/layout/Sidebar.tsx frontend/app/\(dashboard\)/page.tsx
git commit -m "feat: update sidebar with hosted strategies link and add active strategies section to dashboard"
```

---

## Phase 4: Integration & Polish

### Task 14: Wire Backtest Enqueuing to Strategy-Runner

**Files:**
- Modify: `backend/app/deployments/router.py`
- Modify: `backend/app/strategy_runner/main.py`

- [ ] **Step 1: Enqueue backtest tasks from deployment creation**

In `backend/app/deployments/router.py`, after creating a backtest deployment, publish a message to Redis to trigger the strategy-runner:

```python
if body.mode == "backtest":
    redis = request.app.state.redis
    await redis.lpush("strategy-runner:queue", json.dumps({"deployment_id": str(deployment.id), "type": "backtest"}))
```

For paper/live deployments, publish a "register" message:

```python
elif body.mode in ("paper", "live"):
    redis = request.app.state.redis
    await redis.publish("strategy-runner:deployments", json.dumps({"action": "register", "deployment_id": str(deployment.id)}))
```

Similarly, publish "unregister" on pause/stop and "register" on resume.

- [ ] **Step 2: Strategy-runner consumes queue**

In `backend/app/strategy_runner/main.py`, the ARQ worker listens on `strategy-runner:queue` for backtest jobs and calls `backtest_runner.run_backtest_job(deployment_id)`.

The scheduler subscribes to `strategy-runner:deployments` Redis pub/sub channel for register/unregister commands.

- [ ] **Step 3: Commit**

```bash
git add backend/app/deployments/router.py backend/app/strategy_runner/main.py
git commit -m "feat: wire deployment creation to strategy-runner via Redis queue and pub/sub"
```

---

### Task 15: End-to-End Integration Test

**Files:**
- Create: `backend/tests/test_e2e_hosted_strategy.py`

- [ ] **Step 1: Write E2E test**

Test the full flow:
1. Create hosted strategy with SMA template code
2. Create backtest deployment
3. Verify deployment status transitions (pending → completed)
4. Check StrategyResult has trade_log, equity_curve, metrics
5. Promote to paper
6. Verify paper deployment created with correct promoted_from_id
7. Stop paper deployment
8. Verify terminal state

This test mocks the strategy-runner subprocess (since it won't be running in test environment) but validates the API layer, DB models, and state transitions.

- [ ] **Step 2: Run test**

```bash
cd backend && python -m pytest tests/test_e2e_hosted_strategy.py -v
```

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_e2e_hosted_strategy.py
git commit -m "test: add end-to-end integration test for hosted strategy lifecycle"
```

---

## Summary

| Phase | Tasks | Key Deliverables |
|---|---|---|
| **1: Foundation** | Tasks 1-5 | DB models, SDK, CRUD API, deployment API |
| **2: Engine** | Tasks 6-8 | Nautilus integration, strategy-runner service, Docker config |
| **3: Frontend** | Tasks 9-13 | Types, Monaco editor, editor page, deployments page, dashboard |
| **4: Integration** | Tasks 14-15 | Redis wiring, E2E tests |

**Task dependencies:**
- Task 1 (models) blocks all other tasks
- Tasks 2-3 (SDK, subprocess) are independent of Task 4-5 (CRUD, deployment API)
- Task 6 (Nautilus) depends on Task 2 (SDK)
- Task 7 (runner) depends on Tasks 3, 5, 6
- Task 8 (Docker) depends on Task 7
- Tasks 9-13 (frontend) depend on Tasks 4-5 (backend APIs)
- Tasks 14-15 (integration) depend on everything above
