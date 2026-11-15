import { API_URL } from "./voice-catalog";

export type Scenario = {
  id: string;
  title: string;
  description: string;
  language_hint: string;
  system_prompt: string;
  opening_line: string;
  voice: string;
  outbound: boolean;
};

let inflight: Promise<Scenario[]> | null = null;

function parseScenario(value: unknown): Scenario | null {
  if (typeof value !== "object" || value === null) return null;
  const item = value as Record<string, unknown>;
  if (
    typeof item.id !== "string" ||
    typeof item.title !== "string" ||
    typeof item.language_hint !== "string" ||
    typeof item.system_prompt !== "string" ||
    typeof item.opening_line !== "string" ||
    typeof item.voice !== "string"
  ) {
    return null;
  }
  return {
    id: item.id,
    title: item.title,
    description: typeof item.description === "string" ? item.description : "",
    language_hint: item.language_hint,
    system_prompt: item.system_prompt,
    opening_line: item.opening_line,
    voice: item.voice,
    outbound: item.outbound === true,
  };
}

export async function getScenarios(): Promise<Scenario[]> {
  if (inflight) return inflight;
  inflight = (async () => {
    try {
      const response = await fetch(`${API_URL}/api/v1/voice/scenarios`, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) return [];
      const payload: unknown = await response.json();
      if (!Array.isArray(payload)) return [];
      return payload.flatMap((item) => {
        const scenario = parseScenario(item);
        return scenario ? [scenario] : [];
      });
    } catch {
      return [];
    } finally {
      inflight = null;
    }
  })();
  return inflight;
}
