"use client";
import {
  Box, SimpleGrid, Stat, StatLabel, StatNumber, Skeleton, Text,
  useColorModeValue,
} from "@chakra-ui/react";
import { useBrokerStats, useBrokerBalance } from "@/lib/hooks/useApi";

interface Props {
  brokerId: string;
  brokerType?: string;
}

function currencySymbol(currency: string): string {
  if (currency === "INR") return "₹";
  return "";
}

function formatPnl(pnl: number, currency: string): string {
  const sign = pnl >= 0 ? "+" : "-";
  const sym = currencySymbol(currency);
  return `${sign}${sym}${Math.abs(pnl).toLocaleString(undefined, { maximumFractionDigits: 2 })} ${currency}`;
}

function formatAmount(n: number, currency: string): string {
  const sym = currencySymbol(currency);
  return `${sym}${n.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${currency}`;
}

export function BrokerStatsBar({ brokerId, brokerType }: Props) {
  const { data: stats, isLoading: statsLoading } = useBrokerStats(brokerId);
  const { data: futuresBalance } = useBrokerBalance(brokerId, "FUTURES");
  const { data: spotBalance } = useBrokerBalance(brokerId, "SPOT");
  const { data: fundingBalance } = useBrokerBalance(brokerId, "FUNDING");
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

  const futuresCur = futuresBalance?.currency ?? "USDT";
  const spotCur = spotBalance?.currency ?? "USDT";
  const fundingCur = fundingBalance?.currency ?? "USD";

  return (
    <Box mb={6}>
      <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4} mb={4}>
        <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
          <StatLabel>Active Deployments</StatLabel>
          <StatNumber>{stats?.active_deployments ?? "—"}</StatNumber>
        </Stat>
        <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
          <StatLabel>Total Realized P&L</StatLabel>
          <StatNumber color={pnlColor}>{stats ? formatPnl(stats.total_realized_pnl, futuresCur) : "—"}</StatNumber>
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

      <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
        {/* Futures (CFD) account */}
        <Box bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
          <Text fontSize="xs" fontWeight="semibold" color="yellow.400" textTransform="uppercase" mb={3}>
            Futures Account
          </Text>
          <SimpleGrid columns={4} spacing={3}>
            <Stat>
              <StatLabel fontSize="xs">Available Margin</StatLabel>
              <StatNumber fontSize="sm">{futuresBalance !== undefined ? formatAmount(futuresBalance.available, futuresCur) : "—"}</StatNumber>
            </Stat>
            <Stat>
              <StatLabel fontSize="xs">Frozen Deposit</StatLabel>
              <StatNumber fontSize="sm">{futuresBalance !== undefined ? formatAmount(futuresBalance.frozen_deposit, futuresCur) : "—"}</StatNumber>
            </Stat>
            <Stat>
              <StatLabel fontSize="xs">Used Margin</StatLabel>
              <StatNumber fontSize="sm" color="orange.400">{futuresBalance !== undefined ? formatAmount(futuresBalance.used_margin, futuresCur) : "—"}</StatNumber>
            </Stat>
            <Stat>
              <StatLabel fontSize="xs">Unrealized PnL</StatLabel>
              <StatNumber fontSize="sm" color={futuresBalance && futuresBalance.unrealized_pnl >= 0 ? "green.400" : "red.400"}>
                {futuresBalance !== undefined ? formatPnl(futuresBalance.unrealized_pnl, futuresCur) : "—"}
              </StatNumber>
            </Stat>
          </SimpleGrid>
        </Box>

        {/* Spot / Asset account */}
        <Box bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
          <Text fontSize="xs" fontWeight="semibold" color="green.400" textTransform="uppercase" mb={3}>
            Spot Account
          </Text>
          <SimpleGrid columns={3} spacing={3}>
            <Stat>
              <StatLabel fontSize="xs">Available</StatLabel>
              <StatNumber fontSize="sm">{spotBalance !== undefined ? formatAmount(spotBalance.available, spotCur) : "—"}</StatNumber>
            </Stat>
            <Stat>
              <StatLabel fontSize="xs">On Hold</StatLabel>
              <StatNumber fontSize="sm" color="orange.400">{spotBalance !== undefined ? formatAmount(spotBalance.used_margin, spotCur) : "—"}</StatNumber>
            </Stat>
            <Stat>
              <StatLabel fontSize="xs">Total</StatLabel>
              <StatNumber fontSize="sm">{spotBalance !== undefined ? formatAmount(spotBalance.total, spotCur) : "—"}</StatNumber>
            </Stat>
          </SimpleGrid>
        </Box>

        {/* Funding / Asset account */}
        <Box bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
          <Text fontSize="xs" fontWeight="semibold" color="blue.400" textTransform="uppercase" mb={3}>
            Funding Account
          </Text>
          <SimpleGrid columns={2} spacing={3}>
            <Stat>
              <StatLabel fontSize="xs">Available</StatLabel>
              <StatNumber fontSize="sm">{fundingBalance !== undefined ? formatAmount(fundingBalance.available, fundingCur) : "—"}</StatNumber>
            </Stat>
            <Stat>
              <StatLabel fontSize="xs">Total</StatLabel>
              <StatNumber fontSize="sm">{fundingBalance !== undefined ? formatAmount(fundingBalance.total, fundingCur) : "—"}</StatNumber>
            </Stat>
          </SimpleGrid>
        </Box>
      </SimpleGrid>
    </Box>
  );
}
