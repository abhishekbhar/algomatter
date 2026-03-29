import type { Metadata } from "next";
import { PricingContent } from "@/components/pricing/PricingContent";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Simple, transparent pricing for Algomatter. Start with a 14-day free trial.",
};

export default function PricingPage() {
  return <PricingContent />;
}
