"use client";
import { useParams } from "next/navigation";
import {
  Box, Heading, SimpleGrid, Button, useColorModeValue,
} from "@chakra-ui/react";
import { StatCard } from "@/components/shared/StatCard";
import { DataTable, Column } from "@/components/shared/DataTable";
import { EquityCurve } from "@/components/charts/EquityCurve";
import { DrawdownChart } from "@/components/charts/DrawdownChart";
import { ChartContainer } from "@/components/charts/ChartContainer";
import {
  useStrategy,
  useStrategyMetrics,
  useStrategyEquityCurve,
  useStrategyTrades,
} from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { formatCurrency, formatPercent, formatNumber } from "@/lib/utils/formatters";

type Trade = Record<string, unknown>;

const tradeColumns: Column<Trade>[] = [
  { key: "symbol", header: "Symbol", sortable: true },
  { key: "side", header: "Side" },
  { key: "quantity", header: "Qty", sortable: true },
  {
    key: "entry_price",
    header: "Entry",
    sortable: true,
    render: (v) => formatCurrency(Number(v ?? 0)),
  },
  {
    key: "exit_price",
    header: "Exit",
    sortable: true,
    render: (v) => (v != null ? formatCurrency(Number(v)) : "—"),
  },
  {
    key: "pnl",
    header: "P&L",
    sortable: true,
    render: (v) => formatCurrency(Number(v ?? 0)),
  },
  { key: "closed_at", header: "Closed At", sortable: true },
];

export default function StrategyDrilldownPage() {
  const params = useParams();
  const id = params.id as string;
  const cardBg = useColorModeValue("white", "gray.800");

  const { data: strategy } = useStrategy(id);
  const { data: metrics, isLoading: metricsLoading } = useStrategyMetrics(id);
  const { data: equityData, isLoading: equityLoading } = useStrategyEquityCurve(id);
  const { data: trades, isLoading: tradesLoading } = useStrategyTrades(id);

  const m = (metrics ?? {}) as Record<string, unknown>;
  const strategyName = (strategy as Record<string, unknown>)?.name ?? "Strategy";

  const handleExportCsv = async () => {
    try {
      const res = await apiClient<Response>(
        `/api/v1/analytics/strategies/${id}/trades`,
        { rawResponse: true },
      );
      const data = await res.json();
      if (!Array.isArray(data) || data.length === 0) return;

      const headers = Object.keys(data[0]);
      const csv = [
        headers.join(","),
        ...data.map((row: Record<string, unknown>) =>
          headers.map((h) => String(row[h] ?? "")).join(",")
        ),
      ].join("\n");

      const blob = new Blob([csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `trades-${id}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // silently fail
    }
  };

  return (
    <Box>
      <Heading size="lg" mb={6}>
        {String(strategyName)}
      </Heading>

      {/* Row 1: Metric Stat Cards */}
      <SimpleGrid columns={{ base: 1, sm: 2, lg: 3, xl: 6 }} spacing={4} mb={6}>
        <StatCard
          label="Total Return"
          value={metricsLoading ? "..." : formatCurrency(Number(m.total_return ?? 0))}
        />
        <StatCard
          label="Win Rate"
          value={metricsLoading ? "..." : formatPercent(Number(m.win_rate ?? 0))}
        />
        <StatCard
          label="Profit Factor"
          value={metricsLoading ? "..." : formatNumber(Number(m.profit_factor ?? 0))}
        />
        <StatCard
          label="Sharpe Ratio"
          value={metricsLoading ? "..." : formatNumber(Number(m.sharpe_ratio ?? 0))}
        />
        <StatCard
          label="Max Drawdown"
          value={metricsLoading ? "..." : formatPercent(Number(m.max_drawdown ?? 0))}
        />
        <StatCard
          label="Total Trades"
          value={metricsLoading ? "..." : formatNumber(Number(m.total_trades ?? 0))}
        />
      </SimpleGrid>

      {/* Row 2: Two-column charts */}
      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6} mb={6}>
        <Box bg={cardBg} p={4} borderRadius="lg" shadow="sm">
          <Heading size="sm" mb={2}>
            Equity Curve
          </Heading>
          <ChartContainer height={300} isLoading={equityLoading}>
            {() => (
              <EquityCurve
                data={(equityData ?? []).map((d) => ({
                  time: String(d.time ?? ""),
                  value: Number(d.value ?? 0),
                }))}
                height={300}
              />
            )}
          </ChartContainer>
        </Box>

        <Box bg={cardBg} p={4} borderRadius="lg" shadow="sm">
          <Heading size="sm" mb={2}>
            Drawdown
          </Heading>
          <ChartContainer height={300} isLoading={equityLoading}>
            {() => (
              <DrawdownChart
                data={(equityData ?? []).map((d) => ({
                  time: String(d.time ?? ""),
                  value: Number(d.drawdown ?? d.value ?? 0),
                }))}
                height={300}
              />
            )}
          </ChartContainer>
        </Box>
      </SimpleGrid>

      {/* Row 3: Trade Log */}
      <Box bg={cardBg} p={4} borderRadius="lg" shadow="sm">
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Heading size="sm">Trade Log</Heading>
          <Button size="sm" colorScheme="blue" variant="outline" onClick={handleExportCsv}>
            Export CSV
          </Button>
        </Box>
        <DataTable<Trade>
          columns={tradeColumns}
          data={trades ?? []}
          isLoading={tradesLoading}
          emptyMessage="No trades yet"
        />
      </Box>
    </Box>
  );
}
