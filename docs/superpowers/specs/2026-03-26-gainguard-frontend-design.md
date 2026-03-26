# GainGuard Frontend Design Spec

## Overview

Frontend for GainGuard, a multiuser algo-testing SaaS platform for Indian retail traders (NSE/BSE) and crypto traders (Exchange1). The backend API (FastAPI, 27 endpoints across 8 modules) is complete. The frontend provides a data-rich dashboard for active signal monitoring plus deep backtesting/analytics for strategy research.

## Tech Stack

| Technology | Purpose |
|---|---|
| Next.js 14 (App Router) | Framework, server/client components |
| TypeScript | Type safety |
| Chakra UI v2 | Component library, prop-based styling |
| TradingView Lightweight Charts | Financial charts (equity curves, drawdowns) |
| SWR | Data fetching, caching, polling |
| openapi-typescript | Type generation from FastAPI OpenAPI schema |

## User Personas

- **Hands-on trader**: Wants dense, real-time data. Monitors signals, manages paper sessions, tweaks strategy rules.
- **Strategy researcher**: Focuses on backtesting and analytics. Compares strategy performance, analyzes trade logs, exports data.

## Architecture Decisions

### Authentication
- Email/password login matching existing backend JWT endpoints
- Access token (15min) stored in memory (React state)
- Refresh token (7-day) stored in localStorage — acceptable for MVP threat model; XSS mitigation via CSP headers and input sanitization. Can migrate to httpOnly cookies if security requirements tighten.
- `lib/api/client.ts` intercepts 401, attempts refresh via `POST /api/v1/auth/refresh`, retries original request; if refresh fails, redirects to `/login`
- On app mount: `useAuth` hook calls `GET /api/v1/auth/me` to populate user state after silent refresh

### Navigation
- Collapsible left sidebar with icons + labels
- Sidebar sections: Dashboard, Strategies, Webhooks, Brokers, Paper Trading, Backtesting, Analytics, Settings

### Real-Time Updates
- Phase 1: SWR polling (`refreshInterval: 5000-10000ms`) on active pages (signals, paper trading)
- Architecture designed for easy WebSocket swap later (replace SWR fetcher with WS subscription)

### Theme
- Light mode by default
- Dark mode toggle (Chakra UI `useColorMode`)

### Type Safety
- `openapi-typescript` generates TypeScript types from FastAPI's `/openapi.json`
- Single source of truth — no manual type duplication
- Generated types in `lib/api/generated-types.ts`

## Project Structure

```
frontend/
├── app/                          # Next.js 14 App Router
│   ├── (auth)/                   # Route group: unauthenticated pages
│   │   ├── login/page.tsx
│   │   └── signup/page.tsx
│   ├── (dashboard)/              # Route group: authenticated pages
│   │   ├── layout.tsx            # Sidebar + auth guard
│   │   ├── page.tsx              # Dashboard home (overview)
│   │   ├── strategies/
│   │   │   ├── page.tsx          # List
│   │   │   ├── new/page.tsx      # Create form
│   │   │   └── [id]/
│   │   │       ├── page.tsx      # Detail with tabs
│   │   │       └── edit/page.tsx # Edit form
│   │   ├── webhooks/
│   │   │   └── page.tsx          # Config + signal log
│   │   ├── brokers/
│   │   │   ├── page.tsx          # Card grid
│   │   │   └── new/page.tsx      # Add form
│   │   ├── paper-trading/
│   │   │   ├── page.tsx          # Sessions list
│   │   │   └── [id]/page.tsx     # Session detail
│   │   ├── backtesting/
│   │   │   └── page.tsx          # Run form + results
│   │   ├── analytics/
│   │   │   ├── page.tsx          # Portfolio overview
│   │   │   └── strategies/[id]/page.tsx  # Strategy drilldown
│   │   └── settings/
│   │       └── page.tsx          # Health, profile, theme
│   ├── layout.tsx                # Root layout (ChakraProvider, fonts)
│   └── providers.tsx             # Client providers (Chakra, auth context)
├── lib/
│   ├── api/
│   │   ├── client.ts             # Fetch wrapper with JWT auth + refresh
│   │   └── generated-types.ts    # openapi-typescript output
│   ├── hooks/
│   │   ├── useAuth.ts            # Auth context: user, login, signup, logout
│   │   ├── usePolling.ts         # SWR wrapper with configurable interval
│   │   └── useApi.ts             # Typed API hooks per endpoint
│   └── utils/
│       ├── formatters.ts         # Currency, percentage, date formatters
│       └── constants.ts          # API base URL, polling intervals
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx           # Collapsible sidebar with nav items
│   │   ├── NavItem.tsx           # Single nav entry (icon + label)
│   │   └── TopBar.tsx            # User menu, theme toggle
│   ├── charts/
│   │   ├── EquityCurve.tsx       # TradingView area chart wrapper
│   │   ├── DrawdownChart.tsx     # TradingView histogram wrapper
│   │   └── ChartContainer.tsx    # Shared chart layout (timeframe toggles, loading)
│   └── shared/
│       ├── DataTable.tsx         # Sortable, filterable table
│       ├── StatCard.tsx          # Metric card (label, value, change indicator)
│       ├── EmptyState.tsx        # Placeholder for empty lists
│       ├── ConfirmModal.tsx      # Confirmation dialog
│       └── StatusBadge.tsx       # Colored status badges
├── openapi-ts.config.ts
├── package.json
└── tsconfig.json
```

## Pages

### 1. Login (`/login`)

- Email + password form
- "Don't have an account?" link to `/signup`
- On success: stores tokens, redirects to `/dashboard`
- Error handling: invalid credentials message

### 2. Signup (`/signup`)

- Email + password + confirm password form
- "Already have an account?" link to `/login`
- On success: stores tokens, redirects to `/dashboard`
- Validation: email format, password length (8+), password match

### 3. Dashboard Home (`/dashboard`)

The quick-glance overview for active traders.

**Row 1: Stat cards (4 across)**
- Total Strategies (active count)
- Active Paper Sessions
- Today's Signals (count)
- Portfolio P&L (sum across active paper sessions)

**Row 2: Two columns (60/40 split)**
- Left: Recent Signals table — last 10 webhook signals with timestamp, strategy name, action (BUY/SELL), rule result (passed/blocked), status badges. Click row navigates to `/webhooks`.
- Right: Top Strategies — mini cards ranked by total return. Click navigates to `/analytics/strategies/[id]`.

**Row 3: Equity curve**
- Aggregated equity curve via TradingView Lightweight Charts (area chart)
- Timeframe toggle: 1W / 1M / 3M / ALL

**Row 4: Quick actions**
- "New Strategy" → `/strategies/new`
- "Run Backtest" → `/backtesting`
- "Connect Broker" → `/brokers`

**Data fetching:**
- `GET /api/v1/analytics/overview` — stat cards + equity data
- `GET /api/v1/webhooks/signals` (limit 10) — recent signals
- SWR `refreshInterval: 10000` (10s polling)

### 4. Strategies

**`/strategies` — List page**
- Table: Name, Mode (paper/live badge), Active (toggle), Actions (edit/delete)
- Note: "Signals Today" and "Total Return" are not available from `GET /api/v1/strategies` — these columns are deferred to a future enhancement when the backend adds embedded analytics to the strategy list response
- "New Strategy" button top-right
- Filter by mode (All/Paper/Live) and active status
- Click row → `/strategies/[id]`

**`/strategies/new` and `/strategies/[id]/edit` — Form page**
- Shared form component:
  - Name (text input)
  - Broker Connection (select from user's broker connections — determines exchange implicitly)
  - Mode (radio: paper / live)
  - Active (switch)
  - Mapping Template (JSON editor textarea for JSONPath mapping)
  - Rules (structured sub-form, stored as JSON in `rules` column):
    - Symbol Whitelist (tag input)
    - Symbol Blacklist (tag input)
    - Max Open Positions (number)
    - Max Signals Per Day (number)
    - Trading Hours (start/end time pickers)
- Save → `POST /api/v1/strategies` or `PUT /api/v1/strategies/{strategy_id}`
- Delete: confirmation modal on edit page → `DELETE /api/v1/strategies/{strategy_id}`

**`/strategies/[id]` — Detail page**
- Strategy info card (name, exchange, mode, active status)
- Three tabs:
  - **Signals**: Recent webhook signals for this strategy
  - **Paper Trading**: Active session summary (if mode=paper), link to session detail
  - **Analytics**: Strategy-specific metrics + equity curve

### 5. Webhooks (`/webhooks`)

Single page with two sections.

**Section 1: Webhook Config card**
- Webhook URL display: `POST {domain}/api/v1/webhook/{token}`
- Copy-to-clipboard button
- "Regenerate Token" button with confirmation modal
- Help text: how to send signals from TradingView/external sources

**Section 2: Signal Log table**
- Columns: Timestamp, Strategy, Symbol, Action, Rule Result (badge), Execution Result, Processing Time (ms)
- Badges: green=passed, red=blocked, yellow=mapping_error
- Expandable rows: raw payload JSON + parsed signal details
- Sort: timestamp (newest first, default)
- Filters: strategy, rule result, date range
- SWR `refreshInterval: 5000` (5s) — most frequently polled page

### 6. Brokers

**`/brokers` — Card grid**
- Each card: Broker name, Exchange, Status badge (connected/error), Connected date
- "Add Broker" button top-right
- Delete action per card (no edit — credentials can't be retrieved; user deletes and re-adds)

**`/brokers/new` — Add form**
- Broker (select: Zerodha, Exchange1)
- Exchange (select: NSE/BSE for Zerodha, auto-set for Exchange1)
- Credentials (dynamic fields by broker type):
  - Zerodha: API Key, API Secret, User ID
  - Exchange1: API Key, Secret Key
- All credential fields password-masked
- Note: credentials encrypted server-side, never returned in API responses. No edit page because the backend has no `PUT /api/v1/brokers/{id}` or `GET /api/v1/brokers/{id}` — to update credentials, delete and re-add.

### 7. Paper Trading

**`/paper-trading` — Sessions list**
- Table: Strategy Name, Status (active/stopped badge), Initial Capital, Current Equity, P&L (green/red), Open Positions count, Start Date, Actions
- "Start Session" button → modal: Strategy select + Initial Capital input
- Filter by status (All/Active/Stopped)

**`/paper-trading/[id]` — Session detail**

Top: Summary cards — Initial Capital, Current Equity, Unrealized P&L, Realized P&L, Open Positions count

Middle: Two tabs
- **Positions**: Symbol, Side (long/short badge), Quantity, Avg Entry Price, Current Value, Unrealized P&L (colored), Open Date
- **Trades**: Timestamp, Symbol, Action (BUY/SELL badge), Quantity, Price, P&L (closing trades), Commission

Bottom: Equity curve — TradingView area chart derived from trade history (computed client-side)

Actions: "Stop Session" button (active only) with confirmation → `POST /api/v1/paper-trading/sessions/{id}/stop`

### 8. Backtesting (`/backtesting`)

Two-panel layout.

**Left panel: Run form**
- Strategy select (dropdown)
- Start Date (date picker)
- End Date (date picker)
- Initial Capital (number, default 100,000)
- Slippage % (number, default 0.1)
- Commission % (number, default 0.03)
- Signal Data: CSV file upload with drag-and-drop OR paste textarea
  - Format hint: `timestamp,symbol,action,quantity,price`
  - Preview table: first 5 rows after upload/paste
  - File is read client-side and sent as `signals_csv` string in the POST body
- "Run Backtest" button → `POST /api/v1/backtests`

**Async result handling:**
- Backend returns `{backtest_id, status: "queued"}` on submit
- Frontend polls `GET /api/v1/backtests/{id}` every 2s until status is `completed` or `failed`
- Show progress spinner with "Running backtest..." message
- On `failed`: display `error_message` from response
- On `completed`: render results in right panel

**Right panel: Results (after completion)**
- Metrics cards: Total Return, Win Rate, Profit Factor, Sharpe Ratio, Max Drawdown, Total Trades
- Equity Curve: TradingView area chart
- Drawdown Chart: TradingView histogram (inverted, red)
- Trade Log table: Timestamp, Symbol, Action, Quantity, Price, P&L
- Export CSV button

**History (sub-tab):**
- Table of past runs: Date, Strategy, Total Return, Sharpe, Max Drawdown, Actions (view/delete)
- Click → loads results in right panel
- Delete button with confirmation → `DELETE /api/v1/backtests/{backtest_id}`

### 9. Analytics

**`/analytics` — Portfolio overview**

Row 1: Portfolio stat cards — Total Return, Win Rate, Profit Factor, Sharpe Ratio, Max Drawdown, Total Trades

Row 2: Portfolio equity curve — TradingView area chart, timeframe toggles (1W/1M/3M/ALL)

Row 3: Strategy comparison table — sortable by any metric column. Click row → drilldown.

**`/analytics/strategies/[id]` — Strategy drilldown**

Row 1: Strategy stat cards (same 6 metrics)

Row 2: Two charts side by side — Equity curve (area) + Drawdown (histogram, red)

Row 3: Trade log table — filterable by date range and symbol, CSV export button

Row 4: Win/Loss distribution — bar chart grouping trades by P&L buckets

### 10. Settings (`/settings`)

**System Health card:**
- Database status (ok/error badge)
- Redis status (ok/error badge)
- Auto-refresh every 30s via `GET /api/v1/health`

**Profile section:**
- Email (read-only)
- Webhook token display + copy button

**Theme toggle:**
- Light/Dark mode switch

## Shared Components

### DataTable
- Sortable columns (click header to toggle asc/desc)
- Optional filters (dropdowns, date range pickers)
- Optional row expansion (for webhook signal details)
- Pagination (client-side for small datasets, server-side ready)
- Loading skeleton state

### StatCard
- Label, value, optional change indicator (arrow + percentage, colored green/red)
- Responsive: 4 across on desktop, 2 on tablet, 1 on mobile

### EquityCurve
- Wraps TradingView `createChart` + `addAreaSeries`
- Props: data (timestamp + value array), timeframe, height
- Handles resize, cleanup on unmount
- Timeframe toggle buttons (1W/1M/3M/ALL) filter data client-side

### DrawdownChart
- Wraps TradingView `createChart` + `addHistogramSeries`
- Red bars, inverted (negative values shown below zero line)
- Same resize/cleanup pattern as EquityCurve

### StatusBadge
- Variants: success (green), error (red), warning (yellow), info (blue), neutral (gray)
- Used for: rule results, session status, broker status, trade actions

## API Integration

### Backend Endpoints Used

| Endpoint | Used By |
|---|---|
| `POST /api/v1/auth/signup` | Signup page |
| `POST /api/v1/auth/login` | Login page |
| `POST /api/v1/auth/refresh` | Auth client (silent refresh) |
| `GET /api/v1/auth/me` | Auth hook (populate user state on mount) |
| `GET /api/v1/health` | Settings page |
| `GET /api/v1/strategies` | Strategies list, dashboard, backtest form |
| `POST /api/v1/strategies` | Strategy create |
| `GET /api/v1/strategies/{strategy_id}` | Strategy detail |
| `PUT /api/v1/strategies/{strategy_id}` | Strategy edit |
| `DELETE /api/v1/strategies/{strategy_id}` | Strategy delete |
| `GET /api/v1/webhooks/config` | Webhooks page |
| `POST /api/v1/webhooks/config/regenerate-token` | Webhooks page |
| `GET /api/v1/webhooks/signals` | Webhooks page, dashboard |
| `GET /api/v1/brokers` | Brokers list |
| `POST /api/v1/brokers` | Add broker |
| `DELETE /api/v1/brokers/{connection_id}` | Delete broker |
| `GET /api/v1/paper-trading/sessions` | Paper trading list, dashboard |
| `POST /api/v1/paper-trading/sessions` | Start session |
| `GET /api/v1/paper-trading/sessions/{id}` | Session detail |
| `POST /api/v1/paper-trading/sessions/{id}/stop` | Stop session |
| `GET /api/v1/backtests` | Backtest history |
| `POST /api/v1/backtests` | Run backtest |
| `GET /api/v1/backtests/{backtest_id}` | Backtest results + polling |
| `DELETE /api/v1/backtests/{backtest_id}` | Delete backtest (from history table) |
| `GET /api/v1/analytics/overview` | Dashboard, analytics overview |
| `GET /api/v1/analytics/strategies/{strategy_id}/metrics` | Analytics drilldown stat cards |
| `GET /api/v1/analytics/strategies/{strategy_id}/equity-curve` | Analytics equity curve chart |
| `GET /api/v1/analytics/strategies/{strategy_id}/trades` | Analytics trade log + CSV export (`?format=csv`) |

### Polling Configuration

| Page | Endpoint | Interval |
|---|---|---|
| Dashboard | `/analytics/overview`, `/webhooks/signals` | 10s |
| Webhooks | `/webhooks/signals` | 5s |
| Paper Trading detail | `/paper-trading/sessions/{id}` | 10s |
| Settings | `/health` | 30s |

## Error Handling

- **Network errors**: Toast notification (Chakra `useToast`) with retry suggestion
- **401 Unauthorized**: Silent token refresh; if refresh fails, redirect to `/login` with "Session expired" message
- **404 Not Found**: Redirect to parent list page with toast
- **422 Validation errors**: Inline form field errors from API response
- **500 Server errors**: Generic error toast, log to console
- **Empty states**: Friendly `EmptyState` component with illustration and action button (e.g., "No strategies yet. Create your first one.")

## Responsive Design

- **Desktop (1200px+)**: Full sidebar, multi-column layouts
- **Tablet (768-1199px)**: Collapsed sidebar (icons only), 2-column grids become single column where needed
- **Mobile (< 768px)**: Hamburger menu, single column, stacked stat cards, horizontally scrollable tables
