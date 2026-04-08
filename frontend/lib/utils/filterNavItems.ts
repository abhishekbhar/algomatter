/**
 * Pure helper that filters sidebar nav items based on feature flags.
 * Paper Trading, Backtest Deployments, and Backtesting tabs are hidden
 * when their corresponding flag is `false`.
 *
 * The helper is kept as a pure function (no React, no hooks) so it can
 * be unit-tested independently of the Sidebar component.
 */

export interface NavItemDescriptor {
  label: string;
  href: string;
}

export interface NavFeatureFlags {
  paperTrading: boolean;
  backtesting: boolean;
}

const PAPER_TRADING_HREFS = new Set(["/paper-trading"]);
const BACKTESTING_HREFS = new Set(["/backtest-deployments", "/backtesting"]);

// Generic over any concrete nav-item type that has at least `label` and
// `href` fields. The Sidebar passes items that also include an `icon`,
// which this helper ignores but preserves in the returned array.
export function filterNavItems<T extends NavItemDescriptor>(
  items: readonly T[],
  flags: NavFeatureFlags,
): T[] {
  return items.filter((item) => {
    if (!flags.paperTrading && PAPER_TRADING_HREFS.has(item.href)) return false;
    if (!flags.backtesting && BACKTESTING_HREFS.has(item.href)) return false;
    return true;
  });
}
