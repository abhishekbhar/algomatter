# Algomatter Marketing Website Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone marketing website for Algomatter — a crypto algo trading SaaS — with homepage, features, pricing, docs, changelog, and about pages.

**Architecture:** Standalone Next.js 15 project in the `website/` directory (sibling to existing `frontend/` and `backend/`). Uses Tailwind CSS for styling, Framer Motion for animations, and next-mdx-remote for docs/changelog content. Links to the existing app for login/signup.

**Tech Stack:** Next.js 15 (App Router), TypeScript, Tailwind CSS v3, Framer Motion, next-mdx-remote, flexsearch

---

## File Structure

```
website/
├── app/
│   ├── layout.tsx              # Root layout: fonts, metadata, theme
│   ├── page.tsx                # Homepage (composes home/ components)
│   ├── features/page.tsx       # Features page
│   ├── pricing/page.tsx        # Pricing page
│   ├── about/page.tsx          # About page
│   ├── changelog/page.tsx      # Changelog (renders MDX entries)
│   └── docs/
│       ├── layout.tsx          # Docs layout with sidebar
│       └── [[...slug]]/page.tsx # Dynamic MDX doc pages (index + nested)
├── components/
│   ├── layout/
│   │   ├── Navbar.tsx          # Sticky glassmorphism nav
│   │   ├── Footer.tsx          # 4-column footer
│   │   └── MobileMenu.tsx      # Hamburger slide-out menu
│   ├── home/
│   │   ├── Hero.tsx            # Hero with animated equity curve
│   │   ├── ExchangeBar.tsx     # Supported exchanges logos
│   │   ├── HowItWorks.tsx      # 3-step cards
│   │   ├── Features.tsx        # 2x2 feature grid
│   │   ├── PlatformStats.tsx   # Animated counters
│   │   ├── Testimonials.tsx    # Rotating carousel
│   │   └── FinalCTA.tsx        # Bottom call-to-action
│   ├── features/
│   │   └── FeatureSection.tsx  # Alternating text+visual block
│   ├── pricing/
│   │   ├── PricingContent.tsx  # Client wrapper with billing state
│   │   ├── PricingCards.tsx    # 3-tier card comparison
│   │   ├── BillingToggle.tsx   # Monthly/Annual switch
│   │   └── FAQ.tsx             # Accordion component
│   ├── docs/
│   │   ├── DocsSidebar.tsx     # Navigation sidebar
│   │   ├── SearchDialog.tsx    # Cmd-K search modal
│   │   └── MDXComponents.tsx   # Custom MDX renderers (code block, callout)
│   └── shared/
│       ├── AnimatedCounter.tsx # Count-up number animation
│       ├── EquityCurve.tsx     # SVG path draw animation
│       ├── TypeWriter.tsx      # Code typing animation
│       ├── ScrollReveal.tsx    # Intersection observer + Framer Motion wrapper
│       ├── GradientButton.tsx  # Primary CTA button
│       └── Logo.tsx            # Monogram A SVG + wordmark
├── content/
│   ├── docs/
│   │   ├── getting-started/
│   │   │   ├── quick-start.mdx
│   │   │   ├── connecting-exchange.mdx
│   │   │   └── first-strategy.mdx
│   │   ├── strategies/
│   │   │   ├── python-sdk.mdx
│   │   │   ├── templates.mdx
│   │   │   ├── webhooks-tradingview.mdx
│   │   │   └── mapping-templates.mdx
│   │   ├── backtesting/
│   │   │   ├── running-backtest.mdx
│   │   │   ├── understanding-results.mdx
│   │   │   └── slippage-commission.mdx
│   │   └── trading/
│   │       ├── paper-trading.mdx
│   │       ├── going-live.mdx
│   │       └── kill-switch.mdx
│   └── changelog/
│       └── 2026-03-v1.0.0.mdx
├── lib/
│   ├── config.ts               # App URL, site metadata constants
│   ├── mdx.ts                  # MDX file reading/parsing utilities
│   └── docs-manifest.ts        # Sidebar structure + doc metadata
├── public/
│   └── logo.svg                # Monogram A logo
├── tailwind.config.ts
├── next.config.ts
├── package.json
└── tsconfig.json
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `website/package.json`
- Create: `website/tsconfig.json`
- Create: `website/next.config.ts`
- Create: `website/tailwind.config.ts`
- Create: `website/app/globals.css`
- Create: `website/app/layout.tsx`
- Create: `website/app/page.tsx`
- Create: `website/lib/config.ts`
- Create: `website/public/logo.svg`

- [ ] **Step 1: Create the website directory**

```bash
mkdir -p website
```

- [ ] **Step 2: Initialize the Next.js project with dependencies**

```bash
cd website
nix develop .. --command bash -c "
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir=false --import-alias='@/*' --use-npm --yes
"
```

Note: `create-next-app@latest` may scaffold Tailwind v4 (CSS-based config). After scaffolding, downgrade to Tailwind v3:

```bash
cd website
nix develop .. --command bash -c "
npm install tailwindcss@3 postcss autoprefixer
npx tailwindcss init -p --ts
"
```

This creates a `tailwind.config.ts` and `postcss.config.js` with v3 patterns. Remove any `@import 'tailwindcss'` or `@theme` blocks that v4 scaffolding may have generated in `globals.css`.

- [ ] **Step 3: Install additional dependencies**

```bash
cd website
nix develop .. --command bash -c "
npm install framer-motion next-mdx-remote gray-matter flexsearch
npm install -D @types/flexsearch
"
```

- [ ] **Step 4: Configure Tailwind with brand colors**

Update `website/tailwind.config.ts`:

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          bg: "#0f0f23",
          "bg-light": "#1b1b3a",
          indigo: "#6366f1",
          purple: "#a855f7",
          lavender: "#a78bfa",
          cyan: "#22d3ee",
        },
        slate: {
          heading: "#f1f5f9",
          body: "#94a3b8",
          muted: "#64748b",
          faint: "#475569",
          line: "#334155",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 5: Create globals.css with base styles**

Write `website/app/globals.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  body {
    @apply bg-brand-bg text-slate-body antialiased;
  }
}
```

- [ ] **Step 6: Create lib/config.ts**

Write `website/lib/config.ts`:

```typescript
export const siteConfig = {
  name: "Algomatter",
  tagline: "Crypto algo trading, simplified.",
  description:
    "Build strategies in Python, backtest against real market data, and deploy to live crypto markets — all from one platform.",
  appUrl: process.env.NEXT_PUBLIC_APP_URL || "https://app.algomatter.com",
  url: process.env.NEXT_PUBLIC_SITE_URL || "https://algomatter.com",
  social: {
    twitter: "https://x.com/algomatter",
    discord: "https://discord.gg/algomatter",
  },
};
```

- [ ] **Step 7: Create the Logo SVG**

Write `website/public/logo.svg` — the Monogram A icon:

```svg
<svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="logoGrad" x1="0" y1="0" x2="40" y2="40">
      <stop offset="0%" stop-color="#a855f7"/>
      <stop offset="100%" stop-color="#6366f1"/>
    </linearGradient>
  </defs>
  <rect x="2" y="2" width="36" height="36" rx="8" fill="url(#logoGrad)" opacity="0.1" stroke="url(#logoGrad)" stroke-width="1.5"/>
  <path d="M12,30 L20,8 L28,30" stroke="url(#logoGrad)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  <line x1="15" y1="22" x2="25" y2="22" stroke="url(#logoGrad)" stroke-width="2" stroke-linecap="round"/>
  <circle cx="20" cy="8" r="2" fill="#a855f7"/>
  <circle cx="15" cy="22" r="1.5" fill="#6366f1"/>
  <circle cx="25" cy="22" r="1.5" fill="#6366f1"/>
</svg>
```

- [ ] **Step 8: Create root layout with fonts and metadata**

Write `website/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { siteConfig } from "@/lib/config";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: {
    default: `${siteConfig.name} — ${siteConfig.tagline}`,
    template: `%s | ${siteConfig.name}`,
  },
  description: siteConfig.description,
  openGraph: {
    title: siteConfig.name,
    description: siteConfig.description,
    url: siteConfig.url,
    siteName: siteConfig.name,
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrains.variable}`}>
      <body className="font-sans">{children}</body>
    </html>
  );
}
```

- [ ] **Step 9: Create placeholder homepage**

Write `website/app/page.tsx`:

```tsx
export default function HomePage() {
  return (
    <main className="flex min-h-screen items-center justify-content-center">
      <div className="text-center mx-auto">
        <h1 className="text-4xl font-bold text-slate-heading">
          Algomatter
        </h1>
        <p className="mt-2 text-slate-body">Coming soon...</p>
      </div>
    </main>
  );
}
```

- [ ] **Step 10: Verify the dev server starts**

```bash
cd website
nix develop .. --command bash -c "npm run build"
```

Expected: Build completes without errors.

- [ ] **Step 11: Commit**

```bash
git add website/
git commit -m "feat: scaffold Next.js 15 + Tailwind project for marketing website"
```

---

### Task 2: Shared Components (Logo, GradientButton, ScrollReveal)

**Files:**
- Create: `website/components/shared/Logo.tsx`
- Create: `website/components/shared/GradientButton.tsx`
- Create: `website/components/shared/ScrollReveal.tsx`
- Create: `website/components/shared/AnimatedCounter.tsx`
- Create: `website/components/shared/EquityCurve.tsx`
- Create: `website/components/shared/TypeWriter.tsx`

- [ ] **Step 1: Create Logo component**

Write `website/components/shared/Logo.tsx`:

```tsx
import Image from "next/image";
import Link from "next/link";

export function Logo({ size = 32 }: { size?: number }) {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <Image src="/logo.svg" alt="Algomatter" width={size} height={size} />
      <span className="text-lg font-extrabold tracking-tight bg-gradient-to-br from-brand-lavender to-brand-indigo bg-clip-text text-transparent">
        algomatter
      </span>
    </Link>
  );
}
```

- [ ] **Step 2: Create GradientButton component**

Write `website/components/shared/GradientButton.tsx`:

```tsx
import Link from "next/link";

interface GradientButtonProps {
  href: string;
  children: React.ReactNode;
  variant?: "primary" | "ghost";
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function GradientButton({
  href,
  children,
  variant = "primary",
  size = "md",
  className = "",
}: GradientButtonProps) {
  const sizes = {
    sm: "px-4 py-2 text-sm",
    md: "px-6 py-2.5 text-sm",
    lg: "px-8 py-3 text-base",
  };

  const variants = {
    primary:
      "bg-gradient-to-r from-brand-indigo to-brand-purple text-white hover:opacity-90 transition-opacity",
    ghost:
      "border border-slate-line text-slate-body hover:border-slate-muted hover:text-slate-heading transition-colors",
  };

  return (
    <Link
      href={href}
      className={`inline-block rounded-lg font-semibold ${sizes[size]} ${variants[variant]} ${className}`}
    >
      {children}
    </Link>
  );
}
```

- [ ] **Step 3: Create ScrollReveal wrapper**

Write `website/components/shared/ScrollReveal.tsx`:

```tsx
"use client";

import { motion } from "framer-motion";
import { ReactNode } from "react";

interface ScrollRevealProps {
  children: ReactNode;
  delay?: number;
  className?: string;
}

export function ScrollReveal({
  children,
  delay = 0,
  className = "",
}: ScrollRevealProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.5, delay, ease: "easeOut" }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
```

- [ ] **Step 4: Create AnimatedCounter**

Write `website/components/shared/AnimatedCounter.tsx`:

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { useInView, motion } from "framer-motion";

interface AnimatedCounterProps {
  target: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
}

export function AnimatedCounter({
  target,
  prefix = "",
  suffix = "",
  duration = 2,
}: AnimatedCounterProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true });
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!isInView) return;
    let start = 0;
    const step = target / (duration * 60);
    const timer = setInterval(() => {
      start += step;
      if (start >= target) {
        setCount(target);
        clearInterval(timer);
      } else {
        setCount(Math.floor(start));
      }
    }, 1000 / 60);
    return () => clearInterval(timer);
  }, [isInView, target, duration]);

  return (
    <span ref={ref} className="tabular-nums">
      {prefix}
      {count.toLocaleString()}
      {suffix}
    </span>
  );
}
```

- [ ] **Step 5: Create EquityCurve SVG animation**

Write `website/components/shared/EquityCurve.tsx`:

```tsx
"use client";

import { motion, useInView } from "framer-motion";
import { useRef } from "react";

export function EquityCurve({ className = "" }: { className?: string }) {
  const ref = useRef<SVGSVGElement>(null);
  const isInView = useInView(ref, { once: true });

  const curvePath =
    "M0,120 Q50,110 100,100 T200,80 T300,60 T400,45 T500,30 T600,15";
  const areaPath = `${curvePath} L600,160 L0,160 Z`;

  return (
    <svg
      ref={ref}
      viewBox="0 0 600 160"
      className={className}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id="curveGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#6366f1" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
        </linearGradient>
      </defs>
      <motion.path
        d={areaPath}
        fill="url(#curveGrad)"
        initial={{ opacity: 0 }}
        animate={isInView ? { opacity: 1 } : {}}
        transition={{ duration: 1, delay: 0.5 }}
      />
      <motion.path
        d={curvePath}
        fill="none"
        stroke="#6366f1"
        strokeWidth="2"
        initial={{ pathLength: 0 }}
        animate={isInView ? { pathLength: 1 } : {}}
        transition={{ duration: 2, ease: "easeInOut" }}
      />
    </svg>
  );
}
```

- [ ] **Step 6: Create TypeWriter animation**

Write `website/components/shared/TypeWriter.tsx`:

```tsx
"use client";

import { useEffect, useState, useRef } from "react";
import { useInView } from "framer-motion";

interface TypeWriterProps {
  code: string;
  speed?: number;
  className?: string;
}

export function TypeWriter({ code, speed = 30, className = "" }: TypeWriterProps) {
  const ref = useRef<HTMLPreElement>(null);
  const isInView = useInView(ref, { once: true });
  const [displayed, setDisplayed] = useState("");

  useEffect(() => {
    if (!isInView) return;
    let i = 0;
    const timer = setInterval(() => {
      if (i < code.length) {
        setDisplayed(code.slice(0, i + 1));
        i++;
      } else {
        clearInterval(timer);
      }
    }, speed);
    return () => clearInterval(timer);
  }, [isInView, code, speed]);

  return (
    <pre
      ref={ref}
      className={`font-mono text-sm leading-relaxed ${className}`}
    >
      <code>{displayed}<span className="animate-pulse">|</span></code>
    </pre>
  );
}
```

- [ ] **Step 7: Verify build still passes**

```bash
cd website
nix develop .. --command bash -c "npm run build"
```

Expected: Build passes with no errors.

- [ ] **Step 8: Commit**

```bash
git add website/components/shared/
git commit -m "feat: add shared components — Logo, GradientButton, ScrollReveal, animations"
```

---

### Task 3: Navbar & Footer Layout

**Files:**
- Create: `website/components/layout/Navbar.tsx`
- Create: `website/components/layout/MobileMenu.tsx`
- Create: `website/components/layout/Footer.tsx`
- Modify: `website/app/layout.tsx`

- [ ] **Step 1: Create Navbar**

Write `website/components/layout/Navbar.tsx`:

```tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { Logo } from "@/components/shared/Logo";
import { GradientButton } from "@/components/shared/GradientButton";
import { MobileMenu } from "./MobileMenu";
import { siteConfig } from "@/lib/config";

const navLinks = [
  { href: "/features", label: "Features" },
  { href: "/pricing", label: "Pricing" },
  { href: "/docs", label: "Docs" },
  { href: "/changelog", label: "Changelog" },
  { href: "/about", label: "About" },
];

export function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-brand-indigo/10 bg-brand-bg/80 backdrop-blur-xl">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Logo />
        <div className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm text-slate-body hover:text-slate-heading transition-colors"
            >
              {link.label}
            </Link>
          ))}
        </div>
        <div className="hidden md:flex items-center gap-4">
          <Link
            href={`${siteConfig.appUrl}/login`}
            className="text-sm text-slate-body hover:text-slate-heading transition-colors"
          >
            Login
          </Link>
          <GradientButton href={`${siteConfig.appUrl}/signup`} size="sm">
            Start Free Trial
          </GradientButton>
        </div>
        <button
          className="md:hidden text-slate-body"
          onClick={() => setMobileOpen(true)}
          aria-label="Open menu"
        >
          <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      </nav>
      <MobileMenu
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        links={navLinks}
      />
    </header>
  );
}
```

- [ ] **Step 2: Create MobileMenu**

Write `website/components/layout/MobileMenu.tsx`:

```tsx
"use client";

import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { GradientButton } from "@/components/shared/GradientButton";
import { siteConfig } from "@/lib/config";

interface MobileMenuProps {
  open: boolean;
  onClose: () => void;
  links: { href: string; label: string }[];
}

export function MobileMenu({ open, onClose, links }: MobileMenuProps) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-50 bg-black/60"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            className="fixed right-0 top-0 z-50 h-full w-72 bg-brand-bg border-l border-brand-indigo/10 p-6"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
          >
            <button
              onClick={onClose}
              className="mb-8 text-slate-body hover:text-slate-heading"
              aria-label="Close menu"
            >
              <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
            <div className="flex flex-col gap-4">
              {links.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={onClose}
                  className="text-lg text-slate-body hover:text-slate-heading transition-colors"
                >
                  {link.label}
                </Link>
              ))}
              <hr className="border-slate-line my-2" />
              <Link
                href={`${siteConfig.appUrl}/login`}
                className="text-lg text-slate-body hover:text-slate-heading"
              >
                Login
              </Link>
              <GradientButton href={`${siteConfig.appUrl}/signup`} size="lg">
                Start Free Trial
              </GradientButton>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
```

- [ ] **Step 3: Create Footer**

Write `website/components/layout/Footer.tsx`:

```tsx
import Link from "next/link";
import { Logo } from "@/components/shared/Logo";
import { siteConfig } from "@/lib/config";

const footerSections = [
  {
    title: "Product",
    links: [
      { href: "/features", label: "Features" },
      { href: "/pricing", label: "Pricing" },
      { href: "/changelog", label: "Changelog" },
    ],
  },
  {
    title: "Resources",
    links: [
      { href: "/docs", label: "Docs" },
      { href: "/docs/getting-started/quick-start", label: "Getting Started" },
    ],
  },
  {
    title: "Company",
    links: [
      { href: "/about", label: "About" },
      { href: "/about#contact", label: "Contact" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="border-t border-brand-indigo/10">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          <div className="col-span-2 md:col-span-1">
            <Logo />
            <p className="mt-3 text-sm text-slate-muted leading-relaxed">
              {siteConfig.description}
            </p>
          </div>
          {footerSections.map((section) => (
            <div key={section.title}>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-body mb-3">
                {section.title}
              </h4>
              <ul className="space-y-2">
                {section.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-sm text-slate-muted hover:text-slate-body transition-colors"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-10 flex flex-col items-center justify-between gap-4 border-t border-brand-indigo/10 pt-6 sm:flex-row">
          <p className="text-xs text-slate-faint">
            &copy; {new Date().getFullYear()} Algomatter. All rights reserved.
          </p>
          <div className="flex gap-5">
            <a
              href={siteConfig.social.twitter}
              className="text-xs text-slate-faint hover:text-slate-body transition-colors"
              target="_blank"
              rel="noopener noreferrer"
            >
              Twitter/X
            </a>
            <a
              href={siteConfig.social.discord}
              className="text-xs text-slate-faint hover:text-slate-body transition-colors"
              target="_blank"
              rel="noopener noreferrer"
            >
              Discord
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
```

- [ ] **Step 4: Update root layout to include Navbar and Footer**

Modify `website/app/layout.tsx` — wrap `{children}` with Navbar and Footer:

```tsx
import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { siteConfig } from "@/lib/config";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: {
    default: `${siteConfig.name} — ${siteConfig.tagline}`,
    template: `%s | ${siteConfig.name}`,
  },
  description: siteConfig.description,
  openGraph: {
    title: siteConfig.name,
    description: siteConfig.description,
    url: siteConfig.url,
    siteName: siteConfig.name,
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrains.variable}`}>
      <body className="font-sans">
        <Navbar />
        {children}
        <Footer />
      </body>
    </html>
  );
}
```

- [ ] **Step 5: Verify build**

```bash
cd website
nix develop .. --command bash -c "npm run build"
```

Expected: Build passes.

- [ ] **Step 6: Commit**

```bash
git add website/components/layout/ website/app/layout.tsx
git commit -m "feat: add Navbar with mobile menu and Footer"
```

---

### Task 4: Homepage — Hero Section

**Files:**
- Create: `website/components/home/Hero.tsx`
- Modify: `website/app/page.tsx`

- [ ] **Step 1: Create Hero component**

Write `website/components/home/Hero.tsx`:

```tsx
"use client";

import { GradientButton } from "@/components/shared/GradientButton";
import { EquityCurve } from "@/components/shared/EquityCurve";
import { siteConfig } from "@/lib/config";

export function Hero() {
  return (
    <section className="relative overflow-hidden px-6 pb-16 pt-20 text-center md:pt-28 md:pb-24">
      {/* Background glows */}
      <div className="pointer-events-none absolute left-1/2 top-0 -translate-x-1/2 w-[500px] h-[500px] rounded-full bg-brand-indigo/15 blur-3xl" />
      <div className="pointer-events-none absolute right-[10%] top-10 w-[250px] h-[250px] rounded-full bg-brand-purple/10 blur-3xl" />

      <div className="relative z-10 mx-auto max-w-3xl">
        {/* Badge */}
        <span className="inline-block rounded-full border border-brand-indigo/30 bg-brand-indigo/15 px-4 py-1.5 text-xs text-brand-lavender mb-6">
          Now in public beta — try free for 14 days
        </span>

        <h1 className="text-4xl font-extrabold leading-tight tracking-tight text-slate-heading md:text-6xl">
          Crypto algo trading,{" "}
          <span className="bg-gradient-to-r from-brand-indigo via-brand-purple to-brand-cyan bg-clip-text text-transparent">
            simplified.
          </span>
        </h1>

        <p className="mx-auto mt-5 max-w-xl text-lg leading-relaxed text-slate-body">
          {siteConfig.description}
        </p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
          <GradientButton href={`${siteConfig.appUrl}/signup`} size="lg">
            Start Free Trial &rarr;
          </GradientButton>
          <GradientButton href="#how-it-works" variant="ghost" size="lg">
            Watch Demo
          </GradientButton>
        </div>
      </div>

      {/* Hero visual — browser frame with equity curve */}
      <div className="relative mx-auto mt-14 max-w-2xl rounded-xl border border-brand-indigo/20 bg-brand-bg/60 overflow-hidden">
        {/* Browser dots */}
        <div className="flex gap-1.5 px-4 py-3 border-b border-brand-indigo/10">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500/60" />
          <span className="w-2.5 h-2.5 rounded-full bg-yellow-500/60" />
          <span className="w-2.5 h-2.5 rounded-full bg-green-500/60" />
        </div>
        <div className="relative p-4">
          {/* Stats overlay */}
          <div className="absolute top-6 left-6 z-10 text-left">
            <p className="text-xs text-slate-muted">BTC/USDT &middot; 4H</p>
            <p className="mt-1 text-2xl font-bold text-green-400">+142.8%</p>
            <p className="text-xs text-slate-muted">Backtest: 6 months</p>
          </div>
          <div className="absolute top-6 right-6 z-10 text-right text-xs space-y-1">
            <p className="text-slate-muted">Sharpe: <span className="text-brand-lavender">2.41</span></p>
            <p className="text-slate-muted">Max DD: <span className="text-amber-400">-12.3%</span></p>
            <p className="text-slate-muted">Win Rate: <span className="text-green-400">67%</span></p>
          </div>
          <EquityCurve className="w-full h-48" />
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Update homepage to use Hero**

Replace `website/app/page.tsx`:

```tsx
import { Hero } from "@/components/home/Hero";

export default function HomePage() {
  return (
    <main>
      <Hero />
    </main>
  );
}
```

- [ ] **Step 3: Verify build**

```bash
cd website
nix develop .. --command bash -c "npm run build"
```

- [ ] **Step 4: Commit**

```bash
git add website/components/home/Hero.tsx website/app/page.tsx
git commit -m "feat: add homepage Hero section with animated equity curve"
```

---

### Task 5: Homepage — ExchangeBar, HowItWorks, Features Sections

**Files:**
- Create: `website/components/home/ExchangeBar.tsx`
- Create: `website/components/home/HowItWorks.tsx`
- Create: `website/components/home/Features.tsx`
- Modify: `website/app/page.tsx`

- [ ] **Step 1: Create ExchangeBar**

Write `website/components/home/ExchangeBar.tsx`:

```tsx
"use client";

import { ScrollReveal } from "@/components/shared/ScrollReveal";

const exchanges = ["Binance", "Exchange1", "Bybit", "OKX"];

export function ExchangeBar() {
  return (
    <section className="border-y border-brand-indigo/10 py-8">
      <ScrollReveal>
        <p className="text-center text-xs uppercase tracking-widest text-slate-faint mb-5">
          Supported Exchanges
        </p>
        <div className="flex items-center justify-center gap-10 flex-wrap opacity-40">
          {exchanges.map((name) => (
            <span
              key={name}
              className="text-sm font-semibold text-slate-body"
            >
              {name}
            </span>
          ))}
          <span className="text-sm font-semibold text-slate-body">+ more</span>
        </div>
      </ScrollReveal>
    </section>
  );
}
```

- [ ] **Step 2: Create HowItWorks**

Write `website/components/home/HowItWorks.tsx`:

```tsx
"use client";

import { ScrollReveal } from "@/components/shared/ScrollReveal";
import { TypeWriter } from "@/components/shared/TypeWriter";

const steps = [
  {
    number: 1,
    title: "Write your strategy",
    description:
      "Code in Python using our SDK, or connect signals from TradingView via webhooks. No framework lock-in.",
    visual: "code",
  },
  {
    number: 2,
    title: "Backtest & validate",
    description:
      "Run against historical data with realistic slippage and fees. See equity curves, drawdowns, Sharpe ratio, and every trade.",
    visual: "metrics",
  },
  {
    number: 3,
    title: "Deploy & monitor",
    description:
      "Paper trade first, then go live. Monitor positions, P&L, and trades in real-time. Kill switch if anything goes wrong.",
    visual: "live",
  },
];

const codeSnippet = `def on_candle(self, candle):
    if candle.rsi < 30:
        self.buy("BTC/USDT")`;

function StepVisual({ type }: { type: string }) {
  if (type === "code") {
    return (
      <div className="mt-3 rounded-md bg-[#0a0a1a] p-3">
        <TypeWriter code={codeSnippet} speed={40} className="text-brand-lavender text-xs" />
      </div>
    );
  }
  if (type === "metrics") {
    return (
      <div className="mt-3 rounded-md bg-[#0a0a1a] p-3 flex justify-between text-xs">
        <div>
          <span className="text-slate-muted">Return</span>
          <p className="text-green-400 text-lg font-bold">+142%</p>
        </div>
        <div>
          <span className="text-slate-muted">Sharpe</span>
          <p className="text-brand-lavender text-lg font-bold">2.41</p>
        </div>
        <div>
          <span className="text-slate-muted">Max DD</span>
          <p className="text-amber-400 text-lg font-bold">-12%</p>
        </div>
      </div>
    );
  }
  return (
    <div className="mt-3 rounded-md bg-[#0a0a1a] p-3 text-xs">
      <div className="flex justify-between items-center">
        <span className="text-slate-muted">BTC/USDT Long</span>
        <span className="text-green-400 font-semibold">● LIVE</span>
      </div>
      <div className="flex justify-between mt-2">
        <span className="text-slate-muted">Entry: $67,420</span>
        <span className="text-green-400">P&L: +$1,240</span>
      </div>
    </div>
  );
}

export function HowItWorks() {
  return (
    <section id="how-it-works" className="px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <ScrollReveal className="text-center mb-12">
          <p className="text-xs uppercase tracking-widest text-brand-indigo mb-2">
            How it works
          </p>
          <h2 className="text-3xl font-bold text-slate-heading">
            From idea to live trading in minutes
          </h2>
          <p className="mt-2 text-slate-muted">
            Three steps to automate your crypto strategy
          </p>
        </ScrollReveal>
        <div className="grid gap-6 md:grid-cols-3">
          {steps.map((step, i) => (
            <ScrollReveal key={step.number} delay={i * 0.15}>
              <div className="rounded-xl border border-brand-indigo/10 bg-brand-indigo/5 p-6">
                <div className="mb-4 flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-brand-indigo to-brand-purple text-sm font-bold text-white">
                  {step.number}
                </div>
                <h3 className="text-base font-semibold text-slate-heading mb-2">
                  {step.title}
                </h3>
                <p className="text-sm text-slate-muted leading-relaxed">
                  {step.description}
                </p>
                <StepVisual type={step.visual} />
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Create Features grid**

Write `website/components/home/Features.tsx`:

```tsx
"use client";

import { ScrollReveal } from "@/components/shared/ScrollReveal";

const features = [
  {
    icon: "📊",
    title: "Backtesting Engine",
    description:
      "Powered by Nautilus Trader. Realistic fills, configurable slippage & commission. Full trade logs and equity curves.",
  },
  {
    icon: "🔗",
    title: "Webhook Signals",
    description:
      "Connect TradingView or any alert source. Map JSON fields with zero code. Rules filter what gets executed.",
  },
  {
    icon: "🐍",
    title: "Python Strategies",
    description:
      "Write strategies in Python with our SDK. Built-in editor, version control, and templates to get started fast.",
  },
  {
    icon: "⚡",
    title: "Paper → Live",
    description:
      "Test with virtual capital first. When you're confident, flip to live with one click. Kill switch for safety.",
  },
];

export function Features() {
  return (
    <section className="px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <ScrollReveal className="text-center mb-12">
          <p className="text-xs uppercase tracking-widest text-brand-indigo mb-2">
            Features
          </p>
          <h2 className="text-3xl font-bold text-slate-heading">
            Everything you need to trade algorithmically
          </h2>
        </ScrollReveal>
        <div className="grid gap-5 sm:grid-cols-2">
          {features.map((f, i) => (
            <ScrollReveal key={f.title} delay={i * 0.1}>
              <div className="rounded-xl border border-brand-indigo/10 bg-brand-indigo/5 p-6">
                <div className="text-2xl mb-3">{f.icon}</div>
                <h3 className="text-base font-semibold text-slate-heading mb-1.5">
                  {f.title}
                </h3>
                <p className="text-sm text-slate-muted leading-relaxed">
                  {f.description}
                </p>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Add sections to homepage**

Update `website/app/page.tsx`:

```tsx
import { Hero } from "@/components/home/Hero";
import { ExchangeBar } from "@/components/home/ExchangeBar";
import { HowItWorks } from "@/components/home/HowItWorks";
import { Features } from "@/components/home/Features";

export default function HomePage() {
  return (
    <main>
      <Hero />
      <ExchangeBar />
      <HowItWorks />
      <div className="mx-6 h-px bg-gradient-to-r from-transparent via-brand-indigo/20 to-transparent" />
      <Features />
    </main>
  );
}
```

- [ ] **Step 5: Verify build**

```bash
cd website
nix develop .. --command bash -c "npm run build"
```

- [ ] **Step 6: Commit**

```bash
git add website/components/home/ExchangeBar.tsx website/components/home/HowItWorks.tsx website/components/home/Features.tsx website/app/page.tsx
git commit -m "feat: add ExchangeBar, HowItWorks, and Features homepage sections"
```

---

### Task 6: Homepage — PlatformStats, Testimonials, FinalCTA

**Files:**
- Create: `website/components/home/PlatformStats.tsx`
- Create: `website/components/home/Testimonials.tsx`
- Create: `website/components/home/FinalCTA.tsx`
- Modify: `website/app/page.tsx`

- [ ] **Step 1: Create PlatformStats with animated counters**

Write `website/components/home/PlatformStats.tsx`:

```tsx
"use client";

import { ScrollReveal } from "@/components/shared/ScrollReveal";
import { AnimatedCounter } from "@/components/shared/AnimatedCounter";

const stats = [
  { target: 1200, suffix: "+", label: "Backtests Run" },
  { target: 50, suffix: "+", label: "Active Strategies" },
  { target: 2.4, prefix: "$", suffix: "M", label: "Volume Traded" },
  { target: 99.9, suffix: "%", label: "Uptime" },
];

export function PlatformStats() {
  return (
    <section className="px-6 py-16">
      <ScrollReveal>
        <p className="text-center text-xs uppercase tracking-widest text-brand-indigo mb-8">
          Platform Stats
        </p>
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-center gap-12 md:gap-16">
          {stats.map((s) => (
            <div key={s.label} className="text-center">
              <div className="text-3xl font-extrabold bg-gradient-to-br from-brand-indigo to-brand-purple bg-clip-text text-transparent">
                <AnimatedCounter
                  target={s.target}
                  prefix={s.prefix}
                  suffix={s.suffix}
                />
              </div>
              <p className="mt-1 text-xs text-slate-muted">{s.label}</p>
            </div>
          ))}
        </div>
      </ScrollReveal>
    </section>
  );
}
```

- [ ] **Step 2: Create Testimonials carousel**

Write `website/components/home/Testimonials.tsx`:

```tsx
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
```

- [ ] **Step 3: Create FinalCTA**

Write `website/components/home/FinalCTA.tsx`:

```tsx
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
```

- [ ] **Step 4: Complete the homepage**

Update `website/app/page.tsx`:

```tsx
import { Hero } from "@/components/home/Hero";
import { ExchangeBar } from "@/components/home/ExchangeBar";
import { HowItWorks } from "@/components/home/HowItWorks";
import { Features } from "@/components/home/Features";
import { PlatformStats } from "@/components/home/PlatformStats";
import { Testimonials } from "@/components/home/Testimonials";
import { FinalCTA } from "@/components/home/FinalCTA";

function Divider() {
  return (
    <div className="mx-6 h-px bg-gradient-to-r from-transparent via-brand-indigo/20 to-transparent" />
  );
}

export default function HomePage() {
  return (
    <main>
      <Hero />
      <ExchangeBar />
      <HowItWorks />
      <Divider />
      <Features />
      <Divider />
      <PlatformStats />
      <Divider />
      <Testimonials />
      <Divider />
      <FinalCTA />
    </main>
  );
}
```

- [ ] **Step 5: Verify build**

```bash
cd website
nix develop .. --command bash -c "npm run build"
```

- [ ] **Step 6: Commit**

```bash
git add website/components/home/ website/app/page.tsx
git commit -m "feat: complete homepage — PlatformStats, Testimonials, FinalCTA"
```

---

### Task 7: Features Page

**Files:**
- Create: `website/components/features/FeatureSection.tsx`
- Create: `website/app/features/page.tsx`

- [ ] **Step 1: Create FeatureSection component**

Write `website/components/features/FeatureSection.tsx`:

```tsx
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
```

- [ ] **Step 2: Create Features page**

Write `website/app/features/page.tsx`:

```tsx
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
            <div className="flex justify-between"><span className="text-slate-muted">Balance</span><span className="text-slate-heading font-mono">$10,000.00</span></div>
            <div className="flex justify-between"><span className="text-slate-muted">Open P&L</span><span className="text-green-400 font-mono">+$342.50</span></div>
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
            <div className="flex justify-between"><span className="text-slate-muted">Entry</span><span className="text-slate-heading font-mono">$67,420.00</span></div>
            <div className="flex justify-between"><span className="text-slate-muted">Current</span><span className="text-slate-heading font-mono">$68,660.00</span></div>
            <div className="flex justify-between"><span className="text-slate-muted">Unrealized P&L</span><span className="text-green-400 font-mono">+$1,240.00</span></div>
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
```

- [ ] **Step 3: Verify build**

```bash
cd website
nix develop .. --command bash -c "npm run build"
```

- [ ] **Step 4: Commit**

```bash
git add website/components/features/ website/app/features/
git commit -m "feat: add Features page with alternating section layout"
```

---

### Task 8: Pricing Page

**Files:**
- Create: `website/components/pricing/BillingToggle.tsx`
- Create: `website/components/pricing/PricingCards.tsx`
- Create: `website/components/pricing/PricingContent.tsx`
- Create: `website/components/pricing/FAQ.tsx`
- Create: `website/app/pricing/page.tsx`

- [ ] **Step 1: Create BillingToggle**

Write `website/components/pricing/BillingToggle.tsx`:

```tsx
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
```

- [ ] **Step 2: Create PricingCards**

Write `website/components/pricing/PricingCards.tsx`:

```tsx
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
                  <span className="mt-0.5 text-brand-indigo">✓</span>
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
```

- [ ] **Step 3: Create FAQ accordion**

Write `website/components/pricing/FAQ.tsx`:

```tsx
"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const faqs = [
  {
    q: "What happens after the free trial?",
    a: "After 14 days, you'll be asked to choose a plan. If you don't, your account switches to read-only — you can still view your data, but can't run strategies or backtests until you subscribe.",
  },
  {
    q: "Can I cancel anytime?",
    a: "Yes. Cancel from your account settings at any time. You'll keep access through the end of your billing period.",
  },
  {
    q: "Which exchanges are supported?",
    a: "We currently support Binance, Exchange1, Bybit, and OKX with more coming soon. All exchanges support both paper and live trading.",
  },
  {
    q: "Is my exchange API key secure?",
    a: "Yes. API keys are encrypted with AES-256-GCM before storage. We use per-tenant derived encryption keys. We recommend using API keys with trade-only permissions (no withdrawal).",
  },
  {
    q: "Can I run multiple strategies at once?",
    a: "Yes. The number of concurrent strategies depends on your plan — Starter supports 2, Pro supports 10, and Enterprise is unlimited.",
  },
  {
    q: "What programming language do I need to know?",
    a: "Python. Our SDK is designed to be approachable — if you can write a basic Python function, you can write a strategy. We also support no-code webhook signals from TradingView.",
  },
];

export function FAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <section className="mx-auto max-w-2xl px-6 py-16">
      <h2 className="text-2xl font-bold text-slate-heading text-center mb-8">
        Frequently asked questions
      </h2>
      <div className="space-y-3">
        {faqs.map((faq, i) => (
          <div
            key={i}
            className="rounded-lg border border-brand-indigo/10 bg-brand-indigo/5"
          >
            <button
              onClick={() => setOpenIndex(openIndex === i ? null : i)}
              className="flex w-full items-center justify-between px-5 py-4 text-left text-sm font-medium text-slate-heading"
            >
              {faq.q}
              <span
                className={`ml-2 transition-transform ${
                  openIndex === i ? "rotate-45" : ""
                }`}
              >
                +
              </span>
            </button>
            <AnimatePresence>
              {openIndex === i && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden"
                >
                  <p className="px-5 pb-4 text-sm text-slate-body leading-relaxed">
                    {faq.a}
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Create Pricing page**

Write `website/app/pricing/page.tsx` — note: the page itself is a server component with static metadata. The client-side billing toggle state is handled by a wrapper component inside:

```tsx
import type { Metadata } from "next";
import { PricingContent } from "@/components/pricing/PricingContent";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Simple, transparent pricing for Algomatter. Start with a 14-day free trial.",
};

export default function PricingPage() {
  return <PricingContent />;
}
```

Then create the client wrapper. Write `website/components/pricing/PricingContent.tsx`:

```tsx
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
```

- [ ] **Step 5: Verify build**

```bash
cd website
nix develop .. --command bash -c "npm run build"
```

- [ ] **Step 6: Commit**

```bash
git add website/components/pricing/ website/app/pricing/
git commit -m "feat: add Pricing page with billing toggle, tier cards, and FAQ"
```

---

### Task 9: About Page

**Files:**
- Create: `website/app/about/page.tsx`

- [ ] **Step 1: Create About page**

Write `website/app/about/page.tsx`:

```tsx
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About",
  description: "Our mission is to make algorithmic trading accessible to every crypto trader.",
};

const values = [
  {
    title: "Transparency over complexity",
    description: "Every trade, every metric, every fee — visible and verifiable. No black boxes.",
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
```

- [ ] **Step 2: Verify build**

```bash
cd website
nix develop .. --command bash -c "npm run build"
```

- [ ] **Step 3: Commit**

```bash
git add website/app/about/
git commit -m "feat: add About page with mission, values, and contact"
```

---

### Task 10: Docs Infrastructure (MDX processing, sidebar, layout)

**Files:**
- Create: `website/lib/mdx.ts`
- Create: `website/lib/docs-manifest.ts`
- Create: `website/components/docs/DocsSidebar.tsx`
- Create: `website/components/docs/MDXComponents.tsx`
- Create: `website/app/docs/layout.tsx`
- Create: `website/app/docs/[[...slug]]/page.tsx`
- Create: `website/content/docs/getting-started/quick-start.mdx`

- [ ] **Step 1: Create docs manifest (sidebar structure)**

Write `website/lib/docs-manifest.ts`:

```typescript
export interface DocEntry {
  title: string;
  slug: string;
}

export interface DocSection {
  title: string;
  entries: DocEntry[];
}

export const docsManifest: DocSection[] = [
  {
    title: "Getting Started",
    entries: [
      { title: "Quick Start", slug: "getting-started/quick-start" },
      { title: "Connecting an Exchange", slug: "getting-started/connecting-exchange" },
      { title: "Your First Strategy", slug: "getting-started/first-strategy" },
    ],
  },
  {
    title: "Strategies",
    entries: [
      { title: "Python SDK Guide", slug: "strategies/python-sdk" },
      { title: "Strategy Templates", slug: "strategies/templates" },
      { title: "Webhooks & TradingView", slug: "strategies/webhooks-tradingview" },
      { title: "Mapping Templates", slug: "strategies/mapping-templates" },
    ],
  },
  {
    title: "Backtesting",
    entries: [
      { title: "Running a Backtest", slug: "backtesting/running-backtest" },
      { title: "Understanding Results", slug: "backtesting/understanding-results" },
      { title: "Slippage & Commission", slug: "backtesting/slippage-commission" },
    ],
  },
  {
    title: "Trading",
    entries: [
      { title: "Paper Trading", slug: "trading/paper-trading" },
      { title: "Going Live", slug: "trading/going-live" },
      { title: "Kill Switch & Safety", slug: "trading/kill-switch" },
    ],
  },
];

export function getAllDocSlugs(): string[] {
  return docsManifest.flatMap((section) =>
    section.entries.map((entry) => entry.slug)
  );
}

export function findAdjacentDocs(slug: string) {
  const all = docsManifest.flatMap((s) => s.entries);
  const index = all.findIndex((e) => e.slug === slug);
  return {
    prev: index > 0 ? all[index - 1] : null,
    next: index < all.length - 1 ? all[index + 1] : null,
  };
}
```

- [ ] **Step 2: Create MDX processing utilities**

Write `website/lib/mdx.ts`:

```typescript
import fs from "fs";
import path from "path";
import matter from "gray-matter";

const CONTENT_DIR = path.join(process.cwd(), "content", "docs");

export async function getDocBySlug(slug: string) {
  const filePath = path.join(CONTENT_DIR, `${slug}.mdx`);
  if (!fs.existsSync(filePath)) return null;
  const raw = fs.readFileSync(filePath, "utf-8");
  const { data, content } = matter(raw);
  return { frontmatter: data, content, slug };
}
```

- [ ] **Step 3: Create MDXComponents**

Write `website/components/docs/MDXComponents.tsx`:

```tsx
import type { MDXComponents } from "mdx/types";

export const mdxComponents: MDXComponents = {
  h1: (props) => (
    <h1 className="text-3xl font-bold text-slate-heading mt-8 mb-4" {...props} />
  ),
  h2: (props) => (
    <h2 className="text-2xl font-bold text-slate-heading mt-8 mb-3" {...props} />
  ),
  h3: (props) => (
    <h3 className="text-lg font-semibold text-slate-heading mt-6 mb-2" {...props} />
  ),
  p: (props) => (
    <p className="text-sm text-slate-body leading-relaxed mb-4" {...props} />
  ),
  ul: (props) => <ul className="list-disc pl-5 mb-4 space-y-1 text-sm text-slate-body" {...props} />,
  ol: (props) => <ol className="list-decimal pl-5 mb-4 space-y-1 text-sm text-slate-body" {...props} />,
  li: (props) => <li className="leading-relaxed" {...props} />,
  code: (props) => (
    <code className="rounded bg-brand-indigo/10 px-1.5 py-0.5 text-xs font-mono text-brand-lavender" {...props} />
  ),
  pre: (props) => (
    <pre className="rounded-lg bg-[#0a0a1a] p-4 overflow-x-auto mb-4 text-xs leading-relaxed" {...props} />
  ),
  a: (props) => (
    <a className="text-brand-lavender hover:underline" {...props} />
  ),
  blockquote: (props) => (
    <blockquote className="border-l-2 border-brand-indigo/30 pl-4 italic text-slate-muted mb-4" {...props} />
  ),
};
```

- [ ] **Step 4: Create DocsSidebar**

Write `website/components/docs/DocsSidebar.tsx`:

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { docsManifest } from "@/lib/docs-manifest";

export function DocsSidebar() {
  const pathname = usePathname();

  return (
    <nav className="space-y-6">
      {docsManifest.map((section) => (
        <div key={section.title}>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-body mb-2">
            {section.title}
          </h4>
          <ul className="space-y-1">
            {section.entries.map((entry) => {
              const href = `/docs/${entry.slug}`;
              const active = pathname === href;
              return (
                <li key={entry.slug}>
                  <Link
                    href={href}
                    className={`block rounded-md px-3 py-1.5 text-sm transition-colors ${
                      active
                        ? "bg-brand-indigo/10 text-brand-lavender font-medium"
                        : "text-slate-muted hover:text-slate-body"
                    }`}
                  >
                    {entry.title}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
```

- [ ] **Step 5: Create docs layout**

Write `website/app/docs/layout.tsx`:

```tsx
import type { Metadata } from "next";
import { DocsSidebar } from "@/components/docs/DocsSidebar";

export const metadata: Metadata = {
  title: {
    default: "Docs",
    template: "%s | Algomatter Docs",
  },
};

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto flex max-w-6xl gap-8 px-6 py-12">
      <aside className="hidden w-56 shrink-0 md:block">
        <div className="sticky top-24">
          <DocsSidebar />
        </div>
      </aside>
      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}
```

- [ ] **Step 6: Create dynamic doc page**

Write `website/app/docs/[[...slug]]/page.tsx`:

```tsx
import { notFound } from "next/navigation";
import { MDXRemote } from "next-mdx-remote/rsc";
import { getDocBySlug } from "@/lib/mdx";
import { getAllDocSlugs, findAdjacentDocs } from "@/lib/docs-manifest";
import { mdxComponents } from "@/components/docs/MDXComponents";
import Link from "next/link";

interface PageProps {
  params: Promise<{ slug?: string[] }>;
}

export async function generateStaticParams() {
  const slugs = getAllDocSlugs();
  return [
    { slug: undefined }, // /docs index
    ...slugs.map((s) => ({ slug: s.split("/") })),
  ];
}

export default async function DocPage({ params }: PageProps) {
  const { slug } = await params;

  // /docs index — redirect to quick-start
  if (!slug || slug.length === 0) {
    const doc = await getDocBySlug("getting-started/quick-start");
    if (!doc) notFound();
    const { prev, next } = findAdjacentDocs(doc.slug);
    return (
      <article>
        <MDXRemote source={doc.content} components={mdxComponents} />
        <NavLinks prev={prev} next={next} />
      </article>
    );
  }

  const joinedSlug = slug.join("/");
  const doc = await getDocBySlug(joinedSlug);
  if (!doc) notFound();

  const { prev, next } = findAdjacentDocs(joinedSlug);

  return (
    <article>
      <MDXRemote source={doc.content} components={mdxComponents} />
      <NavLinks prev={prev} next={next} />
    </article>
  );
}

function NavLinks({
  prev,
  next,
}: {
  prev: { title: string; slug: string } | null;
  next: { title: string; slug: string } | null;
}) {
  return (
    <div className="mt-12 flex justify-between border-t border-brand-indigo/10 pt-6 text-sm">
      {prev ? (
        <Link href={`/docs/${prev.slug}`} className="text-brand-lavender hover:underline">
          &larr; {prev.title}
        </Link>
      ) : (
        <span />
      )}
      {next ? (
        <Link href={`/docs/${next.slug}`} className="text-brand-lavender hover:underline">
          {next.title} &rarr;
        </Link>
      ) : (
        <span />
      )}
    </div>
  );
}
```

- [ ] **Step 7: Create a starter doc**

Write `website/content/docs/getting-started/quick-start.mdx`:

```mdx
---
title: Quick Start
description: Get up and running with Algomatter in 5 minutes
---

# Quick Start

Welcome to Algomatter! This guide will have you running your first backtest in under 5 minutes.

## 1. Create an account

Sign up at [algomatter.com](https://algomatter.com) and start your 14-day free trial. No credit card required.

## 2. Connect an exchange

Navigate to **Brokers** in the sidebar and click **Add Broker**. Select your exchange (Binance, Exchange1, Bybit, or OKX) and enter your API key and secret.

> We recommend creating a dedicated API key with trade-only permissions (no withdrawal access).

## 3. Create a strategy

Go to **Strategies → Hosted** and click **New Strategy**. You'll see a Python editor with a starter template:

```python
from algomatter import Strategy

class MyStrategy(Strategy):
    def on_candle(self, candle):
        if candle.rsi < 30:
            self.buy(candle.symbol, qty=0.1)
        elif candle.rsi > 70:
            self.sell(candle.symbol)
```

## 4. Run a backtest

Click **Backtest** and configure:
- **Symbol:** BTC/USDT
- **Timeframe:** 4H
- **Date range:** Last 6 months
- **Starting capital:** $10,000

Hit **Run** and watch the results come in — equity curve, trade log, and performance metrics.

## 5. Paper trade

Happy with the results? Click **Deploy → Paper** to run your strategy against live market data with virtual capital. Monitor it in the **Live Trading** dashboard.

## Next steps

- [Connecting an Exchange](/docs/getting-started/connecting-exchange) — detailed exchange setup
- [Python SDK Guide](/docs/strategies/python-sdk) — full SDK reference
- [Understanding Results](/docs/backtesting/understanding-results) — reading backtest metrics
```

- [ ] **Step 8: Create placeholder MDX files for remaining docs**

Create directories and all placeholder files. Use this bash script to generate them all:

```bash
cd website
mkdir -p content/docs/{getting-started,strategies,backtesting,trading}

declare -A docs=(
  ["getting-started/connecting-exchange"]="Connecting an Exchange"
  ["getting-started/first-strategy"]="Your First Strategy"
  ["strategies/python-sdk"]="Python SDK Guide"
  ["strategies/templates"]="Strategy Templates"
  ["strategies/webhooks-tradingview"]="Webhooks & TradingView"
  ["strategies/mapping-templates"]="Mapping Templates"
  ["backtesting/running-backtest"]="Running a Backtest"
  ["backtesting/understanding-results"]="Understanding Results"
  ["backtesting/slippage-commission"]="Slippage & Commission"
  ["trading/paper-trading"]="Paper Trading"
  ["trading/going-live"]="Going Live"
  ["trading/kill-switch"]="Kill Switch & Safety"
)

for slug in "${!docs[@]}"; do
  title="${docs[$slug]}"
  cat > "content/docs/${slug}.mdx" << ENDMDX
---
title: "${title}"
description: "${title} — content coming soon"
---

# ${title}

Content coming soon.
ENDMDX
done
```

- [ ] **Step 9: Verify build**

```bash
cd website
nix develop .. --command bash -c "npm run build"
```

- [ ] **Step 10: Commit**

```bash
git add website/lib/mdx.ts website/lib/docs-manifest.ts website/components/docs/ website/app/docs/ website/content/docs/
git commit -m "feat: add docs infrastructure — MDX processing, sidebar, layout, starter content"
```

---

### Task 11: Changelog Page

**Files:**
- Create: `website/app/changelog/page.tsx`
- Create: `website/content/changelog/2026-03-v1.0.0.mdx`

- [ ] **Step 1: Create changelog page**

Write `website/app/changelog/page.tsx`:

```tsx
import type { Metadata } from "next";
import fs from "fs";
import path from "path";
import matter from "gray-matter";
import { MDXRemote } from "next-mdx-remote/rsc";
import { mdxComponents } from "@/components/docs/MDXComponents";

export const metadata: Metadata = {
  title: "Changelog",
  description: "What's new in Algomatter — release notes and updates.",
};

async function getChangelogEntries() {
  const dir = path.join(process.cwd(), "content", "changelog");
  if (!fs.existsSync(dir)) return [];
  const files = fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".mdx"))
    .sort()
    .reverse();

  return files.map((file) => {
    const raw = fs.readFileSync(path.join(dir, file), "utf-8");
    const { data, content } = matter(raw);
    return { frontmatter: data, content, slug: file.replace(".mdx", "") };
  });
}

export default async function ChangelogPage() {
  const entries = await getChangelogEntries();

  return (
    <main className="mx-auto max-w-3xl px-6 py-20">
      <h1 className="text-4xl font-extrabold text-slate-heading">Changelog</h1>
      <p className="mt-3 text-slate-body">
        What&apos;s new in Algomatter — release notes and updates.
      </p>
      <div className="mt-10 space-y-12">
        {entries.map((entry) => (
          <article key={entry.slug} className="border-l-2 border-brand-indigo/20 pl-6">
            <MDXRemote source={entry.content} components={mdxComponents} />
          </article>
        ))}
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Create initial changelog entry**

Write `website/content/changelog/2026-03-v1.0.0.mdx`:

```mdx
---
version: "1.0.0"
date: "2026-03-28"
---

## v1.0.0 — March 2026

**New**
- Python strategy editor with syntax highlighting and version control
- Backtesting engine powered by Nautilus Trader
- Paper trading with simulated order execution
- Live trading deployment with real-time monitoring
- Webhook signal processing from TradingView and other sources
- Analytics dashboard with equity curves, drawdown charts, and performance metrics
- Exchange support: Binance, Exchange1, Bybit, OKX
- Emergency kill switch for live deployments
```

- [ ] **Step 3: Verify build**

```bash
cd website
nix develop .. --command bash -c "npm run build"
```

- [ ] **Step 4: Commit**

```bash
git add website/app/changelog/ website/content/changelog/
git commit -m "feat: add Changelog page with initial v1.0.0 entry"
```

---

### Task 12: SEO & Final Polish

**Files:**
- Create: `website/app/sitemap.ts`
- Create: `website/app/robots.ts`
- Modify: `website/app/layout.tsx` (add favicon)

- [ ] **Step 1: Create sitemap generator**

Write `website/app/sitemap.ts`:

```typescript
import type { MetadataRoute } from "next";
import { siteConfig } from "@/lib/config";
import { getAllDocSlugs } from "@/lib/docs-manifest";

export default function sitemap(): MetadataRoute.Sitemap {
  const staticPages = [
    "",
    "/features",
    "/pricing",
    "/about",
    "/changelog",
    "/docs",
  ];

  const docPages = getAllDocSlugs().map((slug) => `/docs/${slug}`);

  return [...staticPages, ...docPages].map((route) => ({
    url: `${siteConfig.url}${route}`,
    lastModified: new Date(),
    changeFrequency: route === "" ? "weekly" : "monthly",
    priority: route === "" ? 1 : 0.8,
  }));
}
```

- [ ] **Step 2: Create robots.txt**

Write `website/app/robots.ts`:

```typescript
import type { MetadataRoute } from "next";
import { siteConfig } from "@/lib/config";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
    sitemap: `${siteConfig.url}/sitemap.xml`,
  };
}
```

- [ ] **Step 3: Add favicon link to layout**

Modify `website/app/layout.tsx` metadata to include favicon:

```typescript
export const metadata: Metadata = {
  title: {
    default: `${siteConfig.name} — ${siteConfig.tagline}`,
    template: `%s | ${siteConfig.name}`,
  },
  description: siteConfig.description,
  icons: { icon: "/logo.svg" },
  openGraph: {
    title: siteConfig.name,
    description: siteConfig.description,
    url: siteConfig.url,
    siteName: siteConfig.name,
    type: "website",
  },
};
```

- [ ] **Step 4: Final build verification**

```bash
cd website
nix develop .. --command bash -c "npm run build"
```

Expected: All pages build successfully with no errors.

- [ ] **Step 5: Commit**

```bash
git add website/app/sitemap.ts website/app/robots.ts website/app/layout.tsx
git commit -m "feat: add sitemap, robots.txt, and favicon for SEO"
```

---

### Task 13: Docs Search (Cmd-K)

**Files:**
- Create: `website/components/docs/SearchDialog.tsx`
- Modify: `website/app/docs/layout.tsx`

- [ ] **Step 1: Create SearchDialog component**

Write `website/components/docs/SearchDialog.tsx`:

```tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { docsManifest } from "@/lib/docs-manifest";

const allDocs = docsManifest.flatMap((section) =>
  section.entries.map((entry) => ({
    ...entry,
    section: section.title,
  }))
);

export function SearchDialog() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const router = useRouter();

  const filtered = query
    ? allDocs.filter(
        (d) =>
          d.title.toLowerCase().includes(query.toLowerCase()) ||
          d.section.toLowerCase().includes(query.toLowerCase())
      )
    : allDocs;

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === "Escape") setOpen(false);
    },
    []
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  function navigate(slug: string) {
    setOpen(false);
    setQuery("");
    router.push(`/docs/${slug}`);
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="flex w-full items-center gap-2 rounded-lg border border-brand-indigo/10 bg-brand-indigo/5 px-3 py-2 text-sm text-slate-muted hover:border-brand-indigo/20 transition-colors"
      >
        <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="6" cy="6" r="5" />
          <path d="M10 10l3 3" />
        </svg>
        Search docs...
        <kbd className="ml-auto rounded bg-brand-bg px-1.5 py-0.5 text-xs text-slate-faint">
          ⌘K
        </kbd>
      </button>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              className="fixed inset-0 z-50 bg-black/60"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
            />
            <motion.div
              className="fixed left-1/2 top-[20%] z-50 w-full max-w-lg -translate-x-1/2 rounded-xl border border-brand-indigo/20 bg-brand-bg shadow-2xl"
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
            >
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search docs..."
                className="w-full border-b border-brand-indigo/10 bg-transparent px-4 py-3 text-sm text-slate-heading outline-none placeholder:text-slate-muted"
              />
              <div className="max-h-72 overflow-y-auto p-2">
                {filtered.length === 0 ? (
                  <p className="px-3 py-4 text-sm text-slate-muted text-center">
                    No results found
                  </p>
                ) : (
                  filtered.map((doc) => (
                    <button
                      key={doc.slug}
                      onClick={() => navigate(doc.slug)}
                      className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm hover:bg-brand-indigo/10 transition-colors"
                    >
                      <span className="text-slate-heading">{doc.title}</span>
                      <span className="text-xs text-slate-faint">{doc.section}</span>
                    </button>
                  ))
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
```

- [ ] **Step 2: Add SearchDialog to docs layout**

Modify `website/app/docs/layout.tsx` — add search above sidebar:

```tsx
import type { Metadata } from "next";
import { DocsSidebar } from "@/components/docs/DocsSidebar";
import { SearchDialog } from "@/components/docs/SearchDialog";

export const metadata: Metadata = {
  title: {
    default: "Docs",
    template: "%s | Algomatter Docs",
  },
};

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto flex max-w-6xl gap-8 px-6 py-12">
      <aside className="hidden w-56 shrink-0 md:block">
        <div className="sticky top-24 space-y-6">
          <SearchDialog />
          <DocsSidebar />
        </div>
      </aside>
      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

```bash
cd website
nix develop .. --command bash -c "npm run build"
```

- [ ] **Step 4: Commit**

```bash
git add website/components/docs/SearchDialog.tsx website/app/docs/layout.tsx
git commit -m "feat: add Cmd-K search dialog for docs"
```
