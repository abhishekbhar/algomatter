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
