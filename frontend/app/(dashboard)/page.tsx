"use client";
import {
  Box, Heading, SimpleGrid, Flex, Button, Text, useColorModeValue,
} from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { StatCard } from "@/components/shared/StatCard";
import { DataTable, Column } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { EquityCurve } from "@/components/charts/EquityCurve";
import { ChartContainer } from "@/components/charts/ChartContainer";
import {
  useAnalyticsOverview,
  useWebhookSignals,
  useStrategies,
  usePaperSessions,
} from "@/lib/hooks/useApi";
import { formatCurrency } from "@/lib/utils/formatters";
import type { WebhookSignal } from "@/lib/api/types";

const signalColumns: Column<WebhookSignal>[] = [
  { key: "status", header: "Status",
    render: (v) => {
      const status = String(v ?? "");
      const variant = status === "passed" ? "success" : status === "blocked" ? "error" : "warning";
      return <StatusBadge variant={variant} text={status} />;
    },
  },
  { key: "received_at", header: "Time", sortable: true, render: (v) => {
    if (!v) return "";
    return new Date(String(v)).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
  }},
];

const equityPlaceholder = [
  { time: "2026-01-01", value: 100000 },
  { time: "2026-01-15", value: 102500 },
  { time: "2026-02-01", value: 101800 },
  { time: "2026-02-15", value: 105200 },
  { time: "2026-03-01", value: 108000 },
  { time: "2026-03-15", value: 112500 },
];

export default function DashboardPage() {
  const router = useRouter();
  const cardBg = useColorModeValue("white", "gray.800");
  const hoverBg = useColorModeValue("gray.50", "gray.700");

  const { data: overview, isLoading: overviewLoading } = useAnalyticsOverview();
  const { data: signals, isLoading: signalsLoading } = useWebhookSignals();
  const { data: strategies, isLoading: strategiesLoading } = useStrategies();
  const { data: paperSessions, isLoading: paperLoading } = usePaperSessions();

  const activeSessions = (paperSessions ?? []).filter(
    (s) => s.status === "running"
  ).length;

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6}>
        <Heading size="lg">Dashboard</Heading>
        <Flex gap={3}>
          <Button size="sm" colorScheme="blue" onClick={() => router.push("/strategies/new")}>
            New Strategy
          </Button>
          <Button size="sm" variant="outline" onClick={() => router.push("/backtests")}>
            Run Backtest
          </Button>
          <Button size="sm" variant="outline" onClick={() => router.push("/brokers")}>
            Connect Broker
          </Button>
        </Flex>
      </Flex>

      {/* Stat Cards */}
      <SimpleGrid columns={{ base: 1, sm: 2, lg: 4 }} spacing={4} mb={6}>
        <StatCard
          label="Active Strategies"
          value={overviewLoading ? "..." : String(overview?.active_strategies ?? 0)}
        />
        <StatCard
          label="Active Paper Sessions"
          value={paperLoading ? "..." : String(activeSessions)}
        />
        <StatCard
          label="Today's Signals"
          value={overviewLoading ? "..." : String(overview?.trades_today ?? 0)}
        />
        <StatCard
          label="Portfolio P&L"
          value={overviewLoading ? "..." : formatCurrency(overview?.total_pnl ?? 0)}
          change={overview?.total_pnl ? (overview.total_pnl / 100000) * 100 : undefined}
        />
      </SimpleGrid>

      {/* Equity Curve */}
      <Box bg={cardBg} p={4} borderRadius="lg" shadow="sm" mb={6}>
        <Heading size="sm" mb={2}>Equity Curve</Heading>
        <ChartContainer height={300} isLoading={overviewLoading}>
          {() => <EquityCurve data={equityPlaceholder} height={300} />}
        </ChartContainer>
      </Box>

      {/* Two-column layout: Recent Signals + Top Strategies */}
      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
        <Box bg={cardBg} p={4} borderRadius="lg" shadow="sm">
          <Heading size="sm" mb={3}>Recent Signals</Heading>
          <DataTable<WebhookSignal>
            columns={signalColumns}
            data={(signals ?? []).slice(0, 10)}
            isLoading={signalsLoading}
            emptyMessage="No signals received yet"
            onRowClick={(row) => router.push(`/strategies/${row.strategy_id}`)}
          />
        </Box>

        <Box bg={cardBg} p={4} borderRadius="lg" shadow="sm">
          <Heading size="sm" mb={3}>Top Strategies</Heading>
          {strategiesLoading ? (
            <Text color="gray.500">Loading...</Text>
          ) : (strategies ?? []).length === 0 ? (
            <Text color="gray.500" textAlign="center" py={4}>No strategies yet</Text>
          ) : (
            (strategies ?? []).slice(0, 5).map((s) => (
              <Box
                key={s.id}
                p={3}
                mb={2}
                borderRadius="md"
                border="1px"
                borderColor="gray.200"
                cursor="pointer"
                _hover={{ bg: hoverBg }}
                onClick={() => router.push(`/strategies/${s.id}`)}
              >
                <Flex justify="space-between" align="center">
                  <Text fontWeight="medium">{s.name}</Text>
                  <StatusBadge
                    variant={s.is_active ? "success" : "neutral"}
                    text={s.is_active ? "Active" : "Inactive"}
                  />
                </Flex>
                <Text fontSize="sm" color="gray.500" mt={1}>
                  Mode: {s.mode}
                </Text>
              </Box>
            ))
          )}
        </Box>
      </SimpleGrid>
    </Box>
  );
}
