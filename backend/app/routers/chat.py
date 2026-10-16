"""Assistente (chat) — responde perguntas sobre o sistema com base na documentação.

Fluxo (RAG leve, sem dependências novas):

1. Recupera os trechos mais relevantes da base de conhecimento
   (``app.services.knowledge``) para a pergunta.
2. Envia esses trechos como contexto ao modelo (``app.services.deepseek``).
3. Retorna a resposta em português + as fontes usadas.

Se a IA não estiver configurada (sem ``DEEPSEEK_API_KEY``) o endpoint **não
inventa** resposta: devolve os trechos de documentação recuperados e sinaliza
``ai_available=false`` — mantendo a política do projeto de nunca fabricar
resultado.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.deps import client_meta, get_access_context
from app.rbac import AccessContext
from app.schemas.chat import ChatRequest, ChatResponse, ChatStatus
from app.services import deepseek, glossary, knowledge

router = APIRouter(prefix="/chat", tags=["chat"])

_SYSTEM_PROMPT = (
    "Você é o assistente de ajuda do IntelliINPI, um sistema multi-tenant de "
    "propriedade industrial (INPI) com CRM e módulo NIT (Núcleo de Inovação "
    "Tecnológica). Responda em português do Brasil, de forma direta e prática, "
    "SOMENTE com base nos trechos de documentação fornecidos no contexto.\n\n"
    "PÚBLICO-ALVO: usuários finais do sistema (analistas, pesquisadores, "
    "gestores), NÃO desenvolvedores. Fale como um manual de ajuda amigável.\n\n"
    "REGRAS DE ESTILO (obrigatórias):\n"
    "- NUNCA mostre rotas técnicas de URL (nada como `/nit/comunicacoes/[id]`), "
    "endpoints de API (nada como `POST /api/...`), nomes de arquivos, tabelas ou "
    "códigos internos.\n"
    "- NUNCA cite códigos de permissão (ex.: `NIT_DOCUMENT_UPLOAD`) nem códigos "
    "de papel (ex.: `NIT_TT_OPERATOR`). Em vez disso, descreva a ação em palavras "
    "(ex.: 'quem tem a permissão de enviar documentos') e, se mencionar papéis, "
    "use o nome legível (ex.: 'Transferência de Tecnologia').\n"
    "- Oriente pela INTERFACE: diga em qual MENU e em qual TELA o usuário deve "
    "clicar, usando os nomes exibidos na tela. Quando precisar indicar a tela, "
    "mencione o nome dela; evite o endereço da página.\n"
    "- Para 'onde encontro/vejo X': informe o nome do menu e da tela, passo a "
    "passo do que clicar.\n"
    "- Para fluxos: descreva os passos em ordem, como o usuário deve proceder.\n"
    "- Use frases curtas e, quando ajudar, uma lista numerada.\n"
    "- Se a resposta NÃO estiver no contexto, diga claramente que não encontrou "
    "essa informação na documentação do sistema e sugira onde procurar — nunca "
    "invente telas, permissões, caminhos ou comportamentos."
)

_MAX_HISTORY = 6


def _build_messages(ctx: AccessContext, req: ChatRequest) -> list[dict[str, str]]:
    """Monta as mensagens: system + histórico recente + pergunta com contexto."""
    context = knowledge.context_block(req.message, top_k=6, max_chars=9000)

    user_block = (
        "Contexto (documentação do IntelliINPI):\n"
        f"{context or '(nenhum trecho relevante encontrado)'}\n\n"
        f"Pergunta do usuário: {req.message}"
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for msg in req.history[-_MAX_HISTORY:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_block})
    return messages


@router.get("/status", response_model=ChatStatus)
def chat_status(ctx: AccessContext = Depends(get_access_context)) -> ChatStatus:
    """Informa se o assistente (IA) está configurado e o tamanho da base."""
    kstats = knowledge.stats()
    configured = deepseek.is_configured()
    return ChatStatus(
        configured=configured,
        model=deepseek.settings.deepseek_model,
        documents=kstats["documents"],
        sections=kstats["sections"],
        message=(
            "Assistente pronto."
            if configured
            else "Respostas automáticas indisponíveis no momento: o assistente "
            "exibirá apenas os trechos de documentação recuperados."
        ),
    )


@router.post("", response_model=ChatResponse)
def ask_chat(
    req: ChatRequest,
    ctx: AccessContext = Depends(get_access_context),
    meta: dict = Depends(client_meta),
) -> ChatResponse:
    """Responde a uma pergunta sobre o sistema (RAG sobre a documentação)."""
    del meta  # reservado para auditoria futura; mantém o padrão de dependências
    srcs = knowledge.sources(req.message, top_k=6)

    try:
        result = deepseek.chat(_build_messages(ctx, req))
    except deepseek.DeepSeekNotConfigured:
        # Degradação explícita: devolve os trechos recuperados, sem inventar.
        context = knowledge.user_context_block(req.message, top_k=3, max_chars=4000)
        if context:
            answer = (
                "O assistente inteligente está indisponível no momento, então "
                "separei os trechos da documentação que podem responder à sua "
                "pergunta. Se precisar, fale com o administrador do sistema para "
                "habilitar as respostas automáticas.\n\n" + context
            )
        else:
            answer = (
                "O assistente inteligente está indisponível e não encontrei "
                "trechos de documentação relevantes para esta pergunta. Tente "
                "reformular mencionando o módulo (CRM, INPI, NIT), o nome da tela "
                "exibida no menu ou a ação desejada."
            )
        return ChatResponse(answer=answer, sources=srcs, ai_available=False, model=None)
    except deepseek.DeepSeekError:
        return ChatResponse(
            answer=(
                "Não consegui consultar o assistente agora. Seguem os trechos de "
                "documentação recuperados:\n\n"
                + knowledge.user_context_block(req.message, top_k=3, max_chars=4000)
            ),
            sources=srcs,
            ai_available=False,
            model=None,
        )

    answer = glossary.humanize((result.content or "").strip())
    if not answer:
        answer = (
            "Não encontrei uma resposta na documentação. Tente reformular a "
            "pergunta mencionando o módulo, o nome da tela no menu ou a ação "
            "desejada."
        )
    return ChatResponse(
        answer=answer, sources=srcs, ai_available=True, model=result.model
    )


__all__ = ["router"]
