"use client";
import {
  Box, Heading, SimpleGrid, Flex, Button, Text, useColorModeValue,
} from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { StatCard } from "@/components/shared/StatCard";
import { DataTable, Column } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { EquityCurve } from "@/components/charts/EquityCurve";
import { ChartContainer, filterByTimeframe } from "@/components/charts/ChartContainer";
import {
  useAnalyticsOverview,
  useWebhookSignals,
  useStrategies,
  usePaperSessions,
  useActiveDeployments,
} from "@/lib/hooks/useApi";
import { formatCurrency } from "@/lib/utils/formatters";
import type { WebhookSignal, Deployment } from "@/lib/api/types";

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


export default function DashboardPage() {
  const router = useRouter();
  const cardBg = useColorModeValue("white", "gray.800");
  const hoverBg = useColorModeValue("gray.50", "gray.700");

  const { data: overview, isLoading: overviewLoading } = useAnalyticsOverview();
  const { data: signals, isLoading: signalsLoading } = useWebhookSignals();
  const { data: strategies, isLoading: strategiesLoading } = useStrategies();
  const { data: paperSessions, isLoading: paperLoading } = usePaperSessions();
  const { data: activeDeployments, isLoading: deploymentsLoading } = useActiveDeployments();

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
          <Button size="sm" variant="outline" onClick={() => router.push("/backtesting")}>
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

      {/* Equity Curve — go to Analytics > strategy to see per-strategy curves */}
      <Box bg={cardBg} p={4} borderRadius="lg" shadow="sm" mb={6}>
        <Flex justify="space-between" align="center" mb={2}>
          <Heading size="sm">Equity Curve</Heading>
          <Button size="xs" variant="link" colorScheme="blue" onClick={() => router.push("/analytics")}>
            View per-strategy →
          </Button>
        </Flex>
        <ChartContainer height={300} isLoading={overviewLoading}>
          {(tf) => <EquityCurve data={filterByTimeframe([], tf)} height={300} />}
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

      {/* Active Hosted Strategies */}
      <Box bg={cardBg} p={4} borderRadius="lg" shadow="sm" mt={6}>
        <Flex justify="space-between" align="center" mb={3}>
          <Heading size="sm">Active Hosted Strategies</Heading>
          <Button size="xs" variant="outline" onClick={() => router.push("/strategies/hosted")}>
            View All
          </Button>
        </Flex>
        {deploymentsLoading ? (
          <Text color="gray.500">Loading...</Text>
        ) : (activeDeployments ?? []).length === 0 ? (
          <Text color="gray.500" textAlign="center" py={4}>
            No active strategies.{" "}
            <Button variant="link" colorScheme="blue" size="sm" onClick={() => router.push("/strategies/hosted/new")}>
              Create one to get started
            </Button>
          </Text>
        ) : (
          <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={3}>
            {(activeDeployments ?? []).map((d) => (
              <Box
                key={d.id}
                p={3}
                borderRadius="md"
                border="1px"
                borderColor="gray.200"
                cursor="pointer"
                _hover={{ bg: hoverBg }}
                onClick={() => router.push(`/strategies/hosted/${d.strategy_code_id}`)}
              >
                <Flex justify="space-between" align="center" mb={1}>
                  <Text fontWeight="medium" fontSize="sm">{d.symbol}</Text>
                  <StatusBadge
                    variant={d.mode === "live" ? "error" : d.mode === "paper" ? "warning" : "info"}
                    text={d.mode}
                  />
                </Flex>
                <Text fontSize="xs" color="gray.500">
                  {d.interval} · {d.exchange}
                </Text>
              </Box>
            ))}
          </SimpleGrid>
        )}
      </Box>
    </Box>
  );
}
