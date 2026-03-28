"use client";
import { SimpleGrid } from "@chakra-ui/react";
import { StatCard } from "@/components/shared/StatCard";
import type { AggregateStats as AggregateStatsType } from "@/lib/api/types";

interface Props {
  stats: AggregateStatsType | undefined;
}

export function AggregateStats({ stats }: Props) {
  return (
    <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
      <StatCard
        label="Deployed Capital"
        value={stats ? `₹${stats.total_deployed_capital.toLocaleString()}` : "—"}
      />
      <StatCard
        label="Total P&L"
        value={stats ? `${stats.aggregate_pnl >= 0 ? "+" : ""}₹${stats.aggregate_pnl.toFixed(2)}` : "—"}
      />
      <StatCard
        label="Active Deployments"
        value={stats?.active_deployments?.toString() ?? "—"}
      />
      <StatCard
        label="Today's Trades"
        value={stats?.todays_trades?.toString() ?? "—"}
      />
    </SimpleGrid>
  );
}
