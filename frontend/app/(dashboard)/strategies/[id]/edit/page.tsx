"use client";
import {
  Box, Heading, FormControl, FormLabel, Input, Select, Radio, RadioGroup,
  Stack, Switch, Textarea, Button, VStack, useToast, NumberInput,
  NumberInputField, Divider, Text, Spinner, Center, Flex,
} from "@chakra-ui/react";
import { useRouter, useParams } from "next/navigation";
import { useState, useEffect } from "react";
import { useBrokers, useStrategy } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";

interface StrategyForm {
  name: string;
  broker_connection_id: string;
  mode: string;
  is_active: boolean;
  mapping_template: string;
  symbol_whitelist: string;
  symbol_blacklist: string;
  max_positions: number;
  max_signals_per_day: number;
}

export default function EditStrategyPage() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;
  const toast = useToast();
  const { data: brokers } = useBrokers();
  const { data: strategy, isLoading } = useStrategy(id);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState<StrategyForm>({
    name: "",
    broker_connection_id: "",
    mode: "paper",
    is_active: true,
    mapping_template: "",
    symbol_whitelist: "",
    symbol_blacklist: "",
    max_positions: 10,
    max_signals_per_day: 50,
  });

  useEffect(() => {
    if (!strategy) return;
    const s = strategy as Record<string, unknown>;
    const rules = (s.rules ?? {}) as Record<string, unknown>;
    setForm({
      name: String(s.name ?? ""),
      broker_connection_id: String(s.broker_connection_id ?? ""),
      mode: String(s.mode ?? "paper"),
      is_active: !!s.is_active,
      mapping_template: s.mapping_template ? JSON.stringify(s.mapping_template, null, 2) : "",
      symbol_whitelist: Array.isArray(rules.symbol_whitelist)
        ? (rules.symbol_whitelist as string[]).join(", ")
        : "",
      symbol_blacklist: Array.isArray(rules.symbol_blacklist)
        ? (rules.symbol_blacklist as string[]).join(", ")
        : "",
      max_positions: Number(rules.max_positions ?? 10),
      max_signals_per_day: Number(rules.max_signals_per_day ?? 50),
    });
  }, [strategy]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const payload = {
        name: form.name,
        broker_connection_id: form.broker_connection_id || null,
        mode: form.mode,
        is_active: form.is_active,
        mapping_template: form.mapping_template ? JSON.parse(form.mapping_template) : null,
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
      await apiClient(`/api/v1/strategies/${id}`, { method: "PUT", body: payload });
      toast({ title: "Strategy updated", status: "success", duration: 3000 });
      router.push(`/strategies/${id}`);
    } catch {
      toast({ title: "Failed to update strategy", status: "error", duration: 3000 });
    } finally {
      setSubmitting(false);
    }
  };

  if (isLoading) {
    return <Center py={20}><Spinner size="xl" /></Center>;
  }

  return (
    <Box maxW="600px">
      <Heading size="lg" mb={6}>Edit Strategy</Heading>
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
                  {b.broker_type} ({b.is_active ? "Active" : "Inactive"})
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

          <FormControl>
            <FormLabel>Mapping Template (JSON)</FormLabel>
            <Textarea
              value={form.mapping_template}
              onChange={(e) => setForm({ ...form, mapping_template: e.target.value })}
              placeholder='{"symbol": "$.ticker", "action": "$.side"}'
              rows={4}
            />
          </FormControl>

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
              Update Strategy
            </Button>
            <Button variant="ghost" onClick={() => router.push(`/strategies/${id}`)}>
              Cancel
            </Button>
          </Flex>
        </VStack>
      </form>
    </Box>
  );
}
