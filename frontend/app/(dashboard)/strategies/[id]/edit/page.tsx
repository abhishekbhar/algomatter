"use client";
import {
  Box, Heading, FormControl, FormLabel, Input, Select, Radio, RadioGroup,
  Stack, Switch, Button, VStack, useToast, NumberInput,
  NumberInputField, Divider, Text, Spinner, Center, Flex, Collapse,
} from "@chakra-ui/react";
import { useRouter, useParams } from "next/navigation";
import { useState, useEffect, useCallback } from "react";
import { useBrokers, useStrategy, useWebhookConfig } from "@/lib/hooks/useApi";
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
  trading_hours_enabled: boolean;
  trading_hours_start: string;
  trading_hours_end: string;
  trading_hours_timezone: string;
  dual_leg_enabled: boolean;
  dual_leg_max_trades: number;
}

export default function EditStrategyPage() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;
  const toast = useToast();
  const { data: brokers } = useBrokers();
  const { data: strategy, isLoading } = useStrategy(id);
  const { data: webhookConfig } = useWebhookConfig();
  const [submitting, setSubmitting] = useState(false);
  const [tradingHoursOpen, setTradingHoursOpen] = useState(false);
  const [dualLegOpen, setDualLegOpen] = useState(false);
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
    trading_hours_enabled: false,
    trading_hours_start: "09:15",
    trading_hours_end: "15:30",
    trading_hours_timezone: "Asia/Kolkata",
    dual_leg_enabled: false,
    dual_leg_max_trades: 5,
  });

  useEffect(() => {
    if (!strategy) return;
    const rules = (strategy.rules ?? {}) as Record<string, unknown>;
    const dualLeg = (rules.dual_leg ?? {}) as Record<string, unknown>;
    const tradingHours = (rules.trading_hours ?? null) as Record<string, unknown> | null;
    setForm({
      name: strategy.name ?? "",
      broker_connection_id: strategy.broker_connection_id ?? "",
      mode: strategy.mode ?? "paper",
      is_active: strategy.is_active,
      mapping_template_obj: strategy.mapping_template
        ? (strategy.mapping_template as Record<string, unknown>)
        : null,
      symbol_whitelist: Array.isArray(rules.symbol_whitelist)
        ? (rules.symbol_whitelist as string[]).join(", ")
        : "",
      symbol_blacklist: Array.isArray(rules.symbol_blacklist)
        ? (rules.symbol_blacklist as string[]).join(", ")
        : "",
      max_positions: Number(rules.max_positions ?? 10),
      max_signals_per_day: Number(rules.max_signals_per_day ?? 50),
      trading_hours_enabled: !!tradingHours,
      trading_hours_start: String(tradingHours?.start ?? "09:15"),
      trading_hours_end: String(tradingHours?.end ?? "15:30"),
      trading_hours_timezone: String(tradingHours?.timezone ?? "Asia/Kolkata"),
      dual_leg_enabled: Boolean(dualLeg.enabled),
      dual_leg_max_trades: Number(dualLeg.max_trades ?? 5),
    });
    // Auto-expand panels if already configured
    if (tradingHours) setTradingHoursOpen(true);
    if (dualLeg.enabled) setDualLegOpen(true);
  }, [strategy]);

  const handleMappingChange = useCallback(
    (val: Record<string, unknown>) => setForm((prev) => ({ ...prev, mapping_template_obj: val })),
    []
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
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
    // Guard: trading hours start must be before end
    if (form.trading_hours_enabled && form.trading_hours_start >= form.trading_hours_end) {
      toast({
        title: "Trading hours: start time must be before end time",
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
          ...(form.trading_hours_enabled
            ? {
                trading_hours: {
                  start: form.trading_hours_start,
                  end: form.trading_hours_end,
                  timezone: form.trading_hours_timezone,
                },
              }
            : {}),
          ...(form.dual_leg_enabled
            ? { dual_leg: { enabled: true, max_trades: form.dual_leg_max_trades } }
            : {}),
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
    <Box maxW="900px">
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
              webhookUrl={
                webhookConfig?.webhook_url && strategy?.slug
                  ? `${webhookConfig.webhook_url}/${strategy.slug}`
                  : webhookConfig?.webhook_url
              }
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

          {/* Trading Hours Panel */}
          <Box border="1px" borderColor="gray.200" borderRadius="md" overflow="hidden">
            <Flex
              align="center"
              justify="space-between"
              px={4}
              py={3}
              cursor="pointer"
              onClick={() => setTradingHoursOpen(!tradingHoursOpen)}
              _hover={{ bg: "gray.50" }}
            >
              <Flex align="center" gap={2}>
                <Text fontSize="sm">{tradingHoursOpen ? "▼" : "▶"}</Text>
                <Text fontWeight="medium">Trading Hours</Text>
              </Flex>
              <Switch
                isChecked={form.trading_hours_enabled}
                onChange={(e) => {
                  e.stopPropagation();
                  const checked = e.target.checked;
                  setForm({ ...form, trading_hours_enabled: checked });
                  if (checked) setTradingHoursOpen(true);
                  else setTradingHoursOpen(false);
                }}
              />
            </Flex>
            <Collapse in={tradingHoursOpen} animateOpacity>
              <Box px={4} pb={4} pt={2} borderTop="1px" borderColor="gray.200">
                <Stack spacing={3}>
                  <Flex gap={4}>
                    <FormControl>
                      <FormLabel fontSize="sm">Start</FormLabel>
                      <Input
                        type="time"
                        value={form.trading_hours_start}
                        onChange={(e) => setForm({ ...form, trading_hours_start: e.target.value })}
                        isDisabled={!form.trading_hours_enabled}
                        size="sm"
                      />
                    </FormControl>
                    <FormControl>
                      <FormLabel fontSize="sm">End</FormLabel>
                      <Input
                        type="time"
                        value={form.trading_hours_end}
                        onChange={(e) => setForm({ ...form, trading_hours_end: e.target.value })}
                        isDisabled={!form.trading_hours_enabled}
                        size="sm"
                      />
                    </FormControl>
                  </Flex>
                  <FormControl>
                    <FormLabel fontSize="sm">Timezone</FormLabel>
                    <Select
                      value={form.trading_hours_timezone}
                      onChange={(e) => setForm({ ...form, trading_hours_timezone: e.target.value })}
                      isDisabled={!form.trading_hours_enabled}
                      size="sm"
                    >
                      <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
                      <option value="UTC">UTC</option>
                      <option value="US/Eastern">US/Eastern (ET)</option>
                      <option value="US/Pacific">US/Pacific (PT)</option>
                    </Select>
                  </FormControl>
                </Stack>
              </Box>
            </Collapse>
          </Box>

          {/* Dual-Leg Execution Panel */}
          <Box border="1px" borderColor="gray.200" borderRadius="md" overflow="hidden">
            <Flex
              align="center"
              justify="space-between"
              px={4}
              py={3}
              cursor="pointer"
              onClick={() => setDualLegOpen(!dualLegOpen)}
              _hover={{ bg: "gray.50" }}
            >
              <Flex align="center" gap={2}>
                <Text fontSize="sm">{dualLegOpen ? "▼" : "▶"}</Text>
                <Text fontWeight="medium">Dual-Leg Execution</Text>
              </Flex>
              <Switch
                isChecked={form.dual_leg_enabled}
                onChange={(e) => {
                  e.stopPropagation();
                  const checked = e.target.checked;
                  setForm({ ...form, dual_leg_enabled: checked });
                  if (checked) setDualLegOpen(true);
                  else setDualLegOpen(false);
                }}
              />
            </Flex>
            <Collapse in={dualLegOpen} animateOpacity>
              <Box px={4} pb={4} pt={2} borderTop="1px" borderColor="gray.200">
                <FormControl>
                  <FormLabel fontSize="sm">Max Trades</FormLabel>
                  <NumberInput
                    value={form.dual_leg_max_trades}
                    onChange={(_, val) => setForm({ ...form, dual_leg_max_trades: val || 0 })}
                    min={0}
                    isDisabled={!form.dual_leg_enabled}
                  >
                    <NumberInputField />
                  </NumberInput>
                  <Text fontSize="xs" color="gray.500" mt={1}>0 = unlimited</Text>
                </FormControl>
              </Box>
            </Collapse>
          </Box>

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
