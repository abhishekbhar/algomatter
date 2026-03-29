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
