import { Navbar } from "@/components/navbar";
import { Hero } from "@/components/marketing/Hero";
import { PipelineSection } from "@/components/marketing/PipelineSection";
import { StreamingSection } from "@/components/marketing/StreamingSection";
import { Capabilities } from "@/components/marketing/Capabilities";
import { Deployment } from "@/components/marketing/Deployment";
import { LatencyStats } from "@/components/marketing/LatencyStats";
import { FAQSection } from "@/components/marketing/FAQSection";
import { StackSection } from "@/components/marketing/StackSection";
import { SecondaryCTA } from "@/components/marketing/SecondaryCTA";
import { Footer } from "@/components/marketing/Footer";

export default function LandingPage() {
  return (
    <div className="flex min-h-dvh flex-col overflow-x-clip bg-background text-foreground">
      <Navbar />
      <main className="flex-1">
        <Hero />
        <PipelineSection />
        <StreamingSection />
        <Capabilities />
        <Deployment />
        <LatencyStats />
        <FAQSection />
        <StackSection />
        <SecondaryCTA />
      </main>
      <Footer />
    </div>
  );
}
