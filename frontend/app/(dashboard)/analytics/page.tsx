"use client";
import {
  Box, Heading, SimpleGrid, useColorModeValue,
} from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { StatCard } from "@/components/shared/StatCard";
import { DataTable, Column } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { EquityCurve } from "@/components/charts/EquityCurve";
import { ChartContainer } from "@/components/charts/ChartContainer";
import { useAnalyticsOverview, useStrategies } from "@/lib/hooks/useApi";
import { formatCurrency } from "@/lib/utils/formatters";

type Strategy = {
  id: string;
  name: string;
  mode: string;
  is_active: boolean;
  [key: string]: unknown;
};

const strategyColumns: Column<Strategy>[] = [
  { key: "name", header: "Name", sortable: true },
  { key: "mode", header: "Mode" },
  {
    key: "is_active",
    header: "Active",
    render: (v) => (
      <StatusBadge
        variant={v ? "success" : "neutral"}
        text={v ? "Active" : "Inactive"}
      />
    ),
  },
];

export default function AnalyticsPage() {
  const router = useRouter();
  const cardBg = useColorModeValue("white", "gray.800");

  const { data: overview, isLoading: overviewLoading } = useAnalyticsOverview();
  const { data: strategies, isLoading: strategiesLoading } = useStrategies();

  return (
    <Box>
      <Heading size="lg" mb={6}>
        Portfolio Overview
      </Heading>

      {/* Row 1: Stat Cards */}
      <SimpleGrid columns={{ base: 1, sm: 2, lg: 3, xl: 6 }} spacing={4} mb={6}>
        <StatCard
          label="Total P&L"
          value={overviewLoading ? "..." : formatCurrency(overview?.total_pnl ?? 0)}
        />
        <StatCard
          label="Active Strategies"
          value={overviewLoading ? "..." : String(overview?.active_strategies ?? 0)}
        />
        <StatCard
          label="Open Positions"
          value={overviewLoading ? "..." : String(overview?.open_positions ?? 0)}
        />
        <StatCard
          label="Trades Today"
          value={overviewLoading ? "..." : String(overview?.trades_today ?? 0)}
        />
        <StatCard label="Win Rate" value={"—"} />
        <StatCard label="Max Drawdown" value={"—"} />
      </SimpleGrid>

      {/* Row 2: Portfolio Equity Curve */}
      <Box bg={cardBg} p={4} borderRadius="lg" shadow="sm" mb={6}>
        <Heading size="sm" mb={2}>
          Portfolio Equity Curve
        </Heading>
        <ChartContainer height={300} isLoading={overviewLoading}>
          {() => <EquityCurve data={[]} height={300} />}
        </ChartContainer>
      </Box>

      {/* Row 3: Strategy Comparison Table */}
      <Box bg={cardBg} p={4} borderRadius="lg" shadow="sm">
        <Heading size="sm" mb={3}>
          Strategy Comparison
        </Heading>
        <DataTable<Strategy>
          columns={strategyColumns}
          data={(strategies ?? []) as Strategy[]}
          isLoading={strategiesLoading}
          emptyMessage="No strategies yet"
          onRowClick={(row) => router.push(`/analytics/strategies/${row.id}`)}
        />
      </Box>
    </Box>
  );
}
