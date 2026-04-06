"use client";
import { useState } from "react";
import {
  Box, Table, Thead, Tbody, Tr, Th, Td, Badge, Text, HStack, Button, Flex,
} from "@chakra-ui/react";
import { useBrokerTrades } from "@/lib/hooks/useApi";
import { formatDate } from "@/lib/utils/formatters";

interface Props {
  brokerId: string;
}

const PAGE_SIZE = 50;

function formatPnl(pnl: number | null): string {
  if (pnl === null) return "—";
  const sign = pnl >= 0 ? "+" : "-";
  return `${sign}₹${Math.abs(pnl).toFixed(2)}`;
}

export function BrokerTradesTable({ brokerId }: Props) {
  const [offset, setOffset] = useState(0);
  const { data, isLoading } = useBrokerTrades(brokerId, offset, PAGE_SIZE);

  if (isLoading) return <Box py={4}><Text color="gray.500">Loading...</Text></Box>;
  if (!data || data.trades.length === 0) {
    return <Box py={8} textAlign="center"><Text color="gray.500">No trades recorded</Text></Box>;
  }

  const { trades, total } = data;
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  return (
    <Box>
      <Box overflowX="auto">
        <Table size="sm" variant="simple">
          <Thead>
            <Tr>
              <Th>Time</Th>
              <Th>Symbol</Th>
              <Th>Action</Th>
              <Th isNumeric>Qty</Th>
              <Th isNumeric>Fill Price</Th>
              <Th isNumeric>P&L</Th>
              <Th>Strategy</Th>
              <Th>Status</Th>
            </Tr>
          </Thead>
          <Tbody>
            {trades.map((t) => (
              <Tr key={t.id}>
                <Td fontSize="xs" color="gray.500">{formatDate(t.created_at)}</Td>
                <Td fontWeight="semibold">{t.symbol}</Td>
                <Td>
                  <Badge colorScheme={t.action === "BUY" ? "green" : "red"}>{t.action}</Badge>
                </Td>
                <Td isNumeric>{t.quantity}</Td>
                <Td isNumeric>{t.fill_price != null ? `₹${t.fill_price.toLocaleString()}` : "—"}</Td>
                <Td isNumeric color={t.realized_pnl == null ? undefined : t.realized_pnl >= 0 ? "green.400" : "red.400"}>
                  {formatPnl(t.realized_pnl)}
                </Td>
                <Td color="gray.500" fontSize="sm">{t.strategy_name}</Td>
                <Td><Badge variant="subtle">{t.status}</Badge></Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </Box>

      {total > PAGE_SIZE && (
        <Flex justify="space-between" align="center" mt={3} px={1}>
          <Text fontSize="sm" color="gray.500">
            {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
          </Text>
          <HStack>
            <Button size="xs" onClick={() => setOffset(offset - PAGE_SIZE)} isDisabled={!canPrev}>
              Prev
            </Button>
            <Button size="xs" onClick={() => setOffset(offset + PAGE_SIZE)} isDisabled={!canNext}>
              Next
            </Button>
          </HStack>
        </Flex>
      )}
    </Box>
  );
}
