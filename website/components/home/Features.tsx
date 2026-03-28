"use client";

import { ScrollReveal } from "@/components/shared/ScrollReveal";

const features = [
  {
    icon: "📊",
    title: "Backtesting Engine",
    description:
      "Powered by Nautilus Trader. Realistic fills, configurable slippage & commission. Full trade logs and equity curves.",
  },
  {
    icon: "🔗",
    title: "Webhook Signals",
    description:
      "Connect TradingView or any alert source. Map JSON fields with zero code. Rules filter what gets executed.",
  },
  {
    icon: "🐍",
    title: "Python Strategies",
    description:
      "Write strategies in Python with our SDK. Built-in editor, version control, and templates to get started fast.",
  },
  {
    icon: "⚡",
    title: "Paper → Live",
    description:
      "Test with virtual capital first. When you're confident, flip to live with one click. Kill switch for safety.",
  },
];

export function Features() {
  return (
    <section className="px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <ScrollReveal className="text-center mb-12">
          <p className="text-xs uppercase tracking-widest text-brand-indigo mb-2">
            Features
          </p>
          <h2 className="text-3xl font-bold text-slate-heading">
            Everything you need to trade algorithmically
          </h2>
        </ScrollReveal>
        <div className="grid gap-5 sm:grid-cols-2">
          {features.map((f, i) => (
            <ScrollReveal key={f.title} delay={i * 0.1}>
              <div className="rounded-xl border border-brand-indigo/10 bg-brand-indigo/5 p-6">
                <div className="text-2xl mb-3">{f.icon}</div>
                <h3 className="text-base font-semibold text-slate-heading mb-1.5">
                  {f.title}
                </h3>
                <p className="text-sm text-slate-muted leading-relaxed">
                  {f.description}
                </p>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}
