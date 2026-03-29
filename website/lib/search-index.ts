import { docsManifest } from "./docs-manifest";

export interface SearchResult {
  title: string;
  slug: string;
  section: string;
  snippet?: string;
}

// Flatten manifest for search
export const allSearchableDocs: SearchResult[] = docsManifest.flatMap((section) =>
  section.entries.map((entry) => ({
    title: entry.title,
    slug: entry.slug,
    section: section.title,
  }))
);
