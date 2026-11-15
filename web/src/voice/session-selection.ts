export type SessionSelection = {
  sttProvider: string;
  sttModel: string;
  ttsProvider: string;
  ttsModel: string;
  voice: string | null;
};

export const SESSION_SELECTION_KEY = "voxora.voice-selection.v1";

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export function readSessionSelection(): SessionSelection | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(SESSION_SELECTION_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return null;
    const record = parsed as Record<string, unknown>;
    const sttProvider = text(record.sttProvider);
    const ttsProvider = text(record.ttsProvider);
    if (!sttProvider || !ttsProvider) return null;
    return {
      sttProvider,
      sttModel: text(record.sttModel),
      ttsProvider,
      ttsModel: text(record.ttsModel),
      voice: text(record.voice) || null,
    };
  } catch {
    return null;
  }
}

export function saveSessionSelection(selection: SessionSelection): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(
      SESSION_SELECTION_KEY,
      JSON.stringify(selection),
    );
  } catch {
    /* Storage can be unavailable in private browsing; the session still works. */
  }
}
