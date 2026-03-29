"use client";

import { GradientButton } from "@/components/shared/GradientButton";
import { EquityCurve } from "@/components/shared/EquityCurve";
import { siteConfig } from "@/lib/config";

export function Hero() {
  return (
    <section className="relative overflow-hidden px-6 pb-16 pt-20 text-center md:pt-28 md:pb-24">
      {/* Background glows */}
      <div className="pointer-events-none absolute left-1/2 top-0 -translate-x-1/2 w-[500px] h-[500px] rounded-full bg-brand-indigo/15 blur-3xl" />
      <div className="pointer-events-none absolute right-[10%] top-10 w-[250px] h-[250px] rounded-full bg-brand-purple/10 blur-3xl" />

      <div className="relative z-10 mx-auto max-w-3xl">
        {/* Badge */}
        <span className="inline-block rounded-full border border-brand-indigo/30 bg-brand-indigo/15 px-4 py-1.5 text-xs text-brand-lavender mb-6">
          Now in public beta — try free for 14 days
        </span>

        <h1 className="text-4xl font-extrabold leading-tight tracking-tight text-slate-heading md:text-6xl">
          Crypto algo trading,{" "}
          <span className="bg-gradient-to-r from-brand-indigo via-brand-purple to-brand-cyan bg-clip-text text-transparent">
            simplified.
          </span>
        </h1>

        <p className="mx-auto mt-5 max-w-xl text-lg leading-relaxed text-slate-body">
          {siteConfig.description}
        </p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
          <GradientButton href={`${siteConfig.appUrl}/signup`} size="lg">
            Start Free Trial &rarr;
          </GradientButton>
          <GradientButton href="#how-it-works" variant="ghost" size="lg">
            Watch Demo
          </GradientButton>
        </div>
      </div>

      {/* Hero visual — browser frame with equity curve */}
      <div className="relative mx-auto mt-14 max-w-2xl rounded-xl border border-brand-indigo/20 bg-brand-bg/60 overflow-hidden">
        {/* Browser dots */}
        <div className="flex gap-1.5 px-4 py-3 border-b border-brand-indigo/10">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500/60" />
          <span className="w-2.5 h-2.5 rounded-full bg-yellow-500/60" />
          <span className="w-2.5 h-2.5 rounded-full bg-green-500/60" />
        </div>
        <div className="relative p-4">
          {/* Stats overlay */}
          <div className="absolute top-6 left-6 z-10 text-left">
            <p className="text-xs text-slate-muted">BTC/USDT &middot; 4H</p>
            <p className="mt-1 text-2xl font-bold text-green-400">+142.8%</p>
            <p className="text-xs text-slate-muted">Backtest: 6 months</p>
          </div>
          <div className="absolute top-6 right-6 z-10 text-right text-xs space-y-1">
            <p className="text-slate-muted">Sharpe: <span className="text-brand-lavender">2.41</span></p>
            <p className="text-slate-muted">Max DD: <span className="text-amber-400">-12.3%</span></p>
            <p className="text-slate-muted">Win Rate: <span className="text-green-400">67%</span></p>
          </div>
          <EquityCurve className="w-full h-48" />
        </div>
      </div>
    </section>
  );
}
