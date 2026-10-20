"use client";

import { MessageSquareIcon, Trash2Icon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ui/conversation";
import { Message, MessageContent } from "@/components/ui/message";
import { cn } from "@/lib/utils";
import type { AgentState, ConnectionStatus } from "@/voice/protocol";
import type { TurnDiagnostics, VoiceMessage } from "@/voice/useVoiceSession";

type Summary = {
  turns: number;
  firstPlaybackP50: number | null;
  firstPlaybackP95: number | null;
  bargeInP95: number | null;
};

type ConversationPanelProps = {
  messages: VoiceMessage[];
  agentState: AgentState;
  status: ConnectionStatus;
  diagnostics: TurnDiagnostics[];
  summary: Summary;
  onClear: () => void;
  onClose: () => void;
};

function formatMs(value: number | null) {
  return value == null ? "—" : `${Math.round(value)} ms`;
}

export function ConversationPanel({
  messages,
  agentState,
  status,
  diagnostics,
  summary,
  onClear,
  onClose,
}: ConversationPanelProps) {
  const thinking =
    agentState === "thinking" && messages.at(-1)?.role === "user";

  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <header className="flex items-start justify-between gap-3 border-b border-border px-4 py-4">
        <div className="min-w-0">
          <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
            Conversation
          </p>
          <h2 className="mt-1 truncate text-lg font-semibold tracking-tight">
            {status === "connected" ? "Live transcript" : "Session transcript"}
          </h2>
        </div>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={onClear}
            disabled={messages.length === 0}
            aria-label="Clear conversation"
            title="Clear conversation"
          >
            <Trash2Icon />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            aria-label="Close conversation"
          >
            <XIcon />
          </Button>
        </div>
      </header>

      {messages.length === 0 ? (
        <ConversationEmptyState
          className="flex-1"
          icon={<MessageSquareIcon className="size-8" />}
          title="No conversation yet"
          description="Start a session and speak. Partial transcripts appear here as they stream."
        />
      ) : (
        <Conversation>
          <ConversationContent className="flex flex-col gap-0">
            {messages.map((message) => {
              const isUser = message.role === "user";
              const streaming = !message.final;

              return (
                <Message
                  key={message.id}
                  from={message.role}
                  className="py-2.5"
                >
                  <MessageContent
                    variant="contained"
                    className={cn(
                      "max-w-[92%] whitespace-pre-wrap break-words",
                      isUser
                        ? "bg-primary text-primary-foreground"
                        : "bg-secondary text-foreground",
                      message.interrupted && "opacity-70",
                      message.failed && "ring-1 ring-destructive/40",
                    )}
                  >
                    <span
                      className={cn(
                        "font-mono text-[10px] uppercase tracking-[0.2em]",
                        isUser
                          ? "text-primary-foreground/70"
                          : "text-muted-foreground",
                      )}
                    >
                      {isUser ? "You" : "Voxora"}
                      {streaming ? " · streaming" : ""}
                      {message.interrupted ? " · interrupted" : ""}
                      {message.failed ? " · failed" : ""}
                    </span>
                    <span>
                      {message.text || (streaming ? "…" : "")}
                      {!isUser && streaming ? (
                        <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-current align-middle" />
                      ) : null}
                    </span>
                  </MessageContent>
                </Message>
              );
            })}

            {thinking ? (
              <div className="flex items-center gap-2 px-1 py-3 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                <span className="size-1.5 animate-pulse rounded-full bg-brand-text" />
                thinking
              </div>
            ) : null}
          </ConversationContent>
          <ConversationScrollButton />
        </Conversation>
      )}

      <footer className="border-t border-border px-4 py-3">
        <div className="grid grid-cols-3 gap-2 text-center font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
          <div>
            <div className="text-sm text-foreground tabular-nums">
              {summary.turns}
            </div>
            turns
          </div>
          <div>
            <div className="text-sm text-foreground tabular-nums">
              {formatMs(summary.firstPlaybackP50)}
            </div>
            first audio p50
          </div>
          <div>
            <div className="text-sm text-foreground tabular-nums">
              {formatMs(summary.bargeInP95)}
            </div>
            barge-in p95
          </div>
        </div>
        {diagnostics.length > 0 ? (
          <div className="mt-3 flex items-center justify-between text-[10px] text-muted-foreground">
            <span>Recent turns</span>
            <span className="font-mono tabular-nums">
              p95 {formatMs(summary.firstPlaybackP95)}
            </span>
          </div>
        ) : null}
      </footer>
    </div>
  );
}
