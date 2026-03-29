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
