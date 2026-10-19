import { Mic, MicOff, PhoneOff, Square } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentState, ConnectionStatus } from "@/voice/protocol";

type MicOrbProps = {
  status: ConnectionStatus;
  agentState: AgentState;
  level: number;
  muted: boolean;
  onStart: () => void;
  onEnd: () => void;
  onInterrupt: () => void;
  onToggleMute: () => void;
};

const STATE_LABEL: Record<AgentState, string> = {
  idle: "Ready when you are",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
  error: "Something went wrong",
};

const STATE_COPY: Record<AgentState, string> = {
  idle: "Press start and speak naturally.",
  listening: "Speak naturally — Voxora is capturing your voice.",
  thinking: "Generating a response as your words arrive.",
  speaking: "Answer streaming — speak any time to interrupt.",
  error: "Retry the session to reconnect.",
};

export function MicOrb({
  status,
  agentState,
  level,
  muted,
  onStart,
  onEnd,
  onInterrupt,
  onToggleMute,
}: MicOrbProps) {
  const live = status === "connected" || status === "reconnecting" || status === "connecting";
  const active = live && agentState !== "idle";
  const pulse = Math.min(1, Math.max(0, level * 6));

  return (
    <div className="flex flex-col items-center gap-6">
      <div className="relative grid size-[176px] place-items-center">
        {/* Level halo */}
        <span
          className={cn(
            "absolute inset-0 rounded-full border border-brand/40 transition-opacity duration-150",
            active ? "opacity-100" : "opacity-0",
          )}
          style={{ transform: `scale(${1 + pulse * 0.22})`, opacity: active ? 0.25 + pulse * 0.5 : 0 }}
          aria-hidden="true"
        />
        <span
          className={cn(
            "absolute inset-4 rounded-full border border-border",
            agentState === "speaking" && "animate-pulse border-brand/60",
            agentState === "thinking" && "border-brand/40",
          )}
          aria-hidden="true"
        />

        <button
          type="button"
          onClick={!live ? onStart : agentState === "speaking" ? onInterrupt : onEnd}
          disabled={status === "connecting"}
          aria-label={
            !live
              ? "Start conversation"
              : agentState === "speaking"
                ? "Interrupt response"
                : "End conversation"
          }
          className={cn(
            "relative grid size-[128px] place-items-center rounded-full border transition-all duration-300",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            !live
              ? "border-brand/50 bg-brand text-brand-foreground hover:bg-brand/85"
              : agentState === "speaking"
                ? "border-brand bg-background text-brand-text hover:bg-brand/10"
                : "border-border bg-card text-foreground hover:bg-muted/50",
            status === "connecting" && "opacity-70",
          )}
        >
          {!live ? (
            <Mic className="size-10" />
          ) : agentState === "speaking" ? (
            <Square className="size-9 fill-current" />
          ) : (
            <MicOff className="size-10" />
          )}
        </button>
      </div>

      <div className="space-y-1 text-center">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-muted-foreground">
          {status === "connecting"
            ? "Connecting"
            : status === "reconnecting"
              ? "Reconnecting"
              : status === "error"
                ? "Offline"
                : STATE_LABEL[agentState]}
        </p>
        <p className="max-w-xs text-sm text-muted-foreground">{STATE_COPY[agentState]}</p>
      </div>

      {live && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onToggleMute}
            className={cn(
              "rounded-[100px] border px-4 py-2 font-mono text-xs uppercase tracking-widest transition-colors",
              muted
                ? "border-destructive/40 bg-destructive/10 text-destructive"
                : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {muted ? "Muted" : "Mute mic"}
          </button>
          <button
            type="button"
            onClick={onEnd}
            className="inline-flex items-center gap-2 rounded-[100px] border border-border px-4 py-2 font-mono text-xs uppercase tracking-widest text-muted-foreground transition-colors hover:border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
          >
            <PhoneOff className="size-3.5" /> End
          </button>
        </div>
      )}
    </div>
  );
}
