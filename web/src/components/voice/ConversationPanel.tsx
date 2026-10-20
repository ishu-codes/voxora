"use client";

import { MessageSquareIcon, Trash2Icon, XIcon } from "lucide-react";
import { useState } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ui/conversation";
import { Message, MessageContent } from "@/components/ui/message";
import { SidebarHeader, SidebarTrigger } from "@/components/ui/sidebar";
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
}: ConversationPanelProps) {
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const trackedTurns = diagnostics.length;
  const thinking = agentState === "thinking" && messages.at(-1)?.role === "user";

  return (
    <div className="flex h-full min-h-0 flex-col bg-sidebar">
      <SidebarHeader className="h-[85px] shrink-0 flex-row items-center justify-between gap-3 border-b border-border bg-sidebar px-4 py-0">
        <div className="min-w-0">
          <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground">Conversation</p>
          <h2 className="mt-1 truncate text-lg font-semibold tracking-tight">
            {status === "connected" ? "Live transcript" : "Session transcript"}
          </h2>
        </div>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => setClearConfirmOpen(true)}
            disabled={messages.length === 0}
            aria-label="Clear conversation"
            title="Clear conversation"
          >
            <Trash2Icon />
          </Button>
          <SidebarTrigger className="size-8 text-muted-foreground" aria-label="Toggle conversation sidebar">
            <XIcon className="size-4" />
            <span className="sr-only">Toggle conversation sidebar</span>
          </SidebarTrigger>
        </div>
      </SidebarHeader>

      <AlertDialog open={clearConfirmOpen} onOpenChange={setClearConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Clear conversation history?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes the transcript and latency summary from the current session. Chat history is kept only in
              this browser tab and is automatically deleted when you close the tab.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                onClear();
                setClearConfirmOpen(false);
              }}
            >
              Clear history
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

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
                <Message key={message.id} from={message.role} className="py-2.5">
                  <MessageContent
                    variant="contained"
                    className={cn(
                      "max-w-[92%] whitespace-pre-wrap break-words",
                      isUser ? "bg-primary text-primary-foreground" : "bg-secondary text-foreground",
                      message.interrupted && "opacity-70",
                      message.failed && "ring-1 ring-destructive/40",
                    )}
                  >
                    <span
                      className={cn(
                        "font-mono text-[10px] uppercase tracking-[0.2em]",
                        isUser ? "text-primary-foreground/70" : "text-muted-foreground",
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

      {/*<footer className="border-t border-border px-4 py-3">
        <div className="flex gap-2 justify-between text-center font-mono text-[10px] tracking-[0.15em] text-muted-foreground">
          <div>
            <div className="text-sm text-foreground tabular-nums">
              {trackedTurns}
            </div>
            <span className="text-[10px] uppercase">turns</span>
          </div>
          <div>
            <div className="text-sm text-foreground tabular-nums">
              {formatMs(summary.firstPlaybackP50)}
            </div>
            <span className="text-[10px] uppercase">first audio p50</span>
          </div>
          <div>
            <div className="text-sm text-foreground tabular-nums">
              {formatMs(summary.bargeInP95)}
            </div>
            <span className="text-[10px] uppercase">barge-in p95</span>
          </div>
        </div>

        {diagnostics.length > 0 ? (
          <div className="mt-3 flex items-center justify-between text-[10px] text-muted-foreground">
            <span>Recent turns</span>
            <span className="font-mono tabular-nums">p95 {formatMs(summary.firstPlaybackP95)}</span>
          </div>
        ) : null}
      </footer>*/}
    </div>
  );
}
