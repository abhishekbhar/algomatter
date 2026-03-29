import { notFound } from "next/navigation";
import { MDXRemote } from "next-mdx-remote/rsc";
import { getDocBySlug } from "@/lib/mdx";
import { getAllDocSlugs, findAdjacentDocs } from "@/lib/docs-manifest";
import { mdxComponents } from "@/components/docs/MDXComponents";
import Link from "next/link";

interface PageProps {
  params: Promise<{ slug?: string[] }>;
}

export async function generateStaticParams() {
  const slugs = getAllDocSlugs();
  return [
    { slug: undefined }, // /docs index
    ...slugs.map((s) => ({ slug: s.split("/") })),
  ];
}

export default async function DocPage({ params }: PageProps) {
  const { slug } = await params;

  // /docs index — redirect to quick-start
  if (!slug || slug.length === 0) {
    const doc = await getDocBySlug("getting-started/quick-start");
    if (!doc) notFound();
    const { prev, next } = findAdjacentDocs(doc.slug);
    return (
      <article>
        <MDXRemote source={doc.content} components={mdxComponents} />
        <NavLinks prev={prev} next={next} />
      </article>
    );
  }

  const joinedSlug = slug.join("/");
  const doc = await getDocBySlug(joinedSlug);
  if (!doc) notFound();

  const { prev, next } = findAdjacentDocs(joinedSlug);

  return (
    <article>
      <MDXRemote source={doc.content} components={mdxComponents} />
      <NavLinks prev={prev} next={next} />
    </article>
  );
}

function NavLinks({
  prev,
  next,
}: {
  prev: { title: string; slug: string } | null;
  next: { title: string; slug: string } | null;
}) {
  return (
    <div className="mt-12 flex justify-between border-t border-brand-indigo/10 pt-6 text-sm">
      {prev ? (
        <Link href={`/docs/${prev.slug}`} className="text-brand-lavender hover:underline">
          &larr; {prev.title}
        </Link>
      ) : (
        <span />
      )}
      {next ? (
        <Link href={`/docs/${next.slug}`} className="text-brand-lavender hover:underline">
          {next.title} &rarr;
        </Link>
      ) : (
        <span />
      )}
    </div>
  );
}
