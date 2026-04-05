# Backtest Deployments UI — Design Spec

**Date:** 2026-04-05
**Status:** Approved

---

## Problem

The app supports a three-tier deployment model: backtest → paper → live. Live and paper deployments each have dedicated UI sections. Backtest *deployments* (mode="backtest" in `StrategyDeployment`) have no dedicated UI — there is no way to view their results, monitor running backtests, inspect trade logs, or promote them to paper trading.

The existing `/backtesting` page is a separate ad-hoc signal testing tool and is not the right home for deployment-based backtests.

---

## Goals

- View all backtest deployments in one place
- Inspect results for a completed backtest (metrics, equity curve, trade log)
- Monitor a running backtest
- Promote a completed backtest to paper trading
- See why a failed backtest failed (logs)

---

## Out of Scope

- Creating new backtest deployments (handled via `/strategies/hosted/[id]/deployments`)
- Modifying backtest parameters
- Side-by-side comparison of multiple backtests

---

## Pages & Routes

| Route | Purpose |
|-------|---------|
| `/backtest-deployments` | List all backtest deployments as cards |
| `/backtest-deployments/[deploymentId]` | Detail view — metrics header + tabbed content |

The nav sidebar (`components/layout/Sidebar.tsx`) gets a new entry in `NAV_ITEMS` between Paper Trading (index 6) and Backtesting (index 7):

```ts
{ label: "Backtest Deployments", href: "/backtest-deployments", icon: MdQueryStats }
```

`MdQueryStats` must be added to the `react-icons/md` import in `Sidebar.tsx` — it is not currently imported.

---

## Required Changes to Existing Code

Before the new pages can be built, these existing files need small updates:

### 1. `useDeployment` — add optional `refreshInterval`

`useApi.ts` currently hardcodes `refreshInterval: 2000` inside `useDeployment`. Update the hook to accept an optional config parameter so callers can override it:

```ts
export function useDeployment(id: string | null, config?: { refreshInterval?: number }) {
  return useSWR(id ? `/api/v1/deployments/${id}` : null, fetcher, {
    refreshInterval: config?.refreshInterval ?? 2000,
    ...config,
  })
}
```

### 2. `useDeploymentTrades` — add optional `refreshInterval`

Same pattern. Update to accept `config?: { refreshInterval?: number }` with a default of `5000`.

### 3. `TradeHistoryTable` — add optional `refreshInterval` prop

Add `refreshInterval?: number` (default `5000`) to the component's props and forward it to its internal `useDeploymentTrades` call.

---

## List Page — `/backtest-deployments`

### Layout
Grid of `BacktestDeploymentCard` components. Empty state with a link to `/strategies/hosted`. All cards are clickable and navigate to the detail page regardless of status.

### Card Design (`BacktestDeploymentCard`)
Each card shows:
- Strategy name + symbol/exchange/interval
- Status badge (RUNNING / COMPLETED / FAILED / PENDING / STOPPED)
- **Equity sparkline** (SVG, only rendered for `completed` deployments with non-null, non-empty `equity_curve`)
- 4 metrics: Return %, Win Rate, Max Drawdown, Total Trades (shown as `—` when not completed)
- **"Promote to Paper"** button — only when `status === "completed"` and not yet promoted (see Promote section below)
- **"View Logs"** CTA — on `failed` and `stopped` cards instead of metrics

### Data & Polling
- `useBacktestDeployments()` → `GET /api/v1/deployments?mode=backtest`
- Polls every 5s while any deployment in the list has status `running` or `pending`; sets `refreshInterval: 0` once all are in terminal state (`completed`, `failed`, `stopped`)
- Equity curve for sparklines: fetched via `useDeploymentResults(id)` per completed card. Maximum 10 sparklines rendered (top 10 most recent completed deployments) to limit concurrent requests.
- Sparkline fallback: if `equity_curve` is `null` or empty array, render a flat line SVG (not a missing element) so the card height stays consistent.

---

## Detail Page — `/backtest-deployments/[deploymentId]`

### Layout
1. **Header row** — strategy name, symbol/exchange/interval, status badge, "Promote to Paper" button
2. **Metrics row** — return, win rate, max drawdown, Sharpe ratio (4 `StatCard` tiles sourced from `DeploymentResult.metrics`)
3. **Tabs** — Overview | Trades | Logs

### Loading & Error States
- While `useDeployment` is resolving: render a skeleton layout (header + 4 metric tile skeletons + tab bar)
- `status === "pending"`: hook resolved but not yet running — render the tab bar with a "Queued — backtest has not started yet" placeholder in all three tab panes. This is distinct from the loading skeleton.
- If deployment not found (404): show an error card with a back link to `/backtest-deployments`

### Detail Page Polling
- `useDeployment(id)` is called with `{ refreshInterval: status === "running" || status === "pending" ? 2000 : 0 }`. Since status is not known until after first load, initialize with `2000` and update once the first response arrives.

### Tabs

**Overview tab**
- Full equity curve chart (recharts `LineChart`) from `DeploymentResult.equity_curve`
- Extended metrics: profit factor, avg trade P&L, total trades (all from `StrategyMetrics`)
- `best_trade` and `worst_trade` are **not displayed** — they exist on `LiveMetrics` but not on `StrategyMetrics` and are not available from the results endpoint
- When `status !== "completed"`: shows "Backtest in progress…" or "Queued" placeholder instead of chart
- Metric split: the header row `StatCard` tiles show `total_return`, `win_rate`, `max_drawdown`, `sharpe_ratio`. The Overview tab shows `profit_factor`, `avg_trade_pnl`, `total_trades` — no duplication between header row and tab.

**Trades tab**
- Uses existing `TradeHistoryTable` component with `refreshInterval={0}` for completed backtests (static data), `refreshInterval={5000}` for running backtests
- Data source: `useDeploymentTrades(id, offset, limit)` — the paginated `/trades` endpoint. `DeploymentResult.trade_log` is **not used** (typed as `unknown[]`, no per-trade TypeScript type)
- Empty state: "No trades executed"

**Logs tab**
- Uses existing `LogViewer` component (`components/shared/LogViewer.tsx`) — reused exactly as in live trading detail page
- Default active tab when `status === "failed"` or `status === "stopped"`

### Metrics Type Note
`MetricsGrid` (`components/live-trading/MetricsGrid.tsx`) expects `LiveMetrics` which includes `best_trade` and `worst_trade`. `DeploymentResult.metrics` is typed as `StrategyMetrics` which lacks these fields. **`MetricsGrid` is not reused on the backtest detail page.** `BacktestOverviewTab` renders its own metrics grid directly from `StrategyMetrics`.

### Promote Button

**Detection logic (client-side):**
1. On the detail page, fetch `GET /api/v1/deployments?mode=paper` (already available via a light call or reuse of the paper deployments list)
2. Filter results for any paper deployment where `promoted_from_id === this backtest deployment's id`
3. If none found → show "Promote to Paper" button
4. If found → show "Promoted → Paper" label as a link to `/paper-trading/{paper_deployment.id}`

This avoids depending on a `promoted_from_id` query param filter on the backend (which may not exist).

**Shown when:** `status === "completed"` and no matching paper deployment found in step 2 above.

**Mutation:** Call `apiClient.post('/api/v1/deployments/{id}/promote')` directly (same pattern as pause/resume/stop on the live trading detail page). No new hook needed.

**In progress:** button shows loading spinner and is disabled during the request. On success, re-fetch paper deployments to show the "Promoted → Paper" label.

---

## Components

### New Components

| Component | File | Description |
|-----------|------|-------------|
| `BacktestDeploymentCard` | `components/backtest-deployments/BacktestDeploymentCard.tsx` | Card with sparkline, metrics, status badge, promote/view-logs CTA |
| `SparklineChart` | `components/backtest-deployments/SparklineChart.tsx` | Lightweight SVG sparkline from `equity_curve` data. No chart library. Renders flat line when data is null/empty. |
| `BacktestDetailTabs` | `components/backtest-deployments/BacktestDetailTabs.tsx` | Tabs shell: Overview, Trades, Logs |
| `BacktestOverviewTab` | `components/backtest-deployments/BacktestOverviewTab.tsx` | Equity curve (recharts) + `StrategyMetrics` extended grid |

### Reused Components (with required changes noted)

| Component | Source | Change required |
|-----------|--------|-----------------|
| `TradeHistoryTable` | `components/live-trading/TradeHistoryTable.tsx` | Add optional `refreshInterval` prop (default `5000`) |
| `LogViewer` | `components/shared/LogViewer.tsx` | None |

### New Hooks

| Hook | File | Description |
|------|------|-------------|
| `useBacktestDeployments()` | `lib/hooks/useApi.ts` | `GET /api/v1/deployments?mode=backtest`, conditional poll |

---

## Status State Handling

| Status | List card | Detail page |
|--------|-----------|-------------|
| `pending` | Queued badge, metrics `—`, no sparkline, card clickable | Resolved hook: show "Queued" placeholder in all tab panes |
| `running` | Spinner badge, metrics `—`, no sparkline | Trades tab polls 5s; Overview shows in-progress placeholder |
| `completed` | Full metrics + sparkline + Promote button (if not yet promoted) | Full detail, all tabs, conditional promote button |
| `failed` | Error badge + "View Logs" CTA | Defaults to Logs tab |
| `stopped` | Stopped badge + "View Logs" CTA | Defaults to Logs tab |

---

## No New Backend Endpoints Required

All required data is already available:

| Endpoint | Used for |
|----------|----------|
| `GET /api/v1/deployments?mode=backtest` | List page + `useBacktestDeployments` |
| `GET /api/v1/deployments?mode=paper` | Promote button state check (client-side filter) |
| `GET /api/v1/deployments/{id}` | Detail page metadata |
| `GET /api/v1/deployments/{id}/results` | Equity curve + metrics |
| `GET /api/v1/deployments/{id}/trades` | Trades tab |
| `GET /api/v1/deployments/{id}/logs` | Logs tab (via LogViewer) |
| `POST /api/v1/deployments/{id}/promote` | Promote action |

---

## File Structure

```
frontend/
  app/(dashboard)/
    backtest-deployments/
      page.tsx                          # List page
      [deploymentId]/
        page.tsx                        # Detail page
  components/
    backtest-deployments/
      BacktestDeploymentCard.tsx
      SparklineChart.tsx
      BacktestDetailTabs.tsx
      BacktestOverviewTab.tsx
  lib/
    hooks/
      useApi.ts                         # Add useBacktestDeployments(); update useDeployment + useDeploymentTrades to accept optional refreshInterval
  components/
    live-trading/
      TradeHistoryTable.tsx             # Add optional refreshInterval prop
    layout/
      Sidebar.tsx                       # Add MdQueryStats import + new NAV_ITEMS entry
```
