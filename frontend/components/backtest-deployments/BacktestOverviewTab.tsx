"use client";
import { Box, Text, Flex } from "@chakra-ui/react";
import { EquityCurve } from "@/components/charts/EquityCurve";
import type { Deployment, DeploymentResult } from "@/lib/api/types";

interface Props {
  result: DeploymentResult | null | undefined;
  deploymentStatus: Deployment["status"];
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
  const equityCurveData = (result.equity_curve ?? [])
    .filter((p) => p.timestamp != null)
    .map((p) => ({
      time: Math.floor(new Date(p.timestamp!).getTime() / 1000),
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
