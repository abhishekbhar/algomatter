"use client";

import { ScrollReveal } from "@/components/shared/ScrollReveal";
import { AnimatedCounter } from "@/components/shared/AnimatedCounter";

const stats = [
  { target: 1200, suffix: "+", label: "Backtests Run" },
  { target: 50, suffix: "+", label: "Active Strategies" },
  { target: 2.4, prefix: "$", suffix: "M", label: "Volume Traded" },
  { target: 99.9, suffix: "%", label: "Uptime" },
];

export function PlatformStats() {
  return (
    <section className="px-6 py-16">
      <ScrollReveal>
        <p className="text-center text-xs uppercase tracking-widest text-brand-indigo mb-8">
          Platform Stats
        </p>
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-center gap-12 md:gap-16">
          {stats.map((s) => (
            <div key={s.label} className="text-center">
              <div className="text-3xl font-extrabold bg-gradient-to-br from-brand-indigo to-brand-purple bg-clip-text text-transparent">
                <AnimatedCounter
                  target={s.target}
                  prefix={s.prefix}
                  suffix={s.suffix}
                />
              </div>
              <p className="mt-1 text-xs text-slate-muted">{s.label}</p>
            </div>
          ))}
        </div>
      </ScrollReveal>
    </section>
  );
}
