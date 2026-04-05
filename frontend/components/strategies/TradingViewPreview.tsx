"use client";
import {
  Box,
  Button,
  Code,
  Heading,
  HStack,
  Text,
  useClipboard,
  useColorModeValue,
  VStack,
} from "@chakra-ui/react";

interface Props {
  mappingTemplate: Record<string, unknown>;
  webhookUrl?: string;
}

function buildTradingViewJson(
  mappingTemplate: Record<string, unknown>
): Record<string, string> {
  const tv: Record<string, string> = {};
  for (const value of Object.values(mappingTemplate)) {
    if (typeof value === "string" && value.startsWith("$.")) {
      const fieldName = value.slice(2); // strip "$."
      tv[fieldName] = `{{${fieldName}}}`;
    }
  }
  return tv;
}

export function TradingViewPreview({ mappingTemplate, webhookUrl }: Props) {
  const tvJson = buildTradingViewJson(mappingTemplate);
  const tvJsonStr = JSON.stringify(tvJson, null, 2);
  const { hasCopied: copiedJson, onCopy: onCopyJson } = useClipboard(tvJsonStr);
  const { hasCopied: copiedUrl, onCopy: onCopyUrl } = useClipboard(
    webhookUrl ?? ""
  );
  const borderColor = useColorModeValue("gray.200", "gray.700");
  const preBg = useColorModeValue("gray.50", "gray.900");
  const preColor = useColorModeValue("gray.800", "gray.100");
  const listColor = useColorModeValue("gray.700", "gray.300");

  return (
    <VStack spacing={4} align="stretch">
      {/* Webhook URL */}
      {webhookUrl && (
        <Box borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
          <Text
            fontSize="xs"
            fontWeight="semibold"
            color="gray.500"
            mb={2}
            textTransform="uppercase"
          >
            Webhook URL
          </Text>
          <HStack>
            <Text fontSize="xs" fontFamily="mono" flex={1} noOfLines={1}>
              {webhookUrl}
            </Text>
            <Button
              size="xs"
              onClick={onCopyUrl}
              colorScheme={copiedUrl ? "green" : "gray"}
            >
              {copiedUrl ? "Copied!" : "Copy"}
            </Button>
          </HStack>
        </Box>
      )}

      {/* TradingView JSON preview */}
      <Box borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
        <HStack justify="space-between" mb={3}>
          <Heading
            size="xs"
            color="gray.500"
            textTransform="uppercase"
          >
            TradingView Alert Message
          </Heading>
          <Button
            size="xs"
            onClick={onCopyJson}
            colorScheme={copiedJson ? "green" : "blue"}
          >
            {copiedJson ? "Copied!" : "Copy JSON"}
          </Button>
        </HStack>
        <Box
          as="pre"
          fontSize="xs"
          fontFamily="mono"
          whiteSpace="pre-wrap"
          bg={preBg}
          color={preColor}
          p={3}
          borderRadius="sm"
          data-testid="tv-json-preview"
        >
          {tvJsonStr}
        </Box>
        <Text
          fontSize="xs"
          color="gray.500"
          mt={3}
          borderTopWidth={1}
          borderColor={borderColor}
          pt={2}
        >
          Paste this as your TradingView alert "Message" — copy once, works forever.
        </Text>
      </Box>

      {/* How to use */}
      <Box borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
        <Heading
          size="xs"
          mb={3}
          color="gray.500"
          textTransform="uppercase"
        >
          How to use in TradingView
        </Heading>
        <VStack
          align="start"
          spacing={2}
          fontSize="sm"
          color={listColor}
        >
          <Text>1. In your Pine Script strategy, add an alert</Text>
          <Text>
            2. Set the alert <Code fontSize="xs">URL</Code> field to the endpoint above
          </Text>
          <Text>
            3. Set <Code fontSize="xs">Message</Code> to the JSON above
          </Text>
          <Text>4. Every alert fires a trade automatically</Text>
        </VStack>
      </Box>
    </VStack>
  );
}
