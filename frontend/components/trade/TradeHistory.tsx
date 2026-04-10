"use client";
import { useState } from "react";
import {
  Box, Table, Thead, Tbody, Tr, Th, Td, Badge, Button, Flex, Text,
  useColorModeValue, useToast,
} from "@chakra-ui/react";
import { apiClient } from "@/lib/api/client";
import { Pagination } from "@/components/shared/Pagination";
import { useManualTrades, useOpenManualTrades } from "@/lib/hooks/useManualTrades";

const HISTORY_PAGE_SIZE = 50;

interface Props {
  onTradeUpdate?: () => void;
}

export function TradeHistory({ onTradeUpdate }: Props) {
  const [tab, setTab] = useState<"open" | "history">("open");
  const [historyOffset, setHistoryOffset] = useState(0);
  const { data: openData, mutate: refreshOpen } = useOpenManualTrades();
  const { data: historyData, mutate: refreshHistory } = useManualTrades(historyOffset, HISTORY_PAGE_SIZE);
  const toast = useToast();
  const borderColor = useColorModeValue("gray.200", "gray.700");
  const bg = useColorModeValue("white", "gray.800");

  const handleCancel = async (tradeId: string) => {
    try {
      await apiClient(`/api/v1/trades/manual/${tradeId}/cancel`, { method: "POST" });
      toast({ title: "Order cancelled", status: "success", duration: 2000 });
      refreshOpen(); refreshHistory(); onTradeUpdate?.();
    } catch {
      toast({ title: "Failed to cancel", status: "error", duration: 3000 });
    }
  };

  const trades = tab === "open" ? openData?.trades ?? [] : historyData?.trades ?? [];
  const historyTotal = historyData?.total ?? 0;

  return (
    <Box borderTop="1px" borderColor={borderColor} bg={bg}>
      <Flex gap={4} px={3} py={2} borderBottom="1px" borderColor={borderColor}>
        <Text fontSize="sm" fontWeight={tab === "open" ? "bold" : "normal"} color={tab === "open" ? "blue.400" : "gray.500"} cursor="pointer" borderBottom={tab === "open" ? "2px solid" : "none"} borderColor="blue.400" pb={1} onClick={() => setTab("open")}>Open Orders ({openData?.trades?.length ?? 0})</Text>
        <Text fontSize="sm" fontWeight={tab === "history" ? "bold" : "normal"} color={tab === "history" ? "blue.400" : "gray.500"} cursor="pointer" borderBottom={tab === "history" ? "2px solid" : "none"} borderColor="blue.400" pb={1} onClick={() => setTab("history")}>Trade History</Text>
      </Flex>

      {trades.length === 0 ? (
        <Box py={4} textAlign="center"><Text color="gray.500" fontSize="sm">{tab === "open" ? "No open orders" : "No trade history"}</Text></Box>
      ) : (
        <Box overflowX="auto" maxH="200px" overflowY="auto">
          <Table size="sm" variant="simple">
            <Thead><Tr><Th>Time</Th><Th>Symbol</Th><Th>Side</Th><Th>Type</Th><Th isNumeric>Price</Th><Th isNumeric>Qty</Th><Th>Status</Th><Th>Trade ID</Th><Th>Order ID</Th>{tab === "open" && <Th>Action</Th>}</Tr></Thead>
            <Tbody>
              {trades.map((t) => (
                <Tr key={t.id} fontSize="xs">
                  <Td color="gray.500">{new Date(t.created_at).toLocaleTimeString()}</Td>
                  <Td fontWeight="medium">{t.symbol}</Td>
                  <Td><Badge colorScheme={t.action === "BUY" ? "green" : "red"} size="sm">{t.action}</Badge></Td>
                  <Td>{t.order_type}</Td>
                  <Td isNumeric>{t.fill_price ? t.fill_price.toLocaleString() : t.price ? t.price.toLocaleString() : "MKT"}</Td>
                  <Td isNumeric>{t.fill_quantity || t.quantity}</Td>
                  <Td><Badge colorScheme={t.status === "filled" ? "green" : t.status === "open" ? "blue" : t.status === "cancelled" ? "gray" : "red"} size="sm">{t.status}</Badge></Td>
                  <Td color="gray.500" fontFamily="mono" title={t.id}>{t.id.slice(0, 8)}</Td>
                  <Td color="gray.500" fontFamily="mono" title={t.broker_order_id ?? ""}>{t.broker_order_id ? t.broker_order_id.split(":").pop() : "—"}</Td>
                  {tab === "open" && (<Td><Button size="xs" colorScheme="red" variant="ghost" onClick={() => handleCancel(t.id)}>Cancel</Button></Td>)}
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Box>
      )}

      {tab === "history" && (
        <Pagination
          offset={historyOffset}
          pageSize={HISTORY_PAGE_SIZE}
          total={historyTotal}
          onPrev={() => setHistoryOffset(Math.max(0, historyOffset - HISTORY_PAGE_SIZE))}
          onNext={() => setHistoryOffset(historyOffset + HISTORY_PAGE_SIZE)}
        />
      )}
    </Box>
  );
}
