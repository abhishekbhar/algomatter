import { Hero } from "@/components/home/Hero";
import { ExchangeBar } from "@/components/home/ExchangeBar";
import { HowItWorks } from "@/components/home/HowItWorks";
import { Features } from "@/components/home/Features";
import { PlatformStats } from "@/components/home/PlatformStats";
import { Testimonials } from "@/components/home/Testimonials";
import { FinalCTA } from "@/components/home/FinalCTA";

function Divider() {
  return (
    <div className="mx-6 h-px bg-gradient-to-r from-transparent via-brand-indigo/20 to-transparent" />
  );
}

export default function HomePage() {
  return (
    <main>
      <Hero />
      <ExchangeBar />
      <HowItWorks />
      <Divider />
      <Features />
      <Divider />
      <PlatformStats />
      <Divider />
      <Testimonials />
      <Divider />
      <FinalCTA />
    </main>
  );
}
