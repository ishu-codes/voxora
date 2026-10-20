"use client";

import { createContext, type ReactNode, useContext, useEffect } from "react";

import { useConversationStore } from "./conversation-store";
import { useVoiceSession } from "./useVoiceSession";

export type VoiceSession = ReturnType<typeof useVoiceSession>;

const VoiceSessionContext = createContext<VoiceSession | null>(null);

/**
 * Owns the one voice session for the `/app` subtree. Every child reads the same
 * connection, transcript and playback state instead of creating its own socket
 * or microphone capture.
 */
export function VoiceSessionProvider({ children }: { children: ReactNode }) {
  const session = useVoiceSession();

  // Rehydrate transcript history after mount so server-rendered markup matches
  // the first client render. A message that was still streaming when the tab
  // was refreshed can never finish, so settle it as interrupted.
  useEffect(() => {
    void Promise.resolve(useConversationStore.persist.rehydrate()).then(() => {
      const { messages, setMessages } = useConversationStore.getState();
      if (!messages.some((message) => !message.final)) return;
      setMessages(
        messages.map((message) =>
          message.final
            ? message
            : {
                ...message,
                final: true,
                interrupted:
                  message.role === "assistant" ? true : message.interrupted,
              },
        ),
      );
    });
  }, []);

  return (
    <VoiceSessionContext.Provider value={session}>
      {children}
    </VoiceSessionContext.Provider>
  );
}

export function useVoiceSessionContext(): VoiceSession {
  const session = useContext(VoiceSessionContext);
  if (!session) {
    throw new Error(
      "useVoiceSessionContext must be used inside VoiceSessionProvider.",
    );
  }
  return session;
}
