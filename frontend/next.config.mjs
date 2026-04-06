/** @type {import('next').NextConfig} */
const nextConfig = {
  basePath: "/app",
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-eval' 'unsafe-inline' https://cdn.jsdelivr.net https://s3.tradingview.com",
              "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
              "img-src 'self' data: blob:",
              "font-src 'self' data: https://cdn.jsdelivr.net",
              "connect-src 'self' http://localhost:8000 http://localhost:3000 https://cdn.jsdelivr.net https://api.binance.com wss://stream.binance.com:9443",
              "worker-src 'self' blob:",
              "frame-src https://*.tradingview.com https://*.tradingview-widget.com",
              "frame-ancestors 'none'",
            ].join("; "),
          },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
