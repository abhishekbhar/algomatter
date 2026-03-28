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
