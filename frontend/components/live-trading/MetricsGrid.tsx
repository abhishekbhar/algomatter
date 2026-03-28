"use client";
import { SimpleGrid } from "@chakra-ui/react";
import { StatCard } from "@/components/shared/StatCard";
import type { LiveMetrics } from "@/lib/api/types";

interface Props {
  metrics: LiveMetrics | undefined;
}

export function MetricsGrid({ metrics }: Props) {
  if (!metrics) return null;
  return (
    <SimpleGrid columns={{ base: 2, md: 4 }} spacing={3}>
      <StatCard label="Return" value={`${metrics.total_return.toFixed(2)}%`} />
      <StatCard label="Win Rate" value={`${metrics.win_rate.toFixed(1)}%`} />
      <StatCard label="Profit Factor" value={metrics.profit_factor.toFixed(2)} />
      <StatCard label="Sharpe" value={metrics.sharpe_ratio.toFixed(2)} />
      <StatCard label="Max Drawdown" value={`${metrics.max_drawdown.toFixed(2)}%`} />
      <StatCard label="Total Trades" value={metrics.total_trades.toString()} />
      <StatCard label="Best Trade" value={metrics.best_trade != null ? `₹${metrics.best_trade.toFixed(2)}` : "—"} />
      <StatCard label="Worst Trade" value={metrics.worst_trade != null ? `₹${metrics.worst_trade.toFixed(2)}` : "—"} />
    </SimpleGrid>
  );
}
