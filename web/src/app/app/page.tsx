"use client";

import {
  AlertTriangleIcon,
  Loader2Icon,
  MessageSquareIcon,
  MicIcon,
  MicOffIcon,
  PhoneIcon,
  XIcon,
} from "lucide-react";
import { Navbar } from "@/components/navbar/Navbar";
import { BarVisualizer } from "@/components/ui/bar-visualizer";
import { Button } from "@/components/ui/button";
import { Orb } from "@/components/ui/orb";
import {
  Sidebar,
  SidebarInset,
  SidebarProvider,
  useSidebar,
} from "@/components/ui/sidebar";
import { VoicePicker } from "@/components/ui/voice-picker";
import { ConversationPanel } from "@/components/voice/ConversationPanel";
import { QuotaExhaustedAlert } from "@/components/voice/QuotaExhaustedAlert";
import { SessionSetupPicker } from "@/components/voice/SessionSetupPicker";
import { cn } from "@/lib/utils";
import { useVoiceSessionContext } from "@/voice/voice-session-provider";

type VisualizerState = React.ComponentProps<typeof BarVisualizer>["state"];
type OrbVisualizerState = React.ComponentProps<typeof Orb>["agentState"];

function ControlButton({
  label,
  onClick,
  disabled,
  active,
  variant = "outline",
  className,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  active?: boolean;
  variant?: "default" | "outline" | "destructive" | "secondary" | "danger";
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Button
      type="button"
      variant={variant}
      size="icon-lg"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      aria-pressed={active}
      className={cn("rounded-full", className)}
    >
      {children}
    </Button>
  );
}

function ConversationControl() {
  const { open, toggleSidebar } = useSidebar();

  return (
    <ControlButton
      label={open ? "Close conversation" : "Open conversation"}
      onClick={toggleSidebar}
      active={open}
      variant={open ? "secondary" : "outline"}
      className="size-12"
    >
      <MessageSquareIcon className="size-5" />
    </ControlButton>
  );
}

export default function VoiceStudioPage() {
  const session = useVoiceSessionContext();

  const connecting = session.status === "connecting";
  const live =
    session.status === "connected" || session.status === "reconnecting";
  const canHangUp = live || connecting;
  const quotaBlocked =
    session.quotaExhausted != null &&
    session.quotaExhausted.retryAt > Date.now();

  const initializing =
    live && (!session.ready || session.vadStatus === "loading");
  const visualizerState: VisualizerState =
    session.status === "connecting" || session.status === "reconnecting"
      ? "connecting"
      : initializing
        ? "initializing"
        : live && session.agentState === "speaking"
          ? "speaking"
          : live && session.agentState === "thinking"
            ? "thinking"
            : live
              ? "listening"
              : undefined;
  const showBars = visualizerState != null;

  const orbState: OrbVisualizerState =
    visualizerState === "connecting" ||
    visualizerState === "initializing" ||
    visualizerState === "thinking"
      ? "thinking"
      : visualizerState === "speaking"
        ? "talking"
        : visualizerState === "listening"
          ? "listening"
          : null;

  const statusText =
    visualizerState === undefined
      ? session.status === "error"
        ? "Connection error"
        : "Ready"
      : visualizerState === "connecting"
        ? session.status === "reconnecting"
          ? "Reconnecting"
          : "Connecting"
        : visualizerState === "initializing"
          ? "Initializing voice detection"
          : visualizerState === "speaking"
            ? "Voxora is speaking"
            : visualizerState === "thinking"
              ? "Voxora is thinking"
              : session.muted
                ? "Muted"
                : session.agentState === "interrupted"
                  ? "Interrupted"
                  : "Listening";

  return (
    <div className="h-dvh overflow-hidden bg-background text-foreground">
      <SidebarProvider
        defaultOpen={false}
        className="h-full min-h-0 overflow-hidden"
        style={
          {
            "--sidebar-width": "min(24rem, calc(100vw - 1rem))",
          } as React.CSSProperties
        }
      >
        <SidebarInset className="h-full min-h-0 overflow-hidden">
          <Navbar />

          {session.error ? (
            <div className="shrink-0 border-b border-destructive/30 bg-destructive/10">
              <div className="container flex items-center justify-between gap-3 py-2 text-xs text-destructive sm:text-sm">
                <span className="flex min-w-0 items-center gap-2">
                  <AlertTriangleIcon className="size-4 shrink-0" />
                  <span className="truncate">{session.error}</span>
                </span>
                <button
                  type="button"
                  onClick={session.dismissError}
                  aria-label="Dismiss error"
                  className="shrink-0 rounded p-1 transition-colors hover:bg-destructive/10"
                >
                  <XIcon className="size-4" />
                </button>
              </div>
            </div>
          ) : null}

          {session.quotaNoticeVisible ? (
            <QuotaExhaustedAlert
              limit={session.quotaExhausted?.limit ?? 10}
              retryAt={session.quotaExhausted?.retryAt ?? Date.now()}
              onDismiss={session.dismissQuotaNotice}
              onExpired={session.clearQuotaExhausted}
            />
          ) : null}

          <div className="relative flex min-h-0 flex-1">
            <main className="relative flex min-h-0 flex-1 flex-col items-center justify-center overflow-y-auto px-4 py-6">
              <div className="absolute top-4 right-4 z-10 flex flex-col items-end gap-2 sm:top-6 sm:right-6">
                <SessionSetupPicker
                  scenarios={session.scenarios}
                  scenarioId={session.selectedScenarioId}
                  onScenarioChange={session.selectScenario}
                  sttProvider={session.sttProvider}
                  sttChoices={session.sttProviderChoices}
                  onSttProviderChange={session.selectSttProvider}
                  ttsProvider={session.ttsProvider}
                  ttsChoices={session.ttsProviderChoices}
                  onTtsProviderChange={session.selectTtsProvider}
                  disabled={live || connecting}
                />
                <VoicePicker
                  voices={session.voices}
                  value={session.voice}
                  onValueChange={session.selectVoice}
                  disabled={session.voices.length === 0}
                  placeholder="Choose a voice"
                  triggerVariant="ghost"
                  className="h-9 w-auto min-w-[180px] max-w-[240px] rounded-full px-3 text-sm font-normal text-muted-foreground hover:text-foreground"
                />
              </div>

              <div className="flex w-full max-w-xl flex-col items-center gap-5">
                <div className="relative size-65 shrink-0 sm:size-60 lg:size-70 xl:size-80">
                  <Orb
                    agentState={orbState}
                    colors={["#2E1B9C", "#A599E9"]}
                    seed={1234}
                    className="absolute inset-0"
                  />
                </div>

                <div
                  className={cn(
                    "flex h-14 w-full max-w-md items-center justify-center px-4 transition-opacity duration-300",
                    showBars ? "opacity-100" : "opacity-0",
                  )}
                  aria-hidden={!showBars}
                >
                  <BarVisualizer
                    state={visualizerState}
                    mediaStream={session.muted ? null : session.stream}
                    level={session.muted ? 0 : session.level}
                    demo={visualizerState === "speaking"}
                    sensitivity={1.6}
                    barCount={28}
                    centerAlign
                    minHeight={4}
                    maxHeight={56}
                    className="h-14 w-full bg-transparent p-0"
                  />
                </div>

                <output
                  className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground"
                  aria-live="polite"
                >
                  {statusText}
                </output>

                <div className="flex items-center justify-center gap-4">
                  <ControlButton
                    label={session.muted ? "Unmute" : "Mute"}
                    onClick={session.toggleMute}
                    disabled={!live}
                    active={session.muted}
                    variant={session.muted ? "destructive" : "outline"}
                    className="size-12"
                  >
                    {session.muted ? (
                      <MicOffIcon className="size-5" />
                    ) : (
                      <MicIcon className="size-5" />
                    )}
                  </ControlButton>

                  <ControlButton
                    label={
                      quotaBlocked
                        ? "Wait for query limit to reset"
                        : connecting
                          ? "Connecting"
                          : live
                            ? "End conversation"
                            : "Start conversation"
                    }
                    onClick={() => {
                      if (canHangUp) void session.stop();
                      else void session.start();
                    }}
                    disabled={connecting || quotaBlocked}
                    variant={live ? "danger" : "default"}
                    className="size-16 shadow-sm"
                  >
                    {connecting ? (
                      <Loader2Icon className="size-6 animate-spin" />
                    ) : live ? (
                      <PhoneIcon className="size-6 rotate-135" />
                    ) : (
                      <PhoneIcon className="size-6" />
                    )}
                  </ControlButton>

                  <ConversationControl />
                </div>
              </div>
            </main>
          </div>
        </SidebarInset>

        <Sidebar side="right" collapsible="offcanvas" mobileWidth="100vw">
          <ConversationPanel
            messages={session.messages}
            agentState={session.agentState}
            status={session.status}
            ttfaRecords={session.ttfaRecords}
            onClear={session.clearConversation}
            onResetMetrics={session.resetMetrics}
          />
        </Sidebar>
      </SidebarProvider>
    </div>
  );
}
