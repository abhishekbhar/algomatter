"use client";
import { VStack, Text, Button } from "@chakra-ui/react";

interface EmptyStateProps { title: string; description?: string; actionLabel?: string; onAction?: () => void; }

export function EmptyState({ title, description, actionLabel, onAction }: EmptyStateProps) {
  return (
    <VStack py={16} spacing={4}>
      <Text fontSize="lg" fontWeight="semibold" color="gray.500">{title}</Text>
      {description && <Text color="gray.400">{description}</Text>}
      {actionLabel && onAction && <Button colorScheme="blue" onClick={onAction}>{actionLabel}</Button>}
    </VStack>
  );
}
