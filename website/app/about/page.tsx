import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About",
  description: "Our mission is to make algorithmic trading accessible to every crypto trader.",
};

const values = [
  {
    title: "Transparency over complexity",
    description: "Every trade, every metric, every fee \u2014 visible and verifiable. No black boxes.",
  },
  {
    title: "Test before you trade",
    description: "Paper trading and backtesting aren't optional extras. They're the default workflow.",
  },
  {
    title: "Your keys, your strategies",
    description: "Your exchange API keys are encrypted. Your strategy code is yours. We never trade on your behalf.",
  },
  {
    title: "Simplicity is a feature",
    description: "If it takes more than 5 minutes to go from idea to first backtest, we haven't done our job.",
  },
];

export default function AboutPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-20">
      <h1 className="text-4xl font-extrabold text-slate-heading">About Algomatter</h1>

      <section className="mt-10">
        <h2 className="text-xl font-bold text-slate-heading">Our Mission</h2>
        <p className="mt-3 text-slate-body leading-relaxed">
          We believe algorithmic trading shouldn&apos;t require a hedge fund budget.
          Retail crypto traders deserve the same tools the institutions use —
          backtesting, automated execution, and real-time analytics — without the
          complexity or the price tag.
        </p>
      </section>

      <section className="mt-12">
        <h2 className="text-xl font-bold text-slate-heading">What we&apos;re building</h2>
        <p className="mt-3 text-slate-body leading-relaxed">
          Algomatter is a platform where you can write trading strategies in Python,
          backtest them against real historical data, paper trade to build confidence,
          and deploy to live crypto markets — all from a single dashboard. We handle the
          infrastructure so you can focus on your edge.
        </p>
      </section>

      <section className="mt-12">
        <h2 className="text-xl font-bold text-slate-heading">Our Values</h2>
        <div className="mt-5 grid gap-5 sm:grid-cols-2">
          {values.map((v) => (
            <div
              key={v.title}
              className="rounded-xl border border-brand-indigo/10 bg-brand-indigo/5 p-5"
            >
              <h3 className="text-sm font-semibold text-slate-heading">{v.title}</h3>
              <p className="mt-2 text-sm text-slate-muted leading-relaxed">
                {v.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section id="contact" className="mt-12">
        <h2 className="text-xl font-bold text-slate-heading">Contact</h2>
        <p className="mt-3 text-slate-body leading-relaxed">
          Got questions, feedback, or just want to chat about algo trading?
          Reach out at{" "}
          <a href="mailto:hello@algomatter.com" className="text-brand-lavender hover:underline">
            hello@algomatter.com
          </a>{" "}
          or join our{" "}
          <a
            href="https://discord.gg/algomatter"
            className="text-brand-lavender hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            Discord community
          </a>
          .
        </p>
      </section>
    </main>
  );
}
