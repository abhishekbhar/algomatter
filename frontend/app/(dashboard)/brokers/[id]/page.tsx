"use client";
import {
  Box, Flex, Heading, Text, Tab, TabList, TabPanel, TabPanels, Tabs, Badge,
} from "@chakra-ui/react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useBrokers, useBrokerPositions, useBrokerOrders } from "@/lib/hooks/useApi";
import { BrokerStatsBar } from "@/components/brokers/BrokerStatsBar";
import { BrokerPositionsTable } from "@/components/brokers/BrokerPositionsTable";
import { BrokerOrdersTable } from "@/components/brokers/BrokerOrdersTable";
import { BrokerTradesTable } from "@/components/brokers/BrokerTradesTable";

export default function BrokerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: brokers } = useBrokers();
  const { data: positions } = useBrokerPositions(id);
  const { data: orders } = useBrokerOrders(id);

  const broker = brokers?.find((b) => b.id === id);
  const positionCount = positions?.length ?? 0;
  const orderCount = orders?.length ?? 0;

  return (
    <Box>
      <Flex align="center" gap={2} mb={1}>
        <Link href="/brokers">
          <Text fontSize="sm" color="blue.400">← Brokers</Text>
        </Link>
      </Flex>

      <Flex align="center" gap={3} mb={6}>
        <Heading size="lg">{broker?.broker_type ?? id}</Heading>
        {broker && (
          <Badge colorScheme={broker.is_active ? "green" : "gray"}>
            {broker.is_active ? "Connected" : "Inactive"}
          </Badge>
        )}
      </Flex>

      <BrokerStatsBar brokerId={id} />

      <Tabs colorScheme="blue" isLazy>
        <TabList>
          <Tab>
            Positions{positionCount > 0 && (
              <Badge ml={2} colorScheme="blue" variant="subtle">{positionCount}</Badge>
            )}
          </Tab>
          <Tab>
            Open Orders{orderCount > 0 && (
              <Badge ml={2} colorScheme="blue" variant="subtle">{orderCount}</Badge>
            )}
          </Tab>
          <Tab>Order History</Tab>
        </TabList>
        <TabPanels>
          <TabPanel px={0}>
            <BrokerPositionsTable brokerId={id} />
          </TabPanel>
          <TabPanel px={0}>
            <BrokerOrdersTable brokerId={id} />
          </TabPanel>
          <TabPanel px={0}>
            <BrokerTradesTable brokerId={id} />
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Box>
  );
}
