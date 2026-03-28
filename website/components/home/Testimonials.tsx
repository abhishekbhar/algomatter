"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ScrollReveal } from "@/components/shared/ScrollReveal";

const testimonials = [
  {
    quote:
      "I went from a TradingView alert to a live bot in under 10 minutes. The backtesting caught a flaw in my strategy that would have cost me real money.",
    name: "Alex R.",
    role: "Crypto Trader",
  },
  {
    quote:
      "The Python SDK is incredibly clean. I ported my Pine Script strategy in an afternoon and the backtest results were way more detailed than anything I had before.",
    name: "Jordan M.",
    role: "Quant Developer",
  },
  {
    quote:
      "Paper trading gave me the confidence to go live. Being able to see exactly how my strategy would have performed with real slippage — that's what sold me.",
    name: "Sam K.",
    role: "DeFi Trader",
  },
];

export function Testimonials() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setIndex((prev) => (prev + 1) % testimonials.length);
    }, 6000);
    return () => clearInterval(timer);
  }, []);

  const t = testimonials[index];

  return (
    <section className="px-6 py-20">
      <div className="mx-auto max-w-xl">
        <ScrollReveal className="text-center">
          <p className="text-xs uppercase tracking-widest text-brand-indigo mb-8">
            What traders say
          </p>
          <div className="relative min-h-[200px]">
            <AnimatePresence mode="wait">
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.4 }}
                className="rounded-xl border border-brand-indigo/10 bg-brand-indigo/5 p-8"
              >
                <p className="text-base leading-relaxed text-slate-heading/90 italic">
                  &ldquo;{t.quote}&rdquo;
                </p>
                <div className="mt-5 flex items-center justify-center gap-3">
                  <div className="h-8 w-8 rounded-full bg-gradient-to-br from-brand-indigo to-brand-purple" />
                  <div className="text-left">
                    <p className="text-sm font-semibold text-slate-heading">
                      {t.name}
                    </p>
                    <p className="text-xs text-slate-muted">{t.role}</p>
                  </div>
                </div>
              </motion.div>
            </AnimatePresence>
          </div>
          {/* Dots */}
          <div className="mt-5 flex justify-center gap-2">
            {testimonials.map((_, i) => (
              <button
                key={i}
                onClick={() => setIndex(i)}
                className={`h-2 w-2 rounded-full transition-colors ${
                  i === index ? "bg-brand-indigo" : "bg-slate-line"
                }`}
                aria-label={`Testimonial ${i + 1}`}
              />
            ))}
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
