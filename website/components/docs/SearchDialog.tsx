"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Index as FlexIndex } from "flexsearch";
import { docsManifest } from "@/lib/docs-manifest";

interface SearchableDoc {
  title: string;
  slug: string;
  section: string;
}

const allDocs: SearchableDoc[] = docsManifest.flatMap((section) =>
  section.entries.map((entry) => ({
    ...entry,
    section: section.title,
  }))
);

export function SearchDialog() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchableDoc[]>(allDocs);
  const router = useRouter();
  const indexRef = useRef<FlexIndex | null>(null);

  // Build flexsearch index on mount
  useEffect(() => {
    const index = new FlexIndex({
      tokenize: "forward",
      resolution: 9,
    });
    allDocs.forEach((doc, i) => {
      index.add(i, `${doc.title} ${doc.section}`);
    });
    indexRef.current = index;
  }, []);

  useEffect(() => {
    if (!query.trim()) {
      setResults(allDocs);
      return;
    }
    if (!indexRef.current) {
      // Fallback to simple filter if index not ready
      setResults(
        allDocs.filter(
          (d) =>
            d.title.toLowerCase().includes(query.toLowerCase()) ||
            d.section.toLowerCase().includes(query.toLowerCase())
        )
      );
      return;
    }
    const ids = indexRef.current.search(query, { limit: 10 });
    setResults(ids.map((id) => allDocs[id as number]));
  }, [query]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      setOpen((prev) => !prev);
    }
    if (e.key === "Escape") setOpen(false);
  }, []);

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
                {results.length === 0 ? (
                  <p className="px-3 py-4 text-sm text-slate-muted text-center">
                    No results found
                  </p>
                ) : (
                  results.map((doc) => (
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
