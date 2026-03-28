# AlgoMatter Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete AlgoMatter frontend — a data-rich trading dashboard with strategy management, backtesting, paper trading, and analytics.

**Architecture:** Next.js 14 App Router with Chakra UI v2 for components, SWR for data fetching with polling, TradingView Lightweight Charts for financial visualizations. JWT auth with in-memory access token and localStorage refresh token. Types generated from backend OpenAPI schema.

**Tech Stack:** Next.js 14, TypeScript, Chakra UI v2, TradingView Lightweight Charts, SWR, openapi-typescript, React Testing Library, Jest

**Spec:** `docs/superpowers/specs/2026-03-26-algomatter-frontend-design.md`

**Backend API base:** `http://localhost:8000` (FastAPI, already running)

**Environment:** NixOS — use `npx` or project-local `node_modules/.bin/` for CLI tools. Node available at `/nix/store/drzx2kxsfisfvmvgan7ndmfaw2fjhi9b-nodejs-22.21.1/bin/node`.

---

## File Structure

```
frontend/
├── package.json
├── tsconfig.json
├── next.config.js
├── openapi-ts.config.ts
├── jest.config.ts
├── jest.setup.ts
├── app/
│   ├── layout.tsx                    # Root layout — html, body, ChakraProvider
│   ├── providers.tsx                 # Client component — Chakra + Auth providers
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── signup/page.tsx
│   └── (dashboard)/
│       ├── layout.tsx                # Auth guard + Sidebar + TopBar
│       ├── page.tsx                  # Dashboard overview
│       ├── strategies/
│       │   ├── page.tsx              # List
│       │   ├── new/page.tsx          # Create
│       │   └── [id]/
│       │       ├── page.tsx          # Detail (tabs)
│       │       └── edit/page.tsx     # Edit
│       ├── webhooks/page.tsx
│       ├── brokers/
│       │   ├── page.tsx              # Card grid
│       │   └── new/page.tsx          # Add form
│       ├── paper-trading/
│       │   ├── page.tsx              # Sessions list
│       │   └── [id]/page.tsx         # Session detail
│       ├── backtesting/page.tsx      # Run + results + history
│       ├── analytics/
│       │   ├── page.tsx              # Portfolio overview
│       │   └── strategies/[id]/page.tsx  # Strategy drilldown
│       └── settings/page.tsx
├── lib/
│   ├── api/
│   │   ├── client.ts                # Fetch wrapper with JWT auth + refresh
│   │   └── generated-types.ts       # openapi-typescript output (generated)
│   ├── hooks/
│   │   ├── useAuth.tsx              # Auth context + provider
│   │   └── useApi.ts               # SWR hooks per endpoint
│   └── utils/
│       ├── formatters.ts            # Currency, %, date formatters
│       └── constants.ts             # API_BASE_URL, polling intervals
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx
│   │   ├── NavItem.tsx
│   │   └── TopBar.tsx
│   ├── charts/
│   │   ├── EquityCurve.tsx
│   │   ├── DrawdownChart.tsx
│   │   └── ChartContainer.tsx
│   └── shared/
│       ├── DataTable.tsx
│       ├── StatCard.tsx
│       ├── EmptyState.tsx
│       ├── ConfirmModal.tsx
│       └── StatusBadge.tsx
└── __tests__/
    ├── lib/
    │   ├── client.test.ts
    │   ├── useAuth.test.tsx
    │   └── formatters.test.ts
    ├── components/
    │   ├── StatCard.test.tsx
    │   ├── StatusBadge.test.tsx
    │   ├── DataTable.test.tsx
    │   └── Sidebar.test.tsx
    └── pages/
        ├── login.test.tsx
        ├── signup.test.tsx
        ├── dashboard.test.tsx
        ├── strategies.test.tsx
        ├── webhooks.test.tsx
        ├── brokers.test.tsx
        ├── paper-trading.test.tsx
        ├── backtesting.test.tsx
        ├── analytics.test.tsx
        └── settings.test.tsx
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.js`
- Create: `frontend/jest.config.ts`
- Create: `frontend/jest.setup.ts`
- Create: `frontend/.env.local`

- [ ] **Step 1: Initialize Next.js project**

```bash
cd /home/abhishekbhar/projects/algomatter-worktree
npx create-next-app@14 frontend --typescript --app --no-tailwind --no-eslint --no-src-dir --import-alias "@/*"
```

- [ ] **Step 2: Install dependencies**

```bash
cd frontend
npm install @chakra-ui/react @chakra-ui/next-js @emotion/react @emotion/styled framer-motion
npm install swr lightweight-charts react-icons
npm install -D openapi-typescript @testing-library/react @testing-library/jest-dom @testing-library/user-event jest jest-environment-jsdom @types/jest ts-node ts-jest identity-obj-proxy
```

- [ ] **Step 3: Create `.env.local`**

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 4: Create `jest.config.ts`**

```typescript
import type { Config } from "jest";

const config: Config = {
  testEnvironment: "jsdom",
  setupFilesAfterSetup: ["<rootDir>/jest.setup.ts"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1",
  },
  transform: {
    "^.+\\.(ts|tsx)$": [
      "ts-jest",
      { tsconfig: "tsconfig.json" },
    ],
  },
};

export default config;
```

- [ ] **Step 5: Create `jest.setup.ts`**

```typescript
import "@testing-library/jest-dom";
```

- [ ] **Step 6: Verify setup compiles**

```bash
cd frontend && npx next build
```
Expected: Build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold Next.js 14 project with Chakra UI and test deps"
```

---

### Task 2: Utilities and Constants

**Files:**
- Create: `frontend/lib/utils/constants.ts`
- Create: `frontend/lib/utils/formatters.ts`
- Create: `frontend/__tests__/lib/formatters.test.ts`

- [ ] **Step 1: Write formatter tests**

```typescript
// __tests__/lib/formatters.test.ts
import { formatCurrency, formatPercent, formatDate, formatNumber } from "@/lib/utils/formatters";

describe("formatCurrency", () => {
  it("formats positive INR", () => {
    expect(formatCurrency(125000.5)).toBe("₹1,25,000.50");
  });
  it("formats negative", () => {
    expect(formatCurrency(-500)).toBe("-₹500.00");
  });
  it("handles zero", () => {
    expect(formatCurrency(0)).toBe("₹0.00");
  });
});

describe("formatPercent", () => {
  it("formats with 2 decimals", () => {
    expect(formatPercent(12.345)).toBe("12.35%");
  });
  it("handles negative", () => {
    expect(formatPercent(-3.1)).toBe("-3.10%");
  });
});

describe("formatDate", () => {
  it("formats ISO string", () => {
    const result = formatDate("2026-03-25T10:30:00Z");
    expect(result).toContain("2026");
  });
});

describe("formatNumber", () => {
  it("formats with commas", () => {
    expect(formatNumber(1234567)).toBe("12,34,567");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx jest __tests__/lib/formatters.test.ts
```
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement constants**

```typescript
// lib/utils/constants.ts
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export const POLLING_INTERVALS = {
  DASHBOARD: 10_000,
  SIGNALS: 5_000,
  PAPER_TRADING: 10_000,
  HEALTH: 30_000,
  BACKTEST_STATUS: 2_000,
} as const;
```

- [ ] **Step 4: Implement formatters**

```typescript
// lib/utils/formatters.ts
export function formatCurrency(value: number): string {
  const abs = Math.abs(value);
  const formatted = abs.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return value < 0 ? `-₹${formatted}` : `₹${formatted}`;
}

export function formatPercent(value: number): string {
  return `${value.toFixed(2)}%`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatNumber(value: number): string {
  return value.toLocaleString("en-IN");
}
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd frontend && npx jest __tests__/lib/formatters.test.ts
```
Expected: PASS — all 6 tests.

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/utils/ frontend/__tests__/lib/formatters.test.ts
git commit -m "feat(frontend): add utility formatters and constants"
```

---

### Task 3: API Client with JWT Auth

**Files:**
- Create: `frontend/lib/api/client.ts`
- Create: `frontend/__tests__/lib/client.test.ts`

- [ ] **Step 1: Write API client tests**

```typescript
// __tests__/lib/client.test.ts
import { apiClient, setAccessToken, getAccessToken, clearTokens } from "@/lib/api/client";

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

beforeEach(() => {
  mockFetch.mockClear();
  clearTokens();
});

describe("apiClient", () => {
  it("makes GET request with auth header", async () => {
    setAccessToken("test-token");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ data: "ok" }),
    });

    const result = await apiClient("/api/v1/strategies");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/strategies"),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer test-token",
        }),
      })
    );
    expect(result).toEqual({ data: "ok" });
  });

  it("makes POST request with JSON body", async () => {
    setAccessToken("tok");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ id: "1" }),
    });

    await apiClient("/api/v1/strategies", {
      method: "POST",
      body: { name: "test" },
    });

    const [, opts] = mockFetch.mock.calls[0];
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body)).toEqual({ name: "test" });
  });

  it("throws on non-ok response", async () => {
    setAccessToken("tok");
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({ detail: "validation error" }),
    });

    await expect(apiClient("/api/v1/strategies")).rejects.toThrow();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx jest __tests__/lib/client.test.ts
```
Expected: FAIL.

- [ ] **Step 3: Implement API client**

```typescript
// lib/api/client.ts
import { API_BASE_URL } from "@/lib/utils/constants";

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("refresh_token");
}

export function setRefreshToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem("refresh_token", token);
  else localStorage.removeItem("refresh_token");
}

export function clearTokens() {
  accessToken = null;
  if (typeof window !== "undefined") localStorage.removeItem("refresh_token");
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(`API error ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

async function refreshAccessToken(): Promise<boolean> {
  const rt = getRefreshToken();
  if (!rt) return false;
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    setAccessToken(data.access_token);
    setRefreshToken(data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  rawResponse?: boolean;
}

export async function apiClient<T = unknown>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = "GET", body, headers = {}, rawResponse } = options;

  const reqHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...headers,
  };
  if (accessToken) {
    reqHeaders["Authorization"] = `Bearer ${accessToken}`;
  }

  const fetchOpts: RequestInit = { method, headers: reqHeaders };
  if (body) fetchOpts.body = JSON.stringify(body);

  let res = await fetch(`${API_BASE_URL}${path}`, fetchOpts);

  // On 401, try refresh once
  if (res.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      reqHeaders["Authorization"] = `Bearer ${accessToken}`;
      res = await fetch(`${API_BASE_URL}${path}`, { method, headers: reqHeaders, body: fetchOpts.body });
    }
  }

  if (!res.ok) {
    let detail: unknown;
    try { detail = await res.json(); } catch { detail = res.statusText; }
    throw new ApiError(res.status, detail);
  }

  if (rawResponse) return res as unknown as T;
  return res.json() as Promise<T>;
}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd frontend && npx jest __tests__/lib/client.test.ts
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api/client.ts frontend/__tests__/lib/client.test.ts
git commit -m "feat(frontend): add API client with JWT auth and 401 refresh"
```

---

### Task 4: Auth Context and Provider

**Files:**
- Create: `frontend/lib/hooks/useAuth.tsx`
- Create: `frontend/__tests__/lib/useAuth.test.tsx`

- [ ] **Step 1: Write auth hook tests**

```typescript
// __tests__/lib/useAuth.test.tsx
import { renderHook, act, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "@/lib/hooks/useAuth";
import * as client from "@/lib/api/client";
import React from "react";

jest.mock("@/lib/api/client");
const mockedClient = client as jest.Mocked<typeof client>;

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <AuthProvider>{children}</AuthProvider>
);

describe("useAuth", () => {
  beforeEach(() => jest.clearAllMocks());

  it("starts with null user and loading true", () => {
    mockedClient.getRefreshToken.mockReturnValue(null);
    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(result.current.user).toBeNull();
  });

  it("login sets user and tokens", async () => {
    mockedClient.apiClient.mockResolvedValueOnce({
      access_token: "at",
      refresh_token: "rt",
      token_type: "bearer",
    });
    mockedClient.apiClient.mockResolvedValueOnce({
      id: "u1",
      email: "a@b.com",
      is_active: true,
      plan: "free",
      created_at: "2026-01-01",
    });

    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.login("a@b.com", "pass");
    });

    expect(result.current.user?.email).toBe("a@b.com");
    expect(mockedClient.setAccessToken).toHaveBeenCalledWith("at");
    expect(mockedClient.setRefreshToken).toHaveBeenCalledWith("rt");
  });

  it("logout clears tokens and user", async () => {
    mockedClient.getRefreshToken.mockReturnValue(null);
    const { result } = renderHook(() => useAuth(), { wrapper });

    act(() => {
      result.current.logout();
    });

    expect(mockedClient.clearTokens).toHaveBeenCalled();
    expect(result.current.user).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx jest __tests__/lib/useAuth.test.tsx
```
Expected: FAIL.

- [ ] **Step 3: Implement useAuth**

```typescript
// lib/hooks/useAuth.tsx
"use client";
import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import {
  apiClient,
  setAccessToken,
  setRefreshToken,
  getRefreshToken,
  clearTokens,
} from "@/lib/api/client";

interface User {
  id: string;
  email: string;
  is_active: boolean;
  plan: string;
  created_at: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchMe = useCallback(async () => {
    try {
      const me = await apiClient<User>("/api/v1/auth/me");
      setUser(me);
    } catch {
      clearTokens();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    const rt = getRefreshToken();
    if (!rt) {
      setIsLoading(false);
      return;
    }
    apiClient<{ access_token: string; refresh_token: string }>("/api/v1/auth/refresh", {
      method: "POST",
      body: { refresh_token: rt },
    })
      .then((data) => {
        setAccessToken(data.access_token);
        setRefreshToken(data.refresh_token);
        return fetchMe();
      })
      .catch(() => {
        clearTokens();
      })
      .finally(() => setIsLoading(false));
  }, [fetchMe]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await apiClient<{ access_token: string; refresh_token: string }>(
      "/api/v1/auth/login",
      { method: "POST", body: { email, password } }
    );
    setAccessToken(data.access_token);
    setRefreshToken(data.refresh_token);
    await fetchMe();
  }, [fetchMe]);

  const signup = useCallback(async (email: string, password: string) => {
    const data = await apiClient<{ access_token: string; refresh_token: string }>(
      "/api/v1/auth/signup",
      { method: "POST", body: { email, password } }
    );
    setAccessToken(data.access_token);
    setRefreshToken(data.refresh_token);
    await fetchMe();
  }, [fetchMe]);

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd frontend && npx jest __tests__/lib/useAuth.test.tsx
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/hooks/useAuth.tsx frontend/__tests__/lib/useAuth.test.tsx
git commit -m "feat(frontend): add auth context with login/signup/logout and silent refresh"
```

---

### Task 5: Root Layout and Providers

**Files:**
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/providers.tsx`

- [ ] **Step 1: Create providers (client component)**

```typescript
// app/providers.tsx
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
```

- [ ] **Step 2: Create root layout**

```typescript
// app/layout.tsx
import { Inter } from "next/font/google";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata = {
  title: "AlgoMatter",
  description: "Multiuser algo-testing platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

- [ ] **Step 3: Verify build**

```bash
cd frontend && npx next build
```
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/layout.tsx frontend/app/providers.tsx
git commit -m "feat(frontend): add root layout with Chakra and auth providers"
```

---

### Task 6: Shared Components — StatCard, StatusBadge, EmptyState, ConfirmModal

**Files:**
- Create: `frontend/components/shared/StatCard.tsx`
- Create: `frontend/components/shared/StatusBadge.tsx`
- Create: `frontend/components/shared/EmptyState.tsx`
- Create: `frontend/components/shared/ConfirmModal.tsx`
- Create: `frontend/__tests__/components/StatCard.test.tsx`
- Create: `frontend/__tests__/components/StatusBadge.test.tsx`

- [ ] **Step 1: Write StatCard test**

```typescript
// __tests__/components/StatCard.test.tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { StatCard } from "@/components/shared/StatCard";

const wrap = (ui: React.ReactElement) => render(<ChakraProvider>{ui}</ChakraProvider>);

describe("StatCard", () => {
  it("renders label and value", () => {
    wrap(<StatCard label="Total P&L" value="₹12,500" />);
    expect(screen.getByText("Total P&L")).toBeInTheDocument();
    expect(screen.getByText("₹12,500")).toBeInTheDocument();
  });

  it("renders positive change indicator", () => {
    wrap(<StatCard label="Return" value="15%" change={5.2} />);
    expect(screen.getByText("+5.20%")).toBeInTheDocument();
  });

  it("renders negative change indicator", () => {
    wrap(<StatCard label="Return" value="-3%" change={-2.1} />);
    expect(screen.getByText("-2.10%")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Write StatusBadge test**

```typescript
// __tests__/components/StatusBadge.test.tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { StatusBadge } from "@/components/shared/StatusBadge";

const wrap = (ui: React.ReactElement) => render(<ChakraProvider>{ui}</ChakraProvider>);

describe("StatusBadge", () => {
  it("renders text with correct variant", () => {
    wrap(<StatusBadge variant="success" text="passed" />);
    expect(screen.getByText("passed")).toBeInTheDocument();
  });

  it("renders all variants without crashing", () => {
    const variants = ["success", "error", "warning", "info", "neutral"] as const;
    variants.forEach((v) => {
      const { unmount } = wrap(<StatusBadge variant={v} text={v} />);
      expect(screen.getByText(v)).toBeInTheDocument();
      unmount();
    });
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd frontend && npx jest __tests__/components/
```
Expected: FAIL.

- [ ] **Step 4: Implement StatCard**

```typescript
// components/shared/StatCard.tsx
"use client";
import { Box, Text, Flex, useColorModeValue } from "@chakra-ui/react";

interface StatCardProps {
  label: string;
  value: string;
  change?: number;
}

export function StatCard({ label, value, change }: StatCardProps) {
  const bg = useColorModeValue("white", "gray.800");
  const changeColor = change && change >= 0 ? "green.500" : "red.500";

  return (
    <Box bg={bg} p={4} borderRadius="lg" shadow="sm" border="1px" borderColor="gray.200">
      <Text fontSize="sm" color="gray.500">{label}</Text>
      <Text fontSize="2xl" fontWeight="bold" mt={1}>{value}</Text>
      {change !== undefined && (
        <Text fontSize="sm" color={changeColor} mt={1}>
          {change >= 0 ? "+" : ""}{change.toFixed(2)}%
        </Text>
      )}
    </Box>
  );
}
```

- [ ] **Step 5: Implement StatusBadge**

```typescript
// components/shared/StatusBadge.tsx
"use client";
import { Badge } from "@chakra-ui/react";

const VARIANT_MAP = {
  success: "green",
  error: "red",
  warning: "yellow",
  info: "blue",
  neutral: "gray",
} as const;

interface StatusBadgeProps {
  variant: keyof typeof VARIANT_MAP;
  text: string;
}

export function StatusBadge({ variant, text }: StatusBadgeProps) {
  return <Badge colorScheme={VARIANT_MAP[variant]}>{text}</Badge>;
}
```

- [ ] **Step 6: Implement EmptyState**

```typescript
// components/shared/EmptyState.tsx
"use client";
import { VStack, Text, Button } from "@chakra-ui/react";

interface EmptyStateProps {
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({ title, description, actionLabel, onAction }: EmptyStateProps) {
  return (
    <VStack py={16} spacing={4}>
      <Text fontSize="lg" fontWeight="semibold" color="gray.500">{title}</Text>
      {description && <Text color="gray.400">{description}</Text>}
      {actionLabel && onAction && (
        <Button colorScheme="blue" onClick={onAction}>{actionLabel}</Button>
      )}
    </VStack>
  );
}
```

- [ ] **Step 7: Implement ConfirmModal**

```typescript
// components/shared/ConfirmModal.tsx
"use client";
import {
  Modal, ModalOverlay, ModalContent, ModalHeader,
  ModalBody, ModalFooter, Button,
} from "@chakra-ui/react";

interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
  isLoading?: boolean;
}

export function ConfirmModal({
  isOpen, onClose, onConfirm, title, message,
  confirmLabel = "Confirm", isLoading = false,
}: ConfirmModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} isCentered>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>{title}</ModalHeader>
        <ModalBody>{message}</ModalBody>
        <ModalFooter gap={3}>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button colorScheme="red" onClick={onConfirm} isLoading={isLoading}>
            {confirmLabel}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
```

- [ ] **Step 8: Run tests to verify pass**

```bash
cd frontend && npx jest __tests__/components/
```
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/components/shared/ frontend/__tests__/components/
git commit -m "feat(frontend): add shared components — StatCard, StatusBadge, EmptyState, ConfirmModal"
```

---

### Task 7: Shared Component — DataTable

**Files:**
- Create: `frontend/components/shared/DataTable.tsx`
- Create: `frontend/__tests__/components/DataTable.test.tsx`

- [ ] **Step 1: Write DataTable test**

```typescript
// __tests__/components/DataTable.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChakraProvider } from "@chakra-ui/react";
import { DataTable, Column } from "@/components/shared/DataTable";

const wrap = (ui: React.ReactElement) => render(<ChakraProvider>{ui}</ChakraProvider>);

interface Row {
  id: string;
  name: string;
  value: number;
}

const columns: Column<Row>[] = [
  { key: "name", header: "Name" },
  { key: "value", header: "Value", sortable: true },
];

const data: Row[] = [
  { id: "1", name: "Alpha", value: 100 },
  { id: "2", name: "Beta", value: 50 },
  { id: "3", name: "Gamma", value: 200 },
];

describe("DataTable", () => {
  it("renders headers and rows", () => {
    wrap(<DataTable columns={columns} data={data} />);
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByText("Gamma")).toBeInTheDocument();
  });

  it("sorts by sortable column on click", async () => {
    wrap(<DataTable columns={columns} data={data} />);
    const header = screen.getByText("Value");
    await userEvent.click(header);
    const cells = screen.getAllByRole("cell");
    const valuesCells = cells.filter((_, i) => i % 2 === 1);
    expect(valuesCells[0].textContent).toBe("50");
  });

  it("renders empty state when no data", () => {
    wrap(<DataTable columns={columns} data={[]} emptyMessage="No items" />);
    expect(screen.getByText("No items")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx jest __tests__/components/DataTable.test.tsx
```

- [ ] **Step 3: Implement DataTable**

```typescript
// components/shared/DataTable.tsx
"use client";
import { useState, useMemo } from "react";
import {
  Table, Thead, Tbody, Tr, Th, Td,
  Box, Text, useColorModeValue,
} from "@chakra-ui/react";

export interface Column<T> {
  key: keyof T & string;
  header: string;
  sortable?: boolean;
  render?: (value: T[keyof T], row: T) => React.ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
  isLoading?: boolean;
}

export function DataTable<T extends Record<string, unknown>>({
  columns, data, onRowClick, emptyMessage = "No data", isLoading,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState(true);
  const hoverBg = useColorModeValue("gray.50", "gray.700");

  const sorted = useMemo(() => {
    if (!sortKey) return data;
    return [...data].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      if (av == null || bv == null) return 0;
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortAsc ? cmp : -cmp;
    });
  }, [data, sortKey, sortAsc]);

  const handleSort = (key: string) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(true); }
  };

  if (!isLoading && data.length === 0) {
    return <Text py={8} textAlign="center" color="gray.500">{emptyMessage}</Text>;
  }

  return (
    <Box overflowX="auto">
      <Table variant="simple" size="sm">
        <Thead>
          <Tr>
            {columns.map((col) => (
              <Th
                key={col.key}
                cursor={col.sortable ? "pointer" : "default"}
                onClick={col.sortable ? () => handleSort(col.key) : undefined}
                userSelect="none"
              >
                {col.header}
                {sortKey === col.key && (sortAsc ? " ▲" : " ▼")}
              </Th>
            ))}
          </Tr>
        </Thead>
        <Tbody>
          {sorted.map((row, i) => (
            <Tr
              key={i}
              cursor={onRowClick ? "pointer" : "default"}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              _hover={onRowClick ? { bg: hoverBg } : {}}
            >
              {columns.map((col) => (
                <Td key={col.key}>
                  {col.render ? col.render(row[col.key], row) : String(row[col.key] ?? "")}
                </Td>
              ))}
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  );
}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd frontend && npx jest __tests__/components/DataTable.test.tsx
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/shared/DataTable.tsx frontend/__tests__/components/DataTable.test.tsx
git commit -m "feat(frontend): add sortable DataTable component"
```

---

### Task 8: Layout Components — Sidebar, NavItem, TopBar

**Files:**
- Create: `frontend/components/layout/Sidebar.tsx`
- Create: `frontend/components/layout/NavItem.tsx`
- Create: `frontend/components/layout/TopBar.tsx`
- Create: `frontend/__tests__/components/Sidebar.test.tsx`

- [ ] **Step 1: Write Sidebar test**

```typescript
// __tests__/components/Sidebar.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChakraProvider } from "@chakra-ui/react";
import { Sidebar } from "@/components/layout/Sidebar";

jest.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: jest.fn() }),
}));

const wrap = (ui: React.ReactElement) => render(<ChakraProvider>{ui}</ChakraProvider>);

describe("Sidebar", () => {
  it("renders all nav items", () => {
    wrap(<Sidebar />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Strategies")).toBeInTheDocument();
    expect(screen.getByText("Webhooks")).toBeInTheDocument();
    expect(screen.getByText("Brokers")).toBeInTheDocument();
    expect(screen.getByText("Paper Trading")).toBeInTheDocument();
    expect(screen.getByText("Backtesting")).toBeInTheDocument();
    expect(screen.getByText("Analytics")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx jest __tests__/components/Sidebar.test.tsx
```

- [ ] **Step 3: Implement NavItem**

```typescript
// components/layout/NavItem.tsx
"use client";
import { Flex, Text, Icon, useColorModeValue } from "@chakra-ui/react";
import Link from "next/link";
import { IconType } from "react-icons";

interface NavItemProps {
  icon: IconType;
  label: string;
  href: string;
  isActive: boolean;
  isCollapsed: boolean;
}

export function NavItem({ icon, label, href, isActive, isCollapsed }: NavItemProps) {
  const activeBg = useColorModeValue("blue.50", "blue.900");
  const activeColor = useColorModeValue("blue.600", "blue.200");
  const hoverBg = useColorModeValue("gray.100", "gray.700");

  return (
    <Link href={href} style={{ textDecoration: "none" }}>
      <Flex
        align="center"
        px={3}
        py={2}
        borderRadius="md"
        bg={isActive ? activeBg : "transparent"}
        color={isActive ? activeColor : "inherit"}
        _hover={{ bg: isActive ? activeBg : hoverBg }}
        gap={3}
      >
        <Icon as={icon} boxSize={5} />
        {!isCollapsed && <Text fontSize="sm" fontWeight={isActive ? "semibold" : "normal"}>{label}</Text>}
      </Flex>
    </Link>
  );
}
```

- [ ] **Step 4: Implement Sidebar**

```typescript
// components/layout/Sidebar.tsx
"use client";
import { Box, VStack, IconButton, Flex, Text, useColorModeValue } from "@chakra-ui/react";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  MdDashboard, MdShowChart, MdWebhook, MdAccountBalance,
  MdPlayArrow, MdHistory, MdAnalytics, MdSettings, MdChevronLeft, MdChevronRight,
} from "react-icons/md";
import { NavItem } from "./NavItem";

const NAV_ITEMS = [
  { icon: MdDashboard, label: "Dashboard", href: "/" },
  { icon: MdShowChart, label: "Strategies", href: "/strategies" },
  { icon: MdWebhook, label: "Webhooks", href: "/webhooks" },
  { icon: MdAccountBalance, label: "Brokers", href: "/brokers" },
  { icon: MdPlayArrow, label: "Paper Trading", href: "/paper-trading" },
  { icon: MdHistory, label: "Backtesting", href: "/backtesting" },
  { icon: MdAnalytics, label: "Analytics", href: "/analytics" },
  { icon: MdSettings, label: "Settings", href: "/settings" },
];

export function Sidebar() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const pathname = usePathname();
  const bg = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  return (
    <Box
      as="nav"
      w={isCollapsed ? "60px" : "220px"}
      minH="100vh"
      bg={bg}
      borderRight="1px"
      borderColor={borderColor}
      transition="width 0.2s"
      py={4}
    >
      <Flex justify={isCollapsed ? "center" : "space-between"} align="center" px={3} mb={6}>
        {!isCollapsed && <Text fontSize="lg" fontWeight="bold">AlgoMatter</Text>}
        <IconButton
          aria-label="Toggle sidebar"
          icon={isCollapsed ? <MdChevronRight /> : <MdChevronLeft />}
          size="sm"
          variant="ghost"
          onClick={() => setIsCollapsed(!isCollapsed)}
        />
      </Flex>
      <VStack spacing={1} align="stretch" px={2}>
        {NAV_ITEMS.map((item) => (
          <NavItem
            key={item.href}
            icon={item.icon}
            label={item.label}
            href={item.href}
            isActive={pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href))}
            isCollapsed={isCollapsed}
          />
        ))}
      </VStack>
    </Box>
  );
}
```

- [ ] **Step 5: Implement TopBar**

```typescript
// components/layout/TopBar.tsx
"use client";
import { Flex, Text, IconButton, useColorMode, Menu, MenuButton, MenuList, MenuItem, Avatar } from "@chakra-ui/react";
import { MdLightMode, MdDarkMode } from "react-icons/md";
import { useAuth } from "@/lib/hooks/useAuth";

export function TopBar() {
  const { colorMode, toggleColorMode } = useColorMode();
  const { user, logout } = useAuth();

  return (
    <Flex as="header" h="56px" px={6} align="center" justify="flex-end" gap={4} borderBottom="1px" borderColor="gray.200">
      <IconButton
        aria-label="Toggle theme"
        icon={colorMode === "light" ? <MdDarkMode /> : <MdLightMode />}
        variant="ghost"
        onClick={toggleColorMode}
      />
      <Menu>
        <MenuButton>
          <Avatar size="sm" name={user?.email} />
        </MenuButton>
        <MenuList>
          <MenuItem isDisabled>
            <Text fontSize="sm" color="gray.500">{user?.email}</Text>
          </MenuItem>
          <MenuItem onClick={logout}>Logout</MenuItem>
        </MenuList>
      </Menu>
    </Flex>
  );
}
```

- [ ] **Step 6: Run tests to verify pass**

```bash
cd frontend && npx jest __tests__/components/Sidebar.test.tsx
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/components/layout/ frontend/__tests__/components/Sidebar.test.tsx
git commit -m "feat(frontend): add layout components — Sidebar, NavItem, TopBar"
```

---

### Task 9: Dashboard Layout and Auth Pages

**Files:**
- Create: `frontend/app/(dashboard)/layout.tsx`
- Create: `frontend/app/(auth)/login/page.tsx`
- Create: `frontend/app/(auth)/signup/page.tsx`
- Create: `frontend/__tests__/pages/login.test.tsx`

- [ ] **Step 1: Write login page test**

```typescript
// __tests__/pages/login.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChakraProvider } from "@chakra-ui/react";
import LoginPage from "@/app/(auth)/login/page";
import { AuthProvider } from "@/lib/hooks/useAuth";
import * as client from "@/lib/api/client";

jest.mock("@/lib/api/client");
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  redirect: jest.fn(),
}));

const wrap = (ui: React.ReactElement) =>
  render(<ChakraProvider><AuthProvider>{ui}</AuthProvider></ChakraProvider>);

describe("LoginPage", () => {
  it("renders email and password fields", () => {
    wrap(<LoginPage />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /log in/i })).toBeInTheDocument();
  });

  it("shows link to signup", () => {
    wrap(<LoginPage />);
    expect(screen.getByText(/don't have an account/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx jest __tests__/pages/login.test.tsx
```

- [ ] **Step 3: Implement dashboard layout (auth guard + sidebar)**

```typescript
// app/(dashboard)/layout.tsx
"use client";
import { Flex, Box, Spinner, Center } from "@chakra-ui/react";
import { useAuth } from "@/lib/hooks/useAuth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) router.push("/login");
  }, [isLoading, user, router]);

  if (isLoading) {
    return <Center h="100vh"><Spinner size="xl" /></Center>;
  }

  if (!user) return null;

  return (
    <Flex minH="100vh">
      <Sidebar />
      <Box flex={1}>
        <TopBar />
        <Box p={6}>{children}</Box>
      </Box>
    </Flex>
  );
}
```

- [ ] **Step 4: Implement login page**

```typescript
// app/(auth)/login/page.tsx
"use client";
import {
  Box, Button, FormControl, FormLabel, Input, VStack,
  Heading, Text, Link as ChakraLink, useToast, FormErrorMessage,
} from "@chakra-ui/react";
import NextLink from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/hooks/useAuth";
import { ApiError } from "@/lib/api/client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login } = useAuth();
  const router = useRouter();
  const toast = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      await login(email, password);
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError) {
        setError("Invalid email or password");
      } else {
        toast({ title: "Network error", status: "error" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Box maxW="400px" mx="auto" mt={20} p={8}>
      <Heading size="lg" mb={6}>Log In</Heading>
      <form onSubmit={handleSubmit}>
        <VStack spacing={4}>
          <FormControl isRequired isInvalid={!!error}>
            <FormLabel htmlFor="email">Email</FormLabel>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </FormControl>
          <FormControl isRequired isInvalid={!!error}>
            <FormLabel htmlFor="password">Password</FormLabel>
            <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            {error && <FormErrorMessage>{error}</FormErrorMessage>}
          </FormControl>
          <Button type="submit" colorScheme="blue" w="full" isLoading={isSubmitting}>
            Log In
          </Button>
        </VStack>
      </form>
      <Text mt={4} fontSize="sm" textAlign="center">
        Don't have an account?{" "}
        <ChakraLink as={NextLink} href="/signup" color="blue.500">Sign up</ChakraLink>
      </Text>
    </Box>
  );
}
```

- [ ] **Step 5: Implement signup page**

```typescript
// app/(auth)/signup/page.tsx
"use client";
import {
  Box, Button, FormControl, FormLabel, Input, VStack,
  Heading, Text, Link as ChakraLink, useToast, FormErrorMessage,
} from "@chakra-ui/react";
import NextLink from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/hooks/useAuth";
import { ApiError } from "@/lib/api/client";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { signup } = useAuth();
  const router = useRouter();
  const toast = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setIsSubmitting(true);
    try {
      await signup(email, password);
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError) {
        setError("Signup failed. Email may already be registered.");
      } else {
        toast({ title: "Network error", status: "error" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Box maxW="400px" mx="auto" mt={20} p={8}>
      <Heading size="lg" mb={6}>Sign Up</Heading>
      <form onSubmit={handleSubmit}>
        <VStack spacing={4}>
          <FormControl isRequired>
            <FormLabel htmlFor="email">Email</FormLabel>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </FormControl>
          <FormControl isRequired isInvalid={!!error}>
            <FormLabel htmlFor="password">Password</FormLabel>
            <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </FormControl>
          <FormControl isRequired isInvalid={!!error}>
            <FormLabel htmlFor="confirmPassword">Confirm Password</FormLabel>
            <Input id="confirmPassword" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
            {error && <FormErrorMessage>{error}</FormErrorMessage>}
          </FormControl>
          <Button type="submit" colorScheme="blue" w="full" isLoading={isSubmitting}>
            Sign Up
          </Button>
        </VStack>
      </form>
      <Text mt={4} fontSize="sm" textAlign="center">
        Already have an account?{" "}
        <ChakraLink as={NextLink} href="/login" color="blue.500">Log in</ChakraLink>
      </Text>
    </Box>
  );
}
```

- [ ] **Step 6: Run tests**

```bash
cd frontend && npx jest __tests__/pages/login.test.tsx
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/app/
git commit -m "feat(frontend): add auth pages (login/signup) and dashboard layout with auth guard"
```

---

### Task 10: SWR API Hooks

**Files:**
- Create: `frontend/lib/hooks/useApi.ts`

- [ ] **Step 1: Implement SWR hooks for all endpoints**

```typescript
// lib/hooks/useApi.ts
"use client";
import useSWR, { SWRConfiguration } from "swr";
import { apiClient } from "@/lib/api/client";
import { POLLING_INTERVALS } from "@/lib/utils/constants";

function fetcher<T>(path: string): Promise<T> {
  return apiClient<T>(path);
}

function useApiGet<T>(path: string | null, config?: SWRConfiguration) {
  return useSWR<T>(path, fetcher, config);
}

// --- Auth ---
export function useMe() {
  return useApiGet<{ id: string; email: string; is_active: boolean; plan: string }>("/api/v1/auth/me");
}

// --- Health ---
export function useHealth() {
  return useApiGet<{ status: string }>("/api/v1/health", {
    refreshInterval: POLLING_INTERVALS.HEALTH,
  });
}

// --- Strategies ---
export function useStrategies() {
  return useApiGet<Array<{
    id: string; name: string; broker_connection_id: string | null;
    mode: string; is_active: boolean; created_at: string;
    mapping_template: Record<string, unknown> | null; rules: Record<string, unknown>;
  }>>("/api/v1/strategies");
}

export function useStrategy(id: string | null) {
  return useApiGet(id ? `/api/v1/strategies/${id}` : null);
}

// --- Webhooks ---
export function useWebhookConfig() {
  return useApiGet<{ webhook_url: string; token: string }>("/api/v1/webhooks/config");
}

export function useWebhookSignals() {
  return useApiGet<Array<Record<string, unknown>>>("/api/v1/webhooks/signals", {
    refreshInterval: POLLING_INTERVALS.SIGNALS,
  });
}

// --- Brokers ---
export function useBrokers() {
  return useApiGet<Array<{
    id: string; broker_type: string; is_active: boolean; connected_at: string;
  }>>("/api/v1/brokers");
}

// --- Paper Trading ---
export function usePaperSessions() {
  return useApiGet<Array<Record<string, unknown>>>("/api/v1/paper-trading/sessions");
}

export function usePaperSession(id: string | null) {
  return useApiGet(id ? `/api/v1/paper-trading/sessions/${id}` : null, {
    refreshInterval: POLLING_INTERVALS.PAPER_TRADING,
  });
}

// --- Backtests ---
export function useBacktests() {
  return useApiGet<Array<Record<string, unknown>>>("/api/v1/backtests");
}

export function useBacktest(id: string | null) {
  return useApiGet(id ? `/api/v1/backtests/${id}` : null);
}

// --- Analytics ---
export function useAnalyticsOverview() {
  return useApiGet<{
    total_pnl: number; active_strategies: number;
    open_positions: number; trades_today: number;
  }>("/api/v1/analytics/overview", {
    refreshInterval: POLLING_INTERVALS.DASHBOARD,
  });
}

export function useStrategyMetrics(strategyId: string | null) {
  return useApiGet(strategyId ? `/api/v1/analytics/strategies/${strategyId}/metrics` : null);
}

export function useStrategyEquityCurve(strategyId: string | null) {
  return useApiGet<Array<Record<string, unknown>>>(
    strategyId ? `/api/v1/analytics/strategies/${strategyId}/equity-curve` : null
  );
}

export function useStrategyTrades(strategyId: string | null) {
  return useApiGet<Array<Record<string, unknown>>>(
    strategyId ? `/api/v1/analytics/strategies/${strategyId}/trades` : null
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npx next build
```
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/hooks/useApi.ts
git commit -m "feat(frontend): add SWR hooks for all API endpoints with polling"
```

---

### Task 11: Chart Components — EquityCurve, DrawdownChart, ChartContainer

**Files:**
- Create: `frontend/components/charts/EquityCurve.tsx`
- Create: `frontend/components/charts/DrawdownChart.tsx`
- Create: `frontend/components/charts/ChartContainer.tsx`

- [ ] **Step 1: Implement ChartContainer**

```typescript
// components/charts/ChartContainer.tsx
"use client";
import { Box, Flex, Button, ButtonGroup, Skeleton } from "@chakra-ui/react";
import { useState } from "react";

export type Timeframe = "1W" | "1M" | "3M" | "ALL";

interface ChartContainerProps {
  children: (timeframe: Timeframe) => React.ReactNode;
  isLoading?: boolean;
  height?: number;
  showTimeframes?: boolean;
}

export function ChartContainer({
  children, isLoading, height = 300, showTimeframes = true,
}: ChartContainerProps) {
  const [timeframe, setTimeframe] = useState<Timeframe>("1M");

  if (isLoading) return <Skeleton height={`${height}px`} borderRadius="lg" />;

  return (
    <Box>
      {showTimeframes && (
        <Flex justify="flex-end" mb={2}>
          <ButtonGroup size="xs" variant="outline">
            {(["1W", "1M", "3M", "ALL"] as Timeframe[]).map((tf) => (
              <Button
                key={tf}
                onClick={() => setTimeframe(tf)}
                variant={timeframe === tf ? "solid" : "outline"}
                colorScheme={timeframe === tf ? "blue" : "gray"}
              >
                {tf}
              </Button>
            ))}
          </ButtonGroup>
        </Flex>
      )}
      <Box h={`${height}px`}>{children(timeframe)}</Box>
    </Box>
  );
}
```

- [ ] **Step 2: Implement EquityCurve**

```typescript
// components/charts/EquityCurve.tsx
"use client";
import { useRef, useEffect } from "react";
import { createChart, IChartApi, ISeriesApi, AreaData, Time } from "lightweight-charts";
import { useColorModeValue } from "@chakra-ui/react";

interface EquityCurveProps {
  data: Array<{ time: string; value: number }>;
  height?: number;
}

export function EquityCurve({ data, height = 300 }: EquityCurveProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const bgColor = useColorModeValue("#ffffff", "#1a202c");
  const textColor = useColorModeValue("#2d3748", "#e2e8f0");

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: { background: { color: bgColor }, textColor },
      grid: { vertLines: { visible: false }, horzLines: { color: "#e2e8f020" } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    chartRef.current = chart;

    const series = chart.addAreaSeries({
      lineColor: "#3182ce",
      topColor: "rgba(49, 130, 206, 0.4)",
      bottomColor: "rgba(49, 130, 206, 0.0)",
      lineWidth: 2,
    });
    seriesRef.current = series;

    const sorted = [...data].sort((a, b) => a.time.localeCompare(b.time));
    series.setData(sorted as AreaData<Time>[]);
    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [data, height, bgColor, textColor]);

  return <div ref={containerRef} />;
}
```

- [ ] **Step 3: Implement DrawdownChart**

```typescript
// components/charts/DrawdownChart.tsx
"use client";
import { useRef, useEffect } from "react";
import { createChart, IChartApi, HistogramData, Time } from "lightweight-charts";
import { useColorModeValue } from "@chakra-ui/react";

interface DrawdownChartProps {
  data: Array<{ time: string; value: number }>;
  height?: number;
}

export function DrawdownChart({ data, height = 200 }: DrawdownChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const bgColor = useColorModeValue("#ffffff", "#1a202c");
  const textColor = useColorModeValue("#2d3748", "#e2e8f0");

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: { background: { color: bgColor }, textColor },
      grid: { vertLines: { visible: false }, horzLines: { color: "#e2e8f020" } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    chartRef.current = chart;

    const series = chart.addHistogramSeries({ color: "#e53e3e" });
    const sorted = [...data].sort((a, b) => a.time.localeCompare(b.time));
    series.setData(sorted as HistogramData<Time>[]);
    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [data, height, bgColor, textColor]);

  return <div ref={containerRef} />;
}
```

- [ ] **Step 4: Verify build**

```bash
cd frontend && npx next build
```
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/charts/
git commit -m "feat(frontend): add TradingView chart components — EquityCurve, DrawdownChart, ChartContainer"
```

---

### Task 12: Dashboard Home Page

**Files:**
- Create: `frontend/app/(dashboard)/page.tsx`
- Create: `frontend/__tests__/pages/dashboard.test.tsx`

- [ ] **Step 1: Write dashboard test**

```typescript
// __tests__/pages/dashboard.test.tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import DashboardPage from "@/app/(dashboard)/page";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("@/components/charts/EquityCurve", () => ({
  EquityCurve: () => <div data-testid="equity-curve" />,
}));
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

const mockOverview = {
  data: { total_pnl: 12500, active_strategies: 3, open_positions: 5, trades_today: 12 },
  error: undefined, isLoading: false, mutate: jest.fn(), isValidating: false,
};

describe("DashboardPage", () => {
  beforeEach(() => {
    (useApiModule.useAnalyticsOverview as jest.Mock).mockReturnValue(mockOverview);
    (useApiModule.useWebhookSignals as jest.Mock).mockReturnValue({
      data: [], error: undefined, isLoading: false, mutate: jest.fn(), isValidating: false,
    });
    (useApiModule.useStrategies as jest.Mock).mockReturnValue({
      data: [], error: undefined, isLoading: false, mutate: jest.fn(), isValidating: false,
    });
  });

  it("renders stat cards", () => {
    render(<ChakraProvider><DashboardPage /></ChakraProvider>);
    expect(screen.getByText("Active Strategies")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Today's Signals")).toBeInTheDocument();
  });

  it("renders quick action buttons", () => {
    render(<ChakraProvider><DashboardPage /></ChakraProvider>);
    expect(screen.getByText("New Strategy")).toBeInTheDocument();
    expect(screen.getByText("Run Backtest")).toBeInTheDocument();
    expect(screen.getByText("Connect Broker")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx jest __tests__/pages/dashboard.test.tsx
```

- [ ] **Step 3: Implement dashboard page**

```typescript
// app/(dashboard)/page.tsx
"use client";
import { SimpleGrid, Box, Heading, Button, Flex, Text } from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { StatCard } from "@/components/shared/StatCard";
import { DataTable, Column } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { EquityCurve } from "@/components/charts/EquityCurve";
import { ChartContainer } from "@/components/charts/ChartContainer";
import { useAnalyticsOverview, useWebhookSignals, useStrategies, usePaperSessions } from "@/lib/hooks/useApi";
import { formatCurrency } from "@/lib/utils/formatters";

export default function DashboardPage() {
  const router = useRouter();
  const { data: overview, isLoading: loadingOverview } = useAnalyticsOverview();
  const { data: signals } = useWebhookSignals();
  const { data: strategies } = useStrategies();
  const { data: sessions } = usePaperSessions();
  const activeSessions = (sessions ?? []).filter((s) => s.status === "active").length;

  const signalColumns: Column<Record<string, unknown>>[] = [
    { key: "created_at", header: "Time" },
    { key: "symbol", header: "Symbol" },
    { key: "action", header: "Action", render: (v) => (
      <StatusBadge variant={v === "BUY" ? "success" : "error"} text={String(v)} />
    )},
    { key: "rule_result", header: "Result", render: (v) => (
      <StatusBadge
        variant={v === "passed" ? "success" : v === "blocked" ? "error" : "warning"}
        text={String(v ?? "—")}
      />
    )},
  ];

  return (
    <Box>
      <Heading size="md" mb={6}>Dashboard</Heading>

      <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4} mb={8}>
        <StatCard label="Active Strategies" value={String(overview?.active_strategies ?? 0)} />
        <StatCard label="Active Paper Sessions" value={String(activeSessions)} />
        <StatCard label="Today's Signals" value={String(overview?.trades_today ?? 0)} />
        <StatCard label="Portfolio P&L" value={formatCurrency(overview?.total_pnl ?? 0)} />
      </SimpleGrid>

      <Box mb={8}>
        <Heading size="sm" mb={3}>Equity Curve</Heading>
        <ChartContainer>
          {() => <EquityCurve data={[]} height={250} />}
        </ChartContainer>
      </Box>

      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6} mb={8}>
        <Box>
          <Heading size="sm" mb={3}>Recent Signals</Heading>
          <DataTable
            columns={signalColumns}
            data={(signals ?? []).slice(0, 10)}
            onRowClick={() => router.push("/webhooks")}
            emptyMessage="No signals yet"
          />
        </Box>
        <Box>
          <Heading size="sm" mb={3}>Top Strategies</Heading>
          {(strategies ?? []).length === 0 ? (
            <Text color="gray.500" py={4}>No strategies yet</Text>
          ) : (
            (strategies ?? []).slice(0, 5).map((s) => (
              <Box
                key={s.id} p={3} mb={2} borderWidth="1px" borderRadius="md"
                cursor="pointer" _hover={{ bg: "gray.50" }}
                onClick={() => router.push(`/analytics/strategies/${s.id}`)}
              >
                <Text fontWeight="semibold">{s.name}</Text>
                <StatusBadge variant={s.is_active ? "success" : "neutral"} text={s.mode} />
              </Box>
            ))
          )}
        </Box>
      </SimpleGrid>

      <Flex gap={3}>
        <Button colorScheme="blue" size="sm" onClick={() => router.push("/strategies/new")}>
          New Strategy
        </Button>
        <Button variant="outline" size="sm" onClick={() => router.push("/backtesting")}>
          Run Backtest
        </Button>
        <Button variant="outline" size="sm" onClick={() => router.push("/brokers")}>
          Connect Broker
        </Button>
      </Flex>
    </Box>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npx jest __tests__/pages/dashboard.test.tsx
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/\(dashboard\)/page.tsx frontend/__tests__/pages/dashboard.test.tsx
git commit -m "feat(frontend): add dashboard home page with stats, signals, and quick actions"
```

---

### Task 13: Strategies Pages — List, Detail, Create, Edit

**Files:**
- Create: `frontend/app/(dashboard)/strategies/page.tsx`
- Create: `frontend/app/(dashboard)/strategies/new/page.tsx`
- Create: `frontend/app/(dashboard)/strategies/[id]/page.tsx`
- Create: `frontend/app/(dashboard)/strategies/[id]/edit/page.tsx`
- Create: `frontend/__tests__/pages/strategies.test.tsx`

- [ ] **Step 1: Write strategies list test**

```typescript
// __tests__/pages/strategies.test.tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import StrategiesPage from "@/app/(dashboard)/strategies/page";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

describe("StrategiesPage", () => {
  it("renders strategies table with data", () => {
    (useApiModule.useStrategies as jest.Mock).mockReturnValue({
      data: [
        { id: "1", name: "NIFTY Momentum", mode: "paper", is_active: true, created_at: "2026-01-01" },
      ],
      isLoading: false, error: undefined, mutate: jest.fn(),
    });
    render(<ChakraProvider><StrategiesPage /></ChakraProvider>);
    expect(screen.getByText("NIFTY Momentum")).toBeInTheDocument();
    expect(screen.getByText("New Strategy")).toBeInTheDocument();
  });

  it("renders empty state when no strategies", () => {
    (useApiModule.useStrategies as jest.Mock).mockReturnValue({
      data: [], isLoading: false, error: undefined, mutate: jest.fn(),
    });
    render(<ChakraProvider><StrategiesPage /></ChakraProvider>);
    expect(screen.getByText(/no strategies/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx jest __tests__/pages/strategies.test.tsx
```

- [ ] **Step 3: Implement strategies list page**

```typescript
// app/(dashboard)/strategies/page.tsx
"use client";
import { Box, Heading, Button, Flex, Select, Switch, useToast, useDisclosure } from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { DataTable, Column } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { EmptyState } from "@/components/shared/EmptyState";
import { ConfirmModal } from "@/components/shared/ConfirmModal";
import { useStrategies } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { formatDate } from "@/lib/utils/formatters";

export default function StrategiesPage() {
  const router = useRouter();
  const toast = useToast();
  const { data: strategies, isLoading, mutate } = useStrategies();
  const [modeFilter, setModeFilter] = useState("all");
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const { isOpen, onOpen, onClose } = useDisclosure();

  const filtered = (strategies ?? []).filter((s) => {
    if (modeFilter === "all") return true;
    return s.mode === modeFilter;
  });

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await apiClient(`/api/v1/strategies/${deleteId}`, { method: "DELETE" });
      mutate();
      toast({ title: "Strategy deleted", status: "success" });
    } catch {
      toast({ title: "Failed to delete", status: "error" });
    }
    setDeleteId(null);
    onClose();
  };

  const columns: Column<typeof filtered[0]>[] = [
    { key: "name", header: "Name", sortable: true },
    { key: "mode", header: "Mode", render: (v) => (
      <StatusBadge variant={v === "paper" ? "info" : "success"} text={String(v)} />
    )},
    { key: "is_active", header: "Active", render: (v) => <Switch isChecked={!!v} isReadOnly size="sm" /> },
    { key: "created_at", header: "Created", render: (v) => formatDate(String(v)) },
  ];

  if (!isLoading && (strategies ?? []).length === 0) {
    return (
      <Box>
        <Heading size="md" mb={6}>Strategies</Heading>
        <EmptyState
          title="No strategies yet"
          description="Create your first trading strategy to get started."
          actionLabel="New Strategy"
          onAction={() => router.push("/strategies/new")}
        />
      </Box>
    );
  }

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6}>
        <Heading size="md">Strategies</Heading>
        <Flex gap={3}>
          <Select size="sm" w="120px" value={modeFilter} onChange={(e) => setModeFilter(e.target.value)}>
            <option value="all">All</option>
            <option value="paper">Paper</option>
            <option value="live">Live</option>
          </Select>
          <Button colorScheme="blue" size="sm" onClick={() => router.push("/strategies/new")}>
            New Strategy
          </Button>
        </Flex>
      </Flex>

      <DataTable
        columns={columns}
        data={filtered}
        onRowClick={(row) => router.push(`/strategies/${row.id}`)}
      />

      <ConfirmModal
        isOpen={isOpen}
        onClose={onClose}
        onConfirm={handleDelete}
        title="Delete Strategy"
        message="Are you sure? This cannot be undone."
      />
    </Box>
  );
}
```

- [ ] **Step 4: Implement strategy create/edit form page**

Create `frontend/app/(dashboard)/strategies/new/page.tsx` — a form with fields: Name, Broker Connection (select), Mode (radio), Active (switch), Mapping Template (textarea), Rules (whitelist/blacklist tags, max positions, max signals, trading hours). On submit: `POST /api/v1/strategies`. Navigate to `/strategies` on success.

Create `frontend/app/(dashboard)/strategies/[id]/edit/page.tsx` — same form, pre-populated via `GET /api/v1/strategies/{id}`. On submit: `PUT /api/v1/strategies/{id}`.

(Full code similar pattern to login/signup form — form state, handleSubmit, validation, toast on error.)

- [ ] **Step 5: Implement strategy detail page with tabs**

Create `frontend/app/(dashboard)/strategies/[id]/page.tsx` — fetches strategy via `useStrategy(id)`. Shows info card at top (name, mode, active badge). Three Chakra UI `Tabs`: Signals (recent webhook signals), Paper Trading (session link), Analytics (strategy metrics + equity curve).

- [ ] **Step 6: Run tests**

```bash
cd frontend && npx jest __tests__/pages/strategies.test.tsx
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/app/\(dashboard\)/strategies/ frontend/__tests__/pages/strategies.test.tsx
git commit -m "feat(frontend): add strategies pages — list, detail with tabs, create/edit forms"
```

---

### Task 14: Webhooks Page

**Files:**
- Create: `frontend/app/(dashboard)/webhooks/page.tsx`
- Create: `frontend/__tests__/pages/webhooks.test.tsx`

- [ ] **Step 1: Write webhooks test**

```typescript
// __tests__/pages/webhooks.test.tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import WebhooksPage from "@/app/(dashboard)/webhooks/page";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));

describe("WebhooksPage", () => {
  it("renders webhook config section", () => {
    (useApiModule.useWebhookConfig as jest.Mock).mockReturnValue({
      data: { webhook_url: "http://localhost:8000/api/v1/webhook/abc123", token: "abc123" },
      isLoading: false, mutate: jest.fn(),
    });
    (useApiModule.useWebhookSignals as jest.Mock).mockReturnValue({
      data: [], isLoading: false, mutate: jest.fn(),
    });
    render(<ChakraProvider><WebhooksPage /></ChakraProvider>);
    expect(screen.getByText(/webhook url/i)).toBeInTheDocument();
    expect(screen.getByText(/regenerate/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx jest __tests__/pages/webhooks.test.tsx
```

- [ ] **Step 3: Implement webhooks page**

```typescript
// app/(dashboard)/webhooks/page.tsx
"use client";
import {
  Box, Heading, Text, Flex, Button, Code, IconButton, useToast, useDisclosure, useClipboard,
} from "@chakra-ui/react";
import { MdContentCopy } from "react-icons/md";
import { DataTable, Column } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmModal } from "@/components/shared/ConfirmModal";
import { useWebhookConfig, useWebhookSignals } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { formatDate } from "@/lib/utils/formatters";

export default function WebhooksPage() {
  const toast = useToast();
  const { data: config, mutate: mutateConfig } = useWebhookConfig();
  const { data: signals, isLoading } = useWebhookSignals();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const { onCopy } = useClipboard(config?.webhook_url ?? "");

  const handleRegenerate = async () => {
    try {
      await apiClient("/api/v1/webhooks/config/regenerate-token", { method: "POST" });
      mutateConfig();
      toast({ title: "Token regenerated", status: "success" });
    } catch {
      toast({ title: "Failed to regenerate", status: "error" });
    }
    onClose();
  };

  const columns: Column<Record<string, unknown>>[] = [
    { key: "created_at", header: "Time", render: (v) => formatDate(String(v)) },
    { key: "strategy_name", header: "Strategy" },
    { key: "symbol", header: "Symbol" },
    { key: "action", header: "Action", render: (v) => (
      <StatusBadge variant={v === "BUY" ? "success" : "error"} text={String(v)} />
    )},
    { key: "rule_result", header: "Result", render: (v) => (
      <StatusBadge
        variant={v === "passed" ? "success" : v === "blocked" ? "error" : "warning"}
        text={String(v ?? "—")}
      />
    )},
  ];

  return (
    <Box>
      <Heading size="md" mb={6}>Webhooks</Heading>

      <Box p={4} borderWidth="1px" borderRadius="lg" mb={8}>
        <Text fontWeight="semibold" mb={2}>Webhook URL</Text>
        <Flex align="center" gap={2} mb={3}>
          <Code p={2} fontSize="sm" flex={1}>{config?.webhook_url ?? "Loading..."}</Code>
          <IconButton aria-label="Copy URL" icon={<MdContentCopy />} size="sm" onClick={onCopy} />
        </Flex>
        <Button size="sm" colorScheme="orange" variant="outline" onClick={onOpen}>
          Regenerate Token
        </Button>
        <Text fontSize="xs" color="gray.500" mt={2}>
          Send POST requests to this URL from TradingView or any external signal source.
        </Text>
      </Box>

      <Heading size="sm" mb={3}>Signal Log</Heading>
      <DataTable columns={columns} data={signals ?? []} emptyMessage="No signals received yet" isLoading={isLoading} />

      <ConfirmModal
        isOpen={isOpen} onClose={onClose} onConfirm={handleRegenerate}
        title="Regenerate Token"
        message="Your current webhook URL will stop working. Any connected signal sources will need to be updated."
        confirmLabel="Regenerate"
      />
    </Box>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npx jest __tests__/pages/webhooks.test.tsx
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/\(dashboard\)/webhooks/ frontend/__tests__/pages/webhooks.test.tsx
git commit -m "feat(frontend): add webhooks page with config, signal log, and token regeneration"
```

---

### Task 15: Brokers Pages — List and Add

**Files:**
- Create: `frontend/app/(dashboard)/brokers/page.tsx`
- Create: `frontend/app/(dashboard)/brokers/new/page.tsx`
- Create: `frontend/__tests__/pages/brokers.test.tsx`

- [ ] **Step 1: Write brokers test**

```typescript
// __tests__/pages/brokers.test.tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import BrokersPage from "@/app/(dashboard)/brokers/page";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));

describe("BrokersPage", () => {
  it("renders broker cards", () => {
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [{ id: "1", broker_type: "zerodha", is_active: true, connected_at: "2026-01-01" }],
      isLoading: false, mutate: jest.fn(),
    });
    render(<ChakraProvider><BrokersPage /></ChakraProvider>);
    expect(screen.getByText("zerodha")).toBeInTheDocument();
    expect(screen.getByText("Add Broker")).toBeInTheDocument();
  });

  it("renders empty state", () => {
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [], isLoading: false, mutate: jest.fn(),
    });
    render(<ChakraProvider><BrokersPage /></ChakraProvider>);
    expect(screen.getByText(/no broker/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx jest __tests__/pages/brokers.test.tsx
```

- [ ] **Step 3: Implement brokers list page**

```typescript
// app/(dashboard)/brokers/page.tsx
"use client";
import {
  Box, Heading, Button, SimpleGrid, Text, Flex, useToast, useDisclosure,
} from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { EmptyState } from "@/components/shared/EmptyState";
import { ConfirmModal } from "@/components/shared/ConfirmModal";
import { useBrokers } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { formatDate } from "@/lib/utils/formatters";

export default function BrokersPage() {
  const router = useRouter();
  const toast = useToast();
  const { data: brokers, isLoading, mutate } = useBrokers();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await apiClient(`/api/v1/brokers/${deleteId}`, { method: "DELETE" });
      mutate();
      toast({ title: "Broker deleted", status: "success" });
    } catch {
      toast({ title: "Failed to delete", status: "error" });
    }
    setDeleteId(null);
    onClose();
  };

  if (!isLoading && (brokers ?? []).length === 0) {
    return (
      <Box>
        <Heading size="md" mb={6}>Brokers</Heading>
        <EmptyState
          title="No broker connections"
          description="Connect your first broker to start live trading."
          actionLabel="Add Broker"
          onAction={() => router.push("/brokers/new")}
        />
      </Box>
    );
  }

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6}>
        <Heading size="md">Brokers</Heading>
        <Button colorScheme="blue" size="sm" onClick={() => router.push("/brokers/new")}>
          Add Broker
        </Button>
      </Flex>

      <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
        {(brokers ?? []).map((b) => (
          <Box key={b.id} p={4} borderWidth="1px" borderRadius="lg">
            <Text fontWeight="bold" textTransform="capitalize">{b.broker_type}</Text>
            <StatusBadge variant={b.is_active ? "success" : "error"} text={b.is_active ? "Connected" : "Error"} />
            <Text fontSize="xs" color="gray.500" mt={2}>Connected {formatDate(b.connected_at)}</Text>
            <Button
              size="xs" colorScheme="red" variant="ghost" mt={2}
              onClick={() => { setDeleteId(b.id); onOpen(); }}
            >
              Delete
            </Button>
          </Box>
        ))}
      </SimpleGrid>

      <ConfirmModal
        isOpen={isOpen} onClose={onClose} onConfirm={handleDelete}
        title="Delete Broker" message="This will remove the broker connection. To reconnect, add it again."
      />
    </Box>
  );
}
```

- [ ] **Step 4: Implement add broker form page**

Create `frontend/app/(dashboard)/brokers/new/page.tsx` — form with: Broker Type (select: zerodha, exchange1), dynamic credential fields (password inputs), submit → `POST /api/v1/brokers` with `{ broker_type, credentials: { ... } }`. Navigate to `/brokers` on success.

- [ ] **Step 5: Run tests**

```bash
cd frontend && npx jest __tests__/pages/brokers.test.tsx
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/\(dashboard\)/brokers/ frontend/__tests__/pages/brokers.test.tsx
git commit -m "feat(frontend): add brokers pages — card grid and add form"
```

---

### Task 16: Paper Trading Pages — Sessions List and Detail

**Files:**
- Create: `frontend/app/(dashboard)/paper-trading/page.tsx`
- Create: `frontend/app/(dashboard)/paper-trading/[id]/page.tsx`
- Create: `frontend/__tests__/pages/paper-trading.test.tsx`

- [ ] **Step 1: Write paper trading test**

```typescript
// __tests__/pages/paper-trading.test.tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import PaperTradingPage from "@/app/(dashboard)/paper-trading/page";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));

describe("PaperTradingPage", () => {
  it("renders sessions table", () => {
    (useApiModule.usePaperSessions as jest.Mock).mockReturnValue({
      data: [{
        id: "1", strategy_id: "s1", initial_capital: "100000",
        current_balance: "105000", status: "active", started_at: "2026-01-01T00:00:00Z",
      }],
      isLoading: false, mutate: jest.fn(),
    });
    (useApiModule.useStrategies as jest.Mock).mockReturnValue({
      data: [{ id: "s1", name: "Test Strategy" }], isLoading: false, mutate: jest.fn(),
    });
    render(<ChakraProvider><PaperTradingPage /></ChakraProvider>);
    expect(screen.getByText("Start Session")).toBeInTheDocument();
  });

  it("renders empty state", () => {
    (useApiModule.usePaperSessions as jest.Mock).mockReturnValue({
      data: [], isLoading: false, mutate: jest.fn(),
    });
    (useApiModule.useStrategies as jest.Mock).mockReturnValue({
      data: [], isLoading: false, mutate: jest.fn(),
    });
    render(<ChakraProvider><PaperTradingPage /></ChakraProvider>);
    expect(screen.getByText(/no paper trading/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx jest __tests__/pages/paper-trading.test.tsx
```

- [ ] **Step 3: Implement paper trading sessions list**

```typescript
// app/(dashboard)/paper-trading/page.tsx
"use client";
import {
  Box, Heading, Button, Flex, Select, useDisclosure, useToast,
  Modal, ModalOverlay, ModalContent, ModalHeader, ModalBody, ModalFooter,
  FormControl, FormLabel, Input, NumberInput, NumberInputField,
} from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { DataTable, Column } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { EmptyState } from "@/components/shared/EmptyState";
import { usePaperSessions, useStrategies } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { formatCurrency, formatDate } from "@/lib/utils/formatters";

export default function PaperTradingPage() {
  const router = useRouter();
  const toast = useToast();
  const { data: sessions, isLoading, mutate } = usePaperSessions();
  const { data: strategies } = useStrategies();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [strategyId, setStrategyId] = useState("");
  const [capital, setCapital] = useState("100000");
  const [statusFilter, setStatusFilter] = useState("all");

  const filtered = (sessions ?? []).filter((s) => {
    if (statusFilter === "all") return true;
    return s.status === statusFilter;
  });

  const handleCreate = async () => {
    try {
      await apiClient("/api/v1/paper-trading/sessions", {
        method: "POST",
        body: { strategy_id: strategyId, capital: parseFloat(capital) },
      });
      mutate();
      toast({ title: "Session started", status: "success" });
      onClose();
    } catch {
      toast({ title: "Failed to start session", status: "error" });
    }
  };

  const strategyName = (sid: unknown) => {
    const s = (strategies ?? []).find((st) => st.id === sid);
    return s?.name ?? String(sid);
  };

  const columns: Column<Record<string, unknown>>[] = [
    { key: "strategy_id", header: "Strategy", render: (v) => strategyName(v) },
    { key: "status", header: "Status", render: (v) => (
      <StatusBadge variant={v === "active" ? "success" : "neutral"} text={String(v)} />
    )},
    { key: "initial_capital", header: "Initial Capital", render: (v) => formatCurrency(parseFloat(String(v))) },
    { key: "current_balance", header: "Current Equity", render: (v) => formatCurrency(parseFloat(String(v))) },
    { key: "started_at", header: "Started", render: (v) => v ? formatDate(String(v)) : "—" },
  ];

  if (!isLoading && (sessions ?? []).length === 0) {
    return (
      <Box>
        <Heading size="md" mb={6}>Paper Trading</Heading>
        <EmptyState
          title="No paper trading sessions"
          description="Start a paper trading session to test your strategies."
          actionLabel="Start Session"
          onAction={onOpen}
        />
        {/* Start session modal rendered below */}
      </Box>
    );
  }

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6}>
        <Heading size="md">Paper Trading</Heading>
        <Flex gap={3}>
          <Select size="sm" w="120px" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="stopped">Stopped</option>
          </Select>
          <Button colorScheme="blue" size="sm" onClick={onOpen}>Start Session</Button>
        </Flex>
      </Flex>

      <DataTable
        columns={columns}
        data={filtered}
        onRowClick={(row) => router.push(`/paper-trading/${row.id}`)}
      />

      <Modal isOpen={isOpen} onClose={onClose} isCentered>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Start Paper Trading Session</ModalHeader>
          <ModalBody>
            <FormControl mb={4}>
              <FormLabel>Strategy</FormLabel>
              <Select placeholder="Select strategy" value={strategyId} onChange={(e) => setStrategyId(e.target.value)}>
                {(strategies ?? []).map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </Select>
            </FormControl>
            <FormControl>
              <FormLabel>Initial Capital (₹)</FormLabel>
              <NumberInput value={capital} onChange={setCapital} min={1000}>
                <NumberInputField />
              </NumberInput>
            </FormControl>
          </ModalBody>
          <ModalFooter gap={3}>
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button colorScheme="blue" onClick={handleCreate} isDisabled={!strategyId}>Start</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
}
```

- [ ] **Step 4: Implement session detail page**

Create `frontend/app/(dashboard)/paper-trading/[id]/page.tsx` — uses `usePaperSession(id)`. Top: stat cards (Initial Capital, Current Equity, Unrealized P&L, Realized P&L, Open Positions). Middle: Chakra `Tabs` — Positions table and Trades table. Bottom: EquityCurve computed from trades. "Stop Session" button with ConfirmModal → `POST /api/v1/paper-trading/sessions/{id}/stop`.

- [ ] **Step 5: Run tests**

```bash
cd frontend && npx jest __tests__/pages/paper-trading.test.tsx
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/\(dashboard\)/paper-trading/ frontend/__tests__/pages/paper-trading.test.tsx
git commit -m "feat(frontend): add paper trading pages — sessions list and session detail"
```

---

### Task 17: Backtesting Page

**Files:**
- Create: `frontend/app/(dashboard)/backtesting/page.tsx`
- Create: `frontend/__tests__/pages/backtesting.test.tsx`

- [ ] **Step 1: Write backtesting test**

```typescript
// __tests__/pages/backtesting.test.tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import BacktestingPage from "@/app/(dashboard)/backtesting/page";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("@/components/charts/EquityCurve", () => ({ EquityCurve: () => <div data-testid="equity-curve" /> }));
jest.mock("@/components/charts/DrawdownChart", () => ({ DrawdownChart: () => <div data-testid="drawdown" /> }));
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));

describe("BacktestingPage", () => {
  beforeEach(() => {
    (useApiModule.useStrategies as jest.Mock).mockReturnValue({
      data: [{ id: "s1", name: "Test" }], isLoading: false, mutate: jest.fn(),
    });
    (useApiModule.useBacktests as jest.Mock).mockReturnValue({
      data: [], isLoading: false, mutate: jest.fn(),
    });
  });

  it("renders run backtest form", () => {
    render(<ChakraProvider><BacktestingPage /></ChakraProvider>);
    expect(screen.getByText("Run Backtest")).toBeInTheDocument();
    expect(screen.getByText(/strategy/i)).toBeInTheDocument();
    expect(screen.getByText(/initial capital/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx jest __tests__/pages/backtesting.test.tsx
```

- [ ] **Step 3: Implement backtesting page**

Two-panel layout. Left: form (Strategy select, Start Date, End Date, Initial Capital, Slippage %, Commission %, CSV textarea/file upload). Submit → `POST /api/v1/backtests`. Then poll `GET /api/v1/backtests/{id}` every 2s via `setInterval` until `status === "completed"` or `"failed"`. Right: results panel — 6 StatCards for metrics, EquityCurve, DrawdownChart, trade log DataTable with CSV export. History tab: DataTable of past backtests with delete action.

```typescript
// app/(dashboard)/backtesting/page.tsx
"use client";
import {
  Box, Heading, Flex, Button, FormControl, FormLabel, Input, Textarea,
  Select, SimpleGrid, Tabs, TabList, Tab, TabPanels, TabPanel,
  NumberInput, NumberInputField, Spinner, Text, useToast, useDisclosure,
} from "@chakra-ui/react";
import { useState, useRef, useCallback } from "react";
import { StatCard } from "@/components/shared/StatCard";
import { DataTable, Column } from "@/components/shared/DataTable";
import { ConfirmModal } from "@/components/shared/ConfirmModal";
import { EquityCurve } from "@/components/charts/EquityCurve";
import { DrawdownChart } from "@/components/charts/DrawdownChart";
import { useStrategies, useBacktests } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { formatCurrency, formatPercent, formatDate } from "@/lib/utils/formatters";

export default function BacktestingPage() {
  const toast = useToast();
  const { data: strategies } = useStrategies();
  const { data: backtests, mutate: mutateBacktests } = useBacktests();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const [strategyId, setStrategyId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [capital, setCapital] = useState("100000");
  const [slippage, setSlippage] = useState("0.1");
  const [commission, setCommission] = useState("0.03");
  const [signalsCsv, setSignalsCsv] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  const pollResult = useCallback((backtestId: string) => {
    pollRef.current = setInterval(async () => {
      try {
        const data = await apiClient<Record<string, unknown>>(`/api/v1/backtests/${backtestId}`);
        if (data.status === "completed" || data.status === "failed") {
          clearInterval(pollRef.current!);
          setIsRunning(false);
          setResult(data);
          mutateBacktests();
          if (data.status === "failed") {
            toast({ title: "Backtest failed", description: String(data.error_message ?? ""), status: "error" });
          }
        }
      } catch {
        clearInterval(pollRef.current!);
        setIsRunning(false);
        toast({ title: "Error polling results", status: "error" });
      }
    }, 2000);
  }, [mutateBacktests, toast]);

  const handleRun = async () => {
    setIsRunning(true);
    setResult(null);
    try {
      const data = await apiClient<Record<string, unknown>>("/api/v1/backtests", {
        method: "POST",
        body: {
          strategy_id: strategyId, start_date: startDate, end_date: endDate,
          capital: parseFloat(capital), slippage_pct: parseFloat(slippage),
          commission_pct: parseFloat(commission), signals_csv: signalsCsv,
        },
      });
      pollResult(String(data.id));
    } catch {
      setIsRunning(false);
      toast({ title: "Failed to start backtest", status: "error" });
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await apiClient(`/api/v1/backtests/${deleteId}`, { method: "DELETE" });
      mutateBacktests();
      toast({ title: "Backtest deleted", status: "success" });
    } catch {
      toast({ title: "Delete failed", status: "error" });
    }
    setDeleteId(null);
    onClose();
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => setSignalsCsv(String(ev.target?.result ?? ""));
    reader.readAsText(file);
  };

  const metrics = result?.metrics as Record<string, number> | undefined;
  const equityCurve = (result?.equity_curve ?? []) as Array<{ time: string; value: number }>;
  const tradeLog = (result?.trade_log ?? []) as Array<Record<string, unknown>>;

  const historyColumns: Column<Record<string, unknown>>[] = [
    { key: "created_at", header: "Date", render: (v) => formatDate(String(v)) },
    { key: "strategy_id", header: "Strategy" },
    { key: "status", header: "Status" },
  ];

  return (
    <Box>
      <Heading size="md" mb={6}>Backtesting</Heading>

      <Tabs>
        <TabList>
          <Tab>Run Backtest</Tab>
          <Tab>History</Tab>
        </TabList>

        <TabPanels>
          <TabPanel px={0}>
            <Flex gap={6} direction={{ base: "column", lg: "row" }}>
              {/* Left: Form */}
              <Box w={{ base: "100%", lg: "40%" }}>
                <FormControl mb={3}>
                  <FormLabel>Strategy</FormLabel>
                  <Select placeholder="Select" value={strategyId} onChange={(e) => setStrategyId(e.target.value)}>
                    {(strategies ?? []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </Select>
                </FormControl>
                <Flex gap={3} mb={3}>
                  <FormControl><FormLabel>Start Date</FormLabel><Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></FormControl>
                  <FormControl><FormLabel>End Date</FormLabel><Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></FormControl>
                </Flex>
                <FormControl mb={3}>
                  <FormLabel>Initial Capital (₹)</FormLabel>
                  <NumberInput value={capital} onChange={setCapital}><NumberInputField /></NumberInput>
                </FormControl>
                <Flex gap={3} mb={3}>
                  <FormControl><FormLabel>Slippage %</FormLabel><NumberInput value={slippage} onChange={setSlippage} step={0.01}><NumberInputField /></NumberInput></FormControl>
                  <FormControl><FormLabel>Commission %</FormLabel><NumberInput value={commission} onChange={setCommission} step={0.01}><NumberInputField /></NumberInput></FormControl>
                </Flex>
                <FormControl mb={3}>
                  <FormLabel>Signal Data (CSV)</FormLabel>
                  <Input type="file" accept=".csv" onChange={handleFileUpload} mb={2} size="sm" />
                  <Textarea placeholder="Or paste CSV here..." value={signalsCsv} onChange={(e) => setSignalsCsv(e.target.value)} rows={4} fontSize="sm" />
                </FormControl>
                <Button colorScheme="blue" onClick={handleRun} isLoading={isRunning} isDisabled={!strategyId || !signalsCsv}>
                  Run Backtest
                </Button>
              </Box>

              {/* Right: Results */}
              <Box flex={1}>
                {isRunning && <Flex align="center" gap={3} py={8}><Spinner /><Text>Running backtest...</Text></Flex>}
                {result && metrics && (
                  <>
                    <SimpleGrid columns={{ base: 2, md: 3 }} spacing={3} mb={4}>
                      <StatCard label="Total Return" value={formatPercent(metrics.total_return ?? 0)} />
                      <StatCard label="Win Rate" value={formatPercent(metrics.win_rate ?? 0)} />
                      <StatCard label="Profit Factor" value={String((metrics.profit_factor ?? 0).toFixed(2))} />
                      <StatCard label="Sharpe Ratio" value={String((metrics.sharpe_ratio ?? 0).toFixed(2))} />
                      <StatCard label="Max Drawdown" value={formatPercent(metrics.max_drawdown ?? 0)} />
                      <StatCard label="Total Trades" value={String(metrics.total_trades ?? 0)} />
                    </SimpleGrid>
                    {equityCurve.length > 0 && <Box mb={4}><EquityCurve data={equityCurve} /></Box>}
                    {tradeLog.length > 0 && (
                      <DataTable
                        columns={[
                          { key: "symbol", header: "Symbol" },
                          { key: "action", header: "Action" },
                          { key: "quantity", header: "Qty" },
                          { key: "price", header: "Price" },
                        ]}
                        data={tradeLog}
                      />
                    )}
                  </>
                )}
              </Box>
            </Flex>
          </TabPanel>

          <TabPanel px={0}>
            <DataTable
              columns={historyColumns}
              data={backtests ?? []}
              onRowClick={(row) => {
                apiClient<Record<string, unknown>>(`/api/v1/backtests/${row.id}`).then(setResult);
              }}
              emptyMessage="No backtests yet"
            />
            <ConfirmModal isOpen={isOpen} onClose={onClose} onConfirm={handleDelete} title="Delete Backtest" message="Delete this backtest result?" />
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Box>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npx jest __tests__/pages/backtesting.test.tsx
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/\(dashboard\)/backtesting/ frontend/__tests__/pages/backtesting.test.tsx
git commit -m "feat(frontend): add backtesting page with run form, async polling, and history"
```

---

### Task 18: Analytics Pages — Overview and Strategy Drilldown

**Files:**
- Create: `frontend/app/(dashboard)/analytics/page.tsx`
- Create: `frontend/app/(dashboard)/analytics/strategies/[id]/page.tsx`
- Create: `frontend/__tests__/pages/analytics.test.tsx`

- [ ] **Step 1: Write analytics test**

```typescript
// __tests__/pages/analytics.test.tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import AnalyticsPage from "@/app/(dashboard)/analytics/page";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("@/components/charts/EquityCurve", () => ({ EquityCurve: () => <div data-testid="equity-curve" /> }));
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));

describe("AnalyticsPage", () => {
  it("renders portfolio stat cards", () => {
    (useApiModule.useAnalyticsOverview as jest.Mock).mockReturnValue({
      data: { total_pnl: 25000, active_strategies: 5, open_positions: 3, trades_today: 8 },
      isLoading: false,
    });
    (useApiModule.useStrategies as jest.Mock).mockReturnValue({
      data: [{ id: "1", name: "NIFTY", mode: "paper", is_active: true }],
      isLoading: false, mutate: jest.fn(),
    });
    render(<ChakraProvider><AnalyticsPage /></ChakraProvider>);
    expect(screen.getByText("Portfolio Overview")).toBeInTheDocument();
    expect(screen.getByText("Active Strategies")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx jest __tests__/pages/analytics.test.tsx
```

- [ ] **Step 3: Implement analytics overview page**

```typescript
// app/(dashboard)/analytics/page.tsx
"use client";
import { Box, Heading, SimpleGrid } from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { StatCard } from "@/components/shared/StatCard";
import { DataTable, Column } from "@/components/shared/DataTable";
import { EquityCurve } from "@/components/charts/EquityCurve";
import { ChartContainer } from "@/components/charts/ChartContainer";
import { useAnalyticsOverview, useStrategies } from "@/lib/hooks/useApi";
import { formatCurrency, formatPercent } from "@/lib/utils/formatters";

export default function AnalyticsPage() {
  const router = useRouter();
  const { data: overview, isLoading } = useAnalyticsOverview();
  const { data: strategies } = useStrategies();

  const columns: Column<Record<string, unknown>>[] = [
    { key: "name", header: "Strategy", sortable: true },
    { key: "mode", header: "Mode" },
    { key: "is_active", header: "Active", render: (v) => v ? "Yes" : "No" },
  ];

  return (
    <Box>
      <Heading size="md" mb={6}>Portfolio Overview</Heading>

      <SimpleGrid columns={{ base: 2, md: 3, lg: 6 }} spacing={4} mb={8}>
        <StatCard label="Total P&L" value={formatCurrency(overview?.total_pnl ?? 0)} />
        <StatCard label="Active Strategies" value={String(overview?.active_strategies ?? 0)} />
        <StatCard label="Open Positions" value={String(overview?.open_positions ?? 0)} />
        <StatCard label="Trades Today" value={String(overview?.trades_today ?? 0)} />
        <StatCard label="Win Rate" value="—" />
        <StatCard label="Max Drawdown" value="—" />
      </SimpleGrid>

      <Box mb={8}>
        <Heading size="sm" mb={3}>Portfolio Equity Curve</Heading>
        <ChartContainer>
          {() => <EquityCurve data={[]} height={300} />}
        </ChartContainer>
      </Box>

      <Heading size="sm" mb={3}>Strategy Comparison</Heading>
      <DataTable
        columns={columns}
        data={(strategies ?? []) as unknown as Record<string, unknown>[]}
        onRowClick={(row) => router.push(`/analytics/strategies/${row.id}`)}
        emptyMessage="No strategies to compare"
      />
    </Box>
  );
}
```

- [ ] **Step 4: Implement strategy drilldown page**

```typescript
// app/(dashboard)/analytics/strategies/[id]/page.tsx
"use client";
import { Box, Heading, SimpleGrid, Flex, Button } from "@chakra-ui/react";
import { useParams } from "next/navigation";
import { StatCard } from "@/components/shared/StatCard";
import { DataTable, Column } from "@/components/shared/DataTable";
import { EquityCurve } from "@/components/charts/EquityCurve";
import { DrawdownChart } from "@/components/charts/DrawdownChart";
import { useStrategyMetrics, useStrategyEquityCurve, useStrategyTrades, useStrategy } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { formatPercent, formatCurrency } from "@/lib/utils/formatters";

export default function StrategyDrilldownPage() {
  const { id } = useParams<{ id: string }>();
  const { data: strategy } = useStrategy(id);
  const { data: metrics } = useStrategyMetrics(id);
  const { data: equityCurve } = useStrategyEquityCurve(id);
  const { data: trades } = useStrategyTrades(id);

  const m = (metrics ?? {}) as Record<string, number>;

  const handleExportCsv = async () => {
    const res = await apiClient<Response>(
      `/api/v1/analytics/strategies/${id}/trades?format=csv`,
      { rawResponse: true }
    );
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `trades-${id}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const tradeColumns: Column<Record<string, unknown>>[] = [
    { key: "symbol", header: "Symbol" },
    { key: "action", header: "Action" },
    { key: "quantity", header: "Qty" },
    { key: "price", header: "Price" },
    { key: "pnl", header: "P&L" },
  ];

  return (
    <Box>
      <Heading size="md" mb={6}>{(strategy as Record<string, unknown>)?.name as string ?? "Strategy"} Analytics</Heading>

      <SimpleGrid columns={{ base: 2, md: 3 }} spacing={4} mb={6}>
        <StatCard label="Total Return" value={formatPercent(m.total_return ?? 0)} />
        <StatCard label="Win Rate" value={formatPercent(m.win_rate ?? 0)} />
        <StatCard label="Profit Factor" value={String((m.profit_factor ?? 0).toFixed(2))} />
        <StatCard label="Sharpe Ratio" value={String((m.sharpe_ratio ?? 0).toFixed(2))} />
        <StatCard label="Max Drawdown" value={formatPercent(m.max_drawdown ?? 0)} />
        <StatCard label="Total Trades" value={String(m.total_trades ?? 0)} />
      </SimpleGrid>

      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6} mb={6}>
        <Box>
          <Heading size="sm" mb={2}>Equity Curve</Heading>
          <EquityCurve data={(equityCurve ?? []) as Array<{ time: string; value: number }>} />
        </Box>
        <Box>
          <Heading size="sm" mb={2}>Drawdown</Heading>
          <DrawdownChart data={(equityCurve ?? []).map((p: Record<string, unknown>) => ({
            time: String(p.time), value: -Math.abs(Number(p.drawdown ?? 0)),
          }))} />
        </Box>
      </SimpleGrid>

      <Flex justify="space-between" align="center" mb={3}>
        <Heading size="sm">Trade Log</Heading>
        <Button size="xs" variant="outline" onClick={handleExportCsv}>Export CSV</Button>
      </Flex>
      <DataTable columns={tradeColumns} data={(trades ?? []) as Record<string, unknown>[]} emptyMessage="No trades" />
    </Box>
  );
}
```

- [ ] **Step 5: Run tests**

```bash
cd frontend && npx jest __tests__/pages/analytics.test.tsx
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/\(dashboard\)/analytics/ frontend/__tests__/pages/analytics.test.tsx
git commit -m "feat(frontend): add analytics pages — portfolio overview and strategy drilldown"
```

---

### Task 19: Settings Page

**Files:**
- Create: `frontend/app/(dashboard)/settings/page.tsx`
- Create: `frontend/__tests__/pages/settings.test.tsx`

- [ ] **Step 1: Write settings test**

```typescript
// __tests__/pages/settings.test.tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import SettingsPage from "@/app/(dashboard)/settings/page";
import * as useApiModule from "@/lib/hooks/useApi";
import { AuthProvider } from "@/lib/hooks/useAuth";
import * as client from "@/lib/api/client";

jest.mock("@/lib/hooks/useApi");
jest.mock("@/lib/api/client");

describe("SettingsPage", () => {
  it("renders health status and profile", () => {
    (useApiModule.useHealth as jest.Mock).mockReturnValue({
      data: { status: "ok" }, isLoading: false,
    });
    (client.getRefreshToken as jest.Mock).mockReturnValue(null);
    render(
      <ChakraProvider>
        <AuthProvider>
          <SettingsPage />
        </AuthProvider>
      </ChakraProvider>
    );
    expect(screen.getByText(/system health/i)).toBeInTheDocument();
    expect(screen.getByText(/theme/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx jest __tests__/pages/settings.test.tsx
```

- [ ] **Step 3: Implement settings page**

```typescript
// app/(dashboard)/settings/page.tsx
"use client";
import {
  Box, Heading, Text, Flex, Switch, Code, IconButton, useColorMode, useClipboard,
} from "@chakra-ui/react";
import { MdContentCopy } from "react-icons/md";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { useHealth, useWebhookConfig } from "@/lib/hooks/useApi";
import { useAuth } from "@/lib/hooks/useAuth";

export default function SettingsPage() {
  const { data: health, isLoading } = useHealth();
  const { data: config } = useWebhookConfig();
  const { user } = useAuth();
  const { colorMode, toggleColorMode } = useColorMode();
  const { onCopy } = useClipboard(config?.token ?? "");

  const isOk = health?.status === "ok";

  return (
    <Box>
      <Heading size="md" mb={6}>Settings</Heading>

      <Box p={4} borderWidth="1px" borderRadius="lg" mb={6}>
        <Heading size="sm" mb={3}>System Health</Heading>
        <Flex gap={4}>
          <Flex align="center" gap={2}>
            <Text>Database:</Text>
            <StatusBadge variant={isOk ? "success" : "error"} text={isOk ? "OK" : "Error"} />
          </Flex>
          <Flex align="center" gap={2}>
            <Text>Redis:</Text>
            <StatusBadge variant={isOk ? "success" : "error"} text={isOk ? "OK" : "Error"} />
          </Flex>
        </Flex>
        {isLoading && <Text fontSize="sm" color="gray.500" mt={2}>Checking...</Text>}
      </Box>

      <Box p={4} borderWidth="1px" borderRadius="lg" mb={6}>
        <Heading size="sm" mb={3}>Profile</Heading>
        <Text><strong>Email:</strong> {user?.email ?? "—"}</Text>
        <Text fontSize="sm" color="gray.500" mt={1}><strong>Plan:</strong> {user?.plan ?? "free"}</Text>
        {config?.token && (
          <Flex align="center" gap={2} mt={3}>
            <Text fontSize="sm"><strong>Webhook Token:</strong></Text>
            <Code fontSize="xs">{config.token}</Code>
            <IconButton aria-label="Copy token" icon={<MdContentCopy />} size="xs" onClick={onCopy} />
          </Flex>
        )}
      </Box>

      <Box p={4} borderWidth="1px" borderRadius="lg">
        <Heading size="sm" mb={3}>Theme</Heading>
        <Flex align="center" gap={3}>
          <Text>Dark Mode</Text>
          <Switch isChecked={colorMode === "dark"} onChange={toggleColorMode} />
        </Flex>
      </Box>
    </Box>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npx jest __tests__/pages/settings.test.tsx
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/\(dashboard\)/settings/ frontend/__tests__/pages/settings.test.tsx
git commit -m "feat(frontend): add settings page with health check, profile, and theme toggle"
```

---

### Task 20: OpenAPI Type Generation and Final Integration Test

**Files:**
- Create: `frontend/openapi-ts.config.ts`
- Create: `frontend/lib/api/generated-types.ts` (generated)

- [ ] **Step 1: Create openapi-typescript config**

```typescript
// openapi-ts.config.ts
import { defineConfig } from "openapi-typescript";

export default defineConfig({
  input: "http://localhost:8000/openapi.json",
  output: "./lib/api/generated-types.ts",
});
```

- [ ] **Step 2: Generate types from running backend**

```bash
cd frontend && npx openapi-typescript http://localhost:8000/openapi.json -o lib/api/generated-types.ts
```
Expected: File generated with all backend types.

- [ ] **Step 3: Verify full build**

```bash
cd frontend && npx next build
```
Expected: Build succeeds with zero errors.

- [ ] **Step 4: Run all tests**

```bash
cd frontend && npx jest --verbose
```
Expected: All tests pass.

- [ ] **Step 5: Verify dev server starts**

```bash
cd frontend && npx next dev -p 3000 &
sleep 5 && curl -s http://localhost:3000 | head -20
kill %1
```
Expected: HTML response with AlgoMatter title.

- [ ] **Step 6: Commit**

```bash
git add frontend/openapi-ts.config.ts frontend/lib/api/generated-types.ts
git commit -m "feat(frontend): add OpenAPI type generation and verify full build"
```

- [ ] **Step 7: Add npm scripts to package.json**

Add to `frontend/package.json` scripts:
```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "jest",
    "test:watch": "jest --watch",
    "generate-types": "openapi-typescript http://localhost:8000/openapi.json -o lib/api/generated-types.ts"
  }
}
```

- [ ] **Step 8: Final commit**

```bash
git add frontend/package.json
git commit -m "feat(frontend): add npm scripts for dev, build, test, and type generation"
```
