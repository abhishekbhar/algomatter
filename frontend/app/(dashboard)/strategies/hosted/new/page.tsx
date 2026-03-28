"use client";
import { useState } from "react";
import {
  Box, Heading, SimpleGrid, Button, Input, Text, useToast,
  useColorModeValue, Flex, Badge,
} from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { useStrategyTemplates } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";

export default function NewHostedStrategyPage() {
  const router = useRouter();
  const toast = useToast();
  const { data: templates, isLoading } = useStrategyTemplates();
  const [name, setName] = useState("");
  const [selectedTemplate, setSelectedTemplate] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const cardBg = useColorModeValue("white", "gray.800");
  const selectedBorder = useColorModeValue("blue.500", "blue.300");

  const handleCreate = async () => {
    if (!name.trim()) {
      toast({ title: "Please enter a strategy name", status: "warning", duration: 3000 });
      return;
    }
    const template = selectedTemplate !== null ? templates?.[selectedTemplate] : null;
    setCreating(true);
    try {
      const result = await apiClient<{ id: string }>("/api/v1/hosted-strategies", {
        method: "POST",
        body: {
          name: name.trim(),
          code: template?.code ?? "class Strategy(AlgoMatterStrategy):\n    def on_candle(self, candle):\n        pass\n",
          description: template?.description ?? "",
        },
      });
      toast({ title: "Strategy created", status: "success", duration: 3000 });
      router.push(`/strategies/hosted/${result.id}`);
    } catch {
      toast({ title: "Failed to create strategy", status: "error", duration: 3000 });
    } finally {
      setCreating(false);
    }
  };

  return (
    <Box>
      <Heading size="lg" mb={6}>New Hosted Strategy</Heading>

      <Box mb={6}>
        <Text fontWeight="medium" mb={2}>Strategy Name</Text>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="My Trading Strategy"
          maxW="400px"
        />
      </Box>

      <Text fontWeight="medium" mb={3}>Choose a Template</Text>
      {isLoading ? (
        <Text color="gray.500">Loading templates...</Text>
      ) : (
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4} mb={6}>
          {(templates ?? []).map((t, i) => (
            <Box
              key={t.name}
              p={4}
              bg={cardBg}
              borderRadius="lg"
              border="2px"
              borderColor={selectedTemplate === i ? selectedBorder : "transparent"}
              shadow="sm"
              cursor="pointer"
              onClick={() => setSelectedTemplate(i)}
              _hover={{ shadow: "md" }}
            >
              <Text fontWeight="bold" mb={1}>{t.name}</Text>
              <Text fontSize="sm" color="gray.500" mb={2}>{t.description}</Text>
              {Object.keys(t.params).length > 0 && (
                <Flex gap={1} flexWrap="wrap">
                  {Object.keys(t.params).map((k) => (
                    <Badge key={k} size="sm" variant="subtle" colorScheme="gray">{k}</Badge>
                  ))}
                </Flex>
              )}
            </Box>
          ))}
        </SimpleGrid>
      )}

      <Flex gap={3}>
        <Button colorScheme="blue" onClick={handleCreate} isLoading={creating}>
          Create Strategy
        </Button>
        <Button variant="outline" onClick={() => router.back()}>Cancel</Button>
      </Flex>
    </Box>
  );
}
