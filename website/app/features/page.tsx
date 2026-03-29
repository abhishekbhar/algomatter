import type { Metadata } from "next";
import { FeatureSection } from "@/components/features/FeatureSection";
import { GradientButton } from "@/components/shared/GradientButton";
import { siteConfig } from "@/lib/config";

export const metadata: Metadata = {
  title: "Features",
  description:
    "Everything you need to trade algorithmically — backtesting, webhooks, Python strategies, paper trading, live trading, and analytics.",
};

export default function FeaturesPage() {
  return (
    <main>
      {/* Hero */}
      <section className="px-6 pt-20 pb-10 text-center">
        <h1 className="text-4xl font-extrabold text-slate-heading md:text-5xl">
          Everything you need to trade algorithmically
        </h1>
        <p className="mt-4 text-lg text-slate-body max-w-xl mx-auto">
          From strategy creation to live execution — one platform, no glue code.
        </p>
      </section>

      <FeatureSection
        label="Strategies"
        title="Write strategies in Python"
        description="Use our SDK to define entry/exit logic, position sizing, and risk management. Built-in code editor with syntax highlighting, version control, and starter templates so you can go from idea to code in minutes."
        visual={
          <pre className="font-mono text-xs text-brand-lavender leading-relaxed">
            <code>{`class MomentumStrategy(Strategy):
    def on_candle(self, candle):
        if candle.rsi < 30:
            self.buy("BTC/USDT", qty=0.1)
        elif candle.rsi > 70:
            self.sell("BTC/USDT")`}</code>
          </pre>
        }
      />

      <FeatureSection
        label="Signals"
        title="Connect webhooks from TradingView"
        description="Receive alerts from TradingView, AmiBroker, or any source that can send a POST request. Map JSON fields to actions with zero code using our JSONPath mapper. Rules engine filters bad signals before they execute."
        reversed
        visual={
          <div className="text-xs space-y-3">
            <div className="flex items-center gap-3">
              <span className="rounded bg-brand-indigo/20 px-2 py-1 text-brand-lavender font-mono">TradingView</span>
              <span className="text-slate-muted">&rarr;</span>
              <span className="rounded bg-brand-indigo/20 px-2 py-1 text-brand-lavender font-mono">Webhook</span>
              <span className="text-slate-muted">&rarr;</span>
              <span className="rounded bg-brand-indigo/20 px-2 py-1 text-brand-lavender font-mono">Algomatter</span>
              <span className="text-slate-muted">&rarr;</span>
              <span className="rounded bg-green-500/20 px-2 py-1 text-green-400 font-mono">Exchange</span>
            </div>
            <div className="rounded bg-[#0a0a1a] p-3 font-mono text-slate-muted">
              <p>&#123; &quot;ticker&quot;: &quot;BTC/USDT&quot;,</p>
              <p>&nbsp;&nbsp;&quot;action&quot;: &quot;buy&quot;,</p>
              <p>&nbsp;&nbsp;&quot;qty&quot;: 0.1 &#125;</p>
            </div>
          </div>
        }
      />

      <FeatureSection
        label="Backtesting"
        title="Validate before you risk real money"
        description="Run strategies against historical market data with realistic slippage and commission modeling. See equity curves, drawdown charts, Sharpe ratio, max drawdown, win rate, and a complete trade log."
        visual={
          <div className="space-y-3 text-xs">
            <div className="flex justify-between">
              <div><span className="text-slate-muted">Total Return</span><p className="text-green-400 text-xl font-bold">+142.8%</p></div>
              <div><span className="text-slate-muted">Sharpe Ratio</span><p className="text-brand-lavender text-xl font-bold">2.41</p></div>
              <div><span className="text-slate-muted">Max Drawdown</span><p className="text-amber-400 text-xl font-bold">-12.3%</p></div>
            </div>
            <div className="h-20 rounded bg-[#0a0a1a] flex items-end px-2 pb-2 gap-1">
              {[30, 45, 35, 60, 50, 75, 65, 80, 70, 90, 85, 95].map((h, i) => (
                <div key={i} className="flex-1 rounded-t bg-brand-indigo/60" style={{ height: `${h}%` }} />
              ))}
            </div>
          </div>
        }
      />

      <FeatureSection
        label="Paper Trading"
        title="Test with virtual capital"
        description="Paper trading uses the exact same execution logic as live trading — same order routing, same fill simulation, same position tracking. Build confidence without risking a single satoshi."
        reversed
        visual={
          <div className="space-y-2 text-xs">
            <div className="flex justify-between items-center">
              <span className="text-slate-muted">Mode</span>
              <span className="rounded bg-amber-500/20 px-2 py-0.5 text-amber-400 font-semibold">PAPER</span>
            </div>
            <div className="flex justify-between"><span className="text-slate-muted">Balance</span><span className="text-slate-heading font-mono">₹10,000.00</span></div>
            <div className="flex justify-between"><span className="text-slate-muted">Open P&L</span><span className="text-green-400 font-mono">+₹342.50</span></div>
            <div className="flex justify-between"><span className="text-slate-muted">Trades Today</span><span className="text-slate-heading font-mono">7</span></div>
          </div>
        }
      />

      <FeatureSection
        label="Live Trading"
        title="Deploy to real markets"
        description="When your strategy is validated, promote from paper to live with one click. Monitor open positions, P&L, and trade history in real-time. Emergency kill switch stops all activity instantly."
        visual={
          <div className="space-y-2 text-xs">
            <div className="flex justify-between items-center">
              <span className="text-slate-muted">BTC/USDT Long</span>
              <span className="rounded bg-green-500/20 px-2 py-0.5 text-green-400 font-semibold">● LIVE</span>
            </div>
            <div className="flex justify-between"><span className="text-slate-muted">Entry</span><span className="text-slate-heading font-mono">₹67,420.00</span></div>
            <div className="flex justify-between"><span className="text-slate-muted">Current</span><span className="text-slate-heading font-mono">₹68,660.00</span></div>
            <div className="flex justify-between"><span className="text-slate-muted">Unrealized P&L</span><span className="text-green-400 font-mono">+₹1,240.00</span></div>
            <div className="mt-3 pt-3 border-t border-brand-indigo/10">
              <span className="rounded bg-red-500/20 px-3 py-1.5 text-red-400 font-semibold text-xs">⚠ Kill Switch</span>
            </div>
          </div>
        }
      />

      <FeatureSection
        label="Analytics"
        title="Track performance across strategies"
        description="Compare backtest predictions vs. live results. View equity curves, drawdown periods, and per-strategy breakdowns. Understand what's working and what needs tuning."
        reversed
        visual={
          <div className="space-y-3 text-xs">
            <div className="flex gap-4">
              <div className="flex-1 rounded bg-[#0a0a1a] p-2 text-center">
                <p className="text-slate-muted">Backtest</p>
                <p className="text-brand-lavender text-lg font-bold">+142%</p>
              </div>
              <div className="flex-1 rounded bg-[#0a0a1a] p-2 text-center">
                <p className="text-slate-muted">Live</p>
                <p className="text-green-400 text-lg font-bold">+89%</p>
              </div>
            </div>
            <div className="h-16 rounded bg-[#0a0a1a] flex items-end px-2 pb-2 gap-1">
              {[40, 55, 45, 70, 60, 80, 75, 85, 80, 90].map((h, i) => (
                <div key={i} className="flex-1 rounded-t" style={{ height: `${h}%`, background: i < 5 ? 'rgba(99,102,241,0.5)' : 'rgba(34,211,238,0.5)' }} />
              ))}
            </div>
          </div>
        }
      />

      {/* Bottom CTA */}
      <section className="px-6 py-20 text-center">
        <h2 className="text-2xl font-bold text-slate-heading">
          Ready to try it?
        </h2>
        <p className="mt-2 text-slate-muted">
          Start your 14-day free trial. No credit card required.
        </p>
        <div className="mt-6">
          <GradientButton href={`${siteConfig.appUrl}/signup`} size="lg">
            Start Free Trial &rarr;
          </GradientButton>
        </div>
      </section>
    </main>
  );
}
