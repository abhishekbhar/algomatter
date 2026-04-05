"use client";
import {
  Box,
  Heading,
  HStack,
  Text,
  Button,
  Flex,
  Tabs,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
  SimpleGrid,
  Skeleton,
  useToast,
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

function StatTile({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <Box p={4} borderWidth="1px" borderRadius="md" textAlign="center">
      <Text
        fontSize="xs"
        color="gray.500"
        textTransform="uppercase"
        mb={1}
      >
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
  const toast = useToast();

  const { data: dep, error: deploymentError } = useDeployment(deploymentId);
  const isActive = dep?.status === "running" || dep?.status === "pending";

  const { data: result } = useDeploymentResults(deploymentId);
  const { data: paperDeployments = [], mutate: refreshPaper } =
    usePaperDeployments();

  const promotedPaperDep = paperDeployments.find(
    (p) => p.promoted_from_id === deploymentId
  );
  const canPromote = dep?.status === "completed" && !promotedPaperDep;

  // Default to Logs tab (index 2) for failed/stopped, otherwise Overview (index 0)
  const defaultTab =
    dep?.status === "failed" || dep?.status === "stopped" ? 2 : 0;

  const handlePromote = async () => {
    setIsPromoting(true);
    try {
      await apiClient(`/api/v1/deployments/${deploymentId}/promote`, {
        method: "POST",
      });
      await refreshPaper();
      router.push("/paper-trading");
    } catch {
      toast({ title: "Failed to promote deployment", status: "error", duration: 4000, isClosable: true });
    } finally {
      setIsPromoting(false);
    }
  };

  const m = result?.metrics;

  // Loading skeleton
  if (!dep && !deploymentError) {
    return (
      <Box p={6}>
        <Skeleton height="40px" mb={4} />
        <SimpleGrid columns={4} spacing={4} mb={6}>
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} height="80px" borderRadius="md" />
          ))}
        </SimpleGrid>
        <Skeleton height="400px" borderRadius="md" />
      </Box>
    );
  }

  // 404 / error state
  if (!dep) {
    return (
      <Box p={6}>
        <Text color="gray.500" mb={4}>
          Deployment not found.
        </Text>
        <Button
          size="sm"
          onClick={() => router.push("/backtest-deployments")}
        >
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
              onClick={() =>
                router.push(`/paper-trading/${promotedPaperDep.id}`)
              }
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
          value={
            m != null
              ? `${m.total_return >= 0 ? "+" : ""}${m.total_return.toFixed(1)}%`
              : "—"
          }
          color={
            m != null
              ? m.total_return >= 0
                ? "green.400"
                : "red.400"
              : "gray.500"
          }
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
          color={
            m != null
              ? m.sharpe_ratio >= 1
                ? "green.400"
                : "orange.400"
              : "gray.500"
          }
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
            <BacktestOverviewTab
              result={result ?? null}
              deploymentStatus={dep.status}
            />
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
