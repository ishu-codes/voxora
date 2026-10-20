export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

export type VoiceCatalogVoice = {
  id: string;
  name: string;
  gender?: string;
  description?: string;
};

export type VoiceCatalog = {
  provider: string;
  kind: "audio" | "browser";
  model: string;
  default_voice: string;
  languages: string[];
  voices: VoiceCatalogVoice[];
  cache_ttl_seconds: number;
};

type CachedCatalog = {
  savedAt: number;
  catalog: VoiceCatalog;
};

const STORAGE_KEY = "voxora.voice-catalog.v1";
const CACHE_TTL_MS = 24 * 60 * 60 * 1000;
let inflight: Promise<VoiceCatalog | null> | null = null;

function isCatalog(value: unknown): value is VoiceCatalog {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  if (record.kind !== "audio" && record.kind !== "browser") return false;
  if (typeof record.default_voice !== "string") return false;
  if (!Array.isArray(record.voices)) return false;
  return record.voices.every((voice) => {
    if (typeof voice !== "object" || voice === null) return false;
    const entry = voice as Record<string, unknown>;
    return (
      typeof entry.id === "string" &&
      entry.id.length > 0 &&
      typeof entry.name === "string"
    );
  });
}

export function readVoiceCatalogCache(): CachedCatalog | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return null;
    const record = parsed as Record<string, unknown>;
    if (typeof record.savedAt !== "number" || !isCatalog(record.catalog)) {
      return null;
    }
    return { savedAt: record.savedAt, catalog: record.catalog };
  } catch {
    return null;
  }
}

function writeVoiceCatalogCache(catalog: VoiceCatalog): void {
  if (typeof window === "undefined") return;
  try {
    const record: CachedCatalog = { savedAt: Date.now(), catalog };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(record));
  } catch {
    /* Storage can be unavailable in private browsing; the session still works. */
  }
}

export async function getVoiceCatalog(): Promise<VoiceCatalog | null> {
  const cached = readVoiceCatalogCache();
  if (cached && Date.now() - cached.savedAt < CACHE_TTL_MS) {
    return cached.catalog;
  }
  if (inflight) return inflight;

  inflight = (async () => {
    try {
      const response = await fetch(`${API_URL}/api/v1/voice/voices`, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        throw new Error(`Voice catalog request failed (${response.status})`);
      }
      const payload: unknown = await response.json();
      if (!isCatalog(payload)) {
        throw new Error("Voice catalog response has an unexpected shape");
      }
      writeVoiceCatalogCache(payload);
      return payload;
    } catch {
      // A stale catalog is still useful when the API is briefly unavailable.
      return cached?.catalog ?? null;
    } finally {
      inflight = null;
    }
  })();

  return inflight;
}
