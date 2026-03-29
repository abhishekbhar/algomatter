"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const faqs = [
  {
    q: "What happens after the free trial?",
    a: "After 14 days, you'll be asked to choose a plan. If you don't, your account switches to read-only \u2014 you can still view your data, but can't run strategies or backtests until you subscribe.",
  },
  {
    q: "Can I cancel anytime?",
    a: "Yes. Cancel from your account settings at any time. You'll keep access through the end of your billing period.",
  },
  {
    q: "Which exchanges are supported?",
    a: "We currently support Binance, Exchange1, Bybit, and OKX with more coming soon. All exchanges support both paper and live trading.",
  },
  {
    q: "Is my exchange API key secure?",
    a: "Yes. API keys are encrypted with AES-256-GCM before storage. We use per-tenant derived encryption keys. We recommend using API keys with trade-only permissions (no withdrawal).",
  },
  {
    q: "Can I run multiple strategies at once?",
    a: "Yes. The number of concurrent strategies depends on your plan \u2014 Starter supports 2, Pro supports 10, and Enterprise is unlimited.",
  },
  {
    q: "What programming language do I need to know?",
    a: "Python. Our SDK is designed to be approachable \u2014 if you can write a basic Python function, you can write a strategy. We also support no-code webhook signals from TradingView.",
  },
];

export function FAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <section className="mx-auto max-w-2xl px-6 py-16">
      <h2 className="text-2xl font-bold text-slate-heading text-center mb-8">
        Frequently asked questions
      </h2>
      <div className="space-y-3">
        {faqs.map((faq, i) => (
          <div
            key={i}
            className="rounded-lg border border-brand-indigo/10 bg-brand-indigo/5"
          >
            <button
              onClick={() => setOpenIndex(openIndex === i ? null : i)}
              className="flex w-full items-center justify-between px-5 py-4 text-left text-sm font-medium text-slate-heading"
            >
              {faq.q}
              <span
                className={`ml-2 transition-transform ${
                  openIndex === i ? "rotate-45" : ""
                }`}
              >
                +
              </span>
            </button>
            <AnimatePresence>
              {openIndex === i && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden"
                >
                  <p className="px-5 pb-4 text-sm text-slate-body leading-relaxed">
                    {faq.a}
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ))}
      </div>
    </section>
  );
}
