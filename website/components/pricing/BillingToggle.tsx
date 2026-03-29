"use client";

interface BillingToggleProps {
  annual: boolean;
  onChange: (annual: boolean) => void;
}

export function BillingToggle({ annual, onChange }: BillingToggleProps) {
  return (
    <div className="flex items-center justify-center gap-3">
      <span className={`text-sm ${!annual ? "text-slate-heading" : "text-slate-muted"}`}>
        Monthly
      </span>
      <button
        onClick={() => onChange(!annual)}
        className="relative h-7 w-12 rounded-full bg-brand-indigo/20 transition-colors"
        role="switch"
        aria-checked={annual}
        aria-label="Toggle billing period"
      >
        <span
          className={`absolute top-0.5 h-6 w-6 rounded-full bg-brand-indigo transition-transform ${
            annual ? "translate-x-5" : "translate-x-0.5"
          }`}
        />
      </button>
      <span className={`text-sm ${annual ? "text-slate-heading" : "text-slate-muted"}`}>
        Annual
      </span>
      {annual && (
        <span className="rounded-full bg-green-500/15 border border-green-500/30 px-2 py-0.5 text-xs text-green-400">
          Save 20%
        </span>
      )}
    </div>
  );
}
