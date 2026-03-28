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
