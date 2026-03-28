import { GradientButton } from "@/components/shared/GradientButton";
import { siteConfig } from "@/lib/config";

interface PricingCardsProps {
  annual: boolean;
}

const tiers = [
  {
    name: "Starter",
    monthlyPrice: 29,
    description: "For traders getting started with automation",
    features: [
      "2 active strategies",
      "10 backtests/month",
      "Paper trading",
      "1 exchange connection",
      "100 webhook signals/day",
      "30-day data retention",
      "Community support",
    ],
    cta: "Start Free Trial",
    highlighted: false,
  },
  {
    name: "Pro",
    monthlyPrice: 79,
    description: "For serious traders who need more power",
    features: [
      "10 active strategies",
      "Unlimited backtests",
      "Paper trading",
      "3 exchange connections",
      "1,000 webhook signals/day",
      "1-year data retention",
      "Priority email support",
    ],
    cta: "Start Free Trial",
    highlighted: true,
  },
  {
    name: "Enterprise",
    monthlyPrice: null,
    description: "For teams and high-volume traders",
    features: [
      "Unlimited strategies",
      "Unlimited backtests",
      "Paper trading",
      "Unlimited exchanges",
      "Unlimited webhook signals",
      "Unlimited data retention",
      "Dedicated support",
    ],
    cta: "Contact Us",
    highlighted: false,
  },
];

export function PricingCards({ annual }: PricingCardsProps) {
  return (
    <div className="mx-auto grid max-w-5xl gap-6 px-6 md:grid-cols-3">
      {tiers.map((tier) => {
        const price = tier.monthlyPrice
          ? annual
            ? Math.round(tier.monthlyPrice * 0.8)
            : tier.monthlyPrice
          : null;

        return (
          <div
            key={tier.name}
            className={`relative rounded-xl border p-6 ${
              tier.highlighted
                ? "border-brand-indigo/40 bg-brand-indigo/10 shadow-lg shadow-brand-indigo/5"
                : "border-brand-indigo/10 bg-brand-indigo/5"
            }`}
          >
            {tier.highlighted && (
              <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-gradient-to-r from-brand-indigo to-brand-purple px-3 py-0.5 text-xs font-semibold text-white">
                Most Popular
              </span>
            )}
            <h3 className="text-lg font-bold text-slate-heading">{tier.name}</h3>
            <p className="mt-1 text-sm text-slate-muted">{tier.description}</p>
            <div className="mt-4">
              {price !== null ? (
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-extrabold text-slate-heading">
                    ${price}
                  </span>
                  <span className="text-sm text-slate-muted">/month</span>
                </div>
              ) : (
                <span className="text-3xl font-extrabold text-slate-heading">
                  Custom
                </span>
              )}
              {price !== null && (
                <p className="mt-1 text-xs text-slate-faint">
                  14-day free trial included
                </p>
              )}
            </div>
            <ul className="mt-6 space-y-2.5">
              {tier.features.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm text-slate-body">
                  <span className="mt-0.5 text-brand-indigo">&#10003;</span>
                  {f}
                </li>
              ))}
            </ul>
            <div className="mt-6">
              <GradientButton
                href={
                  tier.cta === "Contact Us"
                    ? "/about#contact"
                    : `${siteConfig.appUrl}/signup`
                }
                variant={tier.highlighted ? "primary" : "ghost"}
                size="md"
                className="w-full text-center"
              >
                {tier.cta}
              </GradientButton>
            </div>
          </div>
        );
      })}
    </div>
  );
}
