/**
 * Wire protocol shared with the Voxora FastAPI backend.
 * Keep in sync with `api/src/voice/pipeline.py`.
 */

export type ProviderInfo = {
  name: string;
  reason?: string;
};

export type ReadyEvent = {
  type: "ready";
  session_id: string;
  scenario_id?: string | null;
  audio: { format: "pcm16"; input_sample_rate: number; frame_ms: number };
  stt: ProviderInfo & {
    partials: boolean;
    mode: "browser-stt" | "server-stt";
    language?: string;
  };
  llm: ProviderInfo;
  tts: ProviderInfo & {
    kind: "audio" | "browser";
    sample_rate: number;
    voice?: string;
  };
  vad: { name: string; threshold: number; end_silence_ms: number };
  platform?: {
    limited: boolean;
    turn_limit: number | null;
    window_seconds?: number | null;
  };
  targets: {
    first_audio_p50_ms: number;
    first_audio_p95_ms: number;
    barge_in_p95_ms: number;
  };
};

export type ServerEvent =
  | ReadyEvent
  | { type: "state"; state: AgentState; turn_id: string }
  | { type: "audio.level"; rms: number; speech: boolean }
  | { type: "speech.start"; turn_id: string }
  | { type: "transcript.partial"; text: string; final?: boolean }
  | { type: "transcript.final"; turn_id: string; text: string }
  | { type: "assistant.delta"; turn_id: string; text: string }
  | { type: "assistant.done"; turn_id: string; text: string }
  | { type: "assistant.failed"; turn_id: string }
  | { type: "speak.chunk"; turn_id: string; text: string; index: number }
  | { type: "speak.end"; turn_id: string }
  | {
      type: "audio.chunk";
      turn_id: string;
      data: string;
      sample_rate: number;
      format: "pcm16";
      /** Spoken sentence that begins at this first chunk of audio. */
      text?: string;
    }
  | {
      type: "turn.cancelled";
      turn_id: string;
      reason: "barge_in" | "manual" | string;
    }
  | { type: "turn.empty"; turn_id: string }
  | {
      type: "turn.timing";
      turn_id: string;
      stage: "speech_end" | "llm_first_token";
    }
  | {
      type: "turn.metrics";
      turn_id: string;
      metrics: Record<string, number | null>;
    }
  | {
      type: "error";
      turn_id?: string;
      stage: string;
      message: string;
      recoverable: boolean;
      retry_after_s?: number;
      code?: string;
      limit?: number;
      remaining?: number;
    }
  | { type: "pong" };

export type AgentState =
  | "idle"
  | "listening"
  | "capturing"
  | "thinking"
  | "speaking"
  | "interrupted"
  | "error";

export type ConnectionStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "error";

export type ClientEvent =
  | {
      type: "configure";
      client?: {
        installation_id: string;
        screen_width: number;
        screen_height: number;
        viewport_width: number;
        viewport_height: number;
        pixel_ratio: number;
        color_depth: number;
        timezone: string;
        language: string;
        platform: string;
        hardware_concurrency: number;
        device_memory: number;
        touch_points: number;
        webdriver: boolean;
      };
    }
  | { type: "transcript"; text: string; final: boolean }
  | { type: "interrupt"; reason?: string; turn_id?: string }
  | { type: "voice"; voice: string }
  | { type: "metrics"; turn_id: string; metrics: Record<string, number> }
  | { type: "playback.done" }
  | { type: "ping" };

export function isServerEvent(value: unknown): value is ServerEvent {
  return typeof value === "object" && value !== null && "type" in value;
}
