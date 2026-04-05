"use client";
import { useEffect, useRef, useState } from "react";
import {
  Box,
  Input,
  InputGroup,
  InputRightElement,
  Spinner,
  Text,
  useColorModeValue,
} from "@chakra-ui/react";
import { useExchangeInstruments } from "@/lib/hooks/useApi";

interface SymbolSelectProps {
  exchange: string;
  value: string;
  onChange: (symbol: string) => void;
  placeholder?: string;
}

export function SymbolSelect({ exchange, value, onChange, placeholder }: SymbolSelectProps) {
  const { data: instruments, isLoading } = useExchangeInstruments(exchange || null);
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const dropdownBg = useColorModeValue("white", "gray.700");
  const hoverBg = useColorModeValue("gray.100", "gray.600");
  const borderColor = useColorModeValue("gray.200", "gray.600");

  // Sync display text when value or instruments list changes
  useEffect(() => {
    if (!value) {
      setSearch("");
      return;
    }
    if (instruments) {
      const found = instruments.find((i) => i.symbol === value);
      setSearch(found ? `${found.base_asset}/${found.quote_asset}` : value);
    } else {
      setSearch(value);
    }
  }, [value, instruments]);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = (instruments ?? []).filter((i) => {
    if (!search) return true;
    const q = search.toLowerCase().replace("/", "");
    return (
      i.symbol.toLowerCase().includes(q) ||
      i.base_asset.toLowerCase().includes(q)
    );
  });

  // Deduplicate by symbol so SPOT and FUTURES don't appear twice
  const seen = new Set<string>();
  const unique = filtered.filter((i) => {
    if (seen.has(i.symbol)) return false;
    seen.add(i.symbol);
    return true;
  });

  const handleSelect = (symbol: string, base: string, quote: string) => {
    onChange(symbol);
    setSearch(`${base}/${quote}`);
    setOpen(false);
  };

  // If no instrument data at all, fall back to plain text input
  if (!isLoading && (!instruments || instruments.length === 0)) {
    return (
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? "e.g. BTCUSDT"}
      />
    );
  }

  return (
    <Box ref={containerRef} position="relative">
      <InputGroup>
        <Input
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder={isLoading ? "Loading..." : (placeholder ?? "Search symbol (e.g. BTC)")}
          autoComplete="off"
        />
        {isLoading && (
          <InputRightElement>
            <Spinner size="xs" />
          </InputRightElement>
        )}
      </InputGroup>

      {open && unique.length > 0 && (
        <Box
          position="absolute"
          zIndex={1500}
          bg={dropdownBg}
          border="1px solid"
          borderColor={borderColor}
          borderRadius="md"
          maxH="220px"
          overflowY="auto"
          w="full"
          top="calc(100% + 4px)"
          boxShadow="md"
        >
          {unique.slice(0, 60).map((inst) => (
            <Box
              key={inst.symbol}
              px={3}
              py={2}
              cursor="pointer"
              _hover={{ bg: hoverBg }}
              onMouseDown={(e) => {
                e.preventDefault();
                handleSelect(inst.symbol, inst.base_asset, inst.quote_asset);
              }}
            >
              <Text fontSize="sm" fontWeight="medium">
                {inst.base_asset}/{inst.quote_asset}
              </Text>
              <Text fontSize="xs" color="gray.500">
                {inst.symbol}
              </Text>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}
