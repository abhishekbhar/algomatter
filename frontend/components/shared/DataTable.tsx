"use client";
import { useState, useMemo } from "react";
import { Table, Thead, Tbody, Tr, Th, Td, Box, Text, useColorModeValue } from "@chakra-ui/react";

export interface Column<T> {
  key: keyof T & string;
  header: string;
  sortable?: boolean;
  render?: (value: T[keyof T], row: T) => React.ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
  isLoading?: boolean;
}

export function DataTable<T extends Record<string, unknown>>({
  columns, data, onRowClick, emptyMessage = "No data", isLoading,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState(true);
  const hoverBg = useColorModeValue("gray.50", "gray.700");

  const sorted = useMemo(() => {
    if (!sortKey) return data;
    return [...data].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      if (av == null || bv == null) return 0;
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortAsc ? cmp : -cmp;
    });
  }, [data, sortKey, sortAsc]);

  const handleSort = (key: string) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(true); }
  };

  if (!isLoading && data.length === 0) {
    return <Text py={8} textAlign="center" color="gray.500">{emptyMessage}</Text>;
  }

  return (
    <Box overflowX="auto">
      <Table variant="simple" size="sm">
        <Thead>
          <Tr>
            {columns.map((col) => (
              <Th key={col.key} cursor={col.sortable ? "pointer" : "default"}
                onClick={col.sortable ? () => handleSort(col.key) : undefined} userSelect="none">
                {col.header}{sortKey === col.key && (sortAsc ? " ▲" : " ▼")}
              </Th>
            ))}
          </Tr>
        </Thead>
        <Tbody>
          {sorted.map((row, i) => (
            <Tr key={i} cursor={onRowClick ? "pointer" : "default"}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              _hover={onRowClick ? { bg: hoverBg } : {}}>
              {columns.map((col) => (
                <Td key={col.key}>{col.render ? col.render(row[col.key], row) : String(row[col.key] ?? "")}</Td>
              ))}
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  );
}
