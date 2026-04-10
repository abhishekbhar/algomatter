"use client";
import { HStack, Button, Text } from "@chakra-ui/react";

interface Props {
  offset: number;
  pageSize: number;
  total: number;
  onPrev: () => void;
  onNext: () => void;
}

export function Pagination({ offset, pageSize, total, onPrev, onNext }: Props) {
  if (total <= pageSize) return null;
  return (
    <HStack mt={2} justify="center">
      <Button size="xs" isDisabled={offset === 0} onClick={onPrev}>Prev</Button>
      <Text fontSize="xs">
        {offset + 1}–{Math.min(offset + pageSize, total)} of {total}
      </Text>
      <Button size="xs" isDisabled={offset + pageSize >= total} onClick={onNext}>Next</Button>
    </HStack>
  );
}
