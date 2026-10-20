import { Capabilities } from "@/components/marketing/Capabilities";
import { Deployment } from "@/components/marketing/Deployment";
import { FAQSection } from "@/components/marketing/FAQSection";
import { Footer } from "@/components/marketing/Footer";
import { Hero } from "@/components/marketing/Hero";
import { LatencyStats } from "@/components/marketing/LatencyStats";
import { Navbar } from "@/components/marketing/Navbar";
import { PipelineSection } from "@/components/marketing/PipelineSection";
import { SecondaryCTA } from "@/components/marketing/SecondaryCTA";
import { StackSection } from "@/components/marketing/StackSection";
import { StreamingSection } from "@/components/marketing/StreamingSection";

export default function Home() {
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
