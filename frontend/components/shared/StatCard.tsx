"use client";
import { Box, Text, useColorModeValue } from "@chakra-ui/react";

interface StatCardProps { label: string; value: string; change?: number; }

export function StatCard({ label, value, change }: StatCardProps) {
  const bg = useColorModeValue("white", "gray.800");
  const changeColor = change && change >= 0 ? "green.500" : "red.500";
  return (
    <Box bg={bg} p={4} borderRadius="lg" shadow="sm" border="1px" borderColor="gray.200">
      <Text fontSize="sm" color="gray.500">{label}</Text>
      <Text fontSize="2xl" fontWeight="bold" mt={1}>{value}</Text>
      {change !== undefined && (
        <Text fontSize="sm" color={changeColor} mt={1}>
          {change >= 0 ? "+" : ""}{change.toFixed(2)}%
        </Text>
      )}
    </Box>
  );
}
