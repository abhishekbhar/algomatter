"use client";
import {
  Box, Heading, Button, FormControl, FormLabel, Input, Select, VStack, useToast,
} from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiClient } from "@/lib/api/client";

const BROKER_FIELDS: Record<string, string[]> = {
  zerodha: ["api_key", "api_secret", "user_id"],
  exchange1: ["api_key", "private_key"],
  binance_testnet: ["api_key", "api_secret"],
};

export default function NewBrokerPage() {
  const router = useRouter();
  const toast = useToast();
  const [brokerType, setBrokerType] = useState("");
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const fields = brokerType ? BROKER_FIELDS[brokerType] ?? [] : [];

  const handleFieldChange = (field: string, value: string) => {
    setCredentials((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!brokerType) return;
    setSubmitting(true);
    try {
      await apiClient("/api/v1/brokers", {
        method: "POST",
        body: { broker_type: brokerType, credentials },
      });
      toast({ title: "Broker added", status: "success", duration: 3000 });
      router.push("/brokers");
    } catch {
      toast({ title: "Failed to add broker", status: "error", duration: 3000 });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box maxW="md">
      <Heading size="lg" mb={6}>Add Broker</Heading>
      <form onSubmit={handleSubmit}>
        <VStack spacing={4} align="stretch">
          <FormControl isRequired>
            <FormLabel>Broker Type</FormLabel>
            <Select
              placeholder="Select broker"
              value={brokerType}
              onChange={(e) => {
                setBrokerType(e.target.value);
                setCredentials({});
              }}
            >
              <option value="zerodha">Zerodha</option>
              <option value="exchange1">Exchange1</option>
              <option value="binance_testnet">Binance Testnet</option>
            </Select>
          </FormControl>

          {fields.map((field) => (
            <FormControl key={field} isRequired>
              <FormLabel>{field.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}</FormLabel>
              <Input
                type="password"
                value={credentials[field] ?? ""}
                onChange={(e) => handleFieldChange(field, e.target.value)}
                placeholder={`Enter ${field}`}
              />
            </FormControl>
          ))}

          <Button
            type="submit"
            colorScheme="blue"
            isLoading={submitting}
            isDisabled={!brokerType || fields.some((f) => !credentials[f])}
          >
            Add Broker
          </Button>
        </VStack>
      </form>
    </Box>
  );
}
