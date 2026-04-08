"use client";
import {
  Box, Heading, FormControl, FormLabel, Input, Select, Radio, RadioGroup,
  Stack, Switch, Button, VStack, useToast, NumberInput,
  NumberInputField, Divider, Text, Flex,
} from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { useState, useCallback } from "react";
import { useBrokers, useWebhookConfig } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { WebhookParameterBuilder } from "@/components/strategies/WebhookParameterBuilder";

interface StrategyForm {
  name: string;
  broker_connection_id: string;
  mode: string;
  is_active: boolean;
  mapping_template_obj: Record<string, unknown> | null;
  symbol_whitelist: string;
  symbol_blacklist: string;
  max_positions: number;
  max_signals_per_day: number;
}

export default function NewStrategyPage() {
  const router = useRouter();
  const toast = useToast();
  const { data: brokers } = useBrokers();
  const { data: webhookConfig } = useWebhookConfig();
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState<StrategyForm>({
    name: "",
    broker_connection_id: "",
    mode: "paper",
    is_active: true,
    mapping_template_obj: null,
    symbol_whitelist: "",
    symbol_blacklist: "",
    max_positions: 10,
    max_signals_per_day: 50,
  });

  const handleMappingChange = useCallback(
    (val: Record<string, unknown>) => setForm((prev) => ({ ...prev, mapping_template_obj: val })),
    []
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Guard: LIMIT order type requires price
    const mt = form.mapping_template_obj ?? {};
    if (mt.order_type === "LIMIT" && !mt.price) {
      toast({
        title: "Price required",
        description: "Set a price value or signal field when order type is LIMIT.",
        status: "error",
        duration: 4000,
      });
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        name: form.name,
        broker_connection_id: form.broker_connection_id || null,
        mode: form.mode,
        is_active: form.is_active,
        mapping_template: form.mapping_template_obj ?? undefined,
        rules: {
          symbol_whitelist: form.symbol_whitelist
            ? form.symbol_whitelist.split(",").map((s) => s.trim()).filter(Boolean)
            : [],
          symbol_blacklist: form.symbol_blacklist
            ? form.symbol_blacklist.split(",").map((s) => s.trim()).filter(Boolean)
            : [],
          max_positions: form.max_positions,
          max_signals_per_day: form.max_signals_per_day,
        },
      };
      await apiClient("/api/v1/strategies", { method: "POST", body: payload });
      toast({ title: "Strategy created", status: "success", duration: 3000 });
      router.push("/strategies");
    } catch {
      toast({ title: "Failed to create strategy", status: "error", duration: 3000 });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box maxW="900px">
      <Heading size="lg" mb={6}>New Strategy</Heading>
      <form onSubmit={handleSubmit}>
        <VStack spacing={4} align="stretch">
          <FormControl isRequired>
            <FormLabel>Name</FormLabel>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. NIFTY Momentum"
            />
          </FormControl>

          <FormControl>
            <FormLabel>Broker Connection</FormLabel>
            <Select
              value={form.broker_connection_id}
              onChange={(e) => setForm({ ...form, broker_connection_id: e.target.value })}
              placeholder="Select broker (optional)"
            >
              {(brokers ?? []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.label} — {b.broker_type}{b.is_active ? "" : " (Inactive)"}
                </option>
              ))}
            </Select>
          </FormControl>

          <FormControl>
            <FormLabel>Mode</FormLabel>
            <RadioGroup
              value={form.mode}
              onChange={(val) => setForm({ ...form, mode: val })}
            >
              <Stack direction="row" spacing={4}>
                <Radio value="paper">Paper</Radio>
                <Radio value="live">Live</Radio>
              </Stack>
            </RadioGroup>
          </FormControl>

          <FormControl display="flex" alignItems="center">
            <FormLabel mb={0}>Active</FormLabel>
            <Switch
              isChecked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
          </FormControl>

          <Box>
            <Text fontWeight="medium" mb={3}>Signal Mapping</Text>
            <WebhookParameterBuilder
              value={form.mapping_template_obj}
              onChange={handleMappingChange}
              webhookUrl={webhookConfig?.webhook_url}
            />
          </Box>

          <Divider />
          <Text fontWeight="bold">Rules</Text>

          <FormControl>
            <FormLabel>Symbol Whitelist (comma-separated)</FormLabel>
            <Input
              value={form.symbol_whitelist}
              onChange={(e) => setForm({ ...form, symbol_whitelist: e.target.value })}
              placeholder="NIFTY, BANKNIFTY, RELIANCE"
            />
          </FormControl>

          <FormControl>
            <FormLabel>Symbol Blacklist (comma-separated)</FormLabel>
            <Input
              value={form.symbol_blacklist}
              onChange={(e) => setForm({ ...form, symbol_blacklist: e.target.value })}
              placeholder="PENNY1, PENNY2"
            />
          </FormControl>

          <FormControl>
            <FormLabel>Max Positions</FormLabel>
            <NumberInput
              value={form.max_positions}
              onChange={(_, val) => setForm({ ...form, max_positions: val || 0 })}
              min={1}
              max={1000}
            >
              <NumberInputField />
            </NumberInput>
          </FormControl>

          <FormControl>
            <FormLabel>Max Signals Per Day</FormLabel>
            <NumberInput
              value={form.max_signals_per_day}
              onChange={(_, val) => setForm({ ...form, max_signals_per_day: val || 0 })}
              min={1}
              max={10000}
            >
              <NumberInputField />
            </NumberInput>
          </FormControl>

          <Flex gap={3} pt={4}>
            <Button type="submit" colorScheme="blue" isLoading={submitting}>
              Create Strategy
            </Button>
            <Button variant="ghost" onClick={() => router.push("/strategies")}>
              Cancel
            </Button>
          </Flex>
        </VStack>
      </form>
    </Box>
  );
}
