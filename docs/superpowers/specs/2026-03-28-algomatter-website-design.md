# Algomatter Marketing Website — Design Spec

## Overview

A standalone marketing website for Algomatter, a crypto algorithmic trading SaaS platform. The website sits in front of the existing Next.js application — visitors browse the marketing site and are routed to the existing app on login/signup.

**Target audience:** Crypto traders, ranging from curious beginners to experienced traders looking to automate their strategies.

**Primary goal:** Self-serve SaaS funnel — visitors can learn about the platform, explore pricing, and sign up for a free trial.

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Framework | Next.js 15 (App Router) | Familiar from existing app, SSR/SSG for SEO, React ecosystem, latest stable |
| Styling | Tailwind CSS | Full design control for custom gradients, glows, animations — better suited than Chakra for marketing pages |
| Content | MDX | Docs and changelog authored in markdown with embedded components |
| Animations | Framer Motion | Scroll-driven reveals, count-up numbers, equity curve draw animations |
| Deployment | Independent from main app | Separate build/deploy cycle, links to existing app for auth |
| Package manager | Determined by project setup (pnpm/npm) | |

This is a **standalone project** in the `website-mvp` worktree, not an extension of the existing Next.js app.

## Brand Identity

### Visual Direction: Modern Fintech

- **Background:** Deep dark tones (`#0f0f23`, `#1b1b3a`)
- **Primary gradient:** Indigo to purple (`#6366f1` → `#a855f7`)
- **Accent:** Cyan (`#22d3ee`) for highlights, live-data indicators
- **Text:** White/light slate for headings (`#f1f5f9`, `#e2e8f0`), muted slate for body (`#94a3b8`, `#64748b`)
- **Surfaces:** Subtle glass/blur effects, cards with `rgba(99,102,241,0.05)` backgrounds and `rgba(99,102,241,0.1)` borders
- **Glows:** Radial gradient orbs behind hero sections, subtle and atmospheric

### Logo: Monogram "A"

SVG icon: stylized letter "A" inside a rounded square. The A's peak doubles as a chart summit with data points at vertices. Works at all sizes from navbar (32px) to favicon (16px).

- Icon paired with "algomatter" wordmark (system-ui, weight 800, white/gradient text)
- Wordmark uses `background: linear-gradient(135deg, #a78bfa, #6366f1)` with background-clip text for gradient effect in headers

### Tone: Approachable & Educational

- "Crypto algo trading, simplified."
- Assumes some readers are new to algorithmic trading
- Friendly, welcoming, explains concepts without being condescending
- Short, clear sentences. No jargon without context.

### Motion: Live Data Feel

- Equity curves that draw themselves (SVG path animation on load)
- Numbers that count up from 0 when scrolled into view
- Ticker-like scrolling for exchange logos or stats
- Code snippets that type themselves in "How it Works"
- Scroll-driven section reveals (fade up + slide)
- Subtle pulsing gradient orbs in hero backgrounds

## Site Structure

### Navigation

Sticky navbar with glassmorphism (dark blur, semi-transparent background):

```
[Logo + algomatter]   Features   Pricing   Docs   Changelog   About   [Login]  [Start Free Trial →]
```

- Login and Signup link to the existing app (`app.algomatter.com/login`, `app.algomatter.com/signup` or configured domain)
- "Start Free Trial" is the primary CTA (gradient button) throughout
- Mobile: hamburger menu

### Pages

| Route | Page | Content Type |
|-------|------|-------------|
| `/` | Homepage | Static + animated |
| `/features` | Features | Static + animated |
| `/pricing` | Pricing | Static |
| `/docs` | Documentation | MDX |
| `/docs/[...slug]` | Doc pages | MDX |
| `/changelog` | Changelog | MDX |
| `/about` | About | Static |

Login/signup routes redirect to the existing application.

### Footer

4-column layout:

| Algomatter | Product | Resources | Company |
|------------|---------|-----------|---------|
| Logo + tagline | Features | Docs | About |
| | Pricing | Getting Started | Privacy |
| | Changelog | | Terms |
| | | | Contact |

Bottom bar: copyright + social links (Twitter/X, Discord)

No GitHub link — closed source product.

## Page Designs

### Homepage (`/`)

Seven sections flowing top to bottom:

**1. Hero**
- Pill badge: "Now in public beta — try free for 14 days"
- Headline: "Crypto algo trading, simplified."
- Subtext: "Build strategies in Python, backtest against real market data, and deploy to live crypto markets — all from one platform."
- Two CTAs: "Start Free Trial →" (primary gradient) + "Watch Demo" (ghost/outline)
- Hero visual: browser-frame mockup containing an animated equity curve (SVG draws on load) with overlay stats — BTC/USDT pair, +142.8% return, Sharpe 2.41, Max DD -12.3%, Win Rate 67%
- Background: radial gradient orbs (indigo + purple) with subtle pulse animation

**2. Supported Exchanges**
- Subtitle: "Supported Exchanges"
- Logo bar: Binance, Exchange1, Bybit, OKX, + more
- Logos in muted/grayscale, staggered fade-in animation
- Optional infinite scroll if list grows

**3. How It Works**
- Section label: "How it works"
- Heading: "From idea to live trading in minutes"
- Three-step cards in a row:
  - **Step 1: Write your strategy** — Python code snippet showing `on_candle` with RSI buy signal. "Code in Python using our SDK, or connect signals from TradingView via webhooks."
  - **Step 2: Backtest & validate** — Mini metrics panel (Return +142%, Sharpe 2.41, Max DD -12%). "Run against historical data with realistic slippage and fees."
  - **Step 3: Deploy & monitor** — Live position display (BTC/USDT Long, Entry $67,420, P&L +$1,240, status LIVE). "Paper trade first, then go live. Kill switch if anything goes wrong."
- Each card has a numbered gradient badge (1, 2, 3)
- Animation: cards slide up on scroll, code types itself, metrics count up

**4. Key Features**
- Section label: "Features"
- Heading: "Everything you need to trade algorithmically"
- 2x2 grid of feature cards:
  - Backtesting Engine — Nautilus-powered, realistic fills, equity curves
  - Webhook Signals — TradingView/any source, JSONPath mapping, rules engine
  - Python Strategies — SDK, built-in editor, version control, templates
  - Paper → Live — virtual capital testing, one-click live deployment, kill switch
- Cards fade in with stagger on scroll

**5. Platform Stats**
- Section label: "Platform Stats"
- Four large numbers in a row: Backtests Run (1,200+), Active Strategies (50+), Volume Traded ($2.4M), Uptime (99.9%)
- Numbers count up from 0 when section enters viewport
- Gradient text matching brand colors

**6. Testimonials**
- Section label: "What traders say"
- Rotating carousel (auto-advance with fade transition)
- Each card: quote in italics, avatar circle, name, "Crypto Trader" subtitle
- Placeholder content initially — replace with real testimonials as they come in

**7. Final CTA**
- Heading: "Ready to automate your trading?"
- Subtext: "Start your 14-day free trial. No credit card required."
- Single CTA: "Start Free Trial →"
- Background: radial gradient glow that intensifies on scroll, button has subtle pulse

### Features Page (`/features`)

**Hero section:**
- Heading: "Everything you need to trade algorithmically"
- Subtitle describing the end-to-end platform

**Feature deep-dives** — alternating layout (text left / visual right, then swap):

| Feature | Visual Treatment |
|---------|-----------------|
| Python Strategies | Code editor mockup with syntax highlighting, types itself on scroll |
| Webhook Signals | Animated diagram: TradingView → Webhook → Algomatter → Exchange |
| Backtesting | Equity curve draws itself + metrics panel counts up |
| Paper Trading | Dashboard mockup with virtual P&L updating |
| Live Trading | Command center mockup: positions list, P&L, kill switch button |
| Analytics | Multi-chart layout: equity curve, drawdown chart, strategy comparison |

Each section reveals on scroll with the visual animating in.

**Bottom CTA:** "Ready to try it?" → Start Free Trial

### Pricing Page (`/pricing`)

**Hero:**
- Heading: "Simple, transparent pricing"
- Subtitle: "Start free, upgrade when you're ready"

**Billing toggle:** Monthly / Annual (annual shows "Save X%" badge)

**Three tier cards side by side:**

| | Starter | Pro (highlighted) | Enterprise |
|---|---------|-------------------|------------|
| Price | Free 14 days, then $X/mo | $X/mo | Custom |
| Strategies | 2 active | 10 active | Unlimited |
| Backtests | 10/month | Unlimited | Unlimited |
| Paper Trading | Yes | Yes | Yes |
| Live Trading | 1 exchange | 3 exchanges | Unlimited |
| Webhook Signals | 100/day | 1,000/day | Unlimited |
| Data Retention | 30 days | 1 year | Unlimited |
| Support | Community | Priority email | Dedicated |
| CTA | Start Free Trial | Start Free Trial | Contact Us |

- Pro tier: "Most Popular" badge, gradient glow border, slightly elevated
- Prices left as placeholders (`$X`) to be filled in

**FAQ accordion** below the cards:
- What happens after the free trial?
- Can I cancel anytime?
- Which exchanges are supported?
- Is my exchange API key secure?
- Can I run multiple strategies at once?
- What programming language do I need to know?

**Bottom CTA:** "Still not sure? Start with the free trial."

### Docs Page (`/docs`)

**Layout:** Sidebar navigation + main content area + optional table of contents on wide screens

**Sidebar structure:**
```
Getting Started
  ├── Quick Start (5 min)
  ├── Connecting an Exchange
  └── Your First Strategy

Strategies
  ├── Python SDK Guide
  ├── Strategy Templates
  ├── Webhooks & TradingView
  └── Mapping Templates

Backtesting
  ├── Running a Backtest
  ├── Understanding Results
  └── Slippage & Commission

Trading
  ├── Paper Trading
  ├── Going Live
  └── Kill Switch & Safety
```

**Features:**
- Command-K search across all docs (client-side search index)
- Code blocks with syntax highlighting + copy button
- MDX content files in the repo
- Responsive: sidebar collapses to hamburger on mobile
- Previous/Next navigation at bottom of each page

### Changelog Page (`/changelog`)

**Layout:** Single column, reverse chronological

**Each entry:**
```
## v1.2.0 — March 2026

- Added kill switch for live deployments
- Improved backtest performance by 3x
- Fixed webhook signal deduplication bug
```

- MDX content, low-maintenance format
- Version + date heading
- Bullet-point changes, categorized by type if needed (New, Improved, Fixed)

### About Page (`/about`)

**Sections:**
1. **Mission statement** — "We believe algorithmic trading shouldn't require a hedge fund budget." Brief, authentic origin story.
2. **What we're building** — Short paragraph about the platform vision for crypto traders
3. **Values** — 3-4 principles:
   - Transparency over complexity
   - Test before you trade
   - Your keys, your strategies
   - Simplicity is a feature
4. **Contact** — Email, link to Discord community

Clean, minimal. No team photos unless desired later.

## Technical Architecture

### Project Structure

```
website-mvp/
├── app/
│   ├── layout.tsx              # Root layout: fonts, metadata, analytics
│   ├── page.tsx                # Homepage
│   ├── features/page.tsx       # Features page
│   ├── pricing/page.tsx        # Pricing page
│   ├── about/page.tsx          # About page
│   ├── changelog/page.tsx      # Changelog (renders MDX)
│   └── docs/
│       ├── layout.tsx          # Docs layout with sidebar
│       └── [...slug]/page.tsx  # Dynamic MDX doc pages
├── components/
│   ├── layout/
│   │   ├── Navbar.tsx          # Sticky glassmorphism nav
│   │   ├── Footer.tsx          # 4-column footer
│   │   └── MobileMenu.tsx      # Hamburger menu
│   ├── home/
│   │   ├── Hero.tsx            # Hero with animated equity curve
│   │   ├── ExchangeBar.tsx     # Supported exchanges logos
│   │   ├── HowItWorks.tsx      # 3-step cards
│   │   ├── Features.tsx        # 2x2 feature grid
│   │   ├── PlatformStats.tsx   # Animated counters
│   │   ├── Testimonials.tsx    # Rotating carousel
│   │   └── FinalCTA.tsx        # Bottom call-to-action
│   ├── features/
│   │   └── FeatureSection.tsx  # Alternating text+visual layout
│   ├── pricing/
│   │   ├── PricingCards.tsx    # Tier comparison
│   │   ├── BillingToggle.tsx   # Monthly/Annual switch
│   │   └── FAQ.tsx             # Accordion
│   ├── docs/
│   │   ├── DocsSidebar.tsx     # Navigation sidebar
│   │   ├── SearchDialog.tsx    # Cmd-K search
│   │   └── MDXComponents.tsx   # Custom MDX renderers
│   └── shared/
│       ├── AnimatedCounter.tsx # Count-up number animation
│       ├── EquityCurve.tsx     # SVG path draw animation
│       ├── TypeWriter.tsx      # Code typing animation
│       ├── ScrollReveal.tsx    # Intersection observer wrapper
│       └── GradientButton.tsx  # Primary CTA button
├── content/
│   ├── docs/                   # MDX doc files
│   │   ├── getting-started/
│   │   ├── strategies/
│   │   ├── backtesting/
│   │   └── trading/
│   └── changelog/              # MDX changelog entries
├── lib/
│   ├── config.ts               # App URL, site metadata
│   └── mdx.ts                  # MDX processing utilities
├── public/
│   ├── logo.svg                # Monogram A logo
│   ├── og-image.png            # Open Graph image
│   └── exchange-logos/         # Binance, Exchange1, etc.
├── tailwind.config.ts
├── next.config.js
├── package.json
└── tsconfig.json
```

### Key Technical Decisions

**Routing:** Next.js App Router with static generation for all marketing pages. Docs use `generateStaticParams` to pre-render all MDX content at build time.

**MDX processing:** `next-mdx-remote` for docs and changelog content. Custom MDX components for code blocks, callouts, and interactive elements. (Note: contentlayer is unmaintained and incompatible with recent Next.js versions.)

**Animations:** Framer Motion for:
- `ScrollReveal` — intersection observer triggers fade-up animations
- `AnimatedCounter` — count-up from 0 to target number
- `EquityCurve` — SVG `pathLength` animation to draw the line
- `TypeWriter` — character-by-character code reveal

**Search:** Client-side search index built at compile time (e.g., `flexsearch` or `fuse.js`) for docs Cmd-K search.

**Auth integration:** Login and "Start Free Trial" buttons link to the existing app's URL (configurable via `lib/config.ts`). No auth logic in the marketing site itself.

**SEO:** Each page has proper metadata (title, description, Open Graph tags). Sitemap generated at build. All marketing pages are statically generated.

**Responsive:** Mobile-first Tailwind. Navbar collapses to hamburger. Docs sidebar becomes a drawer. Feature grids stack vertically. Pricing cards stack on mobile.

## Out of Scope

- Blog (deferred — no bandwidth to maintain)
- API reference (closed source product)
- GitHub links
- User authentication (handled by existing app)
- Payment processing (handled separately)
- Indian equity/NSE/BSE references (crypto only)
- Internationalization
