"use client";

import { useState, useRef, type ComponentPropsWithoutRef } from "react";

export function CodeBlock(props: ComponentPropsWithoutRef<"pre">) {
  const [copied, setCopied] = useState(false);
  const preRef = useRef<HTMLPreElement>(null);

  function handleCopy() {
    const text = preRef.current?.textContent ?? "";
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="relative group mb-4">
      <pre
        ref={preRef}
        className="rounded-lg bg-[#0a0a1a] p-4 overflow-x-auto text-xs leading-relaxed [&>code]:bg-transparent [&>code]:p-0 [&>code]:text-slate-body"
        {...props}
      />
      <button
        onClick={handleCopy}
        className="absolute right-3 top-3 rounded bg-brand-indigo/20 px-2 py-1 text-xs text-slate-muted hover:text-slate-body opacity-0 group-hover:opacity-100 transition-opacity"
        aria-label="Copy code"
      >
        {copied ? "Copied!" : "Copy"}
      </button>
    </div>
  );
}
