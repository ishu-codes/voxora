import { useState } from "react";
import { Link } from "react-router-dom";
import { Activity, AlertTriangle, ArrowLeft, X } from "lucide-react";

import { Wordmark } from "@/components/marketing/Wordmark";
import { ThemeToggle } from "@/components/navbar/ThemeToggle";
import { Diagnostics } from "@/components/voice/Diagnostics";
import { MicOrb } from "@/components/voice/MicOrb";
import { Transcript } from "@/components/voice/Transcript";
import { useVoiceSession } from "@/voice/useVoiceSession";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  idle: "border-border text-muted-foreground",
  connecting: "border-brand/40 text-brand-text",
  connected: "border-emerald-500/40 text-emerald-400",
  reconnecting: "border-warning/40 text-warning",
  error: "border-destructive/40 text-destructive",
};

export default function VoicePage() {
  const session = useVoiceSession();
  const [showDiagnostics, setShowDiagnostics] = useState(false);

  const statusLabel =
    session.status === "connected"
      ? "live"
      : session.status === "connecting"
        ? "connecting"
        : session.status;

  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground">
      <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur">
        <div className="container flex h-[64px] items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground">
              <ArrowLeft className="size-4" />
              <Wordmark size="md" />
            </Link>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "inline-flex items-center gap-2 rounded-[100px] border px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.2em]",
                STATUS_STYLES[session.status] ?? STATUS_STYLES.idle,
              )}
            >
              <span className="size-1.5 rounded-full bg-current" />
              {statusLabel}
            </span>
            <button
              type="button"
              onClick={() => setShowDiagnostics((value) => !value)}
              className="inline-flex items-center gap-2 rounded-[100px] border border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-pressed={showDiagnostics}
            >
              <Activity className="size-3.5" /> Latency
            </button>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {session.error && (
        <div className="border-b border-destructive/30 bg-destructive/10">
          <div className="container flex items-center justify-between gap-4 py-2.5 text-sm text-destructive">
            <span className="flex items-center gap-2">
              <AlertTriangle className="size-4" /> {session.error}
            </span>
            <button
              type="button"
              onClick={session.dismissError}
              className="text-destructive/70 hover:text-destructive"
              aria-label="Dismiss error"
            >
              <X className="size-4" />
            </button>
          </div>
        </div>
      )}

      <div className="flex flex-1 flex-col lg:flex-row">
        <main className="flex min-h-0 flex-1 flex-col">
          <div className="flex-1 overflow-y-auto">
            <Transcript messages={session.messages} agentState={session.agentState} />
          </div>

          <div className="border-t border-border bg-card/40">
            <div className="container flex flex-col items-center gap-6 py-8">
              <MicOrb
                status={session.status}
                agentState={session.agentState}
                level={session.level}
                muted={session.muted}
                onStart={() => void session.start()}
                onEnd={() => void session.stop()}
                onInterrupt={session.interrupt}
                onToggleMute={session.toggleMute}
              />
            </div>
          </div>
        </main>

        {showDiagnostics && (
          <button
            type="button"
            aria-label="Close diagnostics"
            onClick={() => setShowDiagnostics(false)}
            className="fixed inset-0 z-30 bg-background/60 lg:hidden"
          />
        )}

        <aside
          className={cn(
            "z-40 w-full border-border bg-card lg:static lg:z-auto lg:w-[340px] lg:border-l",
            showDiagnostics
              ? "fixed inset-y-0 right-0 flex max-w-[90vw] flex-col shadow-2xl lg:static lg:max-w-none lg:shadow-none"
              : "hidden lg:flex",
          )}
        >
          <Diagnostics
            status={session.status}
            ready={session.ready}
            summary={session.summary}
            diagnostics={session.diagnostics}
          />
        </aside>
      </div>
    </div>
  );
}
