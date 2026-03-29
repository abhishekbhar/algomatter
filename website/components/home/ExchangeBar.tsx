"use client";

import { ScrollReveal } from "@/components/shared/ScrollReveal";

function BinanceLogo() {
  return (
    <svg width="80" height="28" viewBox="0 0 80 28" fill="currentColor">
      <path d="M14 7.14L17.86 11l-1.43 1.43L14 10l-2.43 2.43L10.14 11 14 7.14zm7.86 6.86L25.72 18l-3.86 3.86-1.43-1.43L23.86 17l-3.43-3.43 1.43-1.43L25.29 15.57l-3.43 3.43zm-15.72 0L2.28 18l3.86 3.86 1.43-1.43L4.14 17l3.43-3.43-1.43-1.43L2.71 15.57l3.43 3.43zM14 16.86L10.14 21l1.43 1.43L14 20l2.43 2.43L17.86 21 14 16.86zM14 12.57L11.43 15.14l-1.43-1.43L14 9.71l4 4-1.43 1.43L14 12.57z"/>
      <text x="32" y="19" fontSize="11" fontWeight="700" fontFamily="system-ui">Binance</text>
    </svg>
  );
}

function Exchange1Logo() {
  return (
    <svg width="88" height="28" viewBox="0 0 88 28" fill="currentColor">
      <rect x="2" y="6" width="16" height="16" rx="3" stroke="currentColor" strokeWidth="1.5" fill="none"/>
      <path d="M6 14h8M10 10v8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <text x="24" y="19" fontSize="11" fontWeight="700" fontFamily="system-ui">Exchange1</text>
    </svg>
  );
}

function BybitLogo() {
  return (
    <svg width="62" height="28" viewBox="0 0 62 28" fill="currentColor">
      <path d="M4 8h6c2.2 0 4 1.8 4 4s-1.8 4-4 4H7v4H4V8zm3 2.5v3h2.5c.8 0 1.5-.7 1.5-1.5s-.7-1.5-1.5-1.5H7z"/>
      <text x="18" y="19" fontSize="11" fontWeight="700" fontFamily="system-ui">Bybit</text>
    </svg>
  );
}

function OKXLogo() {
  return (
    <svg width="52" height="28" viewBox="0 0 52 28" fill="currentColor">
      <rect x="4" y="8" width="5" height="5" rx="0.5"/>
      <rect x="11" y="8" width="5" height="5" rx="0.5"/>
      <rect x="4" y="15" width="5" height="5" rx="0.5"/>
      <rect x="11" y="15" width="5" height="5" rx="0.5"/>
      <text x="22" y="19" fontSize="11" fontWeight="700" fontFamily="system-ui">OKX</text>
    </svg>
  );
}

const exchanges = [
  { name: "Binance", Logo: BinanceLogo },
  { name: "Exchange1", Logo: Exchange1Logo },
  { name: "Bybit", Logo: BybitLogo },
  { name: "OKX", Logo: OKXLogo },
];

export function ExchangeBar() {
  return (
    <section className="border-y border-brand-indigo/10 py-8">
      <ScrollReveal>
        <p className="text-center text-xs uppercase tracking-widest text-slate-faint mb-5">
          Supported Exchanges
        </p>
        <div className="flex items-center justify-center gap-10 flex-wrap text-slate-body/40">
          {exchanges.map(({ name, Logo }) => (
            <Logo key={name} />
          ))}
          <span className="text-sm font-semibold text-slate-body opacity-40">+ more</span>
        </div>
      </ScrollReveal>
    </section>
  );
}
