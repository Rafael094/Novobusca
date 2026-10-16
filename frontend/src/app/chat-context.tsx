"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

import type { ChatMessage } from "@/lib/types";

/**
 * Estado do assistente (chat) mantido **acima** das páginas.
 *
 * O widget é renderizado dentro de `AppShell`, que por sua vez é montado por
 * cada página. Sem este provider, qualquer remontagem da árvore (navegação,
 * Fast Refresh, condições de carregamento da página) destruiria o estado local
 * do widget — fechando a caixa e reiniciando a conversa. Aqui o estado vive no
 * nível dos `Providers` (estável entre rotas), então a conversa permanece
 * aberta até o cliente fechá-la no "x".
 */
type ChatState = {
  open: boolean;
  messages: ChatMessage[];
  sources: string[];
  aiNote: string | null;
  openChat: () => void;
  closeChat: () => void;
  toggleChat: () => void;
  appendMessage: (message: ChatMessage) => void;
  setSources: (sources: string[]) => void;
  setAiNote: (note: string | null) => void;
  reset: () => void;
};

const ChatContext = createContext<ChatState | null>(null);

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sources, setSources] = useState<string[]>([]);
  const [aiNote, setAiNote] = useState<string | null>(null);

  const openChat = useCallback(() => setOpen(true), []);
  const closeChat = useCallback(() => setOpen(false), []);
  const toggleChat = useCallback(() => setOpen((v) => !v), []);

  const appendMessage = useCallback(
    (message: ChatMessage) => setMessages((prev) => [...prev, message]),
    [],
  );

  const reset = useCallback(() => {
    setMessages([]);
    setSources([]);
    setAiNote(null);
  }, []);

  const value = useMemo<ChatState>(
    () => ({
      open,
      messages,
      sources,
      aiNote,
      openChat,
      closeChat,
      toggleChat,
      appendMessage,
      setSources,
      setAiNote,
      reset,
    }),
    [open, messages, sources, aiNote, openChat, closeChat, toggleChat, appendMessage, reset],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatState {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used within a ChatProvider");
  return ctx;
}
