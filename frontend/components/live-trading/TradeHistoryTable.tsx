"use client";
import { Box, Table, Thead, Tbody, Tr, Th, Td, Badge, HStack, Button, Text } from "@chakra-ui/react";
import { useState } from "react";
import { useDeploymentTrades } from "@/lib/hooks/useApi";

const PAGE_SIZE = 20;

interface Props {
  deploymentId: string;
}

export function TradeHistoryTable({ deploymentId }: Props) {
  const [offset, setOffset] = useState(0);
  const { data } = useDeploymentTrades(deploymentId, offset, PAGE_SIZE);

  return (
    <Box>
      <Text fontWeight="bold" mb={2}>Trade History</Text>
      <Box overflowX="auto">
        <Table size="sm">
          <Thead>
            <Tr>
              <Th>Time</Th>
              <Th>Action</Th>
              <Th isNumeric>Qty</Th>
              <Th isNumeric>Price</Th>
              <Th isNumeric>P&L</Th>
              <Th>Status</Th>
            </Tr>
          </Thead>
          <Tbody>
            {data?.trades.map((t) => (
              <Tr key={t.id}>
                <Td fontSize="xs">{new Date(t.created_at).toLocaleTimeString()}</Td>
                <Td>
                  <HStack spacing={1}>
                    <Badge colorScheme={t.action === "BUY" ? "green" : "red"} size="sm">{t.action}</Badge>
                    {t.is_manual && <Badge colorScheme="purple" size="sm">Manual</Badge>}
                  </HStack>
                </Td>
                <Td isNumeric fontSize="xs">{t.quantity}</Td>
                <Td isNumeric fontSize="xs">{t.fill_price?.toFixed(2) ?? "—"}</Td>
                <Td isNumeric fontSize="xs" color={
                  t.realized_pnl == null ? "gray.500" :
                  t.realized_pnl >= 0 ? "green.500" : "red.500"
                }>
                  {t.realized_pnl != null ? t.realized_pnl.toFixed(2) : "—"}
                </Td>
                <Td><Badge size="sm">{t.status}</Badge></Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </Box>
      {data && data.total > PAGE_SIZE && (
        <HStack mt={2} justify="center">
          <Button size="xs" isDisabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
            Prev
          </Button>
          <Text fontSize="xs">{offset + 1}–{Math.min(offset + PAGE_SIZE, data.total)} of {data.total}</Text>
          <Button size="xs" isDisabled={offset + PAGE_SIZE >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)}>
            Next
          </Button>
        </HStack>
      )}
    </Box>
  );
}
