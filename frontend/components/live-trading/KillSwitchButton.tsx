"use client";
import { Button, useDisclosure } from "@chakra-ui/react";
import { ConfirmModal } from "@/components/shared/ConfirmModal";
import { apiClient } from "@/lib/api/client";

interface Props {
  onComplete?: () => void;
}

export function KillSwitchButton({ onComplete }: Props) {
  const { isOpen, onOpen, onClose } = useDisclosure();

  const handleConfirm = async () => {
    await apiClient("/api/v1/deployments/stop-all", { method: "POST" });
    onClose();
    onComplete?.();
  };

  return (
    <>
      <Button colorScheme="red" size="sm" onClick={onOpen}>
        Kill All
      </Button>
      <ConfirmModal
        isOpen={isOpen}
        onClose={onClose}
        onConfirm={handleConfirm}
        title="Stop All Deployments"
        message="This will stop ALL active deployments and cancel all open orders. Are you sure?"
      />
    </>
  );
}
