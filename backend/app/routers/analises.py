"""AI trademark risk analysis (DeepSeek) + INPI cross-referencing.

Flow:
1. Query the local INPI base (marcas by similar name + NICE class, plus
   related patents by keyword) to build the retrieval context.
2. Ask DeepSeek to assess the overall risk, list conflicts/recommendations and
   produce a summary, grounded on the retrieved records.
3. Merge the model output with the deterministic INPI matches into a
   ``AnalysisReport``.

If DeepSeek is not configured (no API key) the endpoint returns HTTP 503 with a
clear message — it never fabricates an analysis.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models import Marca, MarcaClassificacaoNice, Patente, PatenteConteudo
from app.rbac import AccessContext
from app.schemas.analise import (
    AnalysisReport,
    AnalysisRequest,
    AnalysisStatus,
    ConflictOut,
    RelatedPatentOut,
    SimilarBrandOut,
)
from app.services import deepseek

router = APIRouter(prefix="/analises", tags=["analises"])

_SYSTEM_PROMPT = (
    "Você é um especialista em propriedade industrial brasileira (INPI). "
    "Avalie o risco de registro de uma marca com base nos registros do INPI "
    "fornecidos. Responda SEMPRE e SOMENTE com um objeto JSON válido, em "
    "português, no formato: "
    '{"overall_risk": "baixo|moderado|alto|critico", "score": 0-100, '
    '"summary": "texto", "conflicts": [{"title": "", "score": 0-100, '
    '"level": "baixo|moderado|alto|critico", "description": "", "fonte": ""}], '
    '"recommendations": ["..."]}. '
    "Não invente números de processo que não estejam no contexto. "
    "Score alto = maior risco de conflito."
)


def _fold(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _risk_from_score(score: int) -> str:
    if score >= 75:
        return "critico"
    if score >= 50:
        return "alto"
    if score >= 25:
        return "moderado"
    return "baixo"


def _similarity(a: str, b: str) -> int:
    """Cheap token-overlap similarity (0-100); deterministic, no deps."""
    ta = set(_fold(a).split())
    tb = set(_fold(b).split())
    if not ta or not tb:
        return 0
    inter = len(ta & tb)
    base = max(len(ta), len(tb))
    # Prefix bonus when one name starts with the other.
    bonus = 15 if _fold(a).startswith(_fold(b)) or _fold(b).startswith(_fold(a)) else 0
    return min(100, int(inter / base * 85) + bonus)


def _retrieve_marcas(db: Session, req: AnalysisRequest, limit: int = 8) -> list[dict]:
    """Find marcas sharing tokens with the brand name, optionally same NICE."""
    tokens = [t for t in _fold(req.brand_name).split() if len(t) >= 3]
    conditions = []
    for tok in tokens[:4]:
        conditions.append(Marca.elemento_nominativo.ilike(f"%{tok}%"))
    if not conditions:
        conditions.append(
            Marca.elemento_nominativo.ilike(f"%{_fold(req.brand_name)}%")
        )

    stmt = select(Marca).where(or_(*conditions))
    if req.options.strict_nice and req.nice_classes:
        sub = select(MarcaClassificacaoNice.codigo_interno).where(
            MarcaClassificacaoNice.classe_nice.in_(req.nice_classes)
        )
        stmt = stmt.where(Marca.codigo_interno.in_(sub))

    rows = (
        db.execute(stmt.order_by(Marca.data_deposito.desc()).limit(limit))
        .scalars()
        .all()
    )
    out = []
    for m in rows:
        out.append(
            {
                "nome": m.elemento_nominativo,
                "numero_inpi": m.numero_inpi,
                "situacao": m.descricao_situacao or m.codigo_situacao,
                "classes": [],
                "similaridade": _similarity(
                    req.brand_name, m.elemento_nominativo or ""
                ),
            }
        )
    return out


def _retrieve_patentes(db: Session, req: AnalysisRequest, limit: int = 5) -> list[dict]:
    tokens = [t for t in _fold(req.brand_name).split() if len(t) >= 4]
    if not tokens:
        return []
    conditions = []
    for tok in tokens[:3]:
        conditions.append(PatenteConteudo.titulo.ilike(f"%{tok}%"))
        conditions.append(PatenteConteudo.resumo.ilike(f"%{tok}%"))
    ids = select(PatenteConteudo.codigo_interno).where(or_(*conditions))
    rows = (
        db.execute(
            select(Patente).where(Patente.codigo_interno.in_(ids)).limit(limit)
        )
        .scalars()
        .all()
    )
    return [
        {
            "titulo": p.titulo,
            "numero_inpi": p.numero_inpi,
            "depositante": None,
            "relevancia": 60,
        }
        for p in rows
    ]


def _build_context(req: AnalysisRequest, marcas: list[dict], patentes: list[dict]) -> str:
    return json.dumps(
        {
            "marca_requerida": req.brand_name,
            "classes_nice": req.nice_classes,
            "titular": req.holder,
            "apresentacao": req.presentation,
            "natureza": req.nature,
            "marcas_inpi_semelhantes": marcas,
            "patentes_relacionadas": patentes,
        },
        ensure_ascii=False,
    )


@router.get("/status", response_model=AnalysisStatus)
def analysis_status(
    ctx: AccessContext = Depends(require_permission("MARCAS_SEARCH")),
) -> AnalysisStatus:
    configured = deepseek.is_configured()
    return AnalysisStatus(
        configured=configured,
        model=deepseek.settings.deepseek_model,
        message=(
            "Integração DeepSeek pronta para uso."
            if configured
            else "Defina DEEPSEEK_API_KEY para habilitar a análise de IA."
        ),
    )


@router.post("", response_model=AnalysisReport)
def run_analysis(
    payload: AnalysisRequest,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("MARCAS_SEARCH")),
    meta: dict = Depends(client_meta),
) -> AnalysisReport:
    marcas = _retrieve_marcas(db, payload)
    patentes = (
        _retrieve_patentes(db, payload) if payload.options.include_patentes else []
    )

    if not deepseek.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Análise de IA indisponível: DEEPSEEK_API_KEY não configurada. "
                "Defina a chave no ambiente do backend para habilitar."
            ),
        )

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _build_context(payload, marcas, patentes)},
    ]

    try:
        result = deepseek.chat(messages, response_format_json=True)
    except deepseek.DeepSeekNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    except deepseek.DeepSeekError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha na análise de IA: {exc}",
        )

    data = _parse_json(result.content)
    score = _clamp_score(data.get("score"), marcas)
    overall = data.get("overall_risk") or _risk_from_score(score)

    conflicts = [
        ConflictOut(
            title=c.get("title") or "Conflito identificado",
            score=_to_int(c.get("score"), score),
            level=c.get("level") or _risk_from_score(score),
            description=c.get("description"),
            fonte=c.get("fonte") or "INPI",
        )
        for c in data.get("conflicts", [])
        if isinstance(c, dict)
    ]

    report = AnalysisReport(
        brand_name=payload.brand_name,
        holder=payload.holder,
        nice_classes=payload.nice_classes,
        created_at=datetime.now(timezone.utc),
        overall_risk=overall,
        score=score,
        summary=data.get("summary")
        or (
            f"Encontradas {len(marcas)} marcas semelhantes e {len(patentes)} "
            "patentes relacionadas na base do INPI."
        ),
        conflicts=conflicts,
        similar_brands=[
            SimilarBrandOut(
                nome=m["nome"],
                numero_inpi=m["numero_inpi"],
                situacao=m["situacao"],
                similaridade=m["similaridade"],
                classes=m["classes"],
            )
            for m in marcas
        ],
        related_patents=(
            [RelatedPatentOut(**p) for p in patentes]
            if payload.options.include_patentes
            else []
        ),
        recommendations=list(data.get("recommendations", []) or []),
        ai_available=True,
        model=result.model,
    )

    record_audit(
        db,
        action="ANALISE_IA_EXECUTE",
        tenant_id=ctx.user.tenant_id,
        user_id=ctx.user.id,
        resource="analise",
        meta={"brand_name": payload.brand_name, "score": score},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return report


def _parse_json(content: str) -> dict:
    """Best-effort extraction of a JSON object from the model output."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}


def _to_int(value, default: int) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return default


def _clamp_score(value, marcas: list[dict]) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        best = max((m["similaridade"] for m in marcas), default=0)
        score = best
    return max(0, min(100, score))
