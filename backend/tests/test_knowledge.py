"""Testes do serviço de conhecimento (índice + recuperação textual).

Não dependem do banco: exercitam apenas a leitura dos arquivos Markdown e a
pontuação de busca que alimenta o assistente.
"""

from __future__ import annotations

from app.services import knowledge


def test_index_loads_all_documents():
    stats = knowledge.stats()
    assert stats["documents"] >= 10
    assert stats["sections"] >= 40


def test_retrieve_finds_clients_answer():
    chunks = knowledge.retrieve("onde vejo meus clientes", top_k=3)
    assert chunks, "esperava ao menos um trecho recuperado"
    joined = " ".join(c.text for c in chunks).lower()
    # A resposta sobre clientes deve citar a rota /clientes.
    assert "/clientes" in joined


def test_retrieve_finds_nit_flow():
    chunks = knowledge.retrieve("qual o fluxo completo de registro no NIT", top_k=3)
    assert chunks
    joined = " ".join(c.text for c in chunks).lower()
    assert "triagem" in joined or "workflow" in joined


def test_retrieve_documents_path():
    chunks = knowledge.retrieve("como insiro documentos", top_k=3)
    assert chunks
    joined = " ".join(c.text for c in chunks).lower()
    assert "document" in joined


def test_context_block_respects_max_chars():
    block = knowledge.context_block("marcas", top_k=6, max_chars=500)
    assert len(block) <= 500 + 400  # margem do último bloco não incluído


def test_sources_lists_labels():
    srcs = knowledge.sources("permissoes de documentos do NIT", top_k=3)
    assert srcs
    assert all(isinstance(s, str) and s for s in srcs)


def test_unknown_query_returns_empty():
    assert knowledge.retrieve("zzzzqqqxyx inexistente", top_k=3) == []


def test_user_context_block_hides_api_and_file_names():
    block = knowledge.user_context_block("onde vejo meus clientes?", top_k=3)
    assert block
    # Não deve expor nome de arquivo, endpoints nem variáveis internas.
    assert ".md" not in block
    assert "/api/" not in block
    assert "GET " not in block and "POST " not in block
    # Deve manter a informação útil ao usuário (o menu/tela).
    assert "clientes" in block.lower()


def test_user_context_block_drops_dynamic_routes():
    block = knowledge.user_context_block("como insiro documentos do NIT?", top_k=3)
    assert block
    assert "[id]" not in block


def test_user_context_block_respects_max_chars():
    block = knowledge.user_context_block("marcas", top_k=6, max_chars=600)
    assert len(block) <= 600 + 400  # margem do último bloco não incluído

