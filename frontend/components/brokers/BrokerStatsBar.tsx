"use client";
import {
  Box, SimpleGrid, Stat, StatLabel, StatNumber, Skeleton,
  useColorModeValue,
} from "@chakra-ui/react";
import { useBrokerStats, useBrokerBalance } from "@/lib/hooks/useApi";

interface Props {
  brokerId: string;
}

function formatPnl(pnl: number): string {
  const sign = pnl >= 0 ? "+" : "-";
  return `${sign}₹${Math.abs(pnl).toFixed(2)}`;
}

function formatAmount(n: number): string {
  return `₹${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export function BrokerStatsBar({ brokerId }: Props) {
  const { data: stats, isLoading: statsLoading } = useBrokerStats(brokerId);
  const { data: balance } = useBrokerBalance(brokerId, "cfd");
  const cardBg = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");
  const pnlColor = stats && stats.total_realized_pnl >= 0 ? "green.400" : "red.400";

  if (statsLoading) {
    return (
      <Box mb={6}>
        <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4} mb={4}>
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} height="80px" borderRadius="md" />)}
        </SimpleGrid>
      </Box>
    );
  }

  return (
    <Box mb={6}>
      <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4} mb={balance ? 4 : 0}>
        <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
          <StatLabel>Active Deployments</StatLabel>
          <StatNumber>{stats?.active_deployments ?? "—"}</StatNumber>
        </Stat>
        <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
          <StatLabel>Total Realized P&L</StatLabel>
          <StatNumber color={pnlColor}>{stats ? formatPnl(stats.total_realized_pnl) : "—"}</StatNumber>
        </Stat>
        <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
          <StatLabel>Win Rate</StatLabel>
          <StatNumber>{stats ? `${(stats.win_rate * 100).toFixed(1)}%` : "—"}</StatNumber>
        </Stat>
        <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
          <StatLabel>Total Trades</StatLabel>
          <StatNumber>{stats?.total_trades ?? "—"}</StatNumber>
        </Stat>
      </SimpleGrid>

      {balance && (
        <SimpleGrid columns={3} spacing={4}>
          <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
            <StatLabel>Available Balance</StatLabel>
            <StatNumber fontSize="md">{formatAmount(balance.available)}</StatNumber>
          </Stat>
          <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
            <StatLabel>Used Margin</StatLabel>
            <StatNumber fontSize="md" color="orange.400">{formatAmount(balance.used_margin)}</StatNumber>
          </Stat>
          <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
            <StatLabel>Total Balance</StatLabel>
            <StatNumber fontSize="md">{formatAmount(balance.total)}</StatNumber>
          </Stat>
        </SimpleGrid>
      )}
    </Box>
  );
}
