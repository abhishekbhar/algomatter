import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Algomatter — Crypto algo trading, simplified.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OGImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #0f0f23 0%, #1b1b3a 50%, #0f0f23 100%)",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "16px",
            marginBottom: "24px",
          }}
        >
          <svg width="64" height="64" viewBox="0 0 40 40" fill="none">
            <rect x="2" y="2" width="36" height="36" rx="8" fill="#6366f1" opacity="0.15" stroke="#6366f1" strokeWidth="1.5" />
            <path d="M12,30 L20,8 L28,30" stroke="#a855f7" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
            <line x1="15" y1="22" x2="25" y2="22" stroke="#6366f1" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <span
            style={{
              fontSize: "48px",
              fontWeight: 800,
              background: "linear-gradient(135deg, #a78bfa, #6366f1)",
              backgroundClip: "text",
              color: "transparent",
            }}
          >
            algomatter
          </span>
        </div>
        <p
          style={{
            fontSize: "28px",
            color: "#e2e8f0",
            fontWeight: 600,
          }}
        >
          Crypto algo trading, simplified.
        </p>
        <p
          style={{
            fontSize: "18px",
            color: "#94a3b8",
            marginTop: "12px",
            maxWidth: "600px",
            textAlign: "center",
          }}
        >
          Build strategies in Python, backtest against real market data, and deploy to live crypto markets.
        </p>
      </div>
    ),
    { ...size }
  );
}
