import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { AudioCapture, AudioPlayer, decodePcm16 } from "./audio";
import { isServerEvent, type AgentState, type ConnectionStatus, type ReadyEvent, type ServerEvent } from "./protocol";
import { BrowserSpeaker, createRecognition, supportsBrowserStt, type Recognition } from "./speech";

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
  diagnostics: TurnDiagnostics[];
};

const API_URL = ((import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL as string) || "http://localhost:8000";
const WS_URL_OVERRIDE = (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_VOICE_WS as string | undefined;

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
  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [agentState, setAgentState] = useState<AgentState>("idle");
  const [ready, setReady] = useState<ReadyEvent | null>(null);
  const [messages, setMessages] = useState<VoiceMessage[]>([]);
  const [level, setLevel] = useState(IDLE_LEVEL);
  const [error, setError] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);
  const [diagnostics, setDiagnostics] = useState<TurnDiagnostics[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const captureRef = useRef<AudioCapture | null>(null);
  const playerRef = useRef<AudioPlayer | null>(null);
  const speakerRef = useRef<BrowserSpeaker | null>(null);
  const recognitionRef = useRef<Recognition | null>(null);

  const activeRef = useRef(false);
  const intentionalCloseRef = useRef(false);
  const readyRef = useRef<ReadyEvent | null>(null);
  const mutedRef = useRef(false);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<number | null>(null);
  const suppressTurnRef = useRef<string | null>(null);

  const currentUserMessageIdRef = useRef<string | null>(null);
  const currentAssistantTurnRef = useRef<string | null>(null);
  const speechEndAtRef = useRef<number | null>(null);
  const voicedAtRef = useRef<number | null>(null);
  const turnDiagRef = useRef<Map<string, TurnDiagnostics>>(new Map());
  const localVadRef = useRef({ speaking: false, voicedRun: 0, silenceMs: 0, startedAt: 0 });

  const publishDiagnostics = useCallback(() => {
    setDiagnostics(Array.from(turnDiagRef.current.values()).slice(-24));
  }, []);

  const ensureTurnDiagnostics = useCallback(
    (turnId: string): TurnDiagnostics => {
      const existing = turnDiagRef.current.get(turnId);
      if (existing) return existing;
      const created: TurnDiagnostics = { turnId, serverE2e: null, startedAt: Date.now() };
      turnDiagRef.current.set(turnId, created);
      return created;
    },
    [],
  );

  const pushError = useCallback((message: string) => {
    setError(message);
    toast.error(message);
  }, []);

  const send = useCallback((payload: unknown): boolean => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(payload));
    return true;
  }, []);

  const sendTurnMetrics = useCallback(
    (turnId: string, metrics: Record<string, number>) => {
      if (Object.keys(metrics).length) send({ type: "metrics", turn_id: turnId, metrics });
    },
    [send],
  );

  const upsertUserMessage = useCallback((text: string, final: boolean, turnId?: string) => {
    const existingId = currentUserMessageIdRef.current;
    setMessages((previous) => {
      if (existingId) {
        const index = previous.findIndex((message) => message.id === existingId);
        if (index >= 0) {
          const copy = [...previous];
          copy[index] = { ...copy[index], text, final, turnId: turnId ?? copy[index].turnId };
          return copy;
        }
      }
      const id = turnId ? `user-${turnId}` : `user-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
      currentUserMessageIdRef.current = final ? null : id;
      return [...previous, { id, role: "user", text, final, turnId, at: Date.now() }];
    });
    if (final) currentUserMessageIdRef.current = null;
  }, []);

  const appendAssistantMessage = useCallback((turnId: string, text: string) => {
    setMessages((previous) => {
      const index = previous.findIndex(
        (message) => message.role === "assistant" && message.turnId === turnId,
      );
      if (index >= 0) {
        const copy = [...previous];
        copy[index] = { ...copy[index], text: copy[index].text + text, final: false };
        return copy;
      }
      return [
        ...previous,
        { id: `assistant-${turnId}`, role: "assistant", text, final: false, turnId, at: Date.now() },
      ];
    });
  }, []);

  const settleAssistantMessage = useCallback(
    (turnId: string, patch: Partial<VoiceMessage>) => {
      setMessages((previous) => {
        const index = previous.findIndex(
          (message) => message.role === "assistant" && message.turnId === turnId,
        );
        if (index < 0) return previous;
        const copy = [...previous];
        copy[index] = { ...copy[index], final: true, ...patch };
        return copy;
      });
    },
    [],
  );

  const stopPlayback = useCallback(() => {
    playerRef.current?.stop();
    speakerRef.current?.stop();
  }, []);

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

  const ensurePlayer = useCallback((): AudioPlayer => {
    if (!playerRef.current) {
      playerRef.current = new AudioPlayer({
        onSpeakingChange: (speaking) => {
          setAgentState((previous) => {
            if (speaking) return "speaking";
            return previous === "speaking" ? "listening" : previous;
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
          const turnId = currentAssistantTurnRef.current;
          if (turnId) recordFirstPlayback(turnId);
          setAgentState("speaking");
        },
        onEnd: () => {
          setAgentState((previous) => (previous === "speaking" ? "listening" : previous));
        },
      });
    }
    return playerRef.current;
  }, [recordFirstPlayback]);

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
          if (event.stt.mode === "browser-stt" && !recognitionRef.current && activeRef.current) {
            startRecognition();
          }
          break;
        }
        case "state": {
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
          // The backend already cancelled the turn; make sure local playback
          // stops on the same frame the user starts speaking.
          if (playerRef.current?.isSpeaking || speakerRef.current?.isSpeaking) {
            stopPlayback();
            const turnId = currentAssistantTurnRef.current;
            if (turnId && voicedAtRef.current != null) {
              const diag = ensureTurnDiagnostics(turnId);
              if (diag.bargeIn == null) {
                diag.bargeIn = Math.round(performance.now() - voicedAtRef.current);
                publishDiagnostics();
                sendTurnMetrics(turnId, { barge_in_ms: diag.bargeIn });
              }
            }
            if (turnId) suppressTurnRef.current = turnId;
          }
          setAgentState("listening");
          break;
        case "transcript.partial":
          upsertUserMessage(event.text, false);
          break;
        case "transcript.final": {
          upsertUserMessage(event.text, true, event.turn_id);
          currentAssistantTurnRef.current = event.turn_id;
          ensureTurnDiagnostics(event.turn_id);
          publishDiagnostics();
          suppressTurnRef.current = null;
          setAgentState("thinking");
          break;
        }
        case "assistant.delta":
          appendAssistantMessage(event.turn_id, event.text);
          if (!playerRef.current?.isSpeaking) setAgentState("thinking");
          break;
        case "speak.chunk":
          currentAssistantTurnRef.current = event.turn_id;
          speakerRef.current?.speak(event.text);
          break;
        case "speak.end":
          break;
        case "audio.chunk": {
          if (suppressTurnRef.current === event.turn_id) break;
          currentAssistantTurnRef.current = event.turn_id;
          const player = ensurePlayer();
          player.enqueue(decodePcm16(event.data), event.sample_rate);
          break;
        }
        case "assistant.done": {
          settleAssistantMessage(event.turn_id, { text: event.text || undefined });
          suppressTurnRef.current = null;
          if (!playerRef.current?.isSpeaking && !speakerRef.current?.isSpeaking) {
            setAgentState("listening");
          }
          break;
        }
        case "assistant.failed":
          settleAssistantMessage(event.turn_id, { failed: true });
          setAgentState("listening");
          break;
        case "turn.cancelled": {
          stopPlayback();
          settleAssistantMessage(event.turn_id, { interrupted: true });
          suppressTurnRef.current = null;
          setAgentState("listening");
          if (event.reason === "barge_in") {
            const diag = ensureTurnDiagnostics(event.turn_id);
            if (diag.bargeIn == null && voicedAtRef.current != null) {
              diag.bargeIn = Math.round(performance.now() - voicedAtRef.current);
              publishDiagnostics();
              sendTurnMetrics(event.turn_id, { barge_in_ms: diag.bargeIn });
            }
          }
          break;
        }
        case "turn.empty":
          currentUserMessageIdRef.current = null;
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
          pushError(event.message);
          if (event.stage !== "stt") setAgentState("listening");
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
          if (activeRef.current && readyRef.current?.stt.mode === "browser-stt") {
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
      ensurePlayer,
      ensureTurnDiagnostics,
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
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN && !mutedRef.current) {
        ws.send(pcm.buffer.slice(0) as ArrayBuffer);
      }

      let sum = 0;
      for (let i = 0; i < pcm.length; i += 1) {
        const value = pcm[i] / 32768;
        sum += value * value;
      }
      const rms = Math.sqrt(sum / pcm.length);
      const now = performance.now();
      const vad = localVadRef.current;
      const threshold = readyRef.current?.vad.threshold ?? 0.012;

      if (!vad.speaking) {
        vad.voicedRun = rms >= threshold ? vad.voicedRun + 1 : 0;
        if (vad.voicedRun >= BARGE_IN_VOICED_FRAMES) {
          vad.speaking = true;
          vad.silenceMs = 0;
          vad.startedAt = now;
          voicedAtRef.current = now - BARGE_IN_VOICED_FRAMES * 20;
          // Local barge-in: cut playback before the server round-trip lands.
          // The server VAD detects the same onset and cancels outstanding work,
          // so no extra interrupt message is needed here.
          if (playerRef.current?.isSpeaking || speakerRef.current?.isSpeaking) {
            const turnId = currentAssistantTurnRef.current;
            stopPlayback();
            if (turnId) {
              const diag = ensureTurnDiagnostics(turnId);
              if (diag.bargeIn == null && voicedAtRef.current != null) {
                diag.bargeIn = Math.round(now - voicedAtRef.current);
                publishDiagnostics();
                sendTurnMetrics(turnId, { barge_in_ms: diag.bargeIn });
              }
              suppressTurnRef.current = turnId;
            }
          }
        }
      } else {
        if (rms >= threshold) {
          vad.silenceMs = 0;
        } else {
          vad.silenceMs += 20;
        }
        const endSilence = readyRef.current?.vad.end_silence_ms ?? 650;
        if (vad.silenceMs >= endSilence || now - vad.startedAt > 30_000) {
          vad.speaking = false;
          vad.voicedRun = 0;
          vad.silenceMs = 0;
          speechEndAtRef.current = now;
          setAgentState((previous) => (previous === "speaking" ? previous : "thinking"));
        }
      }
    },
    [ensureTurnDiagnostics, publishDiagnostics, sendTurnMetrics, stopPlayback],
  );

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
      if (activeRef.current) connectSocket();
    }, delay);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pushError]);

  const connectSocket = useCallback(() => {
    if (reconnectTimerRef.current) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    const previous = wsRef.current;
    if (previous && (previous.readyState === WebSocket.OPEN || previous.readyState === WebSocket.CONNECTING)) {
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
      if (activeRef.current) pushError("Voice connection error.");
    };
    ws.onclose = () => {
      if (wsRef.current === ws) wsRef.current = null;
      if (intentionalCloseRef.current || !activeRef.current) {
        setStatus((current) => (current === "error" ? current : "idle"));
        return;
      }
      scheduleReconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handleServerEvent, pushError, scheduleReconnect]);

  const start = useCallback(async () => {
    if (activeRef.current) return;
    setError(null);
    setMessages([]);
    setStatus("connecting");
    activeRef.current = true;
    reconnectAttemptsRef.current = 0;
    turnDiagRef.current.clear();
    setDiagnostics([]);
    localVadRef.current = { speaking: false, voicedRun: 0, silenceMs: 0, startedAt: 0 };
    speechEndAtRef.current = null;

    ensurePlayer();
    speakerRef.current?.primeVoices();

    try {
      if (!captureRef.current) captureRef.current = new AudioCapture();
      await captureRef.current.start({ onFrame: handleFrame, onLevel: (rms) => setLevel(rms) });
    } catch (cause) {
      activeRef.current = false;
      const message =
        cause instanceof DOMException && cause.name === "NotAllowedError"
          ? "Microphone permission was denied. Allow access in your browser and try again."
          : cause instanceof Error
            ? cause.message
            : "Could not access the microphone.";
      pushError(message);
      setStatus("error");
      return;
    }

    await playerRef.current?.resume();
    connectSocket();
  }, [connectSocket, ensurePlayer, handleFrame, pushError]);

  const stop = useCallback(async () => {
    activeRef.current = false;
    intentionalCloseRef.current = true;
    if (reconnectTimerRef.current) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    stopPlayback();
    await captureRef.current?.stop();
    captureRef.current = null;
    await playerRef.current?.close();
    playerRef.current = null;
    speakerRef.current = null;
    wsRef.current?.close();
    wsRef.current = null;
    readyRef.current = null;
    setReady(null);
    setStatus("idle");
    setAgentState("idle");
    setLevel(IDLE_LEVEL);
    setMuted(false);
    mutedRef.current = false;
    currentAssistantTurnRef.current = null;
    currentUserMessageIdRef.current = null;
  }, [stopPlayback]);

  const interrupt = useCallback(() => {
    stopPlayback();
    send({ type: "interrupt", reason: "manual" });
    setAgentState("listening");
  }, [send, stopPlayback]);

  const toggleMute = useCallback(() => {
    setMuted((previous) => {
      const next = !previous;
      mutedRef.current = next;
      return next;
    });
  }, []);

  useEffect(() => {
    return () => {
      activeRef.current = false;
      intentionalCloseRef.current = true;
      if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current);
      recognitionRef.current?.abort();
      void captureRef.current?.stop();
      void playerRef.current?.close();
      wsRef.current?.close();
    };
  }, []);

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
    diagnostics,
    summary,
    start,
    stop,
    interrupt,
    toggleMute,
    dismissError: () => setError(null),
  };
}
