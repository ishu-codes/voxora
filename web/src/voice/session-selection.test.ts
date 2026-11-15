import assert from "node:assert/strict";
import test from "node:test";

function memoryStorage(): Storage {
  const data = new Map<string, string>();
  return {
    get length() {
      return data.size;
    },
    clear: () => data.clear(),
    getItem: (key: string) => data.get(key) ?? null,
    key: (index: number) => Array.from(data.keys())[index] ?? null,
    removeItem: (key: string) => {
      data.delete(key);
    },
    setItem: (key: string, value: string) => {
      data.set(key, value);
    },
  };
}

test("session selection round-trips providers, models and voice", async () => {
  const storage = memoryStorage();
  Object.defineProperty(globalThis, "window", {
    value: { sessionStorage: storage },
    configurable: true,
  });

  const { readSessionSelection, saveSessionSelection, SESSION_SELECTION_KEY } =
    await import("./session-selection.ts");
  const selection = {
    sttProvider: "sarvam",
    sttModel: "saaras:v3-realtime",
    ttsProvider: "gnani",
    ttsModel: "timbre-v2.5",
    voice: "Kaveri",
  };

  saveSessionSelection(selection);

  assert.deepEqual(readSessionSelection(), selection);
  assert.equal(
    storage.getItem(SESSION_SELECTION_KEY),
    JSON.stringify(selection),
  );

  Reflect.deleteProperty(globalThis, "window");
});
