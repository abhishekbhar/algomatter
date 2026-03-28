import { Hero } from "@/components/home/Hero";
import { ExchangeBar } from "@/components/home/ExchangeBar";
import { HowItWorks } from "@/components/home/HowItWorks";
import { Features } from "@/components/home/Features";

export default function HomePage() {
  return (
    <main>
      <Hero />
      <ExchangeBar />
      <HowItWorks />
      <div className="mx-6 h-px bg-gradient-to-r from-transparent via-brand-indigo/20 to-transparent" />
      <Features />
    </main>
  );
}
