"use client";

import { ScrollReveal } from "@/components/shared/ScrollReveal";
import { TypeWriter } from "@/components/shared/TypeWriter";

const steps = [
  {
    number: 1,
    title: "Write your strategy",
    description:
      "Code in Python using our SDK, or connect signals from TradingView via webhooks. No framework lock-in.",
    visual: "code",
  },
  {
    number: 2,
    title: "Backtest & validate",
    description:
      "Run against historical data with realistic slippage and fees. See equity curves, drawdowns, Sharpe ratio, and every trade.",
    visual: "metrics",
  },
  {
    number: 3,
    title: "Deploy & monitor",
    description:
      "Paper trade first, then go live. Monitor positions, P&L, and trades in real-time. Kill switch if anything goes wrong.",
    visual: "live",
  },
];

const codeSnippet = `def on_candle(self, candle):
    if candle.rsi < 30:
        self.buy("BTC/USDT")`;

function StepVisual({ type }: { type: string }) {
  if (type === "code") {
    return (
      <div className="mt-3 rounded-md bg-[#0a0a1a] p-3">
        <TypeWriter code={codeSnippet} speed={40} className="text-brand-lavender text-xs" />
      </div>
    );
  }
  if (type === "metrics") {
    return (
      <div className="mt-3 rounded-md bg-[#0a0a1a] p-3 flex justify-between text-xs">
        <div>
          <span className="text-slate-muted">Return</span>
          <p className="text-green-400 text-lg font-bold">+142%</p>
        </div>
        <div>
          <span className="text-slate-muted">Sharpe</span>
          <p className="text-brand-lavender text-lg font-bold">2.41</p>
        </div>
        <div>
          <span className="text-slate-muted">Max DD</span>
          <p className="text-amber-400 text-lg font-bold">-12%</p>
        </div>
      </div>
    );
  }
  return (
    <div className="mt-3 rounded-md bg-[#0a0a1a] p-3 text-xs">
      <div className="flex justify-between items-center">
        <span className="text-slate-muted">BTC/USDT Long</span>
        <span className="text-green-400 font-semibold">● LIVE</span>
      </div>
      <div className="flex justify-between mt-2">
        <span className="text-slate-muted">Entry: $67,420</span>
        <span className="text-green-400">P&L: +$1,240</span>
      </div>
    </div>
  );
}

export function HowItWorks() {
  return (
    <section id="how-it-works" className="px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <ScrollReveal className="text-center mb-12">
          <p className="text-xs uppercase tracking-widest text-brand-indigo mb-2">
            How it works
          </p>
          <h2 className="text-3xl font-bold text-slate-heading">
            From idea to live trading in minutes
          </h2>
          <p className="mt-2 text-slate-muted">
            Three steps to automate your crypto strategy
          </p>
        </ScrollReveal>
        <div className="grid gap-6 md:grid-cols-3">
          {steps.map((step, i) => (
            <ScrollReveal key={step.number} delay={i * 0.15}>
              <div className="rounded-xl border border-brand-indigo/10 bg-brand-indigo/5 p-6">
                <div className="mb-4 flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-brand-indigo to-brand-purple text-sm font-bold text-white">
                  {step.number}
                </div>
                <h3 className="text-base font-semibold text-slate-heading mb-2">
                  {step.title}
                </h3>
                <p className="text-sm text-slate-muted leading-relaxed">
                  {step.description}
                </p>
                <StepVisual type={step.visual} />
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}
