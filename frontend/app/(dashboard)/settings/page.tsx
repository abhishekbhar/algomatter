"use client";
import {
  Box, Heading, SimpleGrid, Text, Flex, Input, IconButton,
  Switch, FormControl, FormLabel, useColorModeValue, useColorMode, useClipboard,
} from "@chakra-ui/react";
import { MdContentCopy } from "react-icons/md";
import { useHealth, useWebhookConfig } from "@/lib/hooks/useApi";
import { useAuth } from "@/lib/hooks/useAuth";
import { StatusBadge } from "@/components/shared/StatusBadge";

export default function SettingsPage() {
  const cardBg = useColorModeValue("white", "gray.800");
  const { colorMode, toggleColorMode } = useColorMode();
  const { user } = useAuth();
  const { data: health, isLoading: healthLoading } = useHealth();
  const { data: webhookConfig } = useWebhookConfig();

  const token = webhookConfig?.token ?? "";
  const { onCopy, hasCopied } = useClipboard(token);

  const isHealthy = health?.status === "ok";

  return (
    <Box>
      <Heading size="lg" mb={6}>
        Settings
      </Heading>

      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
        {/* System Health */}
        <Box bg={cardBg} p={6} borderRadius="lg" shadow="sm">
          <Heading size="sm" mb={4}>
            System Health
          </Heading>
          {healthLoading ? (
            <Text color="gray.500">Loading...</Text>
          ) : (
            <Flex direction="column" gap={3}>
              <Flex justify="space-between" align="center">
                <Text>Database</Text>
                <StatusBadge
                  variant={isHealthy ? "success" : "error"}
                  text={isHealthy ? "Connected" : "Disconnected"}
                />
              </Flex>
              <Flex justify="space-between" align="center">
                <Text>Redis</Text>
                <StatusBadge
                  variant={isHealthy ? "success" : "error"}
                  text={isHealthy ? "Connected" : "Disconnected"}
                />
              </Flex>
            </Flex>
          )}
        </Box>

        {/* Profile */}
        <Box bg={cardBg} p={6} borderRadius="lg" shadow="sm">
          <Heading size="sm" mb={4}>
            Profile
          </Heading>
          <Flex direction="column" gap={3}>
            <Flex justify="space-between" align="center">
              <Text>Email</Text>
              <Text fontWeight="medium">{user?.email ?? "—"}</Text>
            </Flex>
            <Flex justify="space-between" align="center">
              <Text>Plan</Text>
              <Text fontWeight="medium">{user?.plan ?? "free"}</Text>
            </Flex>
            <Box>
              <Text mb={1}>Webhook Token</Text>
              <Flex>
                <Input
                  value={token}
                  isReadOnly
                  size="sm"
                  fontFamily="mono"
                  mr={2}
                />
                <IconButton
                  aria-label="Copy token"
                  icon={<MdContentCopy />}
                  size="sm"
                  onClick={onCopy}
                  colorScheme={hasCopied ? "green" : "gray"}
                />
              </Flex>
            </Box>
          </Flex>
        </Box>

        {/* Theme */}
        <Box bg={cardBg} p={6} borderRadius="lg" shadow="sm">
          <Heading size="sm" mb={4}>
            Theme
          </Heading>
          <FormControl display="flex" alignItems="center">
            <FormLabel htmlFor="dark-mode-toggle" mb="0">
              Dark Mode
            </FormLabel>
            <Switch
              id="dark-mode-toggle"
              isChecked={colorMode === "dark"}
              onChange={toggleColorMode}
            />
          </FormControl>
        </Box>
      </SimpleGrid>
    </Box>
  );
}
