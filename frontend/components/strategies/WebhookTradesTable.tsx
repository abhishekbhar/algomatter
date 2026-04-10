"use client";
import { useState } from "react";
import { Box, Table, Thead, Tbody, Tr, Th, Td, Badge, Text } from "@chakra-ui/react";
import { useStrategySignals } from "@/lib/hooks/useApi";
import { Pagination } from "@/components/shared/Pagination";
import type { WebhookSignal } from "@/lib/api/types";

const PAGE_SIZE = 20;

interface Props {
  strategyId: string;
}

export function WebhookTradesTable({ strategyId }: Props) {
  const { data: signals } = useStrategySignals(strategyId);
  const [offset, setOffset] = useState(0);

  const trades = (signals ?? []).filter(
    (s) => s.execution_result === "filled" && s.execution_detail?.fill_price
  );

  const page = trades.slice(offset, offset + PAGE_SIZE);

  if (trades.length === 0) {
    return (
      <Text py={8} textAlign="center" color="gray.500">
        No executed trades yet
      </Text>
    );
  }

  return (
    <Box overflowX="auto">
      <Table size="sm">
        <Thead>
          <Tr>
            <Th>Time</Th>
            <Th>Action</Th>
            <Th isNumeric>Qty</Th>
            <Th isNumeric>Fill Price</Th>
            <Th>Order ID</Th>
            <Th>Broker Order ID</Th>
            <Th>Status</Th>
          </Tr>
        </Thead>
        <Tbody>
          {page.map((t) => {
            const sig = t.parsed_signal;
            const detail = t.execution_detail;
            const action = sig?.action ? String(sig.action).toUpperCase() : "—";
            return (
              <Tr key={t.id}>
                <Td fontSize="xs">
                  {t.received_at ? new Date(t.received_at).toLocaleString() : "—"}
                </Td>
                <Td>
                  <Badge colorScheme={action === "BUY" ? "green" : action === "SELL" ? "red" : "gray"} size="sm">
                    {action}
                  </Badge>
                </Td>
                <Td isNumeric fontSize="xs">
                  {detail?.fill_quantity ?? (sig?.quantity != null ? String(sig.quantity) : "—")}
                </Td>
                <Td isNumeric fontSize="xs">
                  {detail?.fill_price ? Number(detail.fill_price).toFixed(2) : "—"}
                </Td>
                <Td fontSize="xs">{detail?.order_id ?? "—"}</Td>
                <Td fontSize="xs">{detail?.broker_order_id ?? "—"}</Td>
                <Td>
                  <Badge colorScheme="green" size="sm">
                    {detail?.status ?? t.execution_result ?? "—"}
                  </Badge>
                </Td>
              </Tr>
            );
          })}
        </Tbody>
      </Table>
      <Pagination
        offset={offset}
        pageSize={PAGE_SIZE}
        total={trades.length}
        onPrev={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
        onNext={() => setOffset(offset + PAGE_SIZE)}
      />
    </Box>
  );
}
