"use client";

import { useState } from "react";
import { BillingToggle } from "@/components/pricing/BillingToggle";
import { PricingCards } from "@/components/pricing/PricingCards";
import { FAQ } from "@/components/pricing/FAQ";
import { GradientButton } from "@/components/shared/GradientButton";
import { siteConfig } from "@/lib/config";

export function PricingContent() {
  const [annual, setAnnual] = useState(false);

  return (
    <main>
      <section className="px-6 pt-20 pb-10 text-center">
        <h1 className="text-4xl font-extrabold text-slate-heading md:text-5xl">
          Simple, transparent pricing
        </h1>
        <p className="mt-4 text-lg text-slate-body">
          Start free, upgrade when you&apos;re ready
        </p>
        <div className="mt-8">
          <BillingToggle annual={annual} onChange={setAnnual} />
        </div>
      </section>
      <PricingCards annual={annual} />
      <FAQ />
      <section className="px-6 pb-20 text-center">
        <p className="text-slate-muted">
          Still not sure? Start with the free trial.
        </p>
        <div className="mt-4">
          <GradientButton href={`${siteConfig.appUrl}/signup`} size="lg">
            Start Free Trial &rarr;
          </GradientButton>
        </div>
      </section>
    </main>
  );
}
