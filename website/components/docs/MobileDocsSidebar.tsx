"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { DocsSidebar } from "./DocsSidebar";
import { SearchDialog } from "./SearchDialog";

export function MobileDocsSidebar() {
  const [open, setOpen] = useState(false);

  return (
    <div className="md:hidden mb-4">
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 rounded-lg border border-brand-indigo/10 bg-brand-indigo/5 px-3 py-2 text-sm text-slate-muted"
        aria-label="Open docs navigation"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M2 4h12M2 8h12M2 12h12" strokeLinecap="round" />
        </svg>
        Navigation
      </button>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-black/60"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
            />
            <motion.aside
              className="fixed left-0 top-0 z-50 h-full w-72 overflow-y-auto bg-brand-bg border-r border-brand-indigo/10 p-6"
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "tween", duration: 0.25 }}
            >
              <div className="flex justify-between items-center mb-6">
                <span className="text-sm font-semibold text-slate-heading">Docs</span>
                <button
                  onClick={() => setOpen(false)}
                  className="text-slate-muted hover:text-slate-body"
                  aria-label="Close navigation"
                >
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M4 4l10 10M14 4L4 14" strokeLinecap="round" />
                  </svg>
                </button>
              </div>
              <div className="space-y-6">
                <SearchDialog />
                <DocsSidebar />
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
