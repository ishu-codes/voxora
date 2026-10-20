import assert from "node:assert/strict";
import test from "node:test";

import type { VoiceMessage } from "./useVoiceSession.ts";

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

test("conversation store persists messages in session storage and clears them", async () => {
  const storage = memoryStorage();
  Object.defineProperty(globalThis, "window", {
    value: { sessionStorage: storage },
    configurable: true,
  });

  const { CONVERSATION_STORE_KEY, useConversationStore } = await import(
    "./conversation-store.ts"
  );
  const message: VoiceMessage = {
    id: "user-turn-1",
    role: "user",
    text: "hello",
    final: true,
    turnId: "turn-1",
    at: 1,
  };

  useConversationStore.getState().setMessages([message]);
  const stored = storage.getItem(CONVERSATION_STORE_KEY);
  assert.ok(stored);
  assert.deepEqual(JSON.parse(stored).state.messages, [message]);

  useConversationStore.getState().clearMessages();
  assert.deepEqual(useConversationStore.getState().messages, []);
  const cleared = storage.getItem(CONVERSATION_STORE_KEY);
  assert.ok(cleared);
  assert.deepEqual(JSON.parse(cleared).state.messages, []);

  storage.setItem(
    CONVERSATION_STORE_KEY,
    JSON.stringify({ state: { messages: [message] }, version: 0 }),
  );
  await useConversationStore.persist.rehydrate();
  assert.deepEqual(useConversationStore.getState().messages, [message]);

  Reflect.deleteProperty(globalThis, "window");
});
