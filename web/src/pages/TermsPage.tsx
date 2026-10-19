import { ArrowLeft, FileText } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { DashedPanel } from "@/components/marketing/DashedPanel";

export default function TermsPage() {
  return (
    <div className="min-h-dvh bg-background py-12">
      <div className="container max-w-3xl">
        <div className="mb-8 flex items-center justify-between">
          <Button variant="ghost" size="sm" asChild className="gap-2">
            <Link to="/">
              <ArrowLeft className="size-4" /> Back to home
            </Link>
          </Button>
          <div className="flex size-10 items-center justify-center bg-brand/10 text-brand-text ring-1 ring-brand/20">
            <FileText className="size-5" />
          </div>
        </div>

        <DashedPanel className="bg-card p-8 sm:p-12">
          <div className="space-y-10">
            <header className="space-y-3">
              <h1 className="text-3xl font-semibold tracking-tight">Terms of service</h1>
              <p className="font-mono text-xs text-muted-foreground">Effective date: October 19, 2026</p>
            </header>

            <section className="space-y-3">
              <h2 className="text-lg font-semibold tracking-tight">1. The service</h2>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Voxora is a reference implementation of a streaming voice pipeline. It streams microphone
                audio through speech recognition, a language model and speech synthesis. By using the
                demo you agree to these terms.
              </p>
            </section>

            <section className="space-y-3">
              <h2 className="text-lg font-semibold tracking-tight">2. Acceptable use</h2>
              <div className="space-y-2 border border-border bg-muted/20 p-4">
                <p className="text-sm font-semibold text-foreground">You agree to:</p>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  Use your own provider credentials where required, avoid sending audio you have no right
                  to process, and not use the service for unlawful material. Model output is generated
                  automatically and may be inaccurate.
                </p>
              </div>
            </section>

            <section className="space-y-3">
              <h2 className="text-lg font-semibold tracking-tight">3. Self-hosted deployments</h2>
              <ul className="list-disc space-y-3 pl-5 text-sm leading-relaxed text-muted-foreground">
                <li>You are responsible for the models and providers you configure.</li>
                <li>Provider usage is billed by that provider, not by Voxora.</li>
                <li>Resource limits, authentication and rate limiting are yours to add before public use.</li>
              </ul>
            </section>

            <section className="space-y-3">
              <h2 className="text-lg font-semibold tracking-tight">4. Availability</h2>
              <p className="text-sm leading-relaxed text-muted-foreground italic">
                The software is provided "as is" without warranties. Latency targets are engineering
                goals, not guarantees: actual first-audio latency depends on your network, hardware and
                chosen models.
              </p>
            </section>

            <footer className="border-t pt-6">
              <p className="text-center text-xs text-muted-foreground">Voxora terms of service v1.0</p>
            </footer>
          </div>
        </DashedPanel>
      </div>
    </div>
  );
}
