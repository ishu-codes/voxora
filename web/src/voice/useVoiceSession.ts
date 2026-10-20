import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { VoiceOption } from "@/components/ui/voice-picker";
import { API_URL } from "@/lib/voice-catalog";
import { loadVoiceSettings, toConfigurePayload } from "@/lib/voice-settings";
import { AudioCapture, AudioPlayer, decodePcm16 } from "./audio";
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
  const [messages, setMessages] = useState<VoiceMessage[]>([]);
  const [level, setLevel] = useState(IDLE_LEVEL);
  const [error, setError] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);
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
  const intentionalCloseRef = useRef(false);
  const readyRef = useRef<ReadyEvent | null>(null);
  const mutedRef = useRef(false);
  const voiceRef = useRef<string | undefined>(undefined);
  const voiceKindRef = useRef<"browser" | "audio" | null>(null);
  const catalogRef = useRef(catalog);
  catalogRef.current = catalog;
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<number | null>(null);
  const suppressTurnRef = useRef<string | null>(null);

  const connectSocketRef = useRef<() => void>(() => undefined);
  const currentUserMessageIdRef = useRef<string | null>(null);
  const currentAssistantTurnRef = useRef<string | null>(null);
  const speechEndAtRef = useRef<number | null>(null);
  const voicedAtRef = useRef<number | null>(null);
  const turnDiagRef = useRef<Map<string, TurnDiagnostics>>(new Map());
  const localVadRef = useRef({
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
    [],
  );

  const appendAssistantMessage = useCallback((turnId: string, text: string) => {
    setMessages((previous) => {
      const index = previous.findIndex(
        (message) => message.role === "assistant" && message.turnId === turnId,
      );
      if (index >= 0) {
        const copy = [...previous];
        copy[index] = {
          ...copy[index],
          text: copy[index].text + text,
          final: false,
        };
        return copy;
      }
      return [
        ...previous,
        {
          id: `assistant-${turnId}`,
          role: "assistant",
          text,
          final: false,
          turnId,
          at: Date.now(),
        },
      ];
    });
  }, []);

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
          setAgentState((previous) =>
            previous === "speaking" ? "listening" : previous,
          );
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
                diag.bargeIn = Math.round(
                  performance.now() - voicedAtRef.current,
                );
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
          settleAssistantMessage(event.turn_id, {
            text: event.text || undefined,
          });
          suppressTurnRef.current = null;
          if (
            !playerRef.current?.isSpeaking &&
            !speakerRef.current?.isSpeaking
          ) {
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
              diag.bargeIn = Math.round(
                performance.now() - voicedAtRef.current,
              );
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
          setAgentState((previous) =>
            previous === "speaking" ? previous : "thinking",
          );
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
      ws.send(JSON.stringify(toConfigurePayload(loadVoiceSettings())));
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
      if (activeRef.current) pushError("Voice connection error.");
    };
    ws.onclose = () => {
      if (wsRef.current !== ws) return;
      wsRef.current = null;
      if (intentionalCloseRef.current || !activeRef.current) {
        setStatus((current) => (current === "error" ? current : "idle"));
        return;
      }
      scheduleReconnect();
    };
  }, [handleServerEvent, pushError, scheduleReconnect]);

  useEffect(() => {
    connectSocketRef.current = connectSocket;
  }, [connectSocket]);

  const start = useCallback(async () => {
    if (activeRef.current) return;
    setError(null);
    setMessages([]);
    setStatus("connecting");
    activeRef.current = true;
    reconnectAttemptsRef.current = 0;
    turnDiagRef.current.clear();
    setDiagnostics([]);
    localVadRef.current = {
      speaking: false,
      voicedRun: 0,
      silenceMs: 0,
      startedAt: 0,
    };
    speechEndAtRef.current = null;

    ensurePlayer();
    speakerRef.current?.primeVoices();

    try {
      if (!captureRef.current) captureRef.current = new AudioCapture();
      await captureRef.current.start({
        onFrame: handleFrame,
        onLevel: (rms) => setLevel(rms),
      });
      setCaptureStream(captureRef.current.mediaStream);
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
    setCaptureStream(null);
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
      if (reconnectTimerRef.current)
        window.clearTimeout(reconnectTimerRef.current);
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
    stream: captureStream,
    voices: options,
    voice,
    selectVoice,
    start,
    stop,
    interrupt,
    toggleMute,
    dismissError: () => setError(null),
  };
}
