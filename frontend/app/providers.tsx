"use client";
import { ChakraProvider, extendTheme } from "@chakra-ui/react";
import { AuthProvider } from "@/lib/hooks/useAuth";

const theme = extendTheme({
  config: { initialColorMode: "light", useSystemColorMode: false },
  fonts: { heading: "var(--font-inter)", body: "var(--font-inter)" },
});

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ChakraProvider theme={theme}>
      <AuthProvider>{children}</AuthProvider>
    </ChakraProvider>
  );
}
