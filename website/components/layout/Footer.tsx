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
