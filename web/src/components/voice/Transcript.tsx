import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import type { VoiceMessage } from "@/voice/useVoiceSession";

export function Transcript({ messages, agentState }: { messages: VoiceMessage[]; agentState: string }) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-muted-foreground">
          Transcript
        </p>
        <p className="max-w-sm text-sm text-muted-foreground">
          Your words and Voxora&apos;s replies appear here as they stream. Partial transcripts
          update in place until the turn settles.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 px-4 py-6 sm:px-8">
      {messages.map((message) => {
        const isUser = message.role === "user";
        const streaming = !message.final;
        return (
          <article
            key={message.id}
            className={cn(
              "flex max-w-[85%] flex-col gap-1.5",
              isUser ? "self-end items-end" : "self-start items-start",
            )}
          >
            <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              {isUser ? "You" : "Voxora"}
              {streaming && <span className="ml-2 text-brand-text">streaming</span>}
              {message.interrupted && <span className="ml-2 text-warning">interrupted</span>}
              {message.failed && <span className="ml-2 text-destructive">failed</span>}
            </span>
            <div
              className={cn(
                "whitespace-pre-wrap border px-4 py-3 text-sm leading-relaxed sm:text-[15px]",
                isUser
                  ? "border-border bg-muted/40 text-foreground"
                  : "bg-card text-foreground",
                !isUser && "border-brand/25",
                message.interrupted && "opacity-70",
              )}
            >
              {message.text || (streaming ? "…" : "")}
              {!isUser && streaming && (
                <span className="ml-0.5 inline-block h-4 w-1.5 translate-y-0.5 animate-pulse bg-brand-text" />
              )}
            </div>
          </article>
        );
      })}
      {agentState === "thinking" && messages.at(-1)?.role === "user" && (
        <div className="self-start font-mono text-xs text-muted-foreground">[thinking]</div>
      )}
      <div ref={endRef} />
    </div>
  );
}
