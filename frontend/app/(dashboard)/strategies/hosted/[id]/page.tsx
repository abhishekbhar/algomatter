"use client";
import { useState, useEffect, useRef } from "react";
import {
  Box, Heading, Flex, Button, Tabs, TabList, TabPanels, Tab, TabPanel,
  Select, Text, useToast, useColorModeValue, Badge, VStack,
  Modal, ModalOverlay, ModalContent, ModalHeader, ModalBody, ModalFooter, ModalCloseButton,
  useDisclosure, FormControl, FormLabel, Input,
} from "@chakra-ui/react";
import { useParams, useRouter } from "next/navigation";
import MonacoEditor from "@/components/editor/MonacoEditor";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { useHostedStrategy, useStrategyVersions, useDeployments } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import type { Deployment } from "@/lib/api/types";

export default function StrategyEditorPage() {
  const params = useParams();
  const router = useRouter();
  const toast = useToast();
  const strategyId = params.id as string;

  const { data: strategy, mutate: mutateStrategy } = useHostedStrategy(strategyId);
  const { data: versions } = useStrategyVersions(strategyId);
  const { data: deployments, mutate: mutateDeployments } = useDeployments(strategyId);

  const [code, setCode] = useState("");
  const [saving, setSaving] = useState(false);
  const [readOnly, setReadOnly] = useState(false);
  const cardBg = useColorModeValue("white", "gray.800");

  // Deploy modal state
  const { isOpen: isDeployOpen, onOpen: onDeployOpen, onClose: onDeployClose } = useDisclosure();
  const [deployMode, setDeployMode] = useState<string>("backtest");
  const [deploySymbol, setDeploySymbol] = useState("BTCUSDT");
  const [deployExchange, setDeployExchange] = useState("BINANCE");
  const [deployInterval, setDeployInterval] = useState("5m");
  const [deploying, setDeploying] = useState(false);

  useEffect(() => {
    if (strategy?.code && !code) {
      setCode(strategy.code);
    }
  }, [strategy?.code]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient(`/api/v1/hosted-strategies/${strategyId}`, {
        method: "PUT",
        body: { code },
      });
      mutateStrategy();
      toast({ title: "Strategy saved", status: "success", duration: 2000 });
    } catch {
      toast({ title: "Failed to save", status: "error", duration: 3000 });
    } finally {
      setSaving(false);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    setCode(text);
    toast({ title: "File loaded into editor. Press Save to persist.", status: "info", duration: 3000 });
    e.target.value = "";
  };

  const handleViewVersion = (version: number, versionCode: string) => {
    setCode(versionCode);
    setReadOnly(true);
  };

  const handleRestoreVersion = async (versionNumber: number) => {
    try {
      await apiClient(`/api/v1/hosted-strategies/${strategyId}/versions/${versionNumber}/restore`, {
        method: "POST",
      });
      mutateStrategy();
      setReadOnly(false);
      toast({ title: `Restored to v${versionNumber}`, status: "success", duration: 2000 });
    } catch {
      toast({ title: "Failed to restore", status: "error", duration: 3000 });
    }
  };

  const handleDeploy = async () => {
    setDeploying(true);
    try {
      await apiClient(`/api/v1/hosted-strategies/${strategyId}/deployments`, {
        method: "POST",
        body: {
          mode: deployMode,
          symbol: deploySymbol,
          exchange: deployExchange,
          interval: deployInterval,
          product_type: "DELIVERY",
        },
      });
      mutateDeployments();
      toast({ title: `${deployMode} deployment created`, status: "success", duration: 3000 });
      onDeployClose();
    } catch {
      toast({ title: "Failed to create deployment", status: "error", duration: 3000 });
    } finally {
      setDeploying(false);
    }
  };

  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!strategy) return <Text>Loading...</Text>;

  return (
    <Box h="calc(100vh - 80px)">
      {/* Top Bar */}
      <Flex justify="space-between" align="center" mb={4}>
        <Flex align="center" gap={3}>
          <Heading size="md">{strategy.name}</Heading>
          <Badge colorScheme="gray">v{strategy.version}</Badge>
          {readOnly && <Badge colorScheme="yellow">Read Only</Badge>}
        </Flex>
        <Flex gap={2}>
          {readOnly && (
            <Button size="sm" onClick={() => { setCode(strategy.code); setReadOnly(false); }}>
              Back to Current
            </Button>
          )}
          <input type="file" accept=".py" ref={fileInputRef} hidden onChange={handleUpload} />
          <Button size="sm" variant="outline" onClick={() => fileInputRef.current?.click()}>
            Upload .py
          </Button>
          <Button size="sm" colorScheme="blue" onClick={handleSave} isLoading={saving} isDisabled={readOnly}>
            Save
          </Button>
          <Button size="sm" colorScheme="green" onClick={onDeployOpen}>
            Deploy
          </Button>
        </Flex>
      </Flex>

      {/* Main Layout: Editor + Side Panel */}
      <Flex gap={4} h="calc(100% - 50px)">
        {/* Editor */}
        <Box flex="3" borderRadius="lg" overflow="hidden" border="1px" borderColor="gray.200">
          <MonacoEditor value={code} onChange={setCode} readOnly={readOnly} height="100%" />
        </Box>

        {/* Side Panel */}
        <Box flex="2" bg={cardBg} borderRadius="lg" p={4} overflowY="auto">
          <Tabs size="sm" variant="line">
            <TabList>
              <Tab>Versions</Tab>
              <Tab>Deployments</Tab>
            </TabList>
            <TabPanels>
              <TabPanel px={0}>
                <VStack spacing={2} align="stretch">
                  {(versions ?? []).map((v) => (
                    <Flex
                      key={v.id}
                      p={2}
                      borderRadius="md"
                      border="1px"
                      borderColor="gray.200"
                      justify="space-between"
                      align="center"
                    >
                      <Box>
                        <Text fontWeight="medium" fontSize="sm">Version {v.version}</Text>
                        <Text fontSize="xs" color="gray.500">
                          {new Date(v.created_at).toLocaleString()}
                        </Text>
                      </Box>
                      <Flex gap={1}>
                        <Button size="xs" variant="ghost" onClick={() => handleViewVersion(v.version, v.code)}>
                          View
                        </Button>
                        {v.version !== strategy.version && (
                          <Button size="xs" variant="ghost" colorScheme="blue" onClick={() => handleRestoreVersion(v.version)}>
                            Restore
                          </Button>
                        )}
                      </Flex>
                    </Flex>
                  ))}
                </VStack>
              </TabPanel>
              <TabPanel px={0}>
                <VStack spacing={2} align="stretch">
                  {(deployments ?? []).length === 0 ? (
                    <Text color="gray.500" fontSize="sm" textAlign="center" py={4}>
                      No deployments yet
                    </Text>
                  ) : (
                    (deployments ?? []).map((d: Deployment) => (
                      <Box
                        key={d.id}
                        p={2}
                        borderRadius="md"
                        border="1px"
                        borderColor="gray.200"
                      >
                        <Flex justify="space-between" align="center" mb={1}>
                          <StatusBadge
                            variant={
                              d.status === "running" ? "success" :
                              d.status === "completed" ? "info" :
                              d.status === "failed" ? "error" : "neutral"
                            }
                            text={d.status}
                          />
                          <Badge colorScheme={d.mode === "live" ? "red" : d.mode === "paper" ? "yellow" : "blue"}>
                            {d.mode}
                          </Badge>
                        </Flex>
                        <Text fontSize="xs" color="gray.500">
                          {d.symbol} &middot; {d.interval} &middot; {d.exchange}
                        </Text>
                        <Text fontSize="xs" color="gray.500">
                          {new Date(d.created_at).toLocaleString()}
                        </Text>
                      </Box>
                    ))
                  )}
                </VStack>
              </TabPanel>
            </TabPanels>
          </Tabs>
        </Box>
      </Flex>

      {/* Deploy Modal */}
      <Modal isOpen={isDeployOpen} onClose={onDeployClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Deploy Strategy</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl>
                <FormLabel>Mode</FormLabel>
                <Select value={deployMode} onChange={(e) => setDeployMode(e.target.value)}>
                  <option value="backtest">Backtest</option>
                  <option value="paper">Paper Trading</option>
                  <option value="live">Live Trading</option>
                </Select>
              </FormControl>
              <FormControl>
                <FormLabel>Symbol</FormLabel>
                <Input value={deploySymbol} onChange={(e) => setDeploySymbol(e.target.value)} />
              </FormControl>
              <FormControl>
                <FormLabel>Exchange</FormLabel>
                <Select value={deployExchange} onChange={(e) => setDeployExchange(e.target.value)}>
                  <option value="BINANCE">Binance</option>
                  <option value="EXCHANGE1">Exchange1</option>
                </Select>
              </FormControl>
              <FormControl>
                <FormLabel>Interval</FormLabel>
                <Select value={deployInterval} onChange={(e) => setDeployInterval(e.target.value)}>
                  <option value="5m">5 Minutes</option>
                  <option value="15m">15 Minutes</option>
                  <option value="1h">1 Hour</option>
                  <option value="4h">4 Hours</option>
                  <option value="1d">1 Day</option>
                </Select>
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onDeployClose}>Cancel</Button>
            <Button colorScheme="blue" onClick={handleDeploy} isLoading={deploying}>
              Deploy
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
}
