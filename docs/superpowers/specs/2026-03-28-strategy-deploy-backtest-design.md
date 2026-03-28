# Strategy Deployment & Backtesting Design

**Date:** 2026-03-28
**Status:** Approved
**Scope:** Hosted Python strategies with Nautilus-powered backtesting, cron-based live/paper execution, and a backtest→paper→live promotion pipeline.

---

## 1. Overview

Algomatter currently operates on a webhook-driven model — external systems generate trading signals that the platform routes through mapping, rules, and broker adapters. This design adds a second strategy mode: **hosted Python strategies** that run inside the platform, can be backtested against historical data, and deployed to paper or live trading.

### Two Strategy Modes

- **Webhook strategies** (existing, unchanged) — External signals → JSONPath mapping → rules → broker dispatch
- **Hosted strategies** (new) — User-authored Python code → cron-triggered `on_candle()` → orders → broker dispatch

### Key Design Decisions

| Area | Decision |
|---|---|
| Authoring | Python scripts via in-browser Monaco editor + .py file upload |
| Engine | Nautilus Trader for backtesting, custom runner for live/paper |
| Execution model | Cron-based, OHLCV candles, single symbol per strategy |
| Isolation | Dedicated strategy-runner service + per-strategy subprocess |
| Promotion | Backtest → Paper → Live pipeline with safety gates |

---

## 2. Data Model

### StrategyCode

Stores the user's strategy source code.

| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| tenant_id | UUID | FK → users, RLS-protected |
| name | VARCHAR(255) | User-given name |
| description | TEXT | Optional |
| code | TEXT | Current Python source |
| version | INTEGER | Auto-incremented on each save |
| entrypoint | VARCHAR(100) | Class name to instantiate, default `"Strategy"` |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### StrategyCodeVersion

Immutable version history. Each save inserts a new row.

| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| tenant_id | UUID | FK → users, RLS-protected (denormalized for RLS policy) |
| strategy_code_id | UUID | FK → strategy_code, ON DELETE CASCADE |
| version | INTEGER | Matches the version at time of save. UNIQUE constraint on `(strategy_code_id, version)` |
| code | TEXT | Snapshot of source code |
| created_at | TIMESTAMPTZ | |

### StrategyDeployment

Represents a single run of a strategy in a specific mode.

| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| tenant_id | UUID | FK → users, RLS-protected |
| strategy_code_id | UUID | FK → strategy_code |
| strategy_code_version_id | UUID | FK → strategy_code_version |
| mode | ENUM | `backtest`, `paper`, `live` |
| status | ENUM | `pending`, `running`, `paused`, `stopped`, `completed`, `failed` |
| symbol | VARCHAR(20) | e.g., `"BTCUSDT"` |
| exchange | VARCHAR(20) | e.g., `"BINANCE"`, `"EXCHANGE1"` — maps to broker type |
| product_type | VARCHAR(20) | e.g., `"DELIVERY"`, `"INTRADAY"` — defaults to `"DELIVERY"` for crypto spot |
| interval | VARCHAR(10) | e.g., `"1h"`, `"5m"` |
| broker_connection_id | UUID | FK → broker_connections, nullable for backtest |
| cron_expression | VARCHAR(50) | For paper/live scheduling |
| config | JSONB | initial_capital, commission_rate, slippage_model |
| params | JSONB | User-configurable strategy parameters |
| promoted_from_id | UUID | FK self-ref, nullable — links to prior stage |
| created_at | TIMESTAMPTZ | |
| started_at | TIMESTAMPTZ | |
| stopped_at | TIMESTAMPTZ | |

### StrategyResult (existing, modified)

Add columns:

| Column | Type | Notes |
|---|---|---|
| deployment_id | UUID | FK → strategy_deployment, **nullable** (existing CSV backtests have no deployment) |
| strategy_code_version_id | UUID | FK → strategy_code_version, **nullable** (same reason) |

Existing columns (trade_log, equity_curve, metrics) unchanged. Migration must make new columns nullable to preserve existing data.

### DeploymentState (new table)

Persists strategy state between cron ticks for paper/live deployments.

| Column | Type | Notes |
|---|---|---|
| deployment_id | UUID | PK, FK → strategy_deployment |
| tenant_id | UUID | FK → users, RLS-protected (denormalized) |
| position | JSONB | Current position (quantity, avg_entry_price, unrealized_pnl) |
| open_orders | JSONB | Pending orders list |
| portfolio | JSONB | Balance, equity, available margin |
| user_state | JSONB | Arbitrary state from `self.state` dict |
| updated_at | TIMESTAMPTZ | |

### DeploymentLog (new table)

Stores `self.log()` output from strategy execution.

| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| tenant_id | UUID | FK → users, RLS-protected (denormalized) |
| deployment_id | UUID | FK → strategy_deployment |
| timestamp | TIMESTAMPTZ | |
| level | VARCHAR(10) | `info`, `warn`, `error` |
| message | TEXT | |

**Retention:** Logs older than 30 days are auto-deleted by a daily ARQ task running on the strategy-runner's queue (since the `strategy_runner` DB role has `DELETE` on this table). Table is partitioned by month on `timestamp` for efficient pruning.

---

## 3. AlgoMatterStrategy API

### User-Facing Interface

```python
from algomatter import AlgoMatterStrategy, Candle

class MyStrategy(AlgoMatterStrategy):

    def on_init(self):
        """Called once at startup. Set up indicators, state."""
        self.sma_period = self.params.get("sma_period", 20)
        self.prices = []

    def on_candle(self, candle: Candle):
        """Called on each new candle (bar close)."""
        self.prices.append(candle.close)

        if len(self.prices) < self.sma_period:
            return

        sma = sum(self.prices[-self.sma_period:]) / self.sma_period

        if candle.close > sma and not self.position:
            self.buy(quantity=1, order_type="limit", price=candle.close * 0.999)
        elif candle.close < sma and self.position:
            self.sell(quantity=1)

        # Cancel stale orders
        for order in self.open_orders:
            if order.age_candles > 3:
                self.cancel_order(order.id)

    def on_order_update(self, order_id, status, fill_price, fill_quantity):
        """Optional callback when an order fills/cancels/rejects."""
        if status == "filled":
            self.sell(quantity=fill_quantity, order_type="stop",
                      trigger_price=fill_price * 0.95)

    def on_stop(self):
        """Called when strategy is stopped. Cleanup."""
        pass
```

### Candle Dataclass

```python
@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
```

Note: `float` is used for user-facing simplicity. Internally, OHLCV data is stored as `Numeric(20,8)` / `Decimal`. The conversion from `Decimal` to `float` happens at Candle construction in the subprocess entry point.

### Base Class Methods & Properties

**Order methods:**

- `self.buy(quantity, order_type="market", price=None, trigger_price=None) → str` — Returns order_id
- `self.sell(quantity, order_type="market", price=None, trigger_price=None) → str` — Returns order_id
- `order_type`: `"market"` | `"limit"` | `"stop"` | `"stop_limit"`
- `price` — required for limit/stop_limit
- `trigger_price` — required for stop/stop_limit
- `self.cancel_order(order_id) → None`

**Properties:**

- `self.position` — Current position object (quantity, avg_entry_price, unrealized_pnl) or `None`
- `self.portfolio` — Portfolio object (balance, equity, available_margin)
- `self.open_orders` — List of pending/partially-filled orders
- `self.params` — Dict of user-configurable parameters (set in UI)
- `self.state` — Dict for persisting arbitrary user state between ticks (serialized as JSONB)
- `self.history(periods=N)` — Last N candles as a list

**Utility:**

- `self.log(message, level="info")` — Structured logging visible in UI

**Escape hatch:**

- `self.nautilus_strategy` — Underlying Nautilus `Strategy` instance during backtests. Returns `None` during live/paper execution.

### Lifecycle

1. `on_init()` — Called once per subprocess boot. In **backtest mode**, this is truly once. In **live/paper mode**, this runs on every cron tick (since each tick is a fresh subprocess). `self.state` is restored from DB before `on_init()` is called, so use `self.state` for data that must persist between ticks — not instance variables. Example: `self.state.setdefault("prices", [])` instead of `self.prices = []`.
2. `on_candle(candle)` — Called on each new bar
3. `on_order_update(order_id, status, fill_price, fill_quantity)` — Called when order state changes (called before `on_candle` if there are pending order updates)
4. `on_stop()` — Called when strategy is stopped

### Order Type Translation

The strategy API uses lowercase user-friendly names. The strategy-runner translates these to the platform's internal `BrokerAdapter.OrderRequest.order_type` enum before dispatching. Each broker adapter then further translates to exchange-specific formats internally.

| Strategy API | BrokerAdapter Internal | Notes |
|---|---|---|
| `"market"` | `"MARKET"` | |
| `"limit"` | `"LIMIT"` | |
| `"stop"` | `"SL-M"` | Stop-loss market |
| `"stop_limit"` | `"SL"` | Stop-loss limit |

Translation happens in the strategy-runner after collecting orders from the subprocess, not inside user code. The `exchange` and `product_type` fields are injected from the `StrategyDeployment` config — users never set these per-order.

**Exchange1 limitation:** Exchange1Broker currently supports only `MARKET` and `LIMIT` order types. Stop/stop-limit orders targeting Exchange1 will be rejected at the strategy-runner level with a clear error logged to `DeploymentLog`. Exchange1 stop-order support can be added later as needed.

### `self.history()` Implementation

- **Backtest mode:** Nautilus maintains the full bar history internally. `self.history(N)` reads the last N bars from the Nautilus data cache.
- **Live/Paper mode:** The subprocess input payload includes a `history` field containing the last `max_history_periods` candles (default 200, configurable per deployment). The strategy-runner fetches these from the broker API or `HistoricalOHLCV` cache before each tick. `self.history(N)` reads from this pre-loaded buffer.

---

## 4. Execution Architecture

### Backtesting Path (Nautilus)

```
User clicks "Run Backtest"
    → API creates StrategyDeployment (mode=backtest, status=pending)
    → Enqueues ARQ task to strategy-runner service
    → strategy-runner spawns subprocess:
        1. Deserialize strategy code + params
        2. Boot Nautilus BacktestEngine
        3. Load historical OHLCV from DB or fetch from broker API
        4. Translate AlgoMatterStrategy → Nautilus Strategy via NautilusAdapter
        5. Run engine (candles fed bar-by-bar, fills simulated)
        6. Collect trade_log, equity_curve, metrics
        7. Write StrategyResult to DB
    → Frontend polls deployment status until completed
```

Subprocess constraints: CPU timeout (configurable, default 60s), memory limit (512MB), no network access, no filesystem access outside temp dir.

### Live/Paper Path (Custom Runner)

```
User clicks "Deploy to Paper" or "Promote to Live"
    → API creates StrategyDeployment (mode=paper|live, status=running)
    → Registers cron schedule in strategy-runner service

Every cron tick:
    → strategy-runner spawns subprocess:
        1. Deserialize strategy code + state (position, open_orders, portfolio, user_state)
        2. Fetch latest closed candle from broker API (both paper and live use real market data)
        3. Instantiate AlgoMatterStrategy, restore state, call on_init()
        4. Call on_candle(candle)
        5. Call on_order_update() for any pending order status changes
        6. Collect generated orders + updated state
        7. Return orders + state via stdout JSON
    → strategy-runner processes orders:
        - Paper: SimulatedBroker fills against candle prices
        - Live: Broker adapter (Exchange1, Binance) places real orders
    → Update DeploymentState, trade log, positions in DB
```

### Subprocess Protocol

Communication via stdin/stdout JSON.

**Input (runner → subprocess):**

```json
{
  "code": "class Strategy(AlgoMatterStrategy): ...",
  "entrypoint": "Strategy",
  "candle": {"timestamp": "2026-03-28T10:00:00Z", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 5000},
  "history": [
    {"timestamp": "2026-03-28T09:00:00Z", "open": 99, "high": 101, "low": 98, "close": 100, "volume": 4500}
  ],
  "state": {
    "position": {"quantity": 1, "avg_entry_price": 98.5},
    "open_orders": [{"id": "abc", "action": "sell", "order_type": "stop", "trigger_price": 93.5}],
    "portfolio": {"balance": 10000, "equity": 10250},
    "user_state": {"prices": [100, 101, 99]}
  },
  "order_updates": [
    {"order_id": "abc", "status": "filled", "fill_price": 93.5, "fill_quantity": 1}
  ],
  "params": {"sma_period": 20},
  "mode": "paper"
}
```

- `history`: Last N candles (default 200) for `self.history()`. Fetched by runner before subprocess launch.
- `order_updates`: Status changes on pending orders since last tick. Runner checks broker/SimulatedBroker before each tick.

**Output (subprocess → runner):**

```json
{
  "orders": [{"action": "buy", "quantity": 1, "order_type": "limit", "price": 99.5}],
  "cancelled_orders": ["def"],
  "state": {"user_state": {"prices": [100, 101, 99, 101]}},
  "logs": [{"level": "info", "message": "SMA crossed above, placing buy"}],
  "error": null
}
```

**State ownership:** The subprocess only modifies `user_state`. The runner is responsible for updating `position`, `open_orders`, and `portfolio` in `DeploymentState` after processing orders and fills. This prevents user code from manipulating portfolio state directly.

**Error format:** When `error` is non-null:
```json
{
  "error": {
    "type": "runtime",
    "message": "ZeroDivisionError: division by zero",
    "traceback": "line 15, in on_candle\n    sma = total / count"
  }
}
```
Error types: `"syntax"` (code won't parse), `"runtime"` (unhandled exception), `"timeout"` (CPU limit exceeded), `"oom"` (memory limit exceeded).

For backtests, the subprocess receives the full historical dataset and returns the complete result in one shot.

### Nautilus Integration (Backtest Subprocess)

Inside the backtest subprocess:

1. Parse strategy code, instantiate `AlgoMatterStrategy`
2. Create `NautilusAdapter` that translates `AlgoMatterStrategy` → Nautilus `Strategy`
3. `NautilusAdapter.on_bar()` → calls `AlgoMatterStrategy.on_candle()`
4. Orders from `self.buy()`/`self.sell()` → translated to Nautilus `OrderFactory` calls
5. Nautilus engine handles fill simulation (price crossing, slippage, commissions)
6. `NautilusAdapter.on_order_filled()` → calls `AlgoMatterStrategy.on_order_update()`
7. After run: extract trades from Nautilus `Portfolio`, compute metrics, format results

---

## 5. Strategy-Runner Service

### Architecture

```
strategy-runner service
├── Cron Scheduler (APScheduler)
│   ├── Reads active deployments from DB on startup
│   ├── Registers/unregisters jobs as deployments start/stop
│   └── On tick: submits job to subprocess pool
│
├── Subprocess Pool (asyncio.create_subprocess_exec → nsjail → python)
│   ├── Max concurrent workers configurable (default: 4 per replica, enforced by asyncio.Semaphore)
│   ├── Each execution: nsjail spawns a sandboxed Python process (see Sandbox Security below)
│   └── Resource limits: CPU timeout, memory cap, import allowlist
│
├── Backtest Queue (ARQ consumer)
│   ├── Listens for backtest jobs from API
│   └── Spawns ephemeral subprocess per backtest
│
└── Health Monitor
    ├── Tracks consecutive failures per deployment
    ├── Auto-pauses after 3 consecutive failures
    └── Reports service health to Redis
```

### Docker Compose Service

```yaml
strategy-runner:
  build: ./backend
  command: python -m app.strategy_runner.main
  depends_on: [postgres, redis]
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
```

### Cron Management

- Uses APScheduler >= 4.0 with async scheduler (`AsyncScheduler`) to integrate with the async event loop
- Deployment create/resume → scheduler adds job with cron expression
- Deployment pause/stop → scheduler removes job
- Service restart → reads all `status=running` deployments from DB, re-registers crons
- Distributed lock (Redis) prevents duplicate ticks if multiple runner replicas exist
- **Minimum interval:** 5 minutes. Sub-5-minute cron expressions are rejected at the API level. This keeps subprocess-per-tick overhead manageable. If sub-minute strategies are needed later, a long-running process model would replace subprocess-per-tick for those deployments.

---

## 6. Promotion Pipeline

### State Machine

Mode transitions create new `StrategyDeployment` rows. Status transitions happen within a single row.

```
Mode transitions (new row each time, linked by promoted_from_id):
  [StrategyCode exists] → BACKTEST deployment → PAPER deployment → LIVE deployment

Status transitions (within a single StrategyDeployment row):
  pending → running → paused → running   (pause/resume cycle)
                    → stopped             (terminal)
           → completed                    (backtest finished successfully)
           → failed                       (backtest or tick error)
```

### Promotion Rules

Each promotion creates a **new `StrategyDeployment` row** linked via `promoted_from_id`.

- **Backtest → Paper:** Requires at least one completed backtest. Carries forward symbol, interval, params. User selects or confirms broker connection.
- **Paper → Live:** Requires paper deployment to have run for at least N ticks (configurable, default 10). Shows side-by-side comparison: backtest metrics vs paper metrics. User must confirm broker connection with real credentials.
- **Any stage → Stopped:** Terminal state. Can re-deploy from the same code but creates a new deployment.
- **Running ↔ Paused:** Suspends/resumes the cron schedule. State preserved. Open orders on live are left as-is.

### Safety Guards

- **Code lock on deploy** — Deployment locks to a specific `strategy_code_version`. Editing code creates a new version but doesn't affect running deployments.
- **Kill switch** — "Stop All" endpoint stops every running deployment for the user immediately.
- **Resource limits per user** — Max concurrent deployments (e.g., 5 paper + 2 live). Max concurrent backtests: 3. Configurable.
- **Error threshold** — 3 consecutive subprocess failures → auto-pause deployment and notify user.

---

## 7. API Endpoints

### Strategy Code CRUD

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/hosted-strategies` | Create new strategy |
| GET | `/api/v1/hosted-strategies` | List user's hosted strategies |
| GET | `/api/v1/hosted-strategies/{id}` | Get strategy with current code |
| PUT | `/api/v1/hosted-strategies/{id}` | Update code (auto-increments version) |
| DELETE | `/api/v1/hosted-strategies/{id}` | Delete strategy + all versions |
| POST | `/api/v1/hosted-strategies/{id}/upload` | Upload .py file, replaces code |
| GET | `/api/v1/hosted-strategies/{id}/versions` | List all versions |
| GET | `/api/v1/hosted-strategies/{id}/versions/{version}` | Get specific version's code |

### Deployments

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/hosted-strategies/{id}/deployments` | Create deployment |
| GET | `/api/v1/hosted-strategies/{id}/deployments` | List deployments for strategy |
| GET | `/api/v1/deployments/{id}` | Get deployment detail |
| POST | `/api/v1/deployments/{id}/pause` | Pause running deployment |
| POST | `/api/v1/deployments/{id}/resume` | Resume paused deployment |
| POST | `/api/v1/deployments/{id}/stop` | Stop deployment (terminal) |
| POST | `/api/v1/deployments/{id}/promote` | Promote to next stage |
| POST | `/api/v1/deployments/stop-all` | Kill switch |

### Deployment Results & Logs

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/deployments/{id}/results` | Trade log, equity curve, metrics |
| GET | `/api/v1/deployments/{id}/logs` | Strategy logs (paginated) |
| GET | `/api/v1/deployments/{id}/orders` | Open and historical orders |

### Templates

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/strategy-templates` | List starter templates (no auth) |

---

## 8. Frontend Changes

### New Pages

**Strategy Editor** (`/strategies/hosted/[id]`)
- Left panel: Monaco editor — Python syntax highlighting, autocomplete for AlgoMatterStrategy API
- Right panel: Tabbed — Config (symbol, interval, params), Backtest Results, Deployments
- Top bar: Save, Upload .py, Run Backtest, Deploy buttons
- Version dropdown to view/restore previous code versions
- Starter template selector on new strategy creation

**Deployments View** (`/strategies/hosted/[id]/deployments`)
- Timeline view of backtest → paper → live progression
- Each deployment card: mode, status, duration, key metrics (return, Sharpe, drawdown)
- Promote / Pause / Stop actions per deployment
- Side-by-side metrics comparison when promoting

### Modified Pages

**Dashboard** (`/`)
- New "Active Strategies" section showing running hosted deployments with live P&L

**Sidebar**
- "Strategies" splits into: Webhook Strategies (existing), Hosted Strategies (new)

### New Components

- Monaco editor wrapper (Python language config, AlgoMatterStrategy autocomplete)
- Deployment status badge (mode × status)
- Metrics comparison card (two columns, highlight deltas)
- Strategy log viewer (streaming logs from `self.log()`)

### Unchanged

- All existing webhook, broker, paper trading, backtesting, analytics pages
- API client patterns, SWR hooks, Chakra UI, TradingView charts

---

## 9. Starter Templates

Pre-built strategy templates shipped with the platform:

1. **SMA Crossover** — Buy when price crosses above SMA, sell when below. Params: `sma_period`.
2. **RSI Mean Reversion** — Buy when RSI < oversold threshold, sell when RSI > overbought. Params: `rsi_period`, `oversold`, `overbought`.
3. **MACD Momentum** — Buy on MACD line crossing above signal line, sell on cross below. Params: `fast_period`, `slow_period`, `signal_period`.
4. **Bollinger Band Breakout** — Buy when price breaks above upper band, sell when below lower. Params: `bb_period`, `bb_std`.
5. **Blank Template** — Minimal `on_init()` + `on_candle()` skeleton.

Each template includes comments explaining the strategy logic and available API methods.

---

## 10. Dependencies

### New Python Packages

- `nautilus_trader` — Backtesting engine
- `apscheduler>=4.0` — Async cron scheduling for strategy-runner

### System Dependencies (strategy-runner Docker image)

- `nsjail` — Subprocess sandboxing (installed in Dockerfile for strategy-runner)

### Existing (Already Used)

- `arq` — Background task queue (backtest jobs)
- `sqlalchemy` — ORM (new models)
- `alembic` — Migrations
- `pydantic` — Request/response schemas

### Frontend

- `@monaco-editor/react` — Code editor component

---

## 11. Subprocess Sandbox Security

User-authored Python code executes in a sandboxed subprocess. Security is enforced at multiple layers:

### Layer 1: `nsjail` Wrapper

Each subprocess is launched via [nsjail](https://github.com/google/nsjail), a lightweight process isolation tool. Configuration:

- **Network:** Disabled (`--disable_clone_newnet` or no network namespace access)
- **Filesystem:** Read-only root mount. Write access only to a per-execution tmpdir (auto-cleaned)
- **PID namespace:** Isolated — subprocess cannot see or signal other processes
- **Time limit:** Hard kill after configured timeout (default 60s for backtests, 10s for live/paper ticks)
- **Memory limit:** Configurable cgroup limit (default 512MB for backtests, 256MB for live/paper)
- **No new privileges:** `--disable_clone_newuser` prevents privilege escalation

### Layer 2: Python Import Allowlist

Before `exec()` of user code, the subprocess entry point replaces `__builtins__.__import__` with a filtered version. Allowed modules:

- **Allowed:** `math`, `statistics`, `datetime`, `collections`, `itertools`, `functools`, `decimal`, `json`, `dataclasses`, `typing`, `enum`, `abc`, `copy`, `operator`, `bisect`, `heapq`, `random`
- **Allowed (third-party):** `numpy`, `pandas`, `ta` (technical analysis), `pandas_ta`
- **Blocked:** `os`, `sys`, `subprocess`, `socket`, `http`, `urllib`, `requests`, `ctypes`, `importlib`, `pickle`, `shelve`, `multiprocessing`, `threading`, `signal`, `shutil`, `pathlib`, `io` (file I/O), `builtins` (raw access)

### Layer 3: Environment Sanitization

The **subprocess** (user code) is launched with a minimal environment — only `PATH`, `HOME=/tmp`, `PYTHONPATH` (pointing to the algomatter strategy SDK). Database URLs, API keys, JWT secrets, and master encryption keys are NOT inherited by the subprocess.

The **strategy-runner service itself** (the parent process, not user code) retains access to `ALGOMATTER_MASTER_KEY` and `ALGOMATTER_DATABASE_URL` because it needs to decrypt broker credentials for live order placement and read/write to the DB. The security boundary is between the runner service and the sandboxed subprocess, not between the runner and the rest of the platform.

### Layer 4: Separate Database Role

The strategy-runner service connects to PostgreSQL with a dedicated `strategy_runner` role that has:
- `SELECT`/`INSERT`/`UPDATE` on strategy-related tables only (StrategyCode, StrategyCodeVersion, StrategyDeployment, StrategyResult, DeploymentState, DeploymentLog)
- `DELETE` on DeploymentLog (for log retention pruning)
- `SELECT` on HistoricalOHLCV, BrokerConnection (for reading candle data and credentials)
- `INSERT` on HistoricalOHLCV (for caching fetched candle data)
- No access to `users`, `refresh_tokens`, or other auth tables
- No `DROP`, `ALTER`, or `TRUNCATE` permissions

---

## 12. Historical Data Sourcing

### For Backtests

1. **Check `HistoricalOHLCV` cache** — If candles for the requested symbol/exchange/interval/date-range exist in DB, use them
2. **Fetch from broker API** — If cache miss, use the broker adapter's `get_historical()` method:
   - Binance Testnet / Exchange1: `GET /api/v3/klines` (paginated, max 1000 candles per request)
   - Rate-limited: max 5 requests/second, with backoff
3. **Store in cache** — Fetched candles are inserted into `HistoricalOHLCV` for future backtests
4. **Date range validation** — API rejects backtest requests for date ranges where data is unavailable (e.g., pre-listing dates)

The existing `yfinance`-based historical service is for equity symbols. Crypto symbols route through broker adapters. The `HistoricalOHLCV.exchange` column determines which data source to use.

### For Live/Paper Ticks

The strategy-runner fetches the latest closed candle + history buffer directly from the broker API's `get_historical()` method on each cron tick. No caching needed — the data is fresh per-tick.

---

## 13. Nautilus Integration Detail

### Venue Configuration

Each backtest configures a Nautilus `Venue` representing the exchange:

```python
venue = Venue("BINANCE")  # or "EXCHANGE1"
```

### Instrument Registration

Before running, the adapter registers the trading instrument:

```python
instrument = CryptoSpot(
    instrument_id=InstrumentId(Symbol(symbol), venue),
    raw_symbol=Symbol(symbol),
    base_currency=Currency.from_str(base),    # e.g., "BTC"
    quote_currency=Currency.from_str(quote),   # e.g., "USDT"
    price_precision=price_precision,
    size_precision=size_precision,
    price_increment=Price.from_str(tick_size),
    size_increment=Quantity.from_str(lot_size),
    maker_fee=Decimal(commission_rate),
    taker_fee=Decimal(commission_rate),
)
```

Precision and tick/lot sizes are fetched from the broker adapter's exchange info (cached).

### Data Catalog

Historical OHLCV candles are converted to Nautilus `Bar` objects:

```python
bar_type = BarType(instrument_id, BarSpecification(interval_minutes, BarAggregation.MINUTE, PriceType.LAST))
bars = [Bar(bar_type, open, high, low, close, volume, ts_event, ts_init) for candle in candles]
```

Bars are added to the `BacktestEngine` via `engine.add_data(bars)`.

### NautilusAdapter Translation

The adapter subclasses `nautilus_trader.trading.Strategy`:

- `on_start()` → calls `AlgoMatterStrategy.on_init()`
- `on_bar(bar)` → converts `Bar` to `Candle`, calls `on_candle(candle)`
- Orders from `self.buy()`/`self.sell()` → `self.submit_order(OrderFactory.market(...))` / `OrderFactory.limit(...)` / `OrderFactory.stop_market(...)` / `OrderFactory.stop_limit(...)`
- `on_order_filled(event)` → calls `on_order_update(order_id, "filled", fill_price, fill_quantity)`
- `on_order_canceled(event)` → calls `on_order_update(order_id, "cancelled", None, None)`
- `on_order_rejected(event)` → calls `on_order_update(order_id, "rejected", None, None)`
- `on_stop()` → calls `AlgoMatterStrategy.on_stop()`

### BacktestEngine Configuration

```python
engine = BacktestEngine(
    config=BacktestEngineConfig(
        trader_id=TraderId("ALGOMATTER-001"),
        logging=LoggingConfig(log_level="WARNING"),
    )
)
engine.add_venue(
    venue=venue,
    oms_type=OmsType.NETTING,
    account_type=AccountType.CASH,
    starting_balances=[Money(initial_capital, quote_currency)],
    fill_model=FillModel(
        prob_fill_on_limit=0.95,
        prob_slippage=0.1,
    ),
)
engine.add_instrument(instrument)
engine.add_data(bars)
engine.add_strategy(nautilus_adapter)
engine.run()
```

Results extraction: iterate `engine.trader.generate_order_fills_report()`, `generate_positions_report()`, and `generate_account_report()` to build trade_log, equity_curve, and metrics.

---

## 14. API Request/Response Schemas

### Create Deployment

`POST /api/v1/hosted-strategies/{id}/deployments`

**Request body (backtest):**
```json
{
  "mode": "backtest",
  "symbol": "BTCUSDT",
  "exchange": "BINANCE",
  "interval": "1h",
  "config": {
    "initial_capital": 10000,
    "commission_rate": 0.001,
    "start_date": "2025-01-01",
    "end_date": "2026-03-01"
  },
  "params": {"sma_period": 20},
  "strategy_code_version": null
}
```

`strategy_code_version`: If null, uses latest version. If specified, locks to that version.

**Request body (paper/live):**
```json
{
  "mode": "paper",
  "symbol": "BTCUSDT",
  "exchange": "BINANCE",
  "product_type": "DELIVERY",
  "interval": "1h",
  "broker_connection_id": "uuid-here",
  "cron_expression": "0 * * * *",
  "config": {
    "initial_capital": 10000,
    "commission_rate": 0.001,
    "max_history_periods": 200
  },
  "params": {"sma_period": 20}
}
```

**Response:** The created `StrategyDeployment` object with `id` and `status: "pending"`.

### Promote Deployment

`POST /api/v1/deployments/{id}/promote`

**Request body:**
```json
{
  "broker_connection_id": "uuid-here",
  "cron_expression": "0 * * * *",
  "config_overrides": {}
}
```

- `broker_connection_id`: Required when promoting to live. Optional for paper (can reuse from backtest config).
- `config_overrides`: Optional. Merges with parent deployment's config.

**Response:** The newly created `StrategyDeployment` for the next stage.

**Validation errors:**
- `422`: Paper deployment hasn't run minimum ticks
- `409`: Deployment is not in a promotable state
- `400`: Missing broker connection for live promotion

### Upload Strategy File

`POST /api/v1/hosted-strategies/{id}/upload`

- **Max file size:** 100KB
- **Validation:** Must be valid Python (parsed with `ast.parse()`). Must contain a class that subclasses `AlgoMatterStrategy`.
- **Content-Type:** `multipart/form-data`
- **Response:** Updated strategy object with new version number.

### Restore Version

`POST /api/v1/hosted-strategies/{id}/versions/{version}/restore`

Copies the specified version's code to the current strategy, creating a new version. Response: updated strategy object.

---

## 15. Coexistence with Existing Systems

### CSV Backtesting

The existing CSV-based backtesting system (`/api/v1/backtests/`) remains unchanged. It serves webhook strategies that replay external signals. The new Nautilus-powered backtesting is a separate system for hosted strategies only. Different endpoints, different models, no overlap.

### Webhook Strategies

The existing `Strategy` model (with `mapping_template`, `rules`, `mode`) is unchanged. Hosted strategies use the new `StrategyCode` + `StrategyDeployment` models. The two systems share:
- Broker adapter layer (factory, Exchange1, Binance Testnet)
- Analytics/metrics computation
- Frontend shell (sidebar, layout, auth)

### ARQ Worker

The existing ARQ worker handles webhook processing and CSV backtests. The strategy-runner is a **new, separate service** with its own ARQ consumer listening on a different queue (`strategy-runner:queue`). The API enqueues hosted backtest tasks to this queue specifically.
