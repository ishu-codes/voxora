import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { VoiceOption } from "@/components/ui/voice-picker";
import { collectClientFingerprint } from "@/lib/device-fingerprint";
import { API_URL } from "@/lib/voice-catalog";
import {
  hasUnlimitedVoiceSettings,
  loadVoiceSettings,
  toConfigurePayload,
  type VoiceSettings,
} from "@/lib/voice-settings";
import { AudioCapture, AudioPlayer, decodePcm16 } from "./audio";
import {
  BYOK_SYSTEM_PROMPT,
  BYOK_TTS_SAMPLE_RATE,
  DirectSentenceChunker,
  streamByokLlm,
  synthesizeWithSarvam,
  transcribeWithSarvam,
} from "./byok";
import { useConversationStore } from "./conversation-store";
import { InterruptedTurns } from "./interrupted-turns";
import {
  type AgentState,
  type ConnectionStatus,
  isServerEvent,
  type ReadyEvent,
  type ServerEvent,
} from "./protocol";
import {
  BrowserSpeaker,
  createRecognition,
  listBrowserVoices,
  type Recognition,
  supportsBrowserStt,
} from "./speech";
import { useVoiceCatalog } from "./useVoiceCatalog";
import { float32ToPcm16, LocalVad, MIN_SPEECH_MS } from "./vad";

export type VoiceMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  final: boolean;
  turnId?: string;
  failed?: boolean;
  interrupted?: boolean;
  at: number;
};

export type TurnDiagnostics = {
  turnId: string;
  serverE2e: number | null;
  firstPlayback?: number;
  bargeIn?: number;
  startedAt: number;
};

export type VoiceSessionState = {
  status: ConnectionStatus;
  agentState: AgentState;
  ready: ReadyEvent | null;
  messages: VoiceMessage[];
  level: number;
  error: string | null;
  muted: boolean;
  vadStatus: LocalVadStatus;
  diagnostics: TurnDiagnostics[];
};

export type LocalVadStatus = "off" | "loading" | "active" | "fallback";

export type QuotaExhaustedState = {
  limit: number;
  retryAt: number;
};

const WS_URL_OVERRIDE = process.env.NEXT_PUBLIC_VOICE_WS;

function fallbackVoice(voiceId: string | undefined): VoiceOption | null {
  if (!voiceId) return null;
  return {
    voiceId,
    name: voiceId
      .split(/[-_]/)
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" "),
    labels: { description: "Sarvam Bulbul" },
  };
}

function voiceWsUrl(): string {
  if (WS_URL_OVERRIDE) return WS_URL_OVERRIDE;
  const url = new URL(API_URL);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/api/v1/voice/ws";
  url.search = "";
  return url.toString();
}

const BARGE_IN_VOICED_FRAMES = 5;
const IDLE_LEVEL = 0;
const MAX_RECONNECTS = 6;
const SYSTEM_VOICE = "system";
const MAX_PRE_ROLL_FRAMES = 30; // 600 ms of 20 ms frames
const TURN_WATCHDOG_MS = 60_000;
const SPEECH_TAIL_EXTRA_MS = 200;
const CAPTURE_STALL_MS = 4_000;
const CAPTURE_WATCHDOG_MS = 1_500;
const CAPTURE_RETRY_MS = 2_000;
const CAPTURE_MAX_RETRIES = 6;
// A restart only clears the retry budget once it has stayed healthy this long.
// Without this, a capture that dies every few seconds rebuilds forever.
const CAPTURE_STABILITY_MS = 15_000;
const ENERGY_GATE_FRAMES = 10; // 200 ms of fallback speech while Silero is quiet

function percentile(values: number[], p: number): number | null {
  if (!values.length) return null;
  const ordered = [...values].sort((a, b) => a - b);
  if (ordered.length === 1) return Math.round(ordered[0]);
  const rank = (ordered.length - 1) * (p / 100);
  const lower = Math.floor(rank);
  const upper = Math.min(lower + 1, ordered.length - 1);
  const weight = rank - lower;
  return Math.round(ordered[lower] * (1 - weight) + ordered[upper] * weight);
}

export function useVoiceSession() {
  const catalog = useVoiceCatalog();
  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [agentState, setAgentState] = useState<AgentState>("idle");
  const [ready, setReady] = useState<ReadyEvent | null>(null);
  const messages = useConversationStore((state) => state.messages);
  const setMessages = useConversationStore((state) => state.setMessages);
  const clearMessages = useConversationStore((state) => state.clearMessages);
  const [level, setLevel] = useState(IDLE_LEVEL);
  const [error, setError] = useState<string | null>(null);
  const [quotaExhausted, setQuotaExhausted] =
    useState<QuotaExhaustedState | null>(null);
  const [quotaNoticeDismissed, setQuotaNoticeDismissed] = useState(false);
  const [muted, setMuted] = useState(false);
  const [vadStatus, setVadStatus] = useState<LocalVadStatus>("off");
  const [diagnostics, setDiagnostics] = useState<TurnDiagnostics[]>([]);
  const [captureStream, setCaptureStream] = useState<MediaStream | null>(null);
  const [browserVoices, setBrowserVoices] = useState<SpeechSynthesisVoice[]>(
    [],
  );
  const [voice, setVoiceState] = useState<string | undefined>(undefined);

  const wsRef = useRef<WebSocket | null>(null);
  const captureRef = useRef<AudioCapture | null>(null);
  const playerRef = useRef<AudioPlayer | null>(null);
  const speakerRef = useRef<BrowserSpeaker | null>(null);
  const recognitionRef = useRef<Recognition | null>(null);

  const activeRef = useRef(false);
  const byokRef = useRef(false);
  const byokSettingsRef = useRef<VoiceSettings | null>(null);
  const directAbortRef = useRef<AbortController | null>(null);
  const directGenerationRef = useRef(0);
  const directUtteranceRef = useRef<Int16Array[]>([]);
  const directTurnInFlightRef = useRef(false);
  const finishDirectTurnRef = useRef<(audio?: Float32Array) => void>(
    () => undefined,
  );
  const intentionalCloseRef = useRef(false);
  const fatalConnectionRef = useRef(false);
  const readyRef = useRef<ReadyEvent | null>(null);
  const mutedRef = useRef(false);
  const voiceRef = useRef<string | undefined>(undefined);
  const voiceKindRef = useRef<"browser" | "audio" | null>(null);
  const catalogRef = useRef(catalog);
  catalogRef.current = catalog;
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<number | null>(null);
  const turnsRef = useRef(new InterruptedTurns());
  const stopRef = useRef<(() => Promise<void>) | null>(null);

  const connectSocketRef = useRef<() => void>(() => undefined);
  const currentUserMessageIdRef = useRef<string | null>(null);
  const currentAssistantTurnRef = useRef<string | null>(null);
  const activeTurnRef = useRef<string | null>(null);
  const completedTurnsRef = useRef<Set<string>>(new Set());
  const speechEndAtRef = useRef<number | null>(null);
  const voicedAtRef = useRef<number | null>(null);
  const turnDiagRef = useRef<Map<string, TurnDiagnostics>>(new Map());
  const turnWatchdogRef = useRef<number | null>(null);

  const localVadRef = useRef<LocalVad | null>(null);
  const vadStatusRef = useRef<LocalVadStatus>("off");
  const vadSpeakingRef = useRef(false);
  const vadConfirmedRef = useRef(false);
  const vadStartedAtRef = useRef<number | null>(null);
  const vadGateOpenRef = useRef(true);
  const vadTailTimerRef = useRef<number | null>(null);
  const preRollRef = useRef<Int16Array[]>([]);
  const sessionTokenRef = useRef(0);
  const lastFrameAtRef = useRef(0);
  const energyGateRunRef = useRef(0);
  const captureWatchdogRef = useRef<number | null>(null);
  const captureStartingRef = useRef(false);
  const captureRecoveryRef = useRef({
    inFlight: false,
    attempts: 0,
    lastAttemptAt: 0,
    recoveredAt: 0,
  });
  const rmsVadRef = useRef({
    speaking: false,
    voicedRun: 0,
    silenceMs: 0,
    startedAt: 0,
  });

  // Browser voices are populated asynchronously by the Web Speech API.
  useEffect(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;

    const load = () => setBrowserVoices(listBrowserVoices());
    load();
    window.speechSynthesis.addEventListener("voiceschanged", load);
    return () =>
      window.speechSynthesis.removeEventListener("voiceschanged", load);
  }, []);

  useEffect(() => {
    if (!quotaExhausted) return;
    const delay = Math.max(0, quotaExhausted.retryAt - Date.now());
    const timer = window.setTimeout(() => {
      setQuotaExhausted(null);
      setQuotaNoticeDismissed(false);
    }, delay);
    return () => window.clearTimeout(timer);
  }, [quotaExhausted]);

  const options = useMemo<VoiceOption[]>(() => {
    const kind = ready?.tts.kind ?? catalog?.kind;
    if (kind === "audio") {
      const voices: VoiceOption[] =
        catalog?.voices.map((item) => ({
          voiceId: item.id,
          name: item.name,
          labels: {
            gender: item.gender,
            description: item.description,
          },
        })) ?? [];
      const displayed = voice ?? ready?.tts.voice ?? catalog?.default_voice;
      if (
        displayed &&
        displayed !== SYSTEM_VOICE &&
        !voices.some((item) => item.voiceId === displayed)
      ) {
        const fallback = fallbackVoice(displayed);
        if (fallback) return [fallback, ...voices];
      }
      return voices;
    }
    if (kind === "browser") {
      return [
        {
          voiceId: SYSTEM_VOICE,
          name: "System default",
          labels: { description: "Let the browser choose" },
        },
        ...browserVoices.map((item) => ({
          voiceId: item.voiceURI,
          name: item.name,
          labels: {
            accent: item.lang,
            description: item.localService ? "On-device" : "Network",
          },
        })),
      ];
    }
    return [];
  }, [browserVoices, catalog, ready?.tts.kind, ready?.tts.voice, voice]);

  const publishDiagnostics = useCallback(() => {
    setDiagnostics(Array.from(turnDiagRef.current.values()).slice(-24));
  }, []);

  const ensureTurnDiagnostics = useCallback(
    (turnId: string): TurnDiagnostics => {
      const existing = turnDiagRef.current.get(turnId);
      if (existing) return existing;
      const created: TurnDiagnostics = {
        turnId,
        serverE2e: null,
        startedAt: Date.now(),
      };
      turnDiagRef.current.set(turnId, created);
      return created;
    },
    [],
  );

  const pushError = useCallback((message: string) => {
    setError(message);
  }, []);

  const send = useCallback((payload: unknown): boolean => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(payload));
    return true;
  }, []);

  const sendTurnMetrics = useCallback(
    (turnId: string, metrics: Record<string, number>) => {
      if (Object.keys(metrics).length) {
        send({ type: "metrics", turn_id: turnId, metrics });
      }
    },
    [send],
  );

  const selectVoice = useCallback(
    (voiceId: string) => {
      voiceRef.current = voiceId;
      setVoiceState(voiceId);

      const kind = readyRef.current?.tts.kind;
      if (kind === "browser") {
        speakerRef.current?.setVoice(voiceId === SYSTEM_VOICE ? null : voiceId);
      } else if (kind === "audio") {
        send({ type: "voice", voice: voiceId } satisfies {
          type: "voice";
          voice: string;
        });
      }
    },
    [send],
  );

  useEffect(() => {
    if (catalog?.kind !== "audio" || !catalog.voices.length) return;
    const current = voiceRef.current;
    const valid =
      current &&
      current !== SYSTEM_VOICE &&
      catalog.voices.some((item) => item.id === current);
    const next = valid
      ? current
      : catalog.default_voice || catalog.voices[0].id;
    if (!next || next === current) return;
    voiceRef.current = next;
    setVoiceState(next);
    if (readyRef.current?.tts.kind === "audio") {
      send({ type: "voice", voice: next });
    }
  }, [catalog, send]);

  const upsertUserMessage = useCallback(
    (text: string, final: boolean, turnId?: string) => {
      const existingId = currentUserMessageIdRef.current;
      setMessages((previous) => {
        if (existingId) {
          const index = previous.findIndex(
            (message) => message.id === existingId,
          );
          if (index >= 0) {
            const copy = [...previous];
            copy[index] = {
              ...copy[index],
              text,
              final,
              turnId: turnId ?? copy[index].turnId,
            };
            return copy;
          }
        }
        const id = turnId
          ? `user-${turnId}`
          : `user-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
        currentUserMessageIdRef.current = final ? null : id;
        return [
          ...previous,
          { id, role: "user", text, final, turnId, at: Date.now() },
        ];
      });
      if (final) currentUserMessageIdRef.current = null;
    },
    [setMessages],
  );

  const appendAssistantMessage = useCallback(
    (turnId: string, text: string) => {
      setMessages((previous) => {
        const index = previous.findIndex(
          (message) =>
            message.role === "assistant" && message.turnId === turnId,
        );
        if (index >= 0) {
          const copy = [...previous];
          const current = copy[index].text;
          const separator =
            current.length > 0 &&
            text.length > 0 &&
            !/\s$/.test(current) &&
            !/^\s/.test(text)
              ? " "
              : "";
          copy[index] = {
            ...copy[index],
            text: current + separator + text,
            final: copy[index].final || completedTurnsRef.current.has(turnId),
          };
          return copy;
        }
        return [
          ...previous,
          {
            id: `assistant-${turnId}`,
            role: "assistant",
            text,
            final: completedTurnsRef.current.has(turnId),
            turnId,
            at: Date.now(),
          },
        ];
      });
    },
    [setMessages],
  );

  const completeAssistantMessage = useCallback(
    (turnId: string, text: string, allowTextFallback: boolean) => {
      const completed = completedTurnsRef.current;
      completed.add(turnId);
      while (completed.size > 32) {
        const oldest = completed.values().next().value;
        if (oldest === undefined) break;
        completed.delete(oldest);
      }

      setMessages((previous) => {
        const index = previous.findIndex(
          (message) =>
            message.role === "assistant" && message.turnId === turnId,
        );
        if (index >= 0) {
          const copy = [...previous];
          copy[index] = { ...copy[index], final: true };
          return copy;
        }
        if (!allowTextFallback || !text.trim()) return previous;
        return [
          ...previous,
          {
            id: `assistant-${turnId}`,
            role: "assistant",
            text,
            final: true,
            turnId,
            at: Date.now(),
          },
        ];
      });
    },
    [setMessages],
  );

  const settleAssistantMessage = useCallback(
    (turnId: string, patch: Partial<VoiceMessage>) => {
      setMessages((previous) => {
        const index = previous.findIndex(
          (message) =>
            message.role === "assistant" && message.turnId === turnId,
        );
        if (index < 0) return previous;
        const copy = [...previous];
        copy[index] = { ...copy[index], final: true, ...patch };
        return copy;
      });
    },
    [setMessages],
  );

  const stopPlayback = useCallback(() => {
    playerRef.current?.stop();
    speakerRef.current?.stop();
    localVadRef.current?.setAssistantSpeaking(false);
  }, []);

  const sendPcm = useCallback((pcm: Int16Array): boolean => {
    if (mutedRef.current) return false;
    if (byokRef.current) {
      directUtteranceRef.current.push(new Int16Array(pcm));
      return true;
    }
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    // Copy because AudioWorklet buffers are transferred/detached.
    ws.send(new Int16Array(pcm).buffer as ArrayBuffer);
    return true;
  }, []);

  const clearVadTailTimer = useCallback(() => {
    if (vadTailTimerRef.current != null) {
      window.clearTimeout(vadTailTimerRef.current);
      vadTailTimerRef.current = null;
    }
  }, []);

  const openSpeechGate = useCallback(() => {
    clearVadTailTimer();
    if (vadGateOpenRef.current) return;
    vadGateOpenRef.current = true;
    const frames = preRollRef.current;
    preRollRef.current = [];
    for (const frame of frames) sendPcm(frame);
  }, [clearVadTailTimer, sendPcm]);

  const scheduleSpeechGateClose = useCallback(() => {
    clearVadTailTimer();
    const endSilence = readyRef.current?.vad.end_silence_ms ?? 650;
    const delay = Math.max(300, endSilence + SPEECH_TAIL_EXTRA_MS);
    vadTailTimerRef.current = window.setTimeout(() => {
      vadTailTimerRef.current = null;
      if (vadSpeakingRef.current) return;
      vadGateOpenRef.current = false;
      preRollRef.current = [];
    }, delay);
  }, [clearVadTailTimer]);

  const clearTurnWatchdog = useCallback(() => {
    if (turnWatchdogRef.current != null) {
      window.clearTimeout(turnWatchdogRef.current);
      turnWatchdogRef.current = null;
    }
  }, []);

  const armTurnWatchdog = useCallback(
    (turnId: string) => {
      clearTurnWatchdog();
      turnWatchdogRef.current = window.setTimeout(() => {
        turnWatchdogRef.current = null;
        if (byokRef.current) {
          directGenerationRef.current += 1;
          directAbortRef.current?.abort();
          directAbortRef.current = null;
        }
        turnsRef.current.interrupt(turnId);
        if (activeTurnRef.current === turnId) activeTurnRef.current = null;
        stopPlayback();
        setAgentState((previous) =>
          previous === "speaking" || previous === "thinking"
            ? "listening"
            : previous,
        );
        pushError("The assistant response timed out. You can speak again.");
      }, TURN_WATCHDOG_MS);
    },
    [clearTurnWatchdog, pushError, stopPlayback],
  );

  /**
   * Stop the assistant and invalidate its turn. Called from local VAD, the
   * energy fallback, the server's speech.start and the manual interrupt.
   */
  const handleBargeIn = useCallback(
    (source: "vad" | "rms" | "server"): boolean => {
      if (byokRef.current && source !== "server") {
        directGenerationRef.current += 1;
        directAbortRef.current?.abort();
        directAbortRef.current = null;
      }
      const now = performance.now();
      const turnId =
        activeTurnRef.current ?? currentAssistantTurnRef.current ?? null;
      const playing = Boolean(
        playerRef.current?.isSpeaking || speakerRef.current?.isSpeaking,
      );
      const cancelling = Boolean(
        turnId && (playing || turnsRef.current.isActive(turnId)),
      );

      if (!cancelling && !playing) {
        setAgentState((previous) =>
          previous === "speaking" || previous === "thinking"
            ? previous
            : "capturing",
        );
        return false;
      }

      if (turnId) {
        turnsRef.current.interrupt(turnId);
        if (activeTurnRef.current === turnId) activeTurnRef.current = null;
        settleAssistantMessage(turnId, { interrupted: true });
        const diag = ensureTurnDiagnostics(turnId);
        if (diag.bargeIn == null) {
          const onset = vadStartedAtRef.current ?? now;
          diag.bargeIn = Math.round(now - onset);
          publishDiagnostics();
          sendTurnMetrics(turnId, { barge_in_ms: diag.bargeIn });
        }
      }

      stopPlayback();
      setAgentState("interrupted");

      if (source !== "server") {
        // Explicitly cancel the backend turn as soon as speech is confirmed.
        // turn_id keeps a late interrupt from cancelling a newer response.
        send({
          type: "interrupt",
          reason: "barge_in",
          ...(turnId ? { turn_id: turnId } : {}),
        });
      }
      return true;
    },
    [
      ensureTurnDiagnostics,
      publishDiagnostics,
      send,
      sendTurnMetrics,
      settleAssistantMessage,
      stopPlayback,
    ],
  );

  const recordFirstPlayback = useCallback(
    (turnId: string) => {
      const diag = ensureTurnDiagnostics(turnId);
      if (diag.firstPlayback != null) return;
      const speechEnd = speechEndAtRef.current;
      if (speechEnd == null) return;
      const firstPlayback = Math.round(performance.now() - speechEnd);
      diag.firstPlayback = firstPlayback;
      publishDiagnostics();
      sendTurnMetrics(turnId, { first_playback_ms: firstPlayback });
    },
    [ensureTurnDiagnostics, publishDiagnostics, sendTurnMetrics],
  );

  const startLocalVad = useCallback(
    async (stream: MediaStream, audioContext?: AudioContext | null) => {
      const previous = localVadRef.current;
      if (previous) {
        localVadRef.current = null;
        await previous.destroy();
      }
      if (!activeRef.current) return;
      const token = ++sessionTokenRef.current;
      const vad = new LocalVad(
        {
          getStream: () => stream,
          onSpeechStart: () => {
            if (!activeRef.current || mutedRef.current) return;
            vadSpeakingRef.current = true;
            vadConfirmedRef.current = false;
            vadStartedAtRef.current = performance.now();
            clearVadTailTimer();
          },
          onSpeechRealStart: () => {
            if (!activeRef.current || mutedRef.current) return;
            vadSpeakingRef.current = true;
            vadConfirmedRef.current = true;
            if (byokRef.current) directUtteranceRef.current = [];
            if (vadStartedAtRef.current == null) {
              vadStartedAtRef.current = performance.now() - MIN_SPEECH_MS;
            }
            // Stop audio first, then release the buffered onset frames to STT.
            handleBargeIn("vad");
            openSpeechGate();
          },
          onSpeechEnd: (audio) => {
            const wasConfirmed = vadConfirmedRef.current;
            vadSpeakingRef.current = false;
            vadConfirmedRef.current = false;
            vadStartedAtRef.current = null;
            speechEndAtRef.current = performance.now();
            scheduleSpeechGateClose();
            if (byokRef.current) finishDirectTurnRef.current(audio);
            if (
              wasConfirmed &&
              !playerRef.current?.isSpeaking &&
              !speakerRef.current?.isSpeaking
            ) {
              setAgentState((previous) =>
                previous === "interrupted" || previous === "capturing"
                  ? "thinking"
                  : previous,
              );
            }
          },
          onMisfire: () => {
            vadSpeakingRef.current = false;
            vadConfirmedRef.current = false;
            vadStartedAtRef.current = null;
            directUtteranceRef.current = [];
            scheduleSpeechGateClose();
          },
        },
        {},
        { audioContext },
      );

      localVadRef.current = vad;
      vadStatusRef.current = "loading";
      setVadStatus("loading");

      try {
        await vad.start();
        if (
          !activeRef.current ||
          token !== sessionTokenRef.current ||
          localVadRef.current !== vad
        ) {
          await vad.destroy();
          return;
        }
        vadStatusRef.current = "active";
        setVadStatus("active");
        // From now on silence stays local; confirmed speech is flushed with a
        // pre-roll so the first syllables still reach Sarvam. Speech may have
        // already started while the model was loading, in which case its gate
        // must stay open instead of being closed behind the active utterance.
        if (!vadSpeakingRef.current) {
          vadGateOpenRef.current = false;
          preRollRef.current = [];
        }
        if (playerRef.current?.isSpeaking || speakerRef.current?.isSpeaking) {
          vad.setAssistantSpeaking(true);
        }
      } catch (cause) {
        if (localVadRef.current === vad) localVadRef.current = null;
        await vad.destroy();
        if (!activeRef.current || token !== sessionTokenRef.current) return;
        vadStatusRef.current = "fallback";
        setVadStatus("fallback");
        const detail =
          cause instanceof Error && cause.message ? ` (${cause.message})` : "";
        pushError(
          `Local voice detection could not start${detail}. Falling back to server detection; barge-in still works.`,
        );
      }
    },
    [
      clearVadTailTimer,
      handleBargeIn,
      openSpeechGate,
      pushError,
      scheduleSpeechGateClose,
    ],
  );

  const ensurePlayer = useCallback((): AudioPlayer => {
    if (!playerRef.current) {
      playerRef.current = new AudioPlayer({
        onSpeakingChange: (speaking) => {
          localVadRef.current?.setAssistantSpeaking(speaking);
          setAgentState((previous) => {
            if (speaking) return "speaking";
            if (previous !== "speaking") return previous;
            return vadSpeakingRef.current ? "capturing" : "listening";
          });
        },
        onFirstAudio: () => {
          const turnId = currentAssistantTurnRef.current;
          if (turnId) recordFirstPlayback(turnId);
        },
      });
    }
    if (!speakerRef.current) {
      speakerRef.current = new BrowserSpeaker({
        onStart: () => {
          localVadRef.current?.setAssistantSpeaking(true);
          const turnId = currentAssistantTurnRef.current;
          if (turnId) recordFirstPlayback(turnId);
          setAgentState("speaking");
        },
        onEnd: () => {
          localVadRef.current?.setAssistantSpeaking(false);
          setAgentState((previous) => {
            if (previous !== "speaking") return previous;
            return vadSpeakingRef.current ? "capturing" : "listening";
          });
        },
      });
      speakerRef.current.setVoice(
        voiceRef.current && voiceRef.current !== SYSTEM_VOICE
          ? voiceRef.current
          : null,
      );
      speakerRef.current.primeVoices();
    }
    return playerRef.current;
  }, [recordFirstPlayback]);

  const runDirectTurn = useCallback(
    async (vadAudio?: Float32Array) => {
      const settings = byokSettingsRef.current;
      const collectedFrames = directUtteranceRef.current;
      directUtteranceRef.current = [];
      const frames = vadAudio?.length
        ? [float32ToPcm16(vadAudio)]
        : collectedFrames;
      if (
        !activeRef.current ||
        !byokRef.current ||
        !settings ||
        !frames.length
      ) {
        return;
      }
      if (directTurnInFlightRef.current) return;
      directTurnInFlightRef.current = true;

      const generation = ++directGenerationRef.current;
      const controller = new AbortController();
      directAbortRef.current = controller;
      let turnId: string | null = null;

      try {
        setAgentState("thinking");
        const text = await transcribeWithSarvam(
          settings,
          frames,
          controller.signal,
        );
        if (!activeRef.current || generation !== directGenerationRef.current) {
          return;
        }
        if (!text) {
          setAgentState("listening");
          pushError("No speech detected. Try speaking a little longer.");
          return;
        }

        turnId = `local-${Date.now()}-${generation}`;
        const activeTurnId = turnId;
        upsertUserMessage(text, true, activeTurnId);
        turnsRef.current.begin(activeTurnId);
        activeTurnRef.current = activeTurnId;
        currentAssistantTurnRef.current = activeTurnId;
        ensureTurnDiagnostics(activeTurnId);
        publishDiagnostics();
        armTurnWatchdog(activeTurnId);

        const history = useConversationStore
          .getState()
          .messages.filter((message) => message.text.trim())
          .slice(-24)
          .map((message) => ({
            role: message.role,
            content: message.text,
          }));
        const messages = [
          { role: "system" as const, content: BYOK_SYSTEM_PROMPT },
          ...history,
        ];

        const player = ensurePlayer();
        const chunker = new DirectSentenceChunker();
        let ttsError: unknown = null;
        let speechQueue = Promise.resolve();
        const enqueueSpeech = (sentence: string) => {
          speechQueue = speechQueue
            .then(async () => {
              if (
                ttsError ||
                generation !== directGenerationRef.current ||
                turnsRef.current.isCancelled(activeTurnId)
              ) {
                return;
              }
              const pcm = await synthesizeWithSarvam(
                settings,
                sentence,
                voiceRef.current ?? null,
                controller.signal,
                catalogRef.current?.model ?? "bulbul:v3",
              );
              if (
                generation !== directGenerationRef.current ||
                turnsRef.current.isCancelled(activeTurnId)
              ) {
                return;
              }
              player.enqueue(pcm, BYOK_TTS_SAMPLE_RATE, () => {
                if (
                  generation !== directGenerationRef.current ||
                  turnsRef.current.isCancelled(activeTurnId)
                ) {
                  return;
                }
                appendAssistantMessage(activeTurnId, sentence);
              });
            })
            .catch((cause) => {
              ttsError = cause;
            });
        };

        const fullText = await streamByokLlm(
          settings,
          messages,
          controller.signal,
          (token) => {
            for (const sentence of chunker.feed(token)) {
              enqueueSpeech(sentence);
            }
          },
        );
        const tail = chunker.flush();
        if (tail) enqueueSpeech(tail);
        await speechQueue;
        if (ttsError) throw ttsError;
        if (
          !activeRef.current ||
          generation !== directGenerationRef.current ||
          turnsRef.current.isCancelled(activeTurnId)
        ) {
          return;
        }

        completeAssistantMessage(
          activeTurnId,
          fullText,
          !player.isSpeaking && !speakerRef.current?.isSpeaking,
        );
        turnsRef.current.settle(activeTurnId);
        activeTurnRef.current = null;
        currentAssistantTurnRef.current = null;
        clearTurnWatchdog();
        if (!player.isSpeaking) setAgentState("listening");
      } catch (cause) {
        if (controller.signal.aborted) return;
        const message =
          cause instanceof Error
            ? cause.message
            : "Direct voice request failed.";
        pushError(message);
        if (turnId) {
          settleAssistantMessage(turnId, { failed: true });
          turnsRef.current.settle(turnId);
        }
        activeTurnRef.current = null;
        currentAssistantTurnRef.current = null;
        clearTurnWatchdog();
        setAgentState("listening");
      } finally {
        directTurnInFlightRef.current = false;
        if (directAbortRef.current === controller) {
          directAbortRef.current = null;
        }
      }
    },
    [
      appendAssistantMessage,
      armTurnWatchdog,
      clearTurnWatchdog,
      completeAssistantMessage,
      ensurePlayer,
      ensureTurnDiagnostics,
      publishDiagnostics,
      pushError,
      settleAssistantMessage,
      upsertUserMessage,
    ],
  );

  useEffect(() => {
    finishDirectTurnRef.current = (audio) => {
      void runDirectTurn(audio);
    };
  }, [runDirectTurn]);

  const handleServerEvent = useCallback(
    (event: ServerEvent) => {
      switch (event.type) {
        case "ready": {
          readyRef.current = event;
          setReady(event);
          setStatus("connected");
          reconnectAttemptsRef.current = 0;
          setAgentState("listening");
          setError(null);

          const kind = event.tts.kind;
          if (voiceKindRef.current !== null && voiceKindRef.current !== kind) {
            voiceRef.current = undefined;
          }
          voiceKindRef.current = kind;

          const audioVoices = catalogRef.current?.voices ?? [];
          const currentAudioVoice =
            voiceRef.current &&
            audioVoices.some((item) => item.id === voiceRef.current)
              ? voiceRef.current
              : undefined;
          const nextVoice =
            kind === "audio"
              ? (currentAudioVoice ??
                event.tts.voice ??
                catalogRef.current?.default_voice ??
                audioVoices[0]?.id ??
                "shubh")
              : (voiceRef.current ?? SYSTEM_VOICE);

          voiceRef.current = nextVoice;
          setVoiceState(nextVoice);

          if (kind === "audio" && nextVoice !== event.tts.voice) {
            send({ type: "voice", voice: nextVoice });
          } else if (kind === "browser") {
            speakerRef.current?.setVoice(
              nextVoice === SYSTEM_VOICE ? null : nextVoice,
            );
          }

          if (
            event.stt.mode === "browser-stt" &&
            !recognitionRef.current &&
            activeRef.current
          ) {
            startRecognition();
          }
          break;
        }
        case "state": {
          if (
            turnsRef.current.isCancelled(event.turn_id) &&
            event.state !== "listening"
          ) {
            break;
          }
          if (playerRef.current?.isSpeaking || speakerRef.current?.isSpeaking) {
            setAgentState("speaking");
          } else {
            setAgentState(event.state);
          }
          break;
        }
        case "audio.level":
          setLevel(event.rms);
          break;
        case "speech.start":
          // Server-side VAD confirms the same onset. Local VAD normally stops
          // playback earlier, so this is a fallback for browsers where the
          // Silero model failed to load.
          if (turnsRef.current.isCancelled(event.turn_id)) break;
          if (playerRef.current?.isSpeaking || speakerRef.current?.isSpeaking) {
            handleBargeIn("server");
          } else {
            setAgentState("capturing");
          }
          break;
        case "transcript.partial":
          upsertUserMessage(event.text, false);
          if (!playerRef.current?.isSpeaking) setAgentState("capturing");
          break;
        case "transcript.final": {
          upsertUserMessage(event.text, true, event.turn_id);
          turnsRef.current.begin(event.turn_id);
          activeTurnRef.current = event.turn_id;
          currentAssistantTurnRef.current = event.turn_id;
          ensureTurnDiagnostics(event.turn_id);
          publishDiagnostics();
          armTurnWatchdog(event.turn_id);
          setAgentState("thinking");
          break;
        }
        case "assistant.delta": {
          if (turnsRef.current.isCancelled(event.turn_id)) break;
          if (
            activeTurnRef.current !== null &&
            activeTurnRef.current !== event.turn_id
          ) {
            break;
          }
          appendAssistantMessage(event.turn_id, event.text);
          if (!playerRef.current?.isSpeaking) setAgentState("thinking");
          break;
        }
        case "speak.chunk":
          if (turnsRef.current.isCancelled(event.turn_id)) break;
          if (
            activeTurnRef.current !== null &&
            activeTurnRef.current !== event.turn_id
          ) {
            break;
          }
          currentAssistantTurnRef.current = event.turn_id;
          speakerRef.current?.speak(event.text);
          break;
        case "speak.end":
          break;
        case "audio.chunk": {
          if (turnsRef.current.isCancelled(event.turn_id)) break;
          if (
            activeTurnRef.current !== null &&
            activeTurnRef.current !== event.turn_id
          ) {
            break;
          }
          currentAssistantTurnRef.current = event.turn_id;
          const player = ensurePlayer();
          const spokenText = event.text;
          player.enqueue(
            decodePcm16(event.data),
            event.sample_rate,
            spokenText
              ? () => {
                  if (turnsRef.current.isCancelled(event.turn_id)) return;
                  if (
                    activeTurnRef.current !== null &&
                    activeTurnRef.current !== event.turn_id
                  ) {
                    return;
                  }
                  appendAssistantMessage(event.turn_id, spokenText);
                }
              : undefined,
          );
          break;
        }
        case "assistant.done": {
          const stale =
            turnsRef.current.isCancelled(event.turn_id) ||
            (activeTurnRef.current !== null &&
              activeTurnRef.current !== event.turn_id);
          if (stale) {
            settleAssistantMessage(event.turn_id, {
              interrupted: turnsRef.current.isCancelled(event.turn_id),
            });
            break;
          }
          completeAssistantMessage(
            event.turn_id,
            event.text,
            !playerRef.current?.isSpeaking && !speakerRef.current?.isSpeaking,
          );
          turnsRef.current.settle(event.turn_id);
          if (activeTurnRef.current === event.turn_id) {
            activeTurnRef.current = null;
          }
          clearTurnWatchdog();
          if (
            !playerRef.current?.isSpeaking &&
            !speakerRef.current?.isSpeaking
          ) {
            setAgentState(vadSpeakingRef.current ? "capturing" : "listening");
          }
          break;
        }
        case "assistant.failed": {
          if (
            turnsRef.current.isCancelled(event.turn_id) ||
            (activeTurnRef.current !== null &&
              activeTurnRef.current !== event.turn_id)
          ) {
            break;
          }
          settleAssistantMessage(event.turn_id, { failed: true });
          turnsRef.current.settle(event.turn_id);
          if (activeTurnRef.current === event.turn_id) {
            activeTurnRef.current = null;
          }
          clearTurnWatchdog();
          setAgentState("listening");
          break;
        }
        case "turn.cancelled": {
          const wasCurrent = currentAssistantTurnRef.current === event.turn_id;
          turnsRef.current.interrupt(event.turn_id);
          activeTurnRef.current =
            activeTurnRef.current === event.turn_id
              ? null
              : activeTurnRef.current;
          if (wasCurrent) {
            stopPlayback();
            currentAssistantTurnRef.current = null;
          }
          settleAssistantMessage(event.turn_id, { interrupted: true });
          clearTurnWatchdog();
          if (event.reason === "barge_in") {
            const diag = ensureTurnDiagnostics(event.turn_id);
            if (diag.bargeIn == null) {
              const onset = vadStartedAtRef.current ?? voicedAtRef.current;
              if (onset != null) {
                diag.bargeIn = Math.round(performance.now() - onset);
                publishDiagnostics();
                sendTurnMetrics(event.turn_id, {
                  barge_in_ms: diag.bargeIn,
                });
              }
            }
          }
          if (
            !playerRef.current?.isSpeaking &&
            !speakerRef.current?.isSpeaking &&
            activeTurnRef.current === null
          ) {
            setAgentState(vadSpeakingRef.current ? "capturing" : "listening");
          }
          break;
        }
        case "turn.empty":
          if (turnsRef.current.isCancelled(event.turn_id)) break;
          currentUserMessageIdRef.current = null;
          if (activeTurnRef.current === event.turn_id) {
            activeTurnRef.current = null;
          }
          turnsRef.current.settle(event.turn_id);
          clearTurnWatchdog();
          setAgentState("listening");
          pushError("No speech detected. Try speaking a little longer.");
          break;
        case "turn.metrics": {
          const diag = ensureTurnDiagnostics(event.turn_id);
          const e2e = event.metrics.e2e_first_audio_ms;
          diag.serverE2e = typeof e2e === "number" ? e2e : null;
          publishDiagnostics();
          break;
        }
        case "error":
          if (event.stage === "quota" || event.code === "trial_exhausted") {
            fatalConnectionRef.current = true;
            const retryAfter =
              typeof event.retry_after_s === "number"
                ? Math.max(1, event.retry_after_s)
                : 60 * 60;
            setQuotaExhausted({
              limit:
                event.limit ?? readyRef.current?.platform?.turn_limit ?? 10,
              retryAt: Date.now() + retryAfter * 1000,
            });
            setQuotaNoticeDismissed(false);
            void stopRef.current?.();
            break;
          }
          if (
            !event.recoverable &&
            (event.stage === "rate_limit" ||
              event.stage === "client_validation")
          ) {
            fatalConnectionRef.current = true;
            const retry =
              typeof event.retry_after_s === "number"
                ? ` Try again in ${Math.max(1, Math.ceil(event.retry_after_s))} seconds.`
                : "";
            pushError(`${event.message}${retry}`);
            void stopRef.current?.();
            break;
          }
          if (
            event.turn_id &&
            (turnsRef.current.isCancelled(event.turn_id) ||
              (activeTurnRef.current !== null &&
                activeTurnRef.current !== event.turn_id))
          ) {
            break;
          }
          pushError(event.message);
          if (
            event.stage !== "stt" &&
            !playerRef.current?.isSpeaking &&
            !speakerRef.current?.isSpeaking
          ) {
            setAgentState("listening");
          }
          break;
        case "pong":
          break;
        default:
          break;
      }

      function startRecognition() {
        if (!supportsBrowserStt()) {
          pushError(
            "This browser has no on-device speech recognition. Set STT_PROVIDER=openai or faster-whisper on the server.",
          );
          return;
        }
        const recognition = createRecognition({
          onPartial: (text) => send({ type: "transcript", text, final: false }),
          onFinal: (text) => send({ type: "transcript", text, final: true }),
          onError: (message) => pushError(`Speech recognition: ${message}`),
        });
        if (!recognition) {
          pushError("Could not start on-device speech recognition.");
          return;
        }
        recognition.onend = () => {
          if (
            activeRef.current &&
            readyRef.current?.stt.mode === "browser-stt"
          ) {
            try {
              recognition.start();
            } catch {
              /* restarting too quickly is a no-op */
            }
          }
        };
        recognitionRef.current = recognition;
        try {
          recognition.start();
        } catch {
          /* already started */
        }
      }
    },
    [
      appendAssistantMessage,
      armTurnWatchdog,
      clearTurnWatchdog,
      completeAssistantMessage,
      ensurePlayer,
      ensureTurnDiagnostics,
      handleBargeIn,
      publishDiagnostics,
      pushError,
      send,
      sendTurnMetrics,
      settleAssistantMessage,
      stopPlayback,
      upsertUserMessage,
    ],
  );

  const handleFrame = useCallback(
    (pcm: Int16Array) => {
      // Frames arrive every 20 ms even when the room is silent, so this is the
      // health signal for the capture graph.
      lastFrameAtRef.current = performance.now();

      if (mutedRef.current) {
        preRollRef.current = [];
        energyGateRunRef.current = 0;
        return;
      }

      let sum = 0;
      for (let i = 0; i < pcm.length; i += 1) {
        const value = pcm[i] / 32768;
        sum += value * value;
      }
      const rms = Math.sqrt(sum / pcm.length);
      const now = performance.now();
      const threshold = readyRef.current?.vad.threshold ?? 0.012;

      if (vadGateOpenRef.current) {
        sendPcm(pcm);
        energyGateRunRef.current = 0;
      } else {
        preRollRef.current.push(new Int16Array(pcm));
        if (preRollRef.current.length > MAX_PRE_ROLL_FRAMES) {
          preRollRef.current.shift();
        }

        // This fallback also covers the model-loading window. Keep silence off
        // the wire until either Silero or sustained local energy confirms that
        // the user has started speaking.
        const assistantAudible = Boolean(
          playerRef.current?.isSpeaking || speakerRef.current?.isSpeaking,
        );
        const fallbackThreshold = assistantAudible
          ? Math.max(0.035, threshold * 2.5)
          : Math.max(0.012, threshold);
        if (rms >= fallbackThreshold) {
          energyGateRunRef.current += 1;
          if (energyGateRunRef.current >= ENERGY_GATE_FRAMES) {
            energyGateRunRef.current = 0;
            handleBargeIn("rms");
            openSpeechGate();
          }
        } else {
          energyGateRunRef.current = 0;
        }
      }

      const vad = rmsVadRef.current;

      if (!vad.speaking) {
        vad.voicedRun = rms >= threshold ? vad.voicedRun + 1 : 0;
        if (vad.voicedRun >= BARGE_IN_VOICED_FRAMES) {
          vad.speaking = true;
          vad.silenceMs = 0;
          vad.startedAt = now;
          voicedAtRef.current = now - BARGE_IN_VOICED_FRAMES * 20;
          // Silero owns onset when active. The energy detector still runs so
          // it can close the gate after an energy-fallback utterance.
          if (vadStatusRef.current !== "active") {
            handleBargeIn("rms");
          }
        }
      } else if (rms >= threshold) {
        vad.silenceMs = 0;
      } else {
        vad.silenceMs += 20;
        const endSilence = readyRef.current?.vad.end_silence_ms ?? 650;
        if (vad.silenceMs >= endSilence || now - vad.startedAt > 30_000) {
          vad.speaking = false;
          vad.voicedRun = 0;
          vad.silenceMs = 0;
          speechEndAtRef.current = now;
          scheduleSpeechGateClose();
          if (byokRef.current) finishDirectTurnRef.current();
          setAgentState((previous) =>
            previous === "speaking" ? previous : "thinking",
          );
        }
      }
    },
    [handleBargeIn, openSpeechGate, scheduleSpeechGateClose, sendPcm],
  );

  const stopCaptureWatchdog = useCallback(() => {
    if (captureWatchdogRef.current != null) {
      window.clearInterval(captureWatchdogRef.current);
      captureWatchdogRef.current = null;
    }
  }, []);

  /**
   * Rebuild the microphone graph after the track ends, the device is taken
   * away, or the browser suspends audio in a background tab. The WebSocket and
   * turn state stay intact; only capture and local VAD are replaced.
   */
  const recoverCapture = useCallback(
    async (reason: string, sourceCapture?: AudioCapture) => {
      if (!activeRef.current || captureStartingRef.current) return;
      // Ignore an ended/missing event from a capture that has already been
      // replaced. Without this ownership check, teardown of the old graph can
      // report a loss and immediately rebuild the capture that just succeeded.
      if (sourceCapture !== undefined && captureRef.current !== sourceCapture) {
        return;
      }
      const recovery = captureRecoveryRef.current;
      const now = performance.now();
      if (
        recovery.inFlight ||
        now - recovery.lastAttemptAt < CAPTURE_RETRY_MS
      ) {
        return;
      }
      recovery.inFlight = true;
      captureStartingRef.current = true;
      recovery.lastAttemptAt = now;
      if (process.env.NODE_ENV !== "production") {
        console.info("[voice] rebuilding microphone capture", { reason });
      }
      let capture: AudioCapture | null = null;

      try {
        const previousVad = localVadRef.current;
        localVadRef.current = null;
        await previousVad?.destroy();
        if (!activeRef.current) return;

        vadStatusRef.current = "loading";
        setVadStatus("loading");
        vadGateOpenRef.current = false;
        preRollRef.current = [];
        energyGateRunRef.current = 0;
        rmsVadRef.current = {
          speaking: false,
          voicedRun: 0,
          silenceMs: 0,
          startedAt: 0,
        };

        const previousCapture = captureRef.current;
        captureRef.current = null;
        await previousCapture?.stop();
        if (!activeRef.current) return;

        setCaptureStream(null);
        const nextCapture = new AudioCapture();
        capture = nextCapture;
        await nextCapture.start({
          onFrame: handleFrame,
          onLevel: (rms) => setLevel(rms),
          onStreamLost: (lostReason) => {
            if (captureRef.current === nextCapture) {
              void recoverCapture(lostReason, nextCapture);
            }
          },
        });

        if (!activeRef.current) {
          await capture.stop();
          return;
        }

        if (captureRef.current !== null) {
          await nextCapture.stop();
          return;
        }
        captureRef.current = nextCapture;
        lastFrameAtRef.current = performance.now();
        recovery.recoveredAt = lastFrameAtRef.current;
        setCaptureStream(nextCapture.mediaStream);
        await playerRef.current?.resume();
        const stream = nextCapture.mediaStream;
        if (stream) void startLocalVad(stream, nextCapture.audioContext);
        setError((current) =>
          current?.startsWith("The microphone stopped working")
            ? null
            : current,
        );
      } catch (cause) {
        await capture?.stop();
        if (!activeRef.current) return;
        const failedAt = performance.now();
        const stable =
          recovery.recoveredAt > 0 &&
          failedAt - recovery.recoveredAt >= CAPTURE_STABILITY_MS;
        recovery.attempts = stable ? 1 : recovery.attempts + 1;
        const detail =
          cause instanceof Error && cause.message ? ` (${cause.message})` : "";
        if (recovery.attempts > CAPTURE_MAX_RETRIES) {
          stopCaptureWatchdog();
          vadStatusRef.current = "off";
          setVadStatus("off");
          pushError(
            `The microphone stopped working${detail}. End the conversation and start it again to reconnect.`,
          );
        } else {
          const delay = Math.min(
            CAPTURE_RETRY_MS * 2 ** (recovery.attempts - 1),
            15_000,
          );
          window.setTimeout(() => {
            void recoverCapture(reason);
          }, delay);
        }
      } finally {
        recovery.inFlight = false;
        captureStartingRef.current = false;
      }
    },
    [handleFrame, pushError, startLocalVad, stopCaptureWatchdog],
  );

  const startCaptureWatchdog = useCallback(() => {
    stopCaptureWatchdog();
    captureWatchdogRef.current = window.setInterval(() => {
      if (!activeRef.current) return;
      if (captureStartingRef.current) return;
      if (captureRecoveryRef.current.inFlight) return;
      const capture = captureRef.current;
      if (!capture) {
        if (performance.now() - lastFrameAtRef.current > CAPTURE_STALL_MS) {
          void recoverCapture("missing-capture");
        }
        return;
      }
      if (performance.now() - lastFrameAtRef.current > CAPTURE_STALL_MS) {
        void recoverCapture("stalled-capture", capture);
      }
    }, CAPTURE_WATCHDOG_MS);
  }, [recoverCapture, stopCaptureWatchdog]);

  useEffect(() => {
    // Coming back from a background tab only needs a resume. If frames still
    // do not return, the capture watchdog rebuilds the graph. Rebuilding here
    // as well raced with itself when focus and devicechange fired together.
    const resumeAfterSuspend = () => {
      if (!activeRef.current || document.visibilityState !== "visible") return;
      void captureRef.current?.resume();
      void playerRef.current?.resume();
      void localVadRef.current?.resume();
    };

    const onDeviceChange = () => {
      if (!activeRef.current) return;
      void captureRef.current?.resume();
      void localVadRef.current?.resume();
    };

    document.addEventListener("visibilitychange", resumeAfterSuspend);
    window.addEventListener("focus", resumeAfterSuspend);
    window.addEventListener("pageshow", resumeAfterSuspend);
    navigator.mediaDevices?.addEventListener("devicechange", onDeviceChange);
    return () => {
      document.removeEventListener("visibilitychange", resumeAfterSuspend);
      window.removeEventListener("focus", resumeAfterSuspend);
      window.removeEventListener("pageshow", resumeAfterSuspend);
      navigator.mediaDevices?.removeEventListener(
        "devicechange",
        onDeviceChange,
      );
    };
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (reconnectAttemptsRef.current >= MAX_RECONNECTS) {
      setStatus("error");
      pushError("Connection lost. Press Start to reconnect.");
      return;
    }
    const attempt = reconnectAttemptsRef.current;
    reconnectAttemptsRef.current = attempt + 1;
    setStatus("reconnecting");
    const delay = Math.min(800 * 2 ** attempt, 8_000);
    reconnectTimerRef.current = window.setTimeout(() => {
      if (activeRef.current) connectSocketRef.current();
    }, delay);
  }, [pushError]);

  const connectSocket = useCallback(() => {
    if (reconnectTimerRef.current) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    const previous = wsRef.current;
    if (
      previous &&
      (previous.readyState === WebSocket.OPEN ||
        previous.readyState === WebSocket.CONNECTING)
    ) {
      previous.close();
    }
    intentionalCloseRef.current = false;
    let ws: WebSocket;
    try {
      ws = new WebSocket(voiceWsUrl());
    } catch {
      pushError("Could not open the voice connection.");
      setStatus("error");
      return;
    }
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;
    ws.onopen = () => {
      if (wsRef.current !== ws) return;
      ws.send(JSON.stringify(toConfigurePayload(collectClientFingerprint())));
    };
    ws.onmessage = (message: MessageEvent<string>) => {
      if (typeof message.data !== "string") return;
      try {
        const parsed = JSON.parse(message.data);
        if (isServerEvent(parsed)) handleServerEvent(parsed);
      } catch {
        /* ignore malformed frames */
      }
    };
    ws.onerror = () => {
      if (activeRef.current) {
        handleBargeIn("server");
        pushError("Voice connection error.");
      }
    };
    ws.onclose = () => {
      if (wsRef.current !== ws) return;
      wsRef.current = null;
      if (intentionalCloseRef.current || !activeRef.current) {
        setStatus((current) => (current === "error" ? current : "idle"));
        return;
      }
      // A dropped socket means the in-flight response can no longer be
      // trusted. Stop its audio and leave the UI in a usable state.
      handleBargeIn("server");
      clearTurnWatchdog();
      setAgentState("listening");
      scheduleReconnect();
    };
  }, [
    clearTurnWatchdog,
    handleBargeIn,
    handleServerEvent,
    pushError,
    scheduleReconnect,
  ]);

  useEffect(() => {
    connectSocketRef.current = connectSocket;
  }, [connectSocket]);

  const start = useCallback(async () => {
    if (activeRef.current) return;
    if (quotaExhausted && quotaExhausted.retryAt > Date.now()) return;
    if (quotaExhausted) {
      setQuotaExhausted(null);
      setQuotaNoticeDismissed(false);
    }
    const settings = loadVoiceSettings();
    const direct = hasUnlimitedVoiceSettings(settings);
    byokSettingsRef.current = direct ? settings : null;
    byokRef.current = direct;
    fatalConnectionRef.current = false;
    setError(null);
    setStatus("connecting");
    activeRef.current = true;
    reconnectAttemptsRef.current = 0;
    turnDiagRef.current.clear();
    setDiagnostics([]);
    clearTurnWatchdog();
    clearVadTailTimer();
    turnsRef.current.reset();
    completedTurnsRef.current.clear();
    activeTurnRef.current = null;
    currentAssistantTurnRef.current = null;
    currentUserMessageIdRef.current = null;
    rmsVadRef.current = {
      speaking: false,
      voicedRun: 0,
      silenceMs: 0,
      startedAt: 0,
    };
    vadSpeakingRef.current = false;
    vadConfirmedRef.current = false;
    vadStartedAtRef.current = null;
    vadGateOpenRef.current = false;
    preRollRef.current = [];
    speechEndAtRef.current = null;
    lastFrameAtRef.current = performance.now();
    energyGateRunRef.current = 0;
    captureRecoveryRef.current = {
      inFlight: false,
      attempts: 0,
      lastAttemptAt: 0,
      recoveredAt: 0,
    };
    captureStartingRef.current = true;

    ensurePlayer();
    speakerRef.current?.primeVoices();

    try {
      if (!captureRef.current) captureRef.current = new AudioCapture();
      const initialCapture = captureRef.current;
      await initialCapture.start({
        onFrame: handleFrame,
        onLevel: (rms) => setLevel(rms),
        onStreamLost: (reason) => {
          if (captureRef.current === initialCapture) {
            void recoverCapture(reason, initialCapture);
          }
        },
      });
      lastFrameAtRef.current = performance.now();
      setCaptureStream(initialCapture.mediaStream);
      if (!activeRef.current) {
        await initialCapture.stop();
        captureRef.current = null;
        setCaptureStream(null);
        return;
      }
    } catch (cause) {
      const wasActive = activeRef.current;
      activeRef.current = false;
      byokRef.current = false;
      byokSettingsRef.current = null;
      directAbortRef.current?.abort();
      directAbortRef.current = null;
      stopCaptureWatchdog();
      await captureRef.current?.stop();
      captureRef.current = null;
      setCaptureStream(null);
      if (!wasActive) return;
      const message =
        cause instanceof DOMException && cause.name === "NotAllowedError"
          ? "Microphone permission was denied. Allow access in your browser and try again."
          : cause instanceof Error
            ? cause.message
            : "Could not access the microphone.";
      pushError(message);
      setStatus("error");
      return;
    } finally {
      captureStartingRef.current = false;
    }

    startCaptureWatchdog();
    const stream = captureRef.current.mediaStream;
    if (stream) void startLocalVad(stream, captureRef.current.audioContext);

    await playerRef.current?.resume();
    if (!activeRef.current) return;
    if (direct) {
      const directVoice = voiceRef.current ?? "shubh";
      const readyEvent: ReadyEvent = {
        type: "ready",
        session_id: `local-${crypto.randomUUID()}`,
        audio: { format: "pcm16", input_sample_rate: 16_000, frame_ms: 20 },
        stt: {
          name: "sarvam-direct",
          partials: false,
          mode: "server-stt",
        },
        llm: { name: "browser-direct" },
        tts: {
          name: "sarvam-direct",
          kind: "audio",
          sample_rate: BYOK_TTS_SAMPLE_RATE,
          voice: directVoice,
        },
        vad: {
          name: "local",
          threshold: 0.014,
          end_silence_ms: 650,
        },
        platform: { limited: false, turn_limit: null },
        targets: {
          first_audio_p50_ms: 700,
          first_audio_p95_ms: 1_000,
          barge_in_p95_ms: 200,
        },
      };
      readyRef.current = readyEvent;
      setReady(readyEvent);
      voiceRef.current = directVoice;
      voiceKindRef.current = "audio";
      setVoiceState(directVoice);
      setStatus("connected");
      setAgentState("listening");
      return;
    }
    connectSocket();
  }, [
    clearTurnWatchdog,
    clearVadTailTimer,
    connectSocket,
    ensurePlayer,
    handleFrame,
    pushError,
    recoverCapture,
    startCaptureWatchdog,
    startLocalVad,
    stopCaptureWatchdog,
    quotaExhausted,
  ]);

  const stop = useCallback(async () => {
    activeRef.current = false;
    byokRef.current = false;
    byokSettingsRef.current = null;
    directGenerationRef.current += 1;
    directAbortRef.current?.abort();
    directAbortRef.current = null;
    directUtteranceRef.current = [];
    directTurnInFlightRef.current = false;
    sessionTokenRef.current += 1;
    intentionalCloseRef.current = true;
    stopCaptureWatchdog();
    captureStartingRef.current = false;
    captureRecoveryRef.current = {
      inFlight: false,
      attempts: 0,
      lastAttemptAt: 0,
      recoveredAt: 0,
    };
    lastFrameAtRef.current = 0;
    energyGateRunRef.current = 0;
    if (reconnectTimerRef.current) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    clearTurnWatchdog();
    clearVadTailTimer();
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    stopPlayback();
    const vad = localVadRef.current;
    localVadRef.current = null;
    vadStatusRef.current = "off";
    setVadStatus("off");
    vadSpeakingRef.current = false;
    vadConfirmedRef.current = false;
    vadStartedAtRef.current = null;
    vadGateOpenRef.current = true;
    preRollRef.current = [];
    turnsRef.current.reset();
    activeTurnRef.current = null;
    await vad?.destroy();
    await captureRef.current?.stop();
    captureRef.current = null;
    setCaptureStream(null);
    await playerRef.current?.close();
    playerRef.current = null;
    speakerRef.current = null;
    wsRef.current?.close();
    wsRef.current = null;
    readyRef.current = null;
    setReady(null);
    setStatus(fatalConnectionRef.current ? "error" : "idle");
    setAgentState("idle");
    setLevel(IDLE_LEVEL);
    setMuted(false);
    mutedRef.current = false;
    currentAssistantTurnRef.current = null;
    currentUserMessageIdRef.current = null;
  }, [clearTurnWatchdog, clearVadTailTimer, stopCaptureWatchdog, stopPlayback]);

  useEffect(() => {
    stopRef.current = stop;
  }, [stop]);

  const interrupt = useCallback(() => {
    const turnId =
      activeTurnRef.current ?? currentAssistantTurnRef.current ?? null;
    if (turnId) {
      turnsRef.current.interrupt(turnId);
      settleAssistantMessage(turnId, { interrupted: true });
    }
    activeTurnRef.current = null;
    clearTurnWatchdog();
    stopPlayback();
    send({
      type: "interrupt",
      reason: "manual",
      ...(turnId ? { turn_id: turnId } : {}),
    });
    setAgentState("listening");
  }, [clearTurnWatchdog, send, settleAssistantMessage, stopPlayback]);

  const toggleMute = useCallback(() => {
    setMuted((previous) => {
      const next = !previous;
      mutedRef.current = next;
      // Drop anything buffered before the change and wait for a fresh,
      // confirmed onset after it.
      preRollRef.current = [];
      vadGateOpenRef.current = false;
      return next;
    });
  }, []);

  useEffect(() => {
    return () => {
      activeRef.current = false;
      directGenerationRef.current += 1;
      directAbortRef.current?.abort();
      directAbortRef.current = null;
      sessionTokenRef.current += 1;
      intentionalCloseRef.current = true;
      if (reconnectTimerRef.current)
        window.clearTimeout(reconnectTimerRef.current);
      if (turnWatchdogRef.current) window.clearTimeout(turnWatchdogRef.current);
      if (vadTailTimerRef.current) window.clearTimeout(vadTailTimerRef.current);
      if (captureWatchdogRef.current)
        window.clearInterval(captureWatchdogRef.current);
      recognitionRef.current?.abort();
      const vad = localVadRef.current;
      localVadRef.current = null;
      const capture = captureRef.current;
      captureRef.current = null;
      const player = playerRef.current;
      playerRef.current = null;
      void (async () => {
        // The VAD shares the capture context, so it must disconnect before the
        // context is closed.
        await vad?.destroy();
        await capture?.stop();
        await player?.close();
      })();
      wsRef.current?.close();
    };
  }, []);

  const clearConversation = useCallback(() => {
    clearMessages();
    currentUserMessageIdRef.current = null;
    completedTurnsRef.current.clear();
    turnDiagRef.current.clear();
    setDiagnostics([]);
  }, [clearMessages]);

  const summary = useMemo(() => {
    const firstPlayback = diagnostics
      .map((diag) => diag.firstPlayback)
      .filter((value): value is number => typeof value === "number");
    const bargeIn = diagnostics
      .map((diag) => diag.bargeIn)
      .filter((value): value is number => typeof value === "number");
    return {
      turns: diagnostics.length,
      firstPlaybackP50: percentile(firstPlayback, 50),
      firstPlaybackP95: percentile(firstPlayback, 95),
      bargeInP95: percentile(bargeIn, 95),
    };
  }, [diagnostics]);

  return {
    status,
    agentState,
    ready,
    messages,
    level,
    error,
    muted,
    vadStatus,
    diagnostics,
    summary,
    stream: captureStream,
    voices: options,
    voice,
    selectVoice,
    start,
    stop,
    interrupt,
    toggleMute,
    clearConversation,
    dismissError: () => setError(null),
    quotaExhausted,
    quotaNoticeVisible: quotaExhausted !== null && !quotaNoticeDismissed,
    dismissQuotaNotice: () => setQuotaNoticeDismissed(true),
    clearQuotaExhausted: () => {
      setQuotaExhausted(null);
      setQuotaNoticeDismissed(false);
    },
  };
}
