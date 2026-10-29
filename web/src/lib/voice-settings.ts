/**
 * Provider settings are intentionally browser-local: this prototype has no
 * accounts, so there is no server-side place to own a user's credentials.
 * They are used only for direct browser-to-provider requests. They are never
 * included in WebSocket frames sent to the Voxora API.
 */

import type { ClientFingerprint } from "./device-fingerprint";

export type VoiceSettings = {
  sarvamApiKey: string;
  openaiApiKey: string;
  openaiBaseUrl: string;
  openaiModel: string;
};

export const EMPTY_VOICE_SETTINGS: VoiceSettings = {
  sarvamApiKey: "",
  openaiApiKey: "",
  openaiBaseUrl: "",
  openaiModel: "",
};

const STORAGE_KEY = "voxora.voice-settings.v1";

function clean(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export function loadVoiceSettings(): VoiceSettings {
  if (typeof window === "undefined") return { ...EMPTY_VOICE_SETTINGS };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...EMPTY_VOICE_SETTINGS };
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) {
      return { ...EMPTY_VOICE_SETTINGS };
    }
    const record = parsed as Record<string, unknown>;
    return {
      sarvamApiKey: clean(record.sarvamApiKey),
      openaiApiKey: clean(record.openaiApiKey),
      openaiBaseUrl: clean(record.openaiBaseUrl),
      openaiModel: clean(record.openaiModel),
    };
  } catch {
    return { ...EMPTY_VOICE_SETTINGS };
  }
}

export function saveVoiceSettings(settings: VoiceSettings): VoiceSettings {
  const cleaned: VoiceSettings = {
    sarvamApiKey: settings.sarvamApiKey.trim(),
    openaiApiKey: settings.openaiApiKey.trim(),
    openaiBaseUrl: settings.openaiBaseUrl.trim().replace(/\/+$/, ""),
    openaiModel: settings.openaiModel.trim(),
  };
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(cleaned));
  }
  return cleaned;
}

export function clearVoiceSettings(): void {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(STORAGE_KEY);
  }
}

export function hasVoiceSettings(settings: VoiceSettings): boolean {
  return Boolean(
    settings.sarvamApiKey ||
      settings.openaiApiKey ||
      settings.openaiBaseUrl ||
      settings.openaiModel,
  );
}

/** Both stages must be user-funded to bypass the shared platform trial. */
export function hasUnlimitedVoiceSettings(settings: VoiceSettings): boolean {
  return Boolean(
    settings.sarvamApiKey && (settings.openaiApiKey || settings.openaiBaseUrl),
  );
}

export function toConfigurePayload(client?: ClientFingerprint) {
  return {
    type: "configure" as const,
    ...(client ? { client } : {}),
  };
}
