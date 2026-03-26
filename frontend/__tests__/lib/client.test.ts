// __tests__/lib/client.test.ts
import { apiClient, setAccessToken, getAccessToken, clearTokens } from "@/lib/api/client";

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
      ok: true, status: 200, json: async () => ({ data: "ok" }),
    });
    const result = await apiClient("/api/v1/strategies");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/strategies"),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      })
    );
    expect(result).toEqual({ data: "ok" });
  });

  it("makes POST request with JSON body", async () => {
    setAccessToken("tok");
    mockFetch.mockResolvedValueOnce({
      ok: true, status: 200, json: async () => ({ id: "1" }),
    });
    await apiClient("/api/v1/strategies", { method: "POST", body: { name: "test" } });
    const [, opts] = mockFetch.mock.calls[0];
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body)).toEqual({ name: "test" });
  });

  it("throws on non-ok response", async () => {
    setAccessToken("tok");
    mockFetch.mockResolvedValueOnce({
      ok: false, status: 422, json: async () => ({ detail: "validation error" }),
    });
    await expect(apiClient("/api/v1/strategies")).rejects.toThrow();
  });
});
