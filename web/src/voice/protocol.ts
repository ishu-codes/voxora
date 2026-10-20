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
  audio: { format: "pcm16"; input_sample_rate: number; frame_ms: number };
  stt: ProviderInfo & { partials: boolean; mode: "browser-stt" | "server-stt" };
  llm: ProviderInfo;
  tts: ProviderInfo & {
    kind: "audio" | "browser";
    sample_rate: number;
    voice?: string;
  };
  vad: { name: string; threshold: number; end_silence_ms: number };
  platform?: { limited: boolean; turn_limit: number | null };
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
    }
  | {
      type: "turn.cancelled";
      turn_id: string;
      reason: "barge_in" | "manual" | string;
    }
  | { type: "turn.empty"; turn_id: string }
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
    }
  | { type: "pong" };

export type AgentState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
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
      byok: {
        sarvam_api_key: string;
        openai_api_key: string;
        openai_base_url: string;
        openai_model: string;
      };
    }
  | { type: "transcript"; text: string; final: boolean }
  | { type: "interrupt"; reason?: string }
  | { type: "voice"; voice: string }
  | { type: "metrics"; turn_id: string; metrics: Record<string, number> }
  | { type: "playback.done" }
  | { type: "ping" };

export function isServerEvent(value: unknown): value is ServerEvent {
  return typeof value === "object" && value !== null && "type" in value;
}
