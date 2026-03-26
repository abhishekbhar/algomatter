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
import type { AnalyticsTrade, EquityCurvePoint } from "@/lib/api/types";

const tradeColumns: Column<AnalyticsTrade>[] = [
  { key: "symbol", header: "Symbol", sortable: true },
  { key: "action", header: "Action" },
  { key: "quantity", header: "Qty", sortable: true },
  {
    key: "fill_price",
    header: "Fill Price",
    sortable: true,
    render: (v) => (v != null ? formatCurrency(Number(v)) : "\u2014"),
  },
  {
    key: "pnl",
    header: "P&L",
    sortable: true,
    render: (v) => formatCurrency(Number(v ?? 0)),
  },
  { key: "status", header: "Status" },
  { key: "timestamp", header: "Time", sortable: true },
];

function escapeCsvField(value: string): string {
  if (value.includes(",") || value.includes('"') || value.includes("\n")) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

export default function StrategyDrilldownPage() {
  const params = useParams();
  const id = params.id as string;
  const cardBg = useColorModeValue("white", "gray.800");

  const { data: strategy } = useStrategy(id);
  const { data: metrics, isLoading: metricsLoading } = useStrategyMetrics(id);
  const { data: equityData, isLoading: equityLoading } = useStrategyEquityCurve(id);
  const { data: trades, isLoading: tradesLoading } = useStrategyTrades(id);

  const strategyName = strategy?.name ?? "Strategy";

  const chartData = (equityData ?? []).map((d: EquityCurvePoint) => ({
    time: d.timestamp.split("T")[0],
    value: d.equity,
  }));

  const drawdownData = (equityData ?? []).map((d: EquityCurvePoint) => ({
    time: d.timestamp.split("T")[0],
    value: 0, // TODO: compute drawdown from equity curve
  }));

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
        headers.map(escapeCsvField).join(","),
        ...data.map((row: Record<string, unknown>) =>
          headers.map((h) => escapeCsvField(String(row[h] ?? ""))).join(",")
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
      // CSV export failed — no user-facing action needed
    }
  };

  return (
    <Box>
      <Heading size="lg" mb={6}>
        {strategyName}
      </Heading>

      {/* Row 1: Metric Stat Cards */}
      <SimpleGrid columns={{ base: 1, sm: 2, lg: 3, xl: 6 }} spacing={4} mb={6}>
        <StatCard
          label="Total Return"
          value={metricsLoading ? "..." : formatCurrency(metrics?.total_return ?? 0)}
        />
        <StatCard
          label="Win Rate"
          value={metricsLoading ? "..." : formatPercent(metrics?.win_rate ?? 0)}
        />
        <StatCard
          label="Profit Factor"
          value={metricsLoading ? "..." : formatNumber(metrics?.profit_factor ?? 0)}
        />
        <StatCard
          label="Sharpe Ratio"
          value={metricsLoading ? "..." : formatNumber(metrics?.sharpe_ratio ?? 0)}
        />
        <StatCard
          label="Max Drawdown"
          value={metricsLoading ? "..." : formatPercent(metrics?.max_drawdown ?? 0)}
        />
        <StatCard
          label="Total Trades"
          value={metricsLoading ? "..." : formatNumber(metrics?.total_trades ?? 0)}
        />
      </SimpleGrid>

      {/* Row 2: Two-column charts */}
      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6} mb={6}>
        <Box bg={cardBg} p={4} borderRadius="lg" shadow="sm">
          <Heading size="sm" mb={2}>
            Equity Curve
          </Heading>
          <ChartContainer height={300} isLoading={equityLoading}>
            {() => <EquityCurve data={chartData} height={300} />}
          </ChartContainer>
        </Box>

        <Box bg={cardBg} p={4} borderRadius="lg" shadow="sm">
          <Heading size="sm" mb={2}>
            Drawdown
          </Heading>
          <ChartContainer height={300} isLoading={equityLoading}>
            {() => <DrawdownChart data={drawdownData} height={300} />}
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
        <DataTable<AnalyticsTrade>
          columns={tradeColumns}
          data={trades ?? []}
          isLoading={tradesLoading}
          emptyMessage="No trades yet"
        />
      </Box>
    </Box>
  );
}
