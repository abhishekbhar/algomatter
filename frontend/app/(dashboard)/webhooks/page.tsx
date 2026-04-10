"use client";
import {
  Box, Heading, Flex, Code, IconButton, Button, useDisclosure, useToast, useClipboard,
  Card, CardHeader, CardBody, Text, VStack, HStack, Badge,
  Table, Thead, Tbody, Tr, Th, Td, TableContainer,
} from "@chakra-ui/react";
import { useState } from "react";
import { DataTable, Column } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmModal } from "@/components/shared/ConfirmModal";
import { Pagination } from "@/components/shared/Pagination";
import { useWebhookConfig, useWebhookSignals, useStrategies } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { formatDate } from "@/lib/utils/formatters";
import type { WebhookSignal } from "@/lib/api/types";

function StrategyUrlRow({ strategy, url }: { strategy: { name: string; slug: string }; url: string }) {
  const { onCopy, hasCopied } = useClipboard(url);
  return (
    <Tr>
      <Td fontWeight="medium">{strategy.name}</Td>
      <Td><Code fontSize="xs">{strategy.slug}</Code></Td>
      <Td>
        <Code fontSize="xs" maxW="320px" display="block" isTruncated>
          {url}
        </Code>
      </Td>
      <Td>
        <IconButton
          aria-label="Copy strategy URL"
          icon={hasCopied ? <span>✓</span> : <span>⎘</span>}
          onClick={onCopy}
          size="xs"
          variant="ghost"
        />
      </Td>
    </Tr>
  );
}

const PAGE_SIZE = 50;

export default function WebhooksPage() {
  const toast = useToast();
  const { data: config, isLoading: configLoading, mutate: mutateConfig } = useWebhookConfig();
  const [offset, setOffset] = useState(0);
  const { data: signals, isLoading: signalsLoading, total } = useWebhookSignals(offset, PAGE_SIZE);
  const { data: strategies } = useStrategies();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [regenerating, setRegenerating] = useState(false);

  const webhookUrl = config?.webhook_url ?? "";
  const { onCopy, hasCopied } = useClipboard(webhookUrl);

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      await apiClient("/api/v1/webhooks/config/regenerate-token", { method: "POST" });
      await mutateConfig();
      toast({ title: "Token regenerated", status: "success", duration: 3000 });
    } catch {
      toast({ title: "Failed to regenerate token", status: "error", duration: 3000 });
    } finally {
      setRegenerating(false);
      onClose();
    }
  };

  const actionVariant = (action: string) => {
    const a = action?.toUpperCase();
    if (a === "BUY") return "success";
    if (a === "SELL") return "error";
    return "neutral";
  };

  const resultVariant = (result: string) => {
    const r = result?.toLowerCase();
    if (r === "passed") return "success";
    if (r === "blocked") return "error";
    if (r === "mapping_error") return "warning";
    return "neutral";
  };

  const columns: Column<WebhookSignal>[] = [
    {
      key: "received_at", header: "Time", sortable: true,
      render: (v) => formatDate(String(v ?? "")),
    },
    {
      key: "strategy_name", header: "Strategy",
      render: (_v, row) => row.strategy_name ?? row.strategy_id?.slice(0, 8) ?? "—",
    },
    {
      key: "parsed_signal", header: "Action",
      render: (v) => {
        const sig = v as Record<string, unknown> | null;
        if (!sig?.action) return "—";
        const action = String(sig.action).toUpperCase();
        return (
          <Badge colorScheme={action === "BUY" ? "green" : action === "SELL" ? "red" : "gray"} size="sm">
            {action}
          </Badge>
        );
      },
    },
    {
      key: "status", header: "Rule",
      render: (v) => {
        const status = String(v ?? "");
        const variant = status === "passed" ? "success" : status === "blocked_by_rule" ? "error" : "warning";
        return <StatusBadge variant={variant} text={status} />;
      },
    },
    {
      key: "execution_result", header: "Execution",
      render: (v) => {
        if (!v) return "—";
        const r = String(v);
        const variant = r === "filled" ? "success" : r === "broker_error" ? "error" : "warning";
        return <StatusBadge variant={variant} text={r} />;
      },
    },
    {
      key: "execution_detail", header: "Fill Price",
      render: (v) => {
        const detail = v as WebhookSignal["execution_detail"];
        if (!detail?.fill_price) return "—";
        return Number(detail.fill_price).toFixed(2);
      },
    },
    {
      key: "error_message", header: "Detail",
      render: (_v, row) => {
        if (row.error_message) return row.error_message;
        const detail = row.execution_detail;
        if (detail?.error) return detail.error;
        if (detail?.order_id) return `Order: ${detail.order_id}`;
        return "—";
      },
    },
  ];

  return (
    <Box>
      <Heading size="lg" mb={6}>Webhooks</Heading>

      <Card mb={6}>
        <CardHeader>
          <Heading size="md">Broadcast URL</Heading>
          <Text fontSize="sm" color="gray.500" mt={1}>Triggers all active strategies simultaneously</Text>
        </CardHeader>
        <CardBody>
          <VStack align="stretch" spacing={4}>
            <HStack>
              <Code flex={1} p={3} borderRadius="md" fontSize="sm" overflowX="auto">
                {configLoading ? "Loading..." : webhookUrl}
              </Code>
              <IconButton
                aria-label="Copy webhook URL"
                icon={<Text as="span" fontSize="xs">Copy</Text>}
                size="sm"
                onClick={onCopy}
                colorScheme={hasCopied ? "green" : "gray"}
              />
            </HStack>
            <Flex>
              <Button
                size="sm"
                colorScheme="orange"
                onClick={onOpen}
              >
                Regenerate Token
              </Button>
            </Flex>
          </VStack>
        </CardBody>
      </Card>

      {strategies && strategies.length > 0 && (
        <Card mb={6}>
          <CardHeader>
            <Heading size="sm">Strategy URLs</Heading>
            <Text fontSize="sm" color="gray.500" mt={1}>
              Target a single strategy by appending its slug to the broadcast URL
            </Text>
          </CardHeader>
          <CardBody p={0}>
            <TableContainer>
              <Table size="sm">
                <Thead>
                  <Tr>
                    <Th>Strategy</Th>
                    <Th>Slug</Th>
                    <Th>URL</Th>
                    <Th />
                  </Tr>
                </Thead>
                <Tbody>
                  {strategies.map((s) => {
                    const stratUrl = config
                      ? `${typeof window !== "undefined" ? window.location.origin : ""}/api/v1/webhook/${config.token}/${s.slug}`
                      : "";
                    return (
                      <StrategyUrlRow key={s.id} strategy={s} url={stratUrl} />
                    );
                  })}
                </Tbody>
              </Table>
            </TableContainer>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader>
          <Heading size="md">Signal Log</Heading>
        </CardHeader>
        <CardBody>
          <DataTable<WebhookSignal>
            columns={columns}
            data={signals ?? []}
            isLoading={signalsLoading}
            emptyMessage="No signals received yet."
          />
          <Pagination
            offset={offset}
            pageSize={PAGE_SIZE}
            total={total}
            onPrev={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            onNext={() => setOffset(offset + PAGE_SIZE)}
          />
        </CardBody>
      </Card>

      <ConfirmModal
        isOpen={isOpen}
        onClose={onClose}
        onConfirm={handleRegenerate}
        title="Regenerate Token"
        message="Are you sure you want to regenerate your webhook token? Your existing integrations will stop working until updated with the new URL."
        confirmLabel="Regenerate"
        isLoading={regenerating}
      />
    </Box>
  );
}
