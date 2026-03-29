import type { Metadata } from "next";
import { DocsSidebar } from "@/components/docs/DocsSidebar";
import { SearchDialog } from "@/components/docs/SearchDialog";
import { MobileDocsSidebar } from "@/components/docs/MobileDocsSidebar";

export const metadata: Metadata = {
  title: {
    default: "Docs",
    template: "%s | Algomatter Docs",
  },
};

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <MobileDocsSidebar />
      <div className="flex gap-8">
        <aside className="hidden w-56 shrink-0 md:block">
          <div className="sticky top-24 space-y-6">
            <SearchDialog />
            <DocsSidebar />
          </div>
        </aside>
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
