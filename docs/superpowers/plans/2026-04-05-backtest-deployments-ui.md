# Backtest Deployments UI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `/backtest-deployments` list page and `/backtest-deployments/[deploymentId]` detail page so users can view, monitor, and promote backtest deployments.

**Architecture:** Two new Next.js pages wired to existing backend endpoints via new/updated SWR hooks. Four new components in `components/backtest-deployments/`. Minimal surgery on three existing files (hooks, TradeHistoryTable, Sidebar).

**Tech Stack:** Next.js 13+ app router, Chakra UI, SWR, lightweight-charts (existing `EquityCurve` component), Jest + @testing-library/react.

---

## File Map

| Action | File |
|--------|------|
| Modify | `frontend/lib/hooks/useApi.ts` |
| Modify | `frontend/components/live-trading/TradeHistoryTable.tsx` |
| Modify | `frontend/components/layout/Sidebar.tsx` |
| Modify | `frontend/__tests__/components/Sidebar.test.tsx` |
| Create | `frontend/components/backtest-deployments/SparklineChart.tsx` |
| Create | `frontend/__tests__/components/SparklineChart.test.tsx` |
| Create | `frontend/components/backtest-deployments/BacktestDeploymentCard.tsx` |
| Create | `frontend/__tests__/components/BacktestDeploymentCard.test.tsx` |
| Create | `frontend/app/(dashboard)/backtest-deployments/page.tsx` |
| Create | `frontend/components/backtest-deployments/BacktestOverviewTab.tsx` |
| Create | `frontend/__tests__/components/BacktestOverviewTab.test.tsx` |
| Create | `frontend/app/(dashboard)/backtest-deployments/[deploymentId]/page.tsx` |

---

## Task 1: Update hooks — add `refreshInterval` config + `useBacktestDeployments`

**Files:**
- Modify: `frontend/lib/hooks/useApi.ts`

- [ ] **Step 1.1: Update `useDeployment` to accept optional `refreshInterval`**

Replace lines 181–183 in `useApi.ts`:

```ts
export function useDeployment(id: string | undefined, config?: { refreshInterval?: number }) {
  return useApiGet<Deployment>(id ? `/api/v1/deployments/${id}` : null, {
    refreshInterval: config?.refreshInterval ?? 2000,
  });
}
```

- [ ] **Step 1.2: Update `useDeploymentTrades` to accept optional `refreshInterval`**

Replace lines 228–233 in `useApi.ts`:

```ts
export function useDeploymentTrades(id: string | undefined, offset = 0, limit = 50, config?: { refreshInterval?: number }) {
  return useApiGet<TradesResponse>(
    id ? `/api/v1/deployments/${id}/trades?offset=${offset}&limit=${limit}` : null,
    { refreshInterval: config?.refreshInterval ?? 5000 }
  );
}
```

- [ ] **Step 1.3: Add `useBacktestDeployments` hook**

Append after `useDeployment` in `useApi.ts`:

```ts
export function useBacktestDeployments() {
  const { data, ...rest } = useApiGet<Deployment[]>("/api/v1/deployments?mode=backtest");
  const hasActive = (data ?? []).some(
    (d) => d.status === "running" || d.status === "pending"
  );
  const { data: polled, ...polledRest } = useApiGet<Deployment[]>(
    "/api/v1/deployments?mode=backtest",
    { refreshInterval: hasActive ? 5000 : 0 }
  );
  // Use SWR deduplication — both calls share the same key so only one request fires.
  // The second call controls the refresh interval dynamically.
  return { data: polled ?? data, ...polledRest };
}
```

> Note: SWR deduplicates requests with the same key. The pattern above lets us start with no interval and switch to 5s once we know active deployments exist. A simpler alternative: always poll at 5s and accept the minor overhead for fully-terminal lists.

**Simpler implementation (recommended):**

```ts
export function useBacktestDeployments() {
  const { data, ...rest } = useApiGet<Deployment[]>("/api/v1/deployments?mode=backtest", {
    refreshInterval: 5000,
  });
  // Stop polling once all deployments are terminal
  const allTerminal = (data ?? []).every(
    (d) => d.status === "completed" || d.status === "failed" || d.status === "stopped"
  );
  return {
    data,
    ...rest,
    // Callers can read allTerminal to conditionally disable polling via mutate
    allTerminal,
  };
}
```

Use the simpler version.

- [ ] **Step 1.4: Also add `usePaperDeployments` helper** (needed for promote button check on detail page)

```ts
export function usePaperDeployments() {
  return useApiGet<Deployment[]>("/api/v1/deployments?mode=paper");
}
```

- [ ] **Step 1.5: Verify no TypeScript errors**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors related to changed hooks

- [ ] **Step 1.6: Commit**

```bash
git add frontend/lib/hooks/useApi.ts
git commit -m "feat: add useBacktestDeployments, usePaperDeployments; make refreshInterval configurable on useDeployment and useDeploymentTrades"
```

---

## Task 2: Update `TradeHistoryTable` — add `refreshInterval` prop

**Files:**
- Modify: `frontend/components/live-trading/TradeHistoryTable.tsx`

- [ ] **Step 2.1: Add `refreshInterval` prop**

Replace the `Props` interface and component signature:

```tsx
interface Props {
  deploymentId: string;
  refreshInterval?: number;
}

export function TradeHistoryTable({ deploymentId, refreshInterval = 5000 }: Props) {
  const [offset, setOffset] = useState(0);
  const { data } = useDeploymentTrades(deploymentId, offset, PAGE_SIZE, { refreshInterval });
  // ... rest unchanged
```

- [ ] **Step 2.2: Verify TypeScript**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 2.3: Commit**

```bash
git add frontend/components/live-trading/TradeHistoryTable.tsx
git commit -m "feat: add optional refreshInterval prop to TradeHistoryTable"
```

---

## Task 3: Update `Sidebar` — add Backtest Deployments nav item

**Files:**
- Modify: `frontend/components/layout/Sidebar.tsx`
- Modify: `frontend/__tests__/components/Sidebar.test.tsx`

- [ ] **Step 3.1: Write the failing test first**

In `frontend/__tests__/components/Sidebar.test.tsx`, add to the existing `describe("Sidebar")` block:

```tsx
it("renders Backtest Deployments nav item", () => {
  wrap(<Sidebar />);
  expect(screen.getByText("Backtest Deployments")).toBeInTheDocument();
});
```

- [ ] **Step 3.2: Run test to verify it fails**

Run: `cd frontend && npx jest __tests__/components/Sidebar.test.tsx -t "Backtest Deployments"`
Expected: FAIL — "Unable to find an element with the text: Backtest Deployments"

- [ ] **Step 3.3: Add `MdQueryStats` import to `Sidebar.tsx`**

Replace the import block (lines 5–18):

```tsx
import {
  MdDashboard,
  MdShowChart,
  MdWebhook,
  MdAccountBalance,
  MdPlayArrow,
  MdHistory,
  MdAnalytics,
  MdSettings,
  MdCode,
  MdTrendingUp,
  MdQueryStats,
  MdChevronLeft,
  MdChevronRight,
} from "react-icons/md";
```

- [ ] **Step 3.4: Add nav item to `NAV_ITEMS`**

Insert after Paper Trading (index 6, line 28):

```tsx
{ icon: MdQueryStats, label: "Backtest Deployments", href: "/backtest-deployments" },
```

So `NAV_ITEMS` becomes:

```tsx
const NAV_ITEMS = [
  { icon: MdDashboard, label: "Dashboard", href: "/" },
  { icon: MdShowChart, label: "Webhook Strategies", href: "/strategies" },
  { icon: MdCode, label: "Hosted Strategies", href: "/strategies/hosted" },
  { icon: MdTrendingUp, label: "Live Trading", href: "/live-trading" },
  { icon: MdWebhook, label: "Webhooks", href: "/webhooks" },
  { icon: MdAccountBalance, label: "Brokers", href: "/brokers" },
  { icon: MdPlayArrow, label: "Paper Trading", href: "/paper-trading" },
  { icon: MdQueryStats, label: "Backtest Deployments", href: "/backtest-deployments" },
  { icon: MdHistory, label: "Backtesting", href: "/backtesting" },
  { icon: MdAnalytics, label: "Analytics", href: "/analytics" },
  { icon: MdSettings, label: "Settings", href: "/settings" },
];
```

- [ ] **Step 3.5: Run test to verify it passes**

Run: `cd frontend && npx jest __tests__/components/Sidebar.test.tsx`
Expected: all tests PASS

- [ ] **Step 3.6: Commit**

```bash
git add frontend/components/layout/Sidebar.tsx frontend/__tests__/components/Sidebar.test.tsx
git commit -m "feat: add Backtest Deployments nav item to sidebar"
```

---

## Task 4: Create `SparklineChart` component

**Files:**
- Create: `frontend/components/backtest-deployments/SparklineChart.tsx`
- Create: `frontend/__tests__/components/SparklineChart.test.tsx`

- [ ] **Step 4.1: Write the failing tests**

Create `frontend/__tests__/components/SparklineChart.test.tsx`:

```tsx
import { render } from "@testing-library/react";
import { SparklineChart } from "@/components/backtest-deployments/SparklineChart";

const points = [
  { timestamp: "2024-01-01T00:00:00Z", equity: 100000 },
  { timestamp: "2024-01-02T00:00:00Z", equity: 102000 },
  { timestamp: "2024-01-03T00:00:00Z", equity: 101000 },
  { timestamp: "2024-01-04T00:00:00Z", equity: 105000 },
];

describe("SparklineChart", () => {
  it("renders an SVG element", () => {
    const { container } = render(<SparklineChart data={points} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("renders a flat line when data is empty", () => {
    const { container } = render(<SparklineChart data={[]} />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    // flat line rendered as a path or line element
    expect(svg?.querySelector("path, line")).toBeInTheDocument();
  });

  it("renders a flat line when data is null", () => {
    const { container } = render(<SparklineChart data={null} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("renders with custom width and height", () => {
    const { container } = render(<SparklineChart data={points} width={150} height={40} />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("width", "150");
    expect(svg).toHaveAttribute("height", "40");
  });
});
```

- [ ] **Step 4.2: Run tests to verify they fail**

Run: `cd frontend && npx jest __tests__/components/SparklineChart.test.tsx`
Expected: FAIL — "Cannot find module '@/components/backtest-deployments/SparklineChart'"

- [ ] **Step 4.3: Create `SparklineChart.tsx`**

Create `frontend/components/backtest-deployments/SparklineChart.tsx`:

```tsx
"use client";

interface Point {
  timestamp: string;
  equity: number;
}

interface SparklineChartProps {
  data: Point[] | null | undefined;
  width?: number;
  height?: number;
  color?: string;
}

export function SparklineChart({
  data,
  width = 200,
  height = 40,
  color = "#48BB78",
}: SparklineChartProps) {
  const points = data && data.length > 1 ? data : null;

  if (!points) {
    // Flat line fallback
    const mid = height / 2;
    return (
      <svg width={width} height={height} aria-hidden="true">
        <line x1={0} y1={mid} x2={width} y2={mid} stroke="#4A5568" strokeWidth={1.5} />
      </svg>
    );
  }

  const equities = points.map((p) => p.equity);
  const min = Math.min(...equities);
  const max = Math.max(...equities);
  const range = max - min || 1;
  const pad = 2;

  const toX = (_: Point, i: number) =>
    pad + (i / (points.length - 1)) * (width - pad * 2);
  const toY = (p: Point) =>
    pad + ((max - p.equity) / range) * (height - pad * 2);

  const pathD = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${toX(p, i).toFixed(1)},${toY(p).toFixed(1)}`)
    .join(" ");

  const areaD =
    pathD +
    ` L${(pad + (width - pad * 2)).toFixed(1)},${height} L${pad},${height} Z`;

  const isPositive = equities[equities.length - 1] >= equities[0];
  const lineColor = isPositive ? "#48BB78" : "#FC8181";
  const fillColor = isPositive ? "rgba(72,187,120,0.15)" : "rgba(252,129,129,0.15)";

  return (
    <svg width={width} height={height} aria-hidden="true">
      <path d={areaD} fill={fillColor} stroke="none" />
      <path d={pathD} fill="none" stroke={lineColor} strokeWidth={1.5} strokeLinejoin="round" />
    </svg>
  );
}
```

- [ ] **Step 4.4: Run tests to verify they pass**

Run: `cd frontend && npx jest __tests__/components/SparklineChart.test.tsx`
Expected: all 4 tests PASS

- [ ] **Step 4.5: Commit**

```bash
git add frontend/components/backtest-deployments/SparklineChart.tsx frontend/__tests__/components/SparklineChart.test.tsx
git commit -m "feat: add SparklineChart component with flat-line fallback"
```

---

## Task 5: Create `BacktestDeploymentCard` component

**Files:**
- Create: `frontend/components/backtest-deployments/BacktestDeploymentCard.tsx`
- Create: `frontend/__tests__/components/BacktestDeploymentCard.test.tsx`

- [ ] **Step 5.1: Write the failing tests**

Create `frontend/__tests__/components/BacktestDeploymentCard.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { BacktestDeploymentCard } from "@/components/backtest-deployments/BacktestDeploymentCard";
import type { Deployment, DeploymentResult } from "@/lib/api/types";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

const baseDeployment: Deployment = {
  id: "dep-1",
  strategy_name: "momentum_v2",
  strategy_code_id: "sc-1",
  strategy_code_version_id: "scv-1",
  mode: "backtest",
  status: "completed",
  symbol: "NIFTY50",
  exchange: "NSE",
  product_type: "MIS",
  interval: "15m",
  broker_connection_id: null,
  cron_expression: null,
  config: {},
  params: {},
  promoted_from_id: null,
  created_at: "2024-04-03T10:00:00Z",
  started_at: "2024-04-03T10:01:00Z",
  stopped_at: "2024-04-03T11:00:00Z",
};

const completedResult: DeploymentResult = {
  id: "res-1",
  deployment_id: "dep-1",
  trade_log: null,
  equity_curve: [
    { timestamp: "2024-04-03T10:00:00Z", equity: 100000 },
    { timestamp: "2024-04-03T11:00:00Z", equity: 118400 },
  ],
  metrics: {
    total_return: 18.4,
    win_rate: 64,
    profit_factor: 2.1,
    sharpe_ratio: 1.8,
    max_drawdown: -7.2,
    total_trades: 42,
    avg_trade_pnl: 438,
  },
  status: "completed",
  created_at: "2024-04-03T10:00:00Z",
  completed_at: "2024-04-03T11:00:00Z",
};

const wrap = (ui: React.ReactElement) => render(<ChakraProvider>{ui}</ChakraProvider>);

describe("BacktestDeploymentCard", () => {
  it("renders strategy name and symbol", () => {
    wrap(<BacktestDeploymentCard deployment={baseDeployment} result={null} isPromoted={false} onPromote={jest.fn()} />);
    expect(screen.getByText("momentum_v2")).toBeInTheDocument();
    expect(screen.getByText(/NIFTY50/)).toBeInTheDocument();
  });

  it("shows metrics for completed deployment", () => {
    wrap(<BacktestDeploymentCard deployment={baseDeployment} result={completedResult} isPromoted={false} onPromote={jest.fn()} />);
    expect(screen.getByText(/18.4/)).toBeInTheDocument();
    expect(screen.getByText(/64/)).toBeInTheDocument();
  });

  it("shows Promote button when completed and not promoted", () => {
    wrap(<BacktestDeploymentCard deployment={baseDeployment} result={completedResult} isPromoted={false} onPromote={jest.fn()} />);
    expect(screen.getByRole("button", { name: /promote/i })).toBeInTheDocument();
  });

  it("hides Promote button when already promoted", () => {
    wrap(<BacktestDeploymentCard deployment={baseDeployment} result={completedResult} isPromoted={true} onPromote={jest.fn()} />);
    expect(screen.queryByRole("button", { name: /promote/i })).not.toBeInTheDocument();
    expect(screen.getByText(/promoted/i)).toBeInTheDocument();
  });

  it("shows View Logs text for failed deployment", () => {
    const failed = { ...baseDeployment, status: "failed" as const };
    wrap(<BacktestDeploymentCard deployment={failed} result={null} isPromoted={false} onPromote={jest.fn()} />);
    expect(screen.getByText(/view logs/i)).toBeInTheDocument();
  });

  it("shows dashes for metrics when running", () => {
    const running = { ...baseDeployment, status: "running" as const };
    wrap(<BacktestDeploymentCard deployment={running} result={null} isPromoted={false} onPromote={jest.fn()} />);
    // metrics should be em-dashes
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 5.2: Run tests to verify they fail**

Run: `cd frontend && npx jest __tests__/components/BacktestDeploymentCard.test.tsx`
Expected: FAIL — "Cannot find module '@/components/backtest-deployments/BacktestDeploymentCard'"

- [ ] **Step 5.3: Create `BacktestDeploymentCard.tsx`**

Create `frontend/components/backtest-deployments/BacktestDeploymentCard.tsx`:

```tsx
"use client";
import {
  Box, Text, HStack, VStack, Badge, Button, Skeleton, useColorModeValue, Flex,
} from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { SparklineChart } from "./SparklineChart";
import type { Deployment, DeploymentResult } from "@/lib/api/types";

interface Props {
  deployment: Deployment;
  result: DeploymentResult | null | undefined;
  isPromoted: boolean;
  onPromote: (id: string) => void;
  isPromoting?: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  running: "yellow",
  pending: "gray",
  completed: "green",
  failed: "red",
  stopped: "red",
};

function MetricTile({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <Box textAlign="center">
      <Text fontSize="9px" color="gray.500" textTransform="uppercase" letterSpacing="wide">
        {label}
      </Text>
      <Text fontSize="sm" fontWeight="bold" color={color ?? "inherit"}>
        {value}
      </Text>
    </Box>
  );
}

export function BacktestDeploymentCard({
  deployment,
  result,
  isPromoted,
  onPromote,
  isPromoting = false,
}: Props) {
  const router = useRouter();
  const bg = useColorModeValue("white", "gray.700");
  const borderColor = useColorModeValue("gray.200", "gray.600");
  const isCompleted = deployment.status === "completed";
  const isFailed = deployment.status === "failed" || deployment.status === "stopped";
  const metrics = result?.metrics;

  const returnColor =
    metrics == null
      ? "gray.500"
      : metrics.total_return >= 0
      ? "green.400"
      : "red.400";

  return (
    <Box
      p={4}
      bg={bg}
      borderWidth="1px"
      borderColor={borderColor}
      borderRadius="md"
      cursor="pointer"
      _hover={{ shadow: "md" }}
      onClick={() => router.push(`/backtest-deployments/${deployment.id}`)}
    >
      <VStack align="stretch" spacing={3}>
        {/* Header */}
        <Flex justify="space-between" align="flex-start">
          <Box>
            <Text fontWeight="bold" fontSize="sm" noOfLines={1}>
              {deployment.strategy_name}
            </Text>
            <Text fontSize="xs" color="gray.500">
              {deployment.symbol} · {deployment.exchange} · {deployment.interval}
            </Text>
          </Box>
          <Badge colorScheme={STATUS_COLORS[deployment.status] ?? "gray"} variant="solid" fontSize="xs">
            {deployment.status}
          </Badge>
        </Flex>

        {/* Sparkline */}
        {isCompleted && (
          <Box>
            {result === undefined ? (
              <Skeleton height="40px" borderRadius="sm" />
            ) : (
              <SparklineChart data={result?.equity_curve ?? null} width={220} height={40} />
            )}
          </Box>
        )}

        {/* Metrics */}
        {isFailed ? (
          <Text fontSize="xs" color="red.400">
            View Logs →
          </Text>
        ) : (
          <HStack justify="space-between">
            <MetricTile
              label="Return"
              value={metrics != null ? `${metrics.total_return >= 0 ? "+" : ""}${metrics.total_return.toFixed(1)}%` : "—"}
              color={returnColor}
            />
            <MetricTile
              label="Win Rate"
              value={metrics != null ? `${metrics.win_rate.toFixed(0)}%` : "—"}
            />
            <MetricTile
              label="Max DD"
              value={metrics != null ? `${metrics.max_drawdown.toFixed(1)}%` : "—"}
              color={metrics != null ? "red.400" : undefined}
            />
            <MetricTile
              label="Trades"
              value={metrics != null ? String(metrics.total_trades) : "—"}
            />
          </HStack>
        )}

        {/* Promote / Promoted */}
        {isCompleted && (
          <Box onClick={(e) => e.stopPropagation()}>
            {isPromoted ? (
              <Text fontSize="xs" color="blue.400">
                ✓ Promoted to Paper
              </Text>
            ) : (
              <Button
                size="xs"
                colorScheme="blue"
                variant="outline"
                isLoading={isPromoting}
                onClick={() => onPromote(deployment.id)}
                width="full"
              >
                Promote to Paper →
              </Button>
            )}
          </Box>
        )}
      </VStack>
    </Box>
  );
}
```

- [ ] **Step 5.4: Run tests to verify they pass**

Run: `cd frontend && npx jest __tests__/components/BacktestDeploymentCard.test.tsx`
Expected: all 6 tests PASS

- [ ] **Step 5.5: Commit**

```bash
git add frontend/components/backtest-deployments/BacktestDeploymentCard.tsx frontend/__tests__/components/BacktestDeploymentCard.test.tsx
git commit -m "feat: add BacktestDeploymentCard with sparkline, metrics, and promote action"
```

---

## Task 6: Create the List Page

**Files:**
- Create: `frontend/app/(dashboard)/backtest-deployments/page.tsx`

- [ ] **Step 6.1: Create the directory and page file**

Create `frontend/app/(dashboard)/backtest-deployments/page.tsx`:

```tsx
"use client";
import { Box, Heading, SimpleGrid, Spinner, Center } from "@chakra-ui/react";
import { useState } from "react";
import { useBacktestDeployments, useDeploymentResults, usePaperDeployments } from "@/lib/hooks/useApi";
import { BacktestDeploymentCard } from "@/components/backtest-deployments/BacktestDeploymentCard";
import { EmptyState } from "@/components/shared/EmptyState";
import { apiClient } from "@/lib/api/client";
import { useRouter } from "next/navigation";
import type { Deployment, DeploymentResult } from "@/lib/api/types";

const MAX_SPARKLINES = 10;

function CardWithResult({
  deployment,
  paperDeployments,
  onPromote,
  promotingId,
  index,
}: {
  deployment: Deployment;
  paperDeployments: Deployment[];
  onPromote: (id: string) => void;
  promotingId: string | null;
  index: number;
}) {
  // Only fetch results for the first MAX_SPARKLINES completed deployments
  const shouldFetch = deployment.status === "completed" && index < MAX_SPARKLINES;
  const { data: result } = useDeploymentResults(shouldFetch ? deployment.id : undefined);
  const isPromoted = paperDeployments.some((p) => p.promoted_from_id === deployment.id);

  return (
    <BacktestDeploymentCard
      deployment={deployment}
      result={shouldFetch ? result : null}
      isPromoted={isPromoted}
      onPromote={onPromote}
      isPromoting={promotingId === deployment.id}
    />
  );
}

export default function BacktestDeploymentsPage() {
  const { data: deployments, isLoading, mutate } = useBacktestDeployments();
  const { data: paperDeployments = [] } = usePaperDeployments();
  const [promotingId, setPromotingId] = useState<string | null>(null);
  const router = useRouter();

  const handlePromote = async (id: string) => {
    setPromotingId(id);
    try {
      await apiClient(`/api/v1/deployments/${id}/promote`, { method: "POST" });
      mutate();
      router.push("/paper-trading");
    } finally {
      setPromotingId(null);
    }
  };

  if (isLoading) {
    return (
      <Center h="40vh">
        <Spinner size="lg" />
      </Center>
    );
  }

  return (
    <Box p={6}>
      <Heading size="lg" mb={6}>
        Backtest Deployments
      </Heading>

      {!deployments || deployments.length === 0 ? (
        <EmptyState
          title="No backtest deployments yet"
          description="Deploy a hosted strategy as a backtest to see results here."
          actionLabel="Go to Strategies"
          onAction={() => router.push("/strategies/hosted")}
        />
      ) : (
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
          {deployments.map((dep, i) => (
            <CardWithResult
              key={dep.id}
              deployment={dep}
              paperDeployments={paperDeployments}
              onPromote={handlePromote}
              promotingId={promotingId}
              index={i}
            />
          ))}
        </SimpleGrid>
      )}
    </Box>
  );
}
```

- [ ] **Step 6.2: Verify TypeScript**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 6.3: Commit**

```bash
git add frontend/app/(dashboard)/backtest-deployments/page.tsx
git commit -m "feat: add backtest deployments list page"
```

---

## Task 7: Create `BacktestOverviewTab` component

**Files:**
- Create: `frontend/components/backtest-deployments/BacktestOverviewTab.tsx`
- Create: `frontend/__tests__/components/BacktestOverviewTab.test.tsx`

- [ ] **Step 7.1: Write the failing tests**

Create `frontend/__tests__/components/BacktestOverviewTab.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { BacktestOverviewTab } from "@/components/backtest-deployments/BacktestOverviewTab";
import type { DeploymentResult } from "@/lib/api/types";

const result: DeploymentResult = {
  id: "res-1",
  deployment_id: "dep-1",
  trade_log: null,
  equity_curve: [
    { timestamp: "2024-04-03T10:00:00Z", equity: 100000 },
    { timestamp: "2024-04-03T11:00:00Z", equity: 118400 },
  ],
  metrics: {
    total_return: 18.4,
    win_rate: 64,
    profit_factor: 2.1,
    sharpe_ratio: 1.8,
    max_drawdown: -7.2,
    total_trades: 42,
    avg_trade_pnl: 438,
  },
  status: "completed",
  created_at: "2024-04-03T10:00:00Z",
  completed_at: "2024-04-03T11:00:00Z",
};

const wrap = (ui: React.ReactElement) => render(<ChakraProvider>{ui}</ChakraProvider>);

describe("BacktestOverviewTab", () => {
  it("shows in-progress placeholder when status is running", () => {
    wrap(<BacktestOverviewTab result={null} deploymentStatus="running" />);
    expect(screen.getByText(/in progress/i)).toBeInTheDocument();
  });

  it("shows queued placeholder when status is pending", () => {
    wrap(<BacktestOverviewTab result={null} deploymentStatus="pending" />);
    expect(screen.getByText(/queued/i)).toBeInTheDocument();
  });

  it("renders metrics when result is provided", () => {
    wrap(<BacktestOverviewTab result={result} deploymentStatus="completed" />);
    expect(screen.getByText(/profit factor/i)).toBeInTheDocument();
    expect(screen.getByText("2.1")).toBeInTheDocument();
    expect(screen.getByText(/avg trade/i)).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });
});
```

- [ ] **Step 7.2: Run tests to verify they fail**

Run: `cd frontend && npx jest __tests__/components/BacktestOverviewTab.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 7.3: Create `BacktestOverviewTab.tsx`**

Create `frontend/components/backtest-deployments/BacktestOverviewTab.tsx`:

```tsx
"use client";
import { Box, SimpleGrid, Text, Flex, Skeleton } from "@chakra-ui/react";
import { EquityCurve } from "@/components/charts/EquityCurve";
import type { DeploymentResult } from "@/lib/api/types";

interface Props {
  result: DeploymentResult | null | undefined;
  deploymentStatus: string;
}

function MetricRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <Flex justify="space-between" py={2} borderBottomWidth="1px" borderColor="gray.700">
      <Text fontSize="sm" color="gray.400">
        {label}
      </Text>
      <Text fontSize="sm" fontWeight="semibold" color={color}>
        {value}
      </Text>
    </Flex>
  );
}

export function BacktestOverviewTab({ result, deploymentStatus }: Props) {
  if (deploymentStatus === "pending") {
    return (
      <Flex align="center" justify="center" h="200px">
        <Text color="gray.500">Queued — backtest has not started yet</Text>
      </Flex>
    );
  }

  if (deploymentStatus === "running" || !result) {
    return (
      <Flex align="center" justify="center" h="200px">
        <Text color="gray.500">Backtest in progress…</Text>
      </Flex>
    );
  }

  const m = result.metrics;
  const equityCurveData = (result.equity_curve ?? []).map((p) => ({
    time: p.timestamp,
    value: p.equity,
  }));

  return (
    <Box>
      {/* Equity Curve */}
      <Box mb={6}>
        <Text fontSize="sm" fontWeight="semibold" mb={2}>
          Equity Curve
        </Text>
        {equityCurveData.length > 1 ? (
          <EquityCurve data={equityCurveData} height={220} />
        ) : (
          <Flex h="220px" align="center" justify="center">
            <Text color="gray.500" fontSize="sm">
              No equity curve data
            </Text>
          </Flex>
        )}
      </Box>

      {/* Extended Metrics */}
      {m && (
        <Box>
          <Text fontSize="sm" fontWeight="semibold" mb={2}>
            Performance Metrics
          </Text>
          <MetricRow
            label="Profit Factor"
            value={m.profit_factor.toFixed(2)}
            color={m.profit_factor >= 1 ? "green.400" : "red.400"}
          />
          <MetricRow
            label="Avg Trade P&L"
            value={`${m.avg_trade_pnl >= 0 ? "+" : ""}₹${m.avg_trade_pnl.toFixed(2)}`}
            color={m.avg_trade_pnl >= 0 ? "green.400" : "red.400"}
          />
          <MetricRow label="Total Trades" value={String(m.total_trades)} />
        </Box>
      )}
    </Box>
  );
}
```

- [ ] **Step 7.4: Run tests to verify they pass**

Run: `cd frontend && npx jest __tests__/components/BacktestOverviewTab.test.tsx`
Expected: all 3 tests PASS

- [ ] **Step 7.5: Commit**

```bash
git add frontend/components/backtest-deployments/BacktestOverviewTab.tsx frontend/__tests__/components/BacktestOverviewTab.test.tsx
git commit -m "feat: add BacktestOverviewTab with equity curve and extended metrics"
```

---

## Task 8: Create the Detail Page

**Files:**
- Create: `frontend/app/(dashboard)/backtest-deployments/[deploymentId]/page.tsx`

- [ ] **Step 8.1: Create the directory and page file**

Create `frontend/app/(dashboard)/backtest-deployments/[deploymentId]/page.tsx`:

```tsx
"use client";
import {
  Box, Heading, HStack, VStack, Text, Badge, Button, Flex,
  Tabs, TabList, Tab, TabPanels, TabPanel,
  SimpleGrid, Skeleton, Spinner, Center, Link,
} from "@chakra-ui/react";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import {
  useDeployment,
  useDeploymentResults,
  usePaperDeployments,
} from "@/lib/hooks/useApi";
import { DeploymentBadge } from "@/components/shared/DeploymentBadge";
import { TradeHistoryTable } from "@/components/live-trading/TradeHistoryTable";
import { LogViewer } from "@/components/shared/LogViewer";
import { BacktestOverviewTab } from "@/components/backtest-deployments/BacktestOverviewTab";
import { apiClient } from "@/lib/api/client";

const STATUS_COLORS: Record<string, string> = {
  completed: "green",
  running: "yellow",
  failed: "red",
  stopped: "red",
  pending: "gray",
};

function StatTile({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <Box p={4} borderWidth="1px" borderRadius="md" textAlign="center">
      <Text fontSize="xs" color="gray.500" textTransform="uppercase" mb={1}>
        {label}
      </Text>
      <Text fontSize="xl" fontWeight="bold" color={color}>
        {value}
      </Text>
    </Box>
  );
}

export default function BacktestDetailPage() {
  const { deploymentId } = useParams<{ deploymentId: string }>();
  const router = useRouter();
  const [isPromoting, setIsPromoting] = useState(false);

  // Initial fetch — no polling (used to detect 404 and terminal state)
  const { data: deployment, error: deploymentError } = useDeployment(deploymentId, { refreshInterval: 0 });
  const isActive = deployment?.status === "running" || deployment?.status === "pending";
  const { data: deploymentLive } = useDeployment(
    isActive ? deploymentId : undefined,
    { refreshInterval: 2000 }
  );
  const dep = deploymentLive ?? deployment;

  const { data: result } = useDeploymentResults(deploymentId);
  const { data: paperDeployments = [], mutate: refreshPaper } = usePaperDeployments();

  const promotedPaperDep = paperDeployments.find((p) => p.promoted_from_id === deploymentId);
  const canPromote = dep?.status === "completed" && !promotedPaperDep;

  // Default to Logs tab for failed/stopped
  const defaultTab =
    dep?.status === "failed" || dep?.status === "stopped" ? 2 : 0;

  const handlePromote = async () => {
    setIsPromoting(true);
    try {
      await apiClient(`/api/v1/deployments/${deploymentId}/promote`, { method: "POST" });
      await refreshPaper();
      router.push("/paper-trading");
    } finally {
      setIsPromoting(false);
    }
  };

  const m = result?.metrics;

  // Loading state (hook not yet resolved)
  if (!dep && !deploymentError) {
    return (
      <Box p={6}>
        <Skeleton height="40px" mb={4} />
        <SimpleGrid columns={4} spacing={4} mb={6}>
          {[...Array(4)].map((_, i) => <Skeleton key={i} height="80px" borderRadius="md" />)}
        </SimpleGrid>
        <Skeleton height="400px" borderRadius="md" />
      </Box>
    );
  }

  // 404 / error state
  if (!dep) {
    return (
      <Box p={6}>
        <Text color="gray.500" mb={4}>Deployment not found.</Text>
        <Button size="sm" onClick={() => router.push("/backtest-deployments")}>
          ← Back to Backtest Deployments
        </Button>
      </Box>
    );
  }

  return (
    <Box p={6}>
      {/* Header */}
      <HStack justify="space-between" mb={6} flexWrap="wrap" gap={3}>
        <HStack spacing={3}>
          <Heading size="md">{dep.strategy_name}</Heading>
          <DeploymentBadge mode={dep.mode} status={dep.status} />
        </HStack>
        <HStack>
          {canPromote && (
            <Button
              size="sm"
              colorScheme="blue"
              isLoading={isPromoting}
              onClick={handlePromote}
            >
              Promote to Paper →
            </Button>
          )}
          {promotedPaperDep && (
            <Button
              size="sm"
              variant="ghost"
              colorScheme="blue"
              onClick={() => router.push(`/paper-trading/${promotedPaperDep.id}`)}
            >
              ✓ Promoted to Paper →
            </Button>
          )}
        </HStack>
      </HStack>

      <Text fontSize="sm" color="gray.500" mb={6}>
        {dep.symbol} · {dep.exchange} · {dep.interval}
      </Text>

      {/* Metrics row */}
      <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4} mb={8}>
        <StatTile
          label="Return"
          value={m != null ? `${m.total_return >= 0 ? "+" : ""}${m.total_return.toFixed(1)}%` : "—"}
          color={m != null ? (m.total_return >= 0 ? "green.400" : "red.400") : "gray.500"}
        />
        <StatTile
          label="Win Rate"
          value={m != null ? `${m.win_rate.toFixed(0)}%` : "—"}
        />
        <StatTile
          label="Max Drawdown"
          value={m != null ? `${m.max_drawdown.toFixed(1)}%` : "—"}
          color={m != null ? "red.400" : "gray.500"}
        />
        <StatTile
          label="Sharpe Ratio"
          value={m != null ? m.sharpe_ratio.toFixed(2) : "—"}
          color={m != null ? (m.sharpe_ratio >= 1 ? "green.400" : "orange.400") : "gray.500"}
        />
      </SimpleGrid>

      {/* Tabs */}
      <Tabs size="sm" variant="enclosed" defaultIndex={defaultTab}>
        <TabList>
          <Tab>Overview</Tab>
          <Tab>Trades</Tab>
          <Tab>Logs</Tab>
        </TabList>
        <TabPanels>
          <TabPanel>
            <BacktestOverviewTab result={result ?? null} deploymentStatus={dep.status} />
          </TabPanel>
          <TabPanel>
            {dep.status === "pending" ? (
              <Flex align="center" justify="center" h="200px">
                <Text color="gray.500">Queued — no trades yet</Text>
              </Flex>
            ) : (
              <TradeHistoryTable
                deploymentId={deploymentId}
                refreshInterval={isActive ? 5000 : 0}
              />
            )}
          </TabPanel>
          <TabPanel>
            <LogViewer deploymentId={deploymentId} />
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Box>
  );
}
```

- [ ] **Step 8.2: Verify TypeScript**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 8.3: Run full test suite to confirm no regressions**

Run: `cd frontend && npx jest --passWithNoTests`
Expected: all tests PASS

- [ ] **Step 8.4: Commit**

```bash
git add frontend/app/(dashboard)/backtest-deployments/[deploymentId]/page.tsx
git commit -m "feat: add backtest deployment detail page with metrics, equity curve, trades, and logs"
```

---

## Task 9: Final verification

- [ ] **Step 9.1: Run full TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit 0, no errors

- [ ] **Step 9.2: Run all tests**

Run: `cd frontend && npx jest`
Expected: all tests PASS including the updated Sidebar test

- [ ] **Step 9.3: Final commit**

```bash
git add -A
git commit -m "feat: complete backtest deployments UI — list page, detail page, nav item"
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `lib/hooks/useApi.ts` | Add `useBacktestDeployments`, `usePaperDeployments`; make `useDeployment` + `useDeploymentTrades` accept optional `refreshInterval` |
| `components/live-trading/TradeHistoryTable.tsx` | Add optional `refreshInterval` prop (default 5000) |
| `components/layout/Sidebar.tsx` | Add `MdQueryStats` import + Backtest Deployments nav item |
| `__tests__/components/Sidebar.test.tsx` | Add assertion for Backtest Deployments nav item |
| `components/backtest-deployments/SparklineChart.tsx` | New — SVG sparkline, flat-line fallback |
| `components/backtest-deployments/BacktestDeploymentCard.tsx` | New — card with sparkline, metrics, promote button |
| `components/backtest-deployments/BacktestOverviewTab.tsx` | New — equity curve + extended metrics |
| `app/(dashboard)/backtest-deployments/page.tsx` | New — list page |
| `app/(dashboard)/backtest-deployments/[deploymentId]/page.tsx` | New — detail page |
