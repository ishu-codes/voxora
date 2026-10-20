import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { VoiceMessage } from "./useVoiceSession";

export const CONVERSATION_STORE_KEY = "voxora.conversation.v1";

type MessagesUpdate =
  | VoiceMessage[]
  | ((previous: VoiceMessage[]) => VoiceMessage[]);

type ConversationStore = {
  messages: VoiceMessage[];
  setMessages: (update: MessagesUpdate) => void;
  clearMessages: () => void;
};

/**
 * Transcript state lives outside the session hook so every component under
 * `/app` can read it. `sessionStorage` keeps the conversation for the current
 * browser tab only, including across refreshes.
 */
export const useConversationStore = create<ConversationStore>()(
  persist(
    (set) => ({
      messages: [],
      setMessages: (update) =>
        set((state) => ({
          messages:
            typeof update === "function" ? update(state.messages) : update,
        })),
      clearMessages: () => set({ messages: [] }),
    }),
    {
      name: CONVERSATION_STORE_KEY,
      storage:
        typeof window === "undefined"
          ? undefined
          : createJSONStorage(() => window.sessionStorage),
      skipHydration: true,
      partialize: (state) => ({ messages: state.messages }),
    },
  ),
);
