"use client";

import {
  BarChart3Icon,
  CheckCircle2Icon,
  FileTextIcon,
  LoaderCircleIcon,
  MessageSquareIcon,
  Trash2Icon,
  XCircleIcon,
  XIcon,
} from "lucide-react";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { TurnMetricRecord } from "@/lib/metrics";
import { cn } from "@/lib/utils";
import type { AgentState, ConnectionStatus } from "@/voice/protocol";
import type { BankToolLogEntry, VoiceMessage } from "@/voice/useVoiceSession";
import { TTFAMetricsPanel } from "./TTFAMetricsPanel";

type ConversationPanelProps = {
  messages: VoiceMessage[];
  agentState: AgentState;
  status: ConnectionStatus;
  ttfaRecords: TurnMetricRecord[];
  bankStatus: "checking" | "idle";
  bankToolLog: BankToolLogEntry[];
  bankDocsUsed: string[];
  onClear: () => void;
  onResetMetrics: () => void;
};

export function ConversationPanel({
  messages,
  agentState,
  status,
  ttfaRecords,
  bankStatus,
  bankToolLog,
  bankDocsUsed,
  onClear,
  onResetMetrics,
}: ConversationPanelProps) {
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [tab, setTab] = useState<"chat" | "stats">("chat");
  const showStats = tab === "stats";
  const thinking =
    agentState === "thinking" && messages.at(-1)?.role === "user";

  return (
    <div className="flex h-full min-h-0 flex-col bg-sidebar">
      <SidebarHeader className="h-21.25 shrink-0 flex-row items-center justify-between gap-3 border-b border-border bg-sidebar px-4 py-0">
        <div className="min-w-0">
          <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
            {showStats ? "Session stats" : "Conversation"}
          </p>
          <h2 className="mt-1 truncate text-lg font-semibold tracking-tight">
            {showStats
              ? "Latency breakdown"
              : status === "connected"
                ? "Live transcript"
                : "Session transcript"}
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
          <SidebarTrigger
            className="size-8 text-muted-foreground"
            aria-label="Toggle conversation sidebar"
          >
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
              This removes the transcript and latency summary from the current
              session. Chat history is kept only in this browser tab and is
              automatically deleted when you close the tab.
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

      <Tabs
        value={tab}
        onValueChange={(value) => setTab(value === "stats" ? "stats" : "chat")}
        className="min-h-0 flex-1 gap-0"
      >
        <TabsList className="mx-4 mt-3 grid w-[calc(100%-2rem)] grid-cols-2">
          <TabsTrigger value="chat">
            <MessageSquareIcon />
            Chat
          </TabsTrigger>
          <TabsTrigger value="stats">
            <BarChart3Icon />
            Stats
          </TabsTrigger>
        </TabsList>

        <TabsContent
          value="chat"
          className="flex flex-col data-[hidden]:hidden"
        >
          {bankStatus === "checking" || bankDocsUsed.length ? (
            <div className="mx-4 mt-3 flex items-start gap-2 rounded-xl bg-muted/50 px-3 py-2.5 text-xs">
              {bankStatus === "checking" ? (
                <LoaderCircleIcon className="mt-0.5 size-3.5 shrink-0 animate-spin text-brand-text" />
              ) : (
                <FileTextIcon className="mt-0.5 size-3.5 shrink-0 text-brand-text" />
              )}
              <div className="min-w-0">
                <p className="font-medium">
                  {bankStatus === "checking"
                    ? "Checking Demo Bank documents"
                    : "Documents used for the answer"}
                </p>
                {bankDocsUsed.length ? (
                  <p className="mt-0.5 break-words text-muted-foreground">
                    {bankDocsUsed.join(", ")}
                  </p>
                ) : null}
              </div>
            </div>
          ) : null}
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

                {bankToolLog.length ? (
                  <section
                    aria-label="Document tool log"
                    className="mt-4 border-t border-border pt-3"
                  >
                    <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                      Document tool log
                    </p>
                    <ol className="mt-2 space-y-2">
                      {bankToolLog.slice(-8).map((entry) => (
                        <li
                          key={entry.id}
                          className="flex items-start gap-2 text-xs"
                        >
                          {entry.status === "running" ? (
                            <LoaderCircleIcon className="mt-0.5 size-3.5 shrink-0 animate-spin text-brand-text" />
                          ) : entry.status === "ok" ? (
                            <CheckCircle2Icon className="mt-0.5 size-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                          ) : (
                            <XCircleIcon className="mt-0.5 size-3.5 shrink-0 text-destructive" />
                          )}
                          <span className="min-w-0">
                            <span className="font-medium">
                              {entry.tool === "read_doc"
                                ? entry.arguments.name
                                : "Document list"}
                            </span>
                            <span className="block text-muted-foreground">
                              {entry.status === "running"
                                ? "Looking up"
                                : entry.status === "ok"
                                  ? entry.documents.length
                                    ? `Found ${entry.documents.join(", ")}`
                                    : "Lookup completed"
                                  : "Lookup failed"}
                            </span>
                          </span>
                        </li>
                      ))}
                    </ol>
                  </section>
                ) : null}
              </ConversationContent>
              <ConversationScrollButton />
            </Conversation>
          )}
        </TabsContent>

        <TabsContent value="stats" className="overflow-y-auto">
          <TTFAMetricsPanel records={ttfaRecords} onReset={onResetMetrics} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
