import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          bg: "#0f0f23",
          "bg-light": "#1b1b3a",
          indigo: "#6366f1",
          purple: "#a855f7",
          lavender: "#a78bfa",
          cyan: "#22d3ee",
        },
        slate: {
          heading: "#f1f5f9",
          body: "#94a3b8",
          muted: "#64748b",
          faint: "#475569",
          line: "#334155",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
