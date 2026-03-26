"use client";
import {
  Box, Heading, Flex, Button, SimpleGrid, Card, CardHeader, CardBody, CardFooter,
  Text, useDisclosure, useToast,
} from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmModal } from "@/components/shared/ConfirmModal";
import { EmptyState } from "@/components/shared/EmptyState";
import { useBrokers } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { formatDate } from "@/lib/utils/formatters";

export default function BrokersPage() {
  const router = useRouter();
  const toast = useToast();
  const { data: brokers, isLoading, mutate } = useBrokers();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await apiClient(`/api/v1/brokers/${deleteTarget}`, { method: "DELETE" });
      toast({ title: "Broker deleted", status: "success", duration: 3000 });
      mutate();
    } catch {
      toast({ title: "Failed to delete broker", status: "error", duration: 3000 });
    } finally {
      setDeleting(false);
      setDeleteTarget(null);
      onClose();
    }
  };

  const list = brokers ?? [];

  if (!isLoading && list.length === 0) {
    return (
      <Box>
        <Flex justify="space-between" align="center" mb={6}>
          <Heading size="lg">Brokers</Heading>
          <Button size="sm" colorScheme="blue" onClick={() => router.push("/brokers/new")}>
            Add Broker
          </Button>
        </Flex>
        <EmptyState
          title="No brokers connected"
          description="Connect a broker to start trading."
          actionLabel="Add Broker"
          onAction={() => router.push("/brokers/new")}
        />
      </Box>
    );
  }

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6}>
        <Heading size="lg">Brokers</Heading>
        <Button size="sm" colorScheme="blue" onClick={() => router.push("/brokers/new")}>
          Add Broker
        </Button>
      </Flex>

      <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
        {list.map((broker) => (
          <Card key={broker.id}>
            <CardHeader pb={2}>
              <Flex justify="space-between" align="center">
                <Text fontWeight="bold" fontSize="lg">{broker.broker_type}</Text>
                <StatusBadge
                  variant={broker.is_active ? "success" : "neutral"}
                  text={broker.is_active ? "Active" : "Inactive"}
                />
              </Flex>
            </CardHeader>
            <CardBody py={2}>
              <Text fontSize="sm" color="gray.500">
                Connected: {formatDate(broker.connected_at)}
              </Text>
            </CardBody>
            <CardFooter pt={2}>
              <Button
                size="xs"
                colorScheme="red"
                variant="ghost"
                onClick={() => { setDeleteTarget(broker.id); onOpen(); }}
              >
                Delete
              </Button>
            </CardFooter>
          </Card>
        ))}
      </SimpleGrid>

      <ConfirmModal
        isOpen={isOpen}
        onClose={() => { setDeleteTarget(null); onClose(); }}
        onConfirm={handleDelete}
        title="Delete Broker"
        message="Are you sure you want to delete this broker connection? This action cannot be undone."
        confirmLabel="Delete"
        isLoading={deleting}
      />
    </Box>
  );
}
