"use client";
import { useState } from "react";
import {
  Box, Table, Thead, Tbody, Tr, Th, Td, Badge, Button, Text, useToast,
  useColorModeValue,
} from "@chakra-ui/react";
import { useBrokerPositions } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { mutate } from "swr";

interface Props {
  brokerId: string;
}

function formatPnl(pnl: number): string {
  const sign = pnl >= 0 ? "+" : "-";
  return `${sign}$${Math.abs(pnl).toFixed(2)}`;
}

export function BrokerPositionsTable({ brokerId }: Props) {
  const { data: positions, isLoading } = useBrokerPositions(brokerId);
  const [closingId, setClosingId] = useState<string | null>(null);
  const toast = useToast();
  const borderColor = useColorModeValue("gray.200", "gray.700");

  async function handleClose(deploymentId: string, side: "LONG" | "SHORT", quantity: number) {
    setClosingId(deploymentId);
    try {
      await apiClient(`/api/v1/deployments/${deploymentId}/manual-order`, {
        method: "POST",
        body: JSON.stringify({
          action: side === "LONG" ? "SELL" : "BUY",
          quantity,
          order_type: "market",
        }),
      });
      toast({ title: "Close order placed", status: "success", duration: 3000 });
      mutate(`/api/v1/brokers/${brokerId}/positions`);
    } catch {
      toast({ title: "Failed to place close order", status: "error", duration: 3000 });
    } finally {
      setClosingId(null);
    }
  }

  if (isLoading) return <Box py={4}><Text color="gray.500">Loading...</Text></Box>;
  if (!positions || positions.length === 0) {
    return <Box py={8} textAlign="center"><Text color="gray.500">No open positions</Text></Box>;
  }

  return (
    <Box overflowX="auto">
      <Table size="sm" variant="simple">
        <Thead>
          <Tr>
            <Th>Symbol</Th>
            <Th>Side</Th>
            <Th isNumeric>Qty</Th>
            <Th isNumeric>Avg Entry</Th>
            <Th isNumeric>Unrealized P&L</Th>
            <Th>Strategy</Th>
            <Th />
          </Tr>
        </Thead>
        <Tbody>
          {positions.map((pos) => (
            <Tr key={`${pos.deployment_id}-${pos.symbol}`} borderBottomWidth={1} borderColor={borderColor}>
              <Td fontWeight="semibold">{pos.symbol}</Td>
              <Td>
                <Badge colorScheme={pos.side === "LONG" ? "green" : "red"}>{pos.side}</Badge>
              </Td>
              <Td isNumeric>{pos.quantity}</Td>
              <Td isNumeric>${pos.avg_entry_price.toLocaleString()}</Td>
              <Td isNumeric color={pos.unrealized_pnl >= 0 ? "green.400" : "red.400"}>
                {formatPnl(pos.unrealized_pnl)}
              </Td>
              <Td color="gray.500" fontSize="sm">{pos.deployment_name}</Td>
              <Td>
                <Button
                  size="xs"
                  colorScheme="red"
                  variant="ghost"
                  isLoading={closingId === pos.deployment_id}
                  onClick={() => handleClose(pos.deployment_id, pos.side, pos.quantity)}
                >
                  Close
                </Button>
              </Td>
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  );
}
