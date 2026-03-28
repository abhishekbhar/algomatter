"use client";
import { Box, Table, Thead, Tbody, Tr, Th, Td, Text } from "@chakra-ui/react";
import type { ComparisonData } from "@/lib/api/types";

interface Props {
  comparison: ComparisonData | null | undefined;
}

const METRIC_LABELS: Record<string, string> = {
  total_return: "Return (%)",
  win_rate: "Win Rate (%)",
  profit_factor: "Profit Factor",
  sharpe_ratio: "Sharpe Ratio",
  max_drawdown: "Max Drawdown (%)",
  total_trades: "Total Trades",
  avg_trade_pnl: "Avg Trade P&L",
};

export function ComparisonTable({ comparison }: Props) {
  if (!comparison) return <Text color="gray.500" fontSize="sm">No backtest comparison available</Text>;

  return (
    <Box overflowX="auto">
      <Table size="sm">
        <Thead>
          <Tr>
            <Th>Metric</Th>
            <Th isNumeric>Backtest</Th>
            <Th isNumeric>Live</Th>
            <Th isNumeric>Delta</Th>
          </Tr>
        </Thead>
        <Tbody>
          {Object.entries(METRIC_LABELS).map(([key, label]) => {
            const bt = (comparison.backtest as unknown as Record<string, number>)[key] ?? 0;
            const live = (comparison.current as unknown as Record<string, number>)[key] ?? 0;
            const delta = comparison.deltas[key] ?? 0;
            return (
              <Tr key={key}>
                <Td fontSize="xs">{label}</Td>
                <Td isNumeric fontSize="xs">{typeof bt === "number" ? bt.toFixed(2) : bt}</Td>
                <Td isNumeric fontSize="xs">{typeof live === "number" ? live.toFixed(2) : live}</Td>
                <Td isNumeric fontSize="xs" color={delta >= 0 ? "green.500" : "red.500"}>
                  {delta >= 0 ? "+" : ""}{delta.toFixed(2)}
                </Td>
              </Tr>
            );
          })}
        </Tbody>
      </Table>
    </Box>
  );
}
