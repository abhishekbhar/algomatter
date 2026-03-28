"use client";

import { ScrollReveal } from "@/components/shared/ScrollReveal";

const exchanges = ["Binance", "Exchange1", "Bybit", "OKX"];

export function ExchangeBar() {
  return (
    <section className="border-y border-brand-indigo/10 py-8">
      <ScrollReveal>
        <p className="text-center text-xs uppercase tracking-widest text-slate-faint mb-5">
          Supported Exchanges
        </p>
        <div className="flex items-center justify-center gap-10 flex-wrap opacity-40">
          {exchanges.map((name) => (
            <span
              key={name}
              className="text-sm font-semibold text-slate-body"
            >
              {name}
            </span>
          ))}
          <span className="text-sm font-semibold text-slate-body">+ more</span>
        </div>
      </ScrollReveal>
    </section>
  );
}
