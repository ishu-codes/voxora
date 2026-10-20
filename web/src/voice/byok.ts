import type { VoiceSettings } from "@/lib/voice-settings";

const SARVAM_API_URL = "https://api.sarvam.ai";
const TTS_SAMPLE_RATE = 22_050;

export const BYOK_SYSTEM_PROMPT =
  "You are Voxora, a friendly real-time voice assistant. Your replies are " +
  "spoken aloud, so answer in plain conversational language. Never use " +
  "markdown, bullet lists, headings, emoji, or code fences. Keep most answers " +
  "to two or three short sentences unless the user asks for depth. If you are " +
  "unsure, say so briefly instead of inventing details.";

export type DirectTurnMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

type SarvamErrorBody = {
  error?: { message?: string };
  detail?: string;
};

async function responseError(
  response: Response,
  label: string,
): Promise<Error> {
  let detail = "";
  try {
    const body = (await response.json()) as SarvamErrorBody;
    detail = body.error?.message ?? body.detail ?? "";
  } catch {
    detail = await response.text().catch(() => "");
  }
  return new Error(
    `${label} failed (${response.status})${detail ? `: ${detail.slice(0, 200)}` : ""}`,
  );
}

function pcmWav(frames: Int16Array[]): Blob {
  const sampleCount = frames.reduce((total, frame) => total + frame.length, 0);
  const buffer = new ArrayBuffer(44 + sampleCount * 2);
  const view = new DataView(buffer);
  const write = (offset: number, text: string) => {
    for (let index = 0; index < text.length; index += 1) {
      view.setUint8(offset + index, text.charCodeAt(index));
    }
  };

  write(0, "RIFF");
  view.setUint32(4, 36 + sampleCount * 2, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, 16_000, true);
  view.setUint32(28, 32_000, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, sampleCount * 2, true);

  let offset = 44;
  for (const frame of frames) {
    for (let index = 0; index < frame.length; index += 1) {
      view.setInt16(offset, frame[index], true);
      offset += 2;
    }
  }
  return new Blob([buffer], { type: "audio/wav" });
}

export async function transcribeWithSarvam(
  settings: VoiceSettings,
  frames: Int16Array[],
  signal: AbortSignal,
): Promise<string> {
  if (process.env.NODE_ENV !== "production") {
    const samples = frames.reduce((total, frame) => total + frame.length, 0);
    console.info("[byok] transcribing", { frames: frames.length, samples });
  }
  const form = new FormData();
  form.append("file", pcmWav(frames), "utterance.wav");
  form.append("model", "saaras:v3");
  form.append("mode", "transcribe");
  form.append("language_code", "en-IN");

  const response = await fetch(`${SARVAM_API_URL}/speech-to-text`, {
    method: "POST",
    headers: { "api-subscription-key": settings.sarvamApiKey },
    body: form,
    signal,
  });
  if (!response.ok) throw await responseError(response, "Speech recognition");
  const payload = (await response.json()) as { transcript?: string };
  if (process.env.NODE_ENV !== "production") {
    console.info("[byok] transcript", {
      chars: payload.transcript?.trim().length ?? 0,
    });
  }
  return payload.transcript?.trim() ?? "";
}

export async function streamByokLlm(
  settings: VoiceSettings,
  messages: DirectTurnMessage[],
  signal: AbortSignal,
  onToken: (token: string) => void,
): Promise<string> {
  const baseUrl = (
    settings.openaiBaseUrl || "https://api.openai.com/v1"
  ).replace(/\/+$/, "");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (settings.openaiApiKey) {
    headers.Authorization = `Bearer ${settings.openaiApiKey}`;
  }

  const response = await fetch(`${baseUrl}/chat/completions`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      model: settings.openaiModel || "gpt-4o-mini",
      messages,
      stream: true,
      temperature: 0.7,
      max_tokens: 320,
    }),
    signal,
  });
  if (!response.ok) throw await responseError(response, "Language model");
  if (!response.body) throw new Error("Language model returned no stream.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const tokens: string[] = [];

  const consumeLine = (line: string) => {
    const trimmed = line.trim();
    if (!trimmed) return false;
    const data = trimmed.startsWith("data:")
      ? trimmed.slice(5).trim()
      : trimmed;
    if (data === "[DONE]") return true;
    try {
      const event = JSON.parse(data) as {
        choices?: Array<{ delta?: { content?: string | null } }>;
      };
      const token = event.choices?.[0]?.delta?.content;
      if (token) {
        tokens.push(token);
        onToken(token);
      }
    } catch {
      // Ignore provider keepalive or malformed frames.
    }
    return false;
  };

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (consumeLine(line)) return tokens.join("");
    }
    if (done) break;
  }
  if (buffer) consumeLine(buffer);
  return tokens.join("");
}

function decodeLinear16(base64: string): Int16Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }

  let offset = 0;
  if (
    bytes.length >= 44 &&
    String.fromCharCode(...bytes.slice(0, 4)) === "RIFF"
  ) {
    offset = 12;
    while (offset + 8 <= bytes.length) {
      const id = String.fromCharCode(...bytes.slice(offset, offset + 4));
      const size =
        bytes[offset + 4] |
        (bytes[offset + 5] << 8) |
        (bytes[offset + 6] << 16) |
        (bytes[offset + 7] << 24);
      offset += 8;
      if (id === "data") break;
      offset += Math.max(0, size);
    }
  }

  const samples = Math.floor((bytes.length - offset) / 2);
  return new Int16Array(bytes.buffer, bytes.byteOffset + offset, samples);
}

export async function synthesizeWithSarvam(
  settings: VoiceSettings,
  text: string,
  voice: string | null,
  signal: AbortSignal,
  model = "bulbul:v3",
): Promise<Int16Array> {
  const response = await fetch(`${SARVAM_API_URL}/text-to-speech`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "api-subscription-key": settings.sarvamApiKey,
    },
    body: JSON.stringify({
      text,
      model,
      speaker: voice || "shubh",
      language_code: "en-IN",
      speech_sample_rate: TTS_SAMPLE_RATE,
      output_audio_codec: "linear16",
      temperature: 0.6,
      pace: 1,
    }),
    signal,
  });
  if (!response.ok) throw await responseError(response, "Speech synthesis");
  const payload = (await response.json()) as { audios?: string[] };
  const encoded = payload.audios?.[0];
  if (!encoded) throw new Error("Speech synthesis returned no audio.");
  return decodeLinear16(encoded);
}

export class DirectSentenceChunker {
  private buffer = "";
  private readonly minChars: number;
  private readonly maxChars: number;

  constructor(minChars = 24, maxChars = 220) {
    this.minChars = minChars;
    this.maxChars = maxChars;
  }

  feed(text: string): string[] {
    this.buffer += text;
    const chunks: string[] = [];
    while (true) {
      const match = /[.!?;:](?=\s)|\n+/.exec(this.buffer);
      if (match && match.index >= this.minChars) {
        const boundary = match[0].length;
        chunks.push(this.buffer.slice(0, match.index + boundary).trim());
        this.buffer = this.buffer.slice(match.index + boundary).trimStart();
        continue;
      }
      if (this.buffer.length > this.maxChars) {
        let split = this.buffer.lastIndexOf(" ", this.maxChars);
        if (split < this.minChars) split = this.maxChars;
        chunks.push(this.buffer.slice(0, split).trim());
        this.buffer = this.buffer.slice(split).trimStart();
        continue;
      }
      break;
    }
    return chunks.filter(Boolean);
  }

  flush(): string | null {
    const value = this.buffer.trim();
    this.buffer = "";
    return value || null;
  }
}

export const BYOK_TTS_SAMPLE_RATE = TTS_SAMPLE_RATE;
