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
