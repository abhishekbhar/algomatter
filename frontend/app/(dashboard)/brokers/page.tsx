"use client";
import {
  Box, Heading, Flex, Button, IconButton, SimpleGrid, Card, CardHeader, CardBody, CardFooter,
  Text, useDisclosure, useToast,
} from "@chakra-ui/react";
import { MdEdit, MdKey } from "react-icons/md";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmModal } from "@/components/shared/ConfirmModal";
import { EmptyState } from "@/components/shared/EmptyState";
import { RenameBrokerModal } from "@/components/brokers/RenameBrokerModal";
import { UpdateCredentialsModal } from "@/components/brokers/UpdateCredentialsModal";
import { useBrokers } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { formatDate } from "@/lib/utils/formatters";

export default function BrokersPage() {
  const router = useRouter();
  const toast = useToast();
  const { data: brokers, isLoading, mutate } = useBrokers();
  const deleteDisclosure = useDisclosure();
  const renameDisclosure = useDisclosure();
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [renameTarget, setRenameTarget] = useState<{ id: string; label: string } | null>(null);
  const credentialsDisclosure = useDisclosure();
  const [credentialsTarget, setCredentialsTarget] = useState<{ id: string; brokerType: string } | null>(null);
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
      deleteDisclosure.onClose();
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
          <Link key={broker.id} href={`/brokers/${broker.id}`} style={{ textDecoration: "none" }}>
            <Card _hover={{ borderColor: "blue.400", cursor: "pointer" }} transition="border-color 0.15s">
              <CardHeader pb={2}>
                <Flex justify="space-between" align="start">
                  <Box>
                    <Text fontWeight="bold" fontSize="lg">{broker.label}</Text>
                    <Text fontSize="xs" color="gray.500" textTransform="uppercase">
                      {broker.broker_type}
                    </Text>
                  </Box>
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
              <CardFooter pt={2} gap={2}>
                <IconButton
                  aria-label="Rename broker"
                  icon={<MdEdit />}
                  size="xs"
                  variant="ghost"
                  onClick={(e) => {
                    e.preventDefault();
                    setRenameTarget({ id: broker.id, label: broker.label });
                    renameDisclosure.onOpen();
                  }}
                />
                <IconButton
                  aria-label="Update credentials"
                  icon={<MdKey />}
                  size="xs"
                  variant="ghost"
                  onClick={(e) => {
                    e.preventDefault();
                    setCredentialsTarget({ id: broker.id, brokerType: broker.broker_type });
                    credentialsDisclosure.onOpen();
                  }}
                />
                <Button
                  size="xs"
                  colorScheme="red"
                  variant="ghost"
                  onClick={(e) => { e.preventDefault(); setDeleteTarget(broker.id); deleteDisclosure.onOpen(); }}
                >
                  Delete
                </Button>
              </CardFooter>
            </Card>
          </Link>
        ))}
      </SimpleGrid>

      <ConfirmModal
        isOpen={deleteDisclosure.isOpen}
        onClose={() => { setDeleteTarget(null); deleteDisclosure.onClose(); }}
        onConfirm={handleDelete}
        title="Delete Broker"
        message="This will permanently delete the broker connection and all linked deployments and trade history. This action cannot be undone."
        confirmLabel="Delete"
        isLoading={deleting}
      />

      {renameTarget && (
        <RenameBrokerModal
          isOpen={renameDisclosure.isOpen}
          onClose={() => {
            setRenameTarget(null);
            renameDisclosure.onClose();
          }}
          onRenamed={() => {
            mutate();
            toast({ title: "Broker renamed", status: "success", duration: 3000 });
          }}
          connectionId={renameTarget.id}
          currentLabel={renameTarget.label}
        />
      )}

      {credentialsTarget && (
        <UpdateCredentialsModal
          isOpen={credentialsDisclosure.isOpen}
          onClose={() => {
            setCredentialsTarget(null);
            credentialsDisclosure.onClose();
          }}
          onUpdated={() => {
            mutate();
            toast({ title: "Credentials updated", status: "success", duration: 3000 });
          }}
          connectionId={credentialsTarget.id}
          brokerType={credentialsTarget.brokerType}
        />
      )}
    </Box>
  );
}
