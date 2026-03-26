"use client";
import {
  Box, Heading, Flex, Button, Switch, IconButton, useDisclosure, useToast,
} from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { DataTable, Column } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmModal } from "@/components/shared/ConfirmModal";
import { useStrategies } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { formatDate } from "@/lib/utils/formatters";
import type { Strategy } from "@/lib/api/types";

export default function StrategiesPage() {
  const router = useRouter();
  const toast = useToast();
  const { data: strategies, isLoading, mutate } = useStrategies();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [deleteTarget, setDeleteTarget] = useState<Strategy | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [modeFilter, setModeFilter] = useState<string>("all");

  const filtered = (strategies ?? []).filter(
    (s) => modeFilter === "all" || s.mode === modeFilter
  );

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await apiClient(`/api/v1/strategies/${deleteTarget.id}`, { method: "DELETE" });
      toast({ title: "Strategy deleted", status: "success", duration: 3000 });
      mutate();
    } catch {
      toast({ title: "Failed to delete strategy", status: "error", duration: 3000 });
    } finally {
      setDeleting(false);
      setDeleteTarget(null);
      onClose();
    }
  };

  const columns: Column<Strategy>[] = [
    { key: "name", header: "Name", sortable: true },
    {
      key: "mode", header: "Mode",
      render: (v) => {
        const mode = String(v ?? "");
        return <StatusBadge variant={mode === "live" ? "error" : "info"} text={mode} />;
      },
    },
    {
      key: "is_active", header: "Active",
      render: (v) => <Switch isChecked={!!v} isReadOnly size="sm" />,
    },
    {
      key: "created_at", header: "Created", sortable: true,
      render: (v) => formatDate(String(v ?? "")),
    },
    {
      key: "id", header: "",
      render: (_v, row) => (
        <Button
          size="xs"
          colorScheme="red"
          variant="ghost"
          onClick={(e) => {
            e.stopPropagation();
            setDeleteTarget(row);
            onOpen();
          }}
        >
          Delete
        </Button>
      ),
    },
  ];

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6}>
        <Heading size="lg">Strategies</Heading>
        <Flex gap={3} align="center">
          <Button
            size="xs"
            variant={modeFilter === "all" ? "solid" : "outline"}
            onClick={() => setModeFilter("all")}
          >
            All
          </Button>
          <Button
            size="xs"
            variant={modeFilter === "paper" ? "solid" : "outline"}
            onClick={() => setModeFilter("paper")}
          >
            Paper
          </Button>
          <Button
            size="xs"
            variant={modeFilter === "live" ? "solid" : "outline"}
            onClick={() => setModeFilter("live")}
          >
            Live
          </Button>
          <Button size="sm" colorScheme="blue" onClick={() => router.push("/strategies/new")}>
            New Strategy
          </Button>
        </Flex>
      </Flex>

      <DataTable<Strategy>
        columns={columns}
        data={filtered}
        isLoading={isLoading}
        emptyMessage="No strategies found. Create your first strategy to get started."
        onRowClick={(row) => router.push(`/strategies/${row.id}`)}
      />

      <ConfirmModal
        isOpen={isOpen}
        onClose={() => { setDeleteTarget(null); onClose(); }}
        onConfirm={handleDelete}
        title="Delete Strategy"
        message={`Are you sure you want to delete "${deleteTarget?.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        isLoading={deleting}
      />
    </Box>
  );
}
