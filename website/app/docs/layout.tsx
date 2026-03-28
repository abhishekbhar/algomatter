import type { Metadata } from "next";
import { DocsSidebar } from "@/components/docs/DocsSidebar";
import { SearchDialog } from "@/components/docs/SearchDialog";

export const metadata: Metadata = {
  title: {
    default: "Docs",
    template: "%s | Algomatter Docs",
  },
};

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto flex max-w-6xl gap-8 px-6 py-12">
      <aside className="hidden w-56 shrink-0 md:block">
        <div className="sticky top-24 space-y-6">
          <SearchDialog />
          <DocsSidebar />
        </div>
      </aside>
      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}
