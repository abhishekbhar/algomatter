"use client";
import {
  Box, Heading, Flex, Code, IconButton, Button, useDisclosure, useToast, useClipboard,
  Card, CardHeader, CardBody, Text, VStack, HStack,
} from "@chakra-ui/react";
import { useState } from "react";
import { DataTable, Column } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmModal } from "@/components/shared/ConfirmModal";
import { useWebhookConfig, useWebhookSignals } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { formatDate } from "@/lib/utils/formatters";
import type { WebhookSignal } from "@/lib/api/types";

export default function WebhooksPage() {
  const toast = useToast();
  const { data: config, isLoading: configLoading, mutate: mutateConfig } = useWebhookConfig();
  const { data: signals, isLoading: signalsLoading } = useWebhookSignals();
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
    { key: "strategy_id", header: "Strategy" },
    {
      key: "status", header: "Status",
      render: (v) => {
        const status = String(v ?? "");
        const variant = status === "passed" ? "success" : status === "blocked" ? "error" : "warning";
        return <StatusBadge variant={variant} text={status} />;
      },
    },
    {
      key: "error_message", header: "Error",
      render: (v) => v ? String(v) : "\u2014",
    },
  ];

  return (
    <Box>
      <Heading size="lg" mb={6}>Webhooks</Heading>

      <Card mb={6}>
        <CardHeader>
          <Heading size="md">Webhook URL</Heading>
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
