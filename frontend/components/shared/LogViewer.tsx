"use client";
import { useState } from "react";
import { Box, Text, Flex, Button, useColorModeValue } from "@chakra-ui/react";
import { useDeploymentLogs } from "@/lib/hooks/useApi";

interface LogViewerProps {
  deploymentId: string;
}

const LEVEL_COLORS: Record<string, string> = {
  error: "red.400",
  warning: "orange.400",
  info: "blue.400",
  debug: "gray.400",
};

const PAGE_SIZE = 50;

export function LogViewer({ deploymentId }: LogViewerProps) {
  const [offset, setOffset] = useState(0);
  const { data, isLoading } = useDeploymentLogs(deploymentId, offset, PAGE_SIZE);
  const bg = useColorModeValue("gray.50", "gray.900");

  return (
    <Box>
      <Box bg={bg} borderRadius="md" p={3} fontFamily="mono" fontSize="xs" maxH="400px" overflowY="auto">
        {isLoading ? (
          <Text color="gray.500">Loading logs...</Text>
        ) : (data?.logs ?? []).length === 0 ? (
          <Text color="gray.500">No logs yet</Text>
        ) : (
          (data?.logs ?? []).map((log) => (
            <Flex key={log.id} gap={2} py={0.5}>
              <Text color="gray.500" flexShrink={0}>
                {new Date(log.timestamp).toLocaleTimeString()}
              </Text>
              <Text color={LEVEL_COLORS[log.level] || "gray.400"} flexShrink={0} fontWeight="bold">
                [{log.level.toUpperCase()}]
              </Text>
              <Text>{log.message}</Text>
            </Flex>
          ))
        )}
      </Box>
      {data && data.total > PAGE_SIZE && (
        <Flex justify="space-between" mt={2}>
          <Button size="xs" onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} isDisabled={offset === 0}>
            Previous
          </Button>
          <Text fontSize="xs" color="gray.500">
            {offset + 1}-{Math.min(offset + PAGE_SIZE, data.total)} of {data.total}
          </Text>
          <Button size="xs" onClick={() => setOffset(offset + PAGE_SIZE)} isDisabled={offset + PAGE_SIZE >= data.total}>
            Next
          </Button>
        </Flex>
      )}
    </Box>
  );
}
