import { ArrowLeft, Shield } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { DashedPanel } from "@/components/marketing/DashedPanel";

export default function PrivacyPage() {
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
            <Shield className="size-5" />
          </div>
        </div>

        <DashedPanel className="bg-card p-8 sm:p-12">
          <div className="space-y-10">
            <header className="space-y-3">
              <h1 className="text-3xl font-semibold tracking-tight">Privacy policy</h1>
              <p className="font-mono text-xs text-muted-foreground">Last updated: October 19, 2026</p>
            </header>

            <section className="space-y-3">
              <h2 className="text-lg font-semibold tracking-tight">1. Overview</h2>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Voxora is a real-time voice agent. This policy describes what happens to your
                microphone audio, transcripts and conversation history when you use the studio.
              </p>
            </section>

            <section className="space-y-3">
              <h2 className="text-lg font-semibold tracking-tight">2. Microphone audio</h2>
              <ul className="list-disc space-y-3 pl-5 text-sm leading-relaxed text-muted-foreground">
                <li>
                  <span className="font-semibold text-foreground">Access:</span> the microphone is only
                  requested after you start a session, and it stops when you end it.
                </li>
                <li>
                  <span className="font-semibold text-foreground">Streaming:</span> 20 ms PCM frames are
                  sent to your configured backend so it can detect your turn and transcribe it.
                </li>
                <li>
                  <span className="font-semibold text-foreground">Retention:</span> raw audio is held in
                  memory only for the duration of the current utterance and is discarded once the turn is
                  transcribed. It is not written to disk by default.
                </li>
              </ul>
            </section>

            <section className="space-y-3">
              <h2 className="text-lg font-semibold tracking-tight">3. Transcripts and history</h2>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Conversation history lives in memory for the lifetime of the connection and is used to
                answer follow-up questions. The browser keeps its own copy for display. Deleting the
                session or ending the conversation clears both.
              </p>
            </section>

            <section className="space-y-3">
              <h2 className="text-lg font-semibold tracking-tight">4. Third-party models</h2>
              <p className="border-l-2 border-brand pl-4 text-sm leading-relaxed text-muted-foreground italic">
                If you configure hosted speech recognition, a hosted language model or hosted speech
                synthesis, the relevant audio or text is sent to that provider under your own account.
                Provider credentials are stored only on the server and are never exposed to the browser.
              </p>
            </section>

            <section className="space-y-3">
              <h2 className="text-lg font-semibold tracking-tight">5. Metrics and logs</h2>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Per-stage timings and error counts are recorded to measure latency. Metric records contain
                turn identifiers and durations, not transcript text or audio.
              </p>
            </section>

            <footer className="border-t pt-6">
              <p className="text-center text-xs text-muted-foreground">
                Questions about this policy? Open an issue in the project repository.
              </p>
            </footer>
          </div>
        </DashedPanel>
      </div>
    </div>
  );
}
