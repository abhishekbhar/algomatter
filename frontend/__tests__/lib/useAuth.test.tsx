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
    mockedClient.getRefreshToken.mockReturnValue(null);
    mockedClient.apiClient.mockResolvedValueOnce({
      access_token: "at", refresh_token: "rt", token_type: "bearer",
    });
    mockedClient.apiClient.mockResolvedValueOnce({
      id: "u1", email: "a@b.com", is_active: true, plan: "free", created_at: "2026-01-01",
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

    act(() => { result.current.logout(); });

    expect(mockedClient.clearTokens).toHaveBeenCalled();
    expect(result.current.user).toBeNull();
  });
});
