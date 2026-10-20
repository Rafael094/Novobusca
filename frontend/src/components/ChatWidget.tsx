"use client";

/**
 * Assistente flutuante (chat) que responde perguntas sobre o próprio sistema.
 *
 * Fica fixo no canto inferior direito de qualquer tela autenticada. As respostas
 * vêm do endpoint `/api/chat` (RAG sobre a documentação em `app/knowledge/`).
 * Quando a IA não está configurada no servidor, o backend devolve os trechos de
 * documentação recuperados — o widget apenas os exibe e sinaliza o aviso.
 *
 * O estado da conversa (aberto/fechado, mensagens e fontes) vive no
 * `ChatProvider` (montado no layout raiz), e não neste componente. Assim a caixa
 * permanece aberta com a conversa — mesmo após clicar em um exemplo ou navegar
 * entre telas — até que o usuário a feche explicitamente no "x".
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "@/app/auth-context";
import { useChat } from "@/app/chat-context";
import { useAskChat, useChatStatus } from "@/lib/hooks";
import type { ChatMessage } from "@/lib/types";

const SUGGESTIONS = [
  "Onde vejo meus clientes?",
  "Qual o fluxo completo de registro no NIT?",
  "Como insiro documentos?",
  "Onde pesquiso marcas e patentes?",
];

const MAX_HISTORY = 6;

/**
 * Converte o rótulo técnico da fonte (documento `.md` + caminho de cabeçalhos)
 * em um rótulo legível para o usuário: descarta o nome do arquivo e mantém
 * apenas a trilha de seções, usando "→" como separador.
 *
 * Ex.: `04_nit_f1_comunicacoes.md § Fluxo NIT — F1 > Documentos`
 *      → `Fluxo NIT — F1 → Documentos`
 */
function friendlySource(source: string): string {
  const marker = " § ";
  const idx = source.indexOf(marker);
  const path = idx >= 0 ? source.slice(idx + marker.length) : source;
  const cleaned = path
    .split(">")
    .map((part) => part.trim())
    .filter(Boolean);
  return cleaned.length > 0 ? cleaned.join(" → ") : source;
}

export default function ChatWidget() {
  const { user } = useAuth();
  const {
    open,
    messages,
    sources,
    aiNote,
    toggleChat,
    closeChat,
    appendMessage,
    setSources,
    setAiNote,
    reset,
  } = useChat();
  const [input, setInput] = useState("");

  const ask = useAskChat();
  const status = useChatStatus(!!user);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, open, ask.isPending]);

  const history = useMemo(
    () => messages.slice(-MAX_HISTORY).map((m) => ({ role: m.role, content: m.content })),
    [messages],
  );

  if (!user) return null;

  async function send(text: string) {
    const question = text.trim();
    if (!question || ask.isPending) return;
    appendMessage({ role: "user", content: question });
    setInput("");
    setAiNote(null);
    try {
      const res = await ask.mutateAsync({ message: question, history });
      appendMessage({ role: "assistant", content: res.answer });
      setSources(res.sources ?? []);
      if (!res.ai_available) {
        setAiNote(
          "Respostas automáticas indisponíveis no momento — exibindo trechos da documentação.",
        );
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Falha ao consultar o assistente.";
      appendMessage({ role: "assistant" as ChatMessage["role"], content: `⚠️ ${msg}` });
    }
  }

  return (
    <>
      {/* Botão flutuante */}
      <button
        type="button"
        onClick={toggleChat}
        aria-label={open ? "Fechar assistente" : "Abrir assistente"}
        className="fixed bottom-5 right-5 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-brand-600 text-white shadow-lg transition hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-400"
      >
        {open ? (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        ) : (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        )}
      </button>

      {/* Painel do chat */}
      {open && (
        <div
          className="fixed bottom-24 right-5 z-50 flex h-[min(85vh,44rem)] w-[min(96vw,30rem)] flex-col overflow-hidden rounded-2xl border shadow-2xl sm:w-[min(94vw,34rem)] lg:w-[38rem] lg:max-w-[calc(100vw-11rem)]"
          style={{ background: "var(--bg-card)", borderColor: "var(--border-color)" }}
        >
          <div className="flex items-start justify-between gap-3 bg-brand-600 px-4 py-3 text-white">
            <div className="min-w-0">
              <p className="text-sm font-semibold">Assistente IntelliINPI</p>
              <p className="text-xs text-brand-50">
                {status.data?.configured
                  ? "Pergunte sobre telas, caminhos e fluxos"
                  : "Modo documentação (IA não configurada)"}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              {messages.length > 0 && (
                <button
                  type="button"
                  onClick={reset}
                  title="Iniciar uma nova conversa"
                  aria-label="Iniciar uma nova conversa"
                  className="rounded-lg px-2 py-1 text-xs font-medium text-brand-50 transition hover:bg-white/15 hover:text-white focus:outline-none focus:ring-2 focus:ring-brand-300"
                >
                  Nova conversa
                </button>
              )}
              <button
                type="button"
                onClick={closeChat}
                title="Fechar assistente"
                aria-label="Fechar assistente"
                className="flex h-8 w-8 items-center justify-center rounded-lg transition hover:bg-white/15 focus:outline-none focus:ring-2 focus:ring-brand-300"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4 scrollbar-thin">
            {messages.length === 0 && (
              <div className="space-y-3">
                <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                  Olá! Pergunte sobre qualquer módulo, tela ou caminho do sistema.
                </p>
                <div className="space-y-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => send(s)}
                      className="block w-full rounded-lg border px-3 py-2 text-left text-xs hover:border-brand-300 hover:bg-brand-50"
                      style={{ borderColor: "var(--border-color)", color: "var(--text-muted)" }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm ${
                    m.role === "user" ? "bg-brand-600 text-white" : ""
                  }`}
                  style={
                    m.role === "user"
                      ? undefined
                      : { background: "var(--bg-subtle)", color: "var(--text-main)" }
                  }
                >
                  {m.content}
                </div>
              </div>
            ))}

            {ask.isPending && (
              <div className="flex justify-start">
                <div
                  className="rounded-2xl px-3 py-2 text-sm"
                  style={{ background: "var(--bg-subtle)", color: "var(--text-muted)" }}
                >
                  Consultando…
                </div>
              </div>
            )}
          </div>

          {sources.length > 0 && (
            <div className="border-t px-3 py-2" style={{ borderColor: "var(--border-color)" }}>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-faint)" }}>
                Fontes
              </p>
              <div className="flex flex-wrap gap-1">
                {sources.slice(0, 4).map((s) => (
                  <span
                    key={s}
                    title={friendlySource(s)}
                    className="max-w-full truncate rounded bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500"
                  >
                    {friendlySource(s)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {aiNote && (
            <p className="border-t border-amber-100 bg-amber-50 px-3 py-2 text-[11px] text-amber-700">
              {aiNote}
            </p>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex items-center gap-2 border-t p-2"
            style={{ borderColor: "var(--border-color)" }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Escreva sua pergunta…"
              className="min-w-0 flex-1 rounded-lg border px-3 py-2 text-sm focus:border-brand-400 focus:outline-none"
              style={{ background: "var(--bg-input)", borderColor: "var(--border-color)", color: "var(--text-main)" }}
            />
            <button
              type="submit"
              disabled={ask.isPending || !input.trim()}
              className="rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-brand-700 disabled:opacity-50"
            >
              Enviar
            </button>
          </form>
        </div>
      )}
    </>
  );
}
