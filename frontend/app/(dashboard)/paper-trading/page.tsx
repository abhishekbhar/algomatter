"use client";
import {
  Box, Heading, Flex, Button, Select, useDisclosure, useToast,
  Modal, ModalOverlay, ModalContent, ModalHeader, ModalBody, ModalFooter,
  FormControl, FormLabel, NumberInput, NumberInputField, VStack,
} from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { useState, useMemo } from "react";
import { DataTable, Column } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { EmptyState } from "@/components/shared/EmptyState";
import { usePaperSessions, useAllStrategies } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { formatDate, formatCurrency } from "@/lib/utils/formatters";
import type { PaperSession } from "@/lib/api/types";

export default function PaperTradingPage() {
  const router = useRouter();
  const toast = useToast();
  const { data: sessions, isLoading, mutate } = usePaperSessions();
  const strategies = useAllStrategies();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [statusFilter, setStatusFilter] = useState("all");
  const [newStrategyId, setNewStrategyId] = useState("");
  const [newCapital, setNewCapital] = useState(100000);
  const [creating, setCreating] = useState(false);

  const strategyMap = useMemo(() => {
    const map: Record<string, string> = {};
    strategies.forEach((s) => { map[s.id] = s.name; });
    return map;
  }, [strategies]);

  const list = sessions ?? [];
  const filtered = list.filter(
    (s) => statusFilter === "all" || s.status === statusFilter,
  );

  const statusVariant = (status: string) => {
    if (status === "active") return "success";
    if (status === "stopped") return "neutral";
    if (status === "error") return "error";
    return "info";
  };

  const handleCreate = async () => {
    if (!newStrategyId) return;
    setCreating(true);
    try {
      await apiClient("/api/v1/paper-trading/sessions", {
        method: "POST",
        body: { strategy_id: newStrategyId, capital: newCapital },
      });
      toast({ title: "Session started", status: "success", duration: 3000 });
      mutate();
      onClose();
    } catch {
      toast({ title: "Failed to start session", status: "error", duration: 3000 });
    } finally {
      setCreating(false);
    }
  };

  const columns: Column<PaperSession>[] = [
    {
      key: "strategy_id", header: "Strategy",
      render: (v) => strategyMap[String(v)] ?? String(v),
    },
    {
      key: "status", header: "Status",
      render: (v) => {
        const s = String(v ?? "");
        return <StatusBadge variant={statusVariant(s)} text={s} />;
      },
    },
    {
      key: "initial_capital", header: "Initial Capital",
      render: (v) => formatCurrency(Number(v)),
    },
    {
      key: "current_balance", header: "Current Equity",
      render: (v) => formatCurrency(Number(v)),
    },
    {
      key: "started_at", header: "Started", sortable: true,
      render: (v) => formatDate(String(v ?? "")),
    },
  ];

  if (!isLoading && list.length === 0) {
    return (
      <Box>
        <Flex justify="space-between" align="center" mb={6}>
          <Heading size="lg">Paper Trading</Heading>
          <Button size="sm" colorScheme="blue" onClick={onOpen}>Start Session</Button>
        </Flex>
        <EmptyState
          title="No paper trading sessions"
          description="Start a paper trading session to test your strategies risk-free."
          actionLabel="Start Session"
          onAction={onOpen}
        />
        {renderModal()}
      </Box>
    );
  }

  function renderModal() {
    return (
      <Modal isOpen={isOpen} onClose={onClose} isCentered>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Start Paper Trading Session</ModalHeader>
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isRequired>
                <FormLabel>Strategy</FormLabel>
                <Select
                  placeholder="Select strategy"
                  value={newStrategyId}
                  onChange={(e) => setNewStrategyId(e.target.value)}
                >
                  {strategies.map((s) => (
                    <option key={s.id} value={s.id}>{s.name} ({s.type})</option>
                  ))}
                </Select>
              </FormControl>
              <FormControl isRequired>
                <FormLabel>Initial Capital</FormLabel>
                <NumberInput
                  min={1000}
                  value={newCapital}
                  onChange={(_, val) => setNewCapital(val || 100000)}
                >
                  <NumberInputField />
                </NumberInput>
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter gap={3}>
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button colorScheme="blue" onClick={handleCreate} isLoading={creating} isDisabled={!newStrategyId}>
              Start
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    );
  }

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6}>
        <Heading size="lg">Paper Trading</Heading>
        <Flex gap={3} align="center">
          <Select size="sm" w="auto" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="stopped">Stopped</option>
          </Select>
          <Button size="sm" colorScheme="blue" onClick={onOpen}>Start Session</Button>
        </Flex>
      </Flex>

      <DataTable<PaperSession>
        columns={columns}
        data={filtered}
        isLoading={isLoading}
        emptyMessage="No sessions match the filter."
        onRowClick={(row) => router.push(`/paper-trading/${row.id}`)}
      />

      {renderModal()}
    </Box>
  );
}
