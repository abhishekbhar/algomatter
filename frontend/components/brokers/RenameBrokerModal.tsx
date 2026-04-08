"use client";
import {
  Button, FormControl, FormErrorMessage, FormLabel, Input,
  Modal, ModalBody, ModalCloseButton, ModalContent, ModalFooter, ModalHeader, ModalOverlay,
} from "@chakra-ui/react";
import { useEffect, useState } from "react";
import { ApiError, apiClient } from "@/lib/api/client";

const MAX_LABEL_LEN = 40;

export interface RenameBrokerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRenamed: () => void;
  connectionId: string;
  currentLabel: string;
}

export function RenameBrokerModal({
  isOpen,
  onClose,
  onRenamed,
  connectionId,
  currentLabel,
}: RenameBrokerModalProps) {
  const [label, setLabel] = useState(currentLabel);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setLabel(currentLabel);
      setError(null);
      setSaving(false);
    }
  }, [isOpen, currentLabel]);

  const trimmed = label.trim();
  const valid = trimmed.length > 0 && trimmed.length <= MAX_LABEL_LEN;

  const handleSave = async () => {
    if (!valid) return;
    setSaving(true);
    setError(null);
    try {
      await apiClient(`/api/v1/brokers/${connectionId}`, {
        method: "PATCH",
        body: { label: trimmed },
      });
      onRenamed();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("A connection with this label already exists");
      } else {
        setError("Failed to rename broker");
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} isCentered>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Rename broker connection</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <FormControl isRequired isInvalid={error !== null}>
            <FormLabel>Label</FormLabel>
            <Input
              value={label}
              onChange={(e) => { setLabel(e.target.value); setError(null); }}
              maxLength={MAX_LABEL_LEN}
              placeholder="e.g. Main Exchange1"
            />
            {error && <FormErrorMessage>{error}</FormErrorMessage>}
          </FormControl>
        </ModalBody>
        <ModalFooter gap={2}>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button
            colorScheme="blue"
            onClick={handleSave}
            isLoading={saving}
            isDisabled={!valid || trimmed === currentLabel}
          >
            Save
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
