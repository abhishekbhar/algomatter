"use client";
import { Box, Heading, Flex, Button } from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { DataTable, Column } from "@/components/shared/DataTable";
import { useHostedStrategies } from "@/lib/hooks/useApi";
import { formatDate } from "@/lib/utils/formatters";
import type { HostedStrategy } from "@/lib/api/types";

export default function HostedStrategiesPage() {
  const router = useRouter();
  const { data: strategies, isLoading } = useHostedStrategies();

  const columns: Column<HostedStrategy>[] = [
    { key: "name", header: "Name", sortable: true },
    { key: "version", header: "Version", render: (v) => `v${v}` },
    { key: "entrypoint", header: "Entry Point" },
    { key: "updated_at", header: "Last Updated", sortable: true, render: (v) => formatDate(String(v ?? "")) },
  ];

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6}>
        <Heading size="lg">Hosted Strategies</Heading>
        <Button size="sm" colorScheme="blue" onClick={() => router.push("/strategies/hosted/new")}>
          New Strategy
        </Button>
      </Flex>
      <DataTable<HostedStrategy>
        columns={columns}
        data={strategies ?? []}
        isLoading={isLoading}
        emptyMessage="No hosted strategies yet. Create your first strategy to get started."
        onRowClick={(row) => router.push(`/strategies/hosted/${row.id}`)}
      />
    </Box>
  );
}
