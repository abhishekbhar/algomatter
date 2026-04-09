"use client";
import {
  Button,
  FormControl,
  FormLabel,
  Input,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
import { BROKER_FIELDS } from "@/lib/brokerFields";

export interface UpdateCredentialsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUpdated: () => void;
  connectionId: string;
  brokerType: string;
}

export function UpdateCredentialsModal({
  isOpen,
  onClose,
  onUpdated,
  connectionId,
  brokerType,
}: UpdateCredentialsModalProps) {
  const fields = BROKER_FIELDS[brokerType] ?? [];
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setCredentials({});
      setError(null);
      setSaving(false);
    }
  }, [isOpen]);

  const allFilled =
    fields.length > 0 && fields.every((f) => (credentials[f] ?? "").trim().length > 0);

  const handleSave = async () => {
    if (!allFilled) return;
    setSaving(true);
    setError(null);
    try {
      await apiClient(`/api/v1/brokers/${connectionId}`, {
        method: "PATCH",
        body: { credentials },
      });
      onClose();
      onUpdated();
    } catch {
      setError("Failed to update credentials");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} isCentered>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Update credentials</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <VStack spacing={3} align="stretch">
            {fields.map((field) => (
              <FormControl key={field} isRequired>
                <FormLabel>
                  {field.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                </FormLabel>
                <Input
                  type="password"
                  value={credentials[field] ?? ""}
                  onChange={(e) => {
                    setCredentials((prev) => ({ ...prev, [field]: e.target.value }));
                    setError(null);
                  }}
                  placeholder={`Enter new ${field}`}
                />
              </FormControl>
            ))}
            {error && (
              <Text color="red.400" fontSize="sm">
                {error}
              </Text>
            )}
          </VStack>
        </ModalBody>
        <ModalFooter gap={2}>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            colorScheme="blue"
            onClick={handleSave}
            isLoading={saving}
            isDisabled={!allFilled}
          >
            Update
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
