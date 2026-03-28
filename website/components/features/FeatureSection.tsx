"use client";

import { ScrollReveal } from "@/components/shared/ScrollReveal";
import { ReactNode } from "react";

interface FeatureSectionProps {
  label: string;
  title: string;
  description: string;
  visual: ReactNode;
  reversed?: boolean;
}

export function FeatureSection({
  label,
  title,
  description,
  visual,
  reversed = false,
}: FeatureSectionProps) {
  return (
    <section className="px-6 py-16">
      <div
        className={`mx-auto flex max-w-5xl flex-col gap-10 items-center md:flex-row ${
          reversed ? "md:flex-row-reverse" : ""
        }`}
      >
        <ScrollReveal className="flex-1 space-y-3">
          <p className="text-xs uppercase tracking-widest text-brand-indigo">
            {label}
          </p>
          <h3 className="text-2xl font-bold text-slate-heading">{title}</h3>
          <p className="text-sm leading-relaxed text-slate-body">{description}</p>
        </ScrollReveal>
        <ScrollReveal delay={0.2} className="flex-1">
          <div className="rounded-xl border border-brand-indigo/10 bg-brand-indigo/5 p-6 overflow-hidden">
            {visual}
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
