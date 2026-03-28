import { GradientButton } from "@/components/shared/GradientButton";
import { siteConfig } from "@/lib/config";

export function FinalCTA() {
  return (
    <section className="relative overflow-hidden px-6 py-20 text-center">
      <div className="pointer-events-none absolute bottom-0 left-1/2 -translate-x-1/2 w-[500px] h-[500px] rounded-full bg-brand-indigo/10 blur-3xl" />
      <div className="relative z-10">
        <h2 className="text-3xl font-bold text-slate-heading">
          Ready to automate your trading?
        </h2>
        <p className="mt-3 text-slate-muted">
          Start your 14-day free trial. No credit card required.
        </p>
        <div className="mt-8">
          <GradientButton href={`${siteConfig.appUrl}/signup`} size="lg">
            Start Free Trial &rarr;
          </GradientButton>
        </div>
      </div>
    </section>
  );
}
