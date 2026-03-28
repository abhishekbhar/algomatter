import type { MetadataRoute } from "next";
import { siteConfig } from "@/lib/config";
import { getAllDocSlugs } from "@/lib/docs-manifest";

export default function sitemap(): MetadataRoute.Sitemap {
  const staticPages = [
    "",
    "/features",
    "/pricing",
    "/about",
    "/changelog",
    "/docs",
  ];

  const docPages = getAllDocSlugs().map((slug) => `/docs/${slug}`);

  return [...staticPages, ...docPages].map((route) => ({
    url: `${siteConfig.url}${route}`,
    lastModified: new Date(),
    changeFrequency: route === "" ? "weekly" : "monthly",
    priority: route === "" ? 1 : 0.8,
  }));
}
