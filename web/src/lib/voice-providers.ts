import { API_URL } from "./voice-catalog";

export type ProviderChoice = {
  id: string;
  name: string;
  model: string;
  available: boolean;
};

export type ProviderConfig = {
  sttProvider: string;
  ttsProvider: string;
  stt: ProviderChoice[];
  tts: ProviderChoice[];
};

type RawProviderConfig = {
  stt?: {
    provider?: unknown;
    providers?: unknown;
  };
  tts?: {
    provider?: unknown;
    providers?: unknown;
  };
};

function choices(value: unknown): ProviderChoice[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (typeof item !== "object" || item === null) return [];
    const record = item as Record<string, unknown>;
    if (
      typeof record.id !== "string" ||
      typeof record.name !== "string" ||
      typeof record.model !== "string"
    ) {
      return [];
    }
    return [
      {
        id: record.id,
        name: record.name,
        model: record.model,
        available: record.available !== false,
      },
    ];
  });
}

export async function getProviderConfig(): Promise<ProviderConfig | null> {
  try {
    const response = await fetch(`${API_URL}/api/v1/voice/config`, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) return null;
    const payload = (await response.json()) as RawProviderConfig;
    const stt = choices(payload.stt?.providers);
    const tts = choices(payload.tts?.providers);
    if (!stt.length || !tts.length) return null;
    const sttProvider =
      typeof payload.stt?.provider === "string"
        ? payload.stt.provider
        : stt[0].id;
    const ttsProvider =
      typeof payload.tts?.provider === "string"
        ? payload.tts.provider
        : tts[0].id;
    return {
      sttProvider: stt.some((item) => item.id === sttProvider)
        ? sttProvider
        : stt[0].id,
      ttsProvider: tts.some((item) => item.id === ttsProvider)
        ? ttsProvider
        : tts[0].id,
      stt,
      tts,
    };
  } catch {
    return null;
  }
}
