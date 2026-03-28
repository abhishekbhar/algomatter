"use client";
import { Box, Heading, HStack, SimpleGrid, Table, Thead, Tbody, Tr, Th, Td, Badge } from "@chakra-ui/react";
import { useActiveDeployments, useAggregateStats, useRecentTrades, useDeploymentPosition } from "@/lib/hooks/useApi";
import { AggregateStats } from "@/components/live-trading/AggregateStats";
import { LiveDeploymentCard } from "@/components/live-trading/LiveDeploymentCard";
import { KillSwitchButton } from "@/components/live-trading/KillSwitchButton";
import { EmptyState } from "@/components/shared/EmptyState";
import type { Deployment } from "@/lib/api/types";

function DeploymentCardWithPosition({ deployment }: { deployment: Deployment }) {
  const { data: position } = useDeploymentPosition(deployment.id);
  return <LiveDeploymentCard deployment={deployment} position={position ?? undefined} />;
}

export default function LiveTradingPage() {
  const { data: deployments, mutate: refreshDeployments } = useActiveDeployments();
  const { data: stats, mutate: refreshStats } = useAggregateStats();
  const { data: recentTrades } = useRecentTrades(20);

  const handleKillComplete = () => {
    refreshDeployments();
    refreshStats();
  };

  return (
    <Box p={6}>
      <HStack justify="space-between" mb={6}>
        <Heading size="lg">Live Trading</Heading>
        <KillSwitchButton onComplete={handleKillComplete} />
      </HStack>

      <AggregateStats stats={stats ?? undefined} />

      <Heading size="md" mt={8} mb={4}>Active Deployments</Heading>
      {!deployments || deployments.length === 0 ? (
        <EmptyState title="No active deployments" />
      ) : (
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
          {deployments.map((dep) => (
            <DeploymentCardWithPosition key={dep.id} deployment={dep} />
          ))}
        </SimpleGrid>
      )}

      <Heading size="md" mt={8} mb={4}>Recent Trades</Heading>
      {!recentTrades || recentTrades.trades.length === 0 ? (
        <EmptyState title="No trades yet" />
      ) : (
        <Box overflowX="auto">
          <Table size="sm">
            <Thead>
              <Tr>
                <Th>Time</Th>
                <Th>Strategy</Th>
                <Th>Symbol</Th>
                <Th>Action</Th>
                <Th isNumeric>Qty</Th>
                <Th isNumeric>Price</Th>
                <Th isNumeric>P&L</Th>
              </Tr>
            </Thead>
            <Tbody>
              {recentTrades.trades.map((trade) => (
                <Tr key={trade.id}>
                  <Td fontSize="xs">{new Date(trade.created_at).toLocaleTimeString()}</Td>
                  <Td fontSize="xs">{trade.strategy_name}</Td>
                  <Td fontSize="xs">{trade.symbol}</Td>
                  <Td>
                    <Badge colorScheme={trade.action === "BUY" ? "green" : "red"} size="sm">
                      {trade.action}
                    </Badge>
                  </Td>
                  <Td isNumeric fontSize="xs">{trade.quantity}</Td>
                  <Td isNumeric fontSize="xs">{trade.fill_price?.toFixed(2) ?? "—"}</Td>
                  <Td isNumeric fontSize="xs" color={
                    trade.realized_pnl == null ? "gray.500" :
                    trade.realized_pnl >= 0 ? "green.500" : "red.500"
                  }>
                    {trade.realized_pnl != null ? `${trade.realized_pnl >= 0 ? "+" : ""}${trade.realized_pnl.toFixed(2)}` : "—"}
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Box>
      )}
    </Box>
  );
}
