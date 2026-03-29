export interface DocEntry {
  title: string;
  slug: string;
}

export interface DocSection {
  title: string;
  entries: DocEntry[];
}

export const docsManifest: DocSection[] = [
  {
    title: "Getting Started",
    entries: [
      { title: "Quick Start", slug: "getting-started/quick-start" },
      { title: "Connecting an Exchange", slug: "getting-started/connecting-exchange" },
      { title: "Your First Strategy", slug: "getting-started/first-strategy" },
    ],
  },
  {
    title: "Strategies",
    entries: [
      { title: "Python SDK Guide", slug: "strategies/python-sdk" },
      { title: "Strategy Templates", slug: "strategies/templates" },
      { title: "Webhooks & TradingView", slug: "strategies/webhooks-tradingview" },
      { title: "Mapping Templates", slug: "strategies/mapping-templates" },
    ],
  },
  {
    title: "Backtesting",
    entries: [
      { title: "Running a Backtest", slug: "backtesting/running-backtest" },
      { title: "Understanding Results", slug: "backtesting/understanding-results" },
      { title: "Slippage & Commission", slug: "backtesting/slippage-commission" },
    ],
  },
  {
    title: "Trading",
    entries: [
      { title: "Paper Trading", slug: "trading/paper-trading" },
      { title: "Going Live", slug: "trading/going-live" },
      { title: "Kill Switch & Safety", slug: "trading/kill-switch" },
    ],
  },
];

export function getAllDocSlugs(): string[] {
  return docsManifest.flatMap((section) =>
    section.entries.map((entry) => entry.slug)
  );
}

export function findAdjacentDocs(slug: string) {
  const all = docsManifest.flatMap((s) => s.entries);
  const index = all.findIndex((e) => e.slug === slug);
  return {
    prev: index > 0 ? all[index - 1] : null,
    next: index < all.length - 1 ? all[index + 1] : null,
  };
}
