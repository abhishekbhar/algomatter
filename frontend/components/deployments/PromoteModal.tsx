"use client";
import { useState } from "react";
import {
  Modal, ModalOverlay, ModalContent, ModalHeader, ModalBody, ModalFooter, ModalCloseButton,
  Button, FormControl, FormLabel, Input, Select, Text, useToast, VStack,
} from "@chakra-ui/react";
import { apiClient } from "@/lib/api/client";
import { useBrokers } from "@/lib/hooks/useApi";
import type { Deployment } from "@/lib/api/types";

interface PromoteModalProps {
  isOpen: boolean;
  onClose: () => void;
  deployment: Deployment | null;
  onPromoted?: () => void;
}

export function PromoteModal({ isOpen, onClose, deployment, onPromoted }: PromoteModalProps) {
  const toast = useToast();
  const [brokerId, setBrokerId] = useState("");
  const [cronExpression, setCronExpression] = useState("*/5 * * * *");
  const [promoting, setPromoting] = useState(false);
  const { data: brokers } = useBrokers();

  if (!deployment) return null;

  const targetMode = deployment.mode === "backtest" ? "paper" : "live";
  const needsBroker = targetMode === "live";

  const handlePromote = async () => {
    if (needsBroker && !brokerId.trim()) {
      toast({ title: "Broker connection ID required for live", status: "warning", duration: 3000 });
      return;
    }
    setPromoting(true);
    try {
      await apiClient(`/api/v1/deployments/${deployment.id}/promote`, {
        method: "POST",
        body: JSON.stringify({
          broker_connection_id: needsBroker ? brokerId : null,
          cron_expression: cronExpression || null,
        }),
      });
      toast({ title: `Promoted to ${targetMode}`, status: "success", duration: 3000 });
      onPromoted?.();
      onClose();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Promotion failed";
      toast({ title: msg, status: "error", duration: 3000 });
    } finally {
      setPromoting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Promote to {targetMode.charAt(0).toUpperCase() + targetMode.slice(1)}</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <VStack spacing={4}>
            <Text fontSize="sm">
              Promoting {deployment.symbol} from <strong>{deployment.mode}</strong> to <strong>{targetMode}</strong>
            </Text>
            {needsBroker && (
              <FormControl isRequired>
                <FormLabel>Broker Connection</FormLabel>
                <Select
                  placeholder="Select broker"
                  value={brokerId}
                  onChange={(e) => setBrokerId(e.target.value)}
                >
                  {(brokers ?? []).map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.label} — {b.broker_type}
                    </option>
                  ))}
                </Select>
              </FormControl>
            )}
            <FormControl>
              <FormLabel>Cron Expression</FormLabel>
              <Input value={cronExpression} onChange={(e) => setCronExpression(e.target.value)} placeholder="*/5 * * * *" />
            </FormControl>
          </VStack>
        </ModalBody>
        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={onClose}>Cancel</Button>
          <Button colorScheme="blue" onClick={handlePromote} isLoading={promoting}>
            Promote to {targetMode}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
