"""Global search across marcas and patentes (BUSCA module)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_permission
from app.models import Marca, Patente, PatenteConteudo
from app.rbac import AccessContext

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def global_search(
    q: str = Query(min_length=2),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("BUSCA_GLOBAL")),
) -> dict:
    like = f"%{q}%"

    marcas = (
        db.execute(
            select(Marca.codigo_interno, Marca.numero_inpi, Marca.elemento_nominativo)
            .where(
                or_(
                    Marca.elemento_nominativo.ilike(like),
                    Marca.numero_inpi.ilike(like),
                )
            )
            .limit(limit)
        )
        .all()
    )

    patente_ids = select(PatenteConteudo.codigo_interno).where(
        or_(
            PatenteConteudo.titulo.ilike(like),
            PatenteConteudo.resumo.ilike(like),
        )
    )
    patentes = (
        db.execute(
            select(Patente.codigo_interno, Patente.numero_inpi)
            .where(
                or_(
                    Patente.numero_inpi.ilike(like),
                    Patente.codigo_interno.in_(patente_ids),
                )
            )
            .limit(limit)
        )
        .all()
    )

    return {
        "query": q,
        "marcas": [
            {
                "codigo_interno": r[0],
                "numero_inpi": r[1],
                "elemento_nominativo": r[2],
            }
            for r in marcas
        ],
        "patentes": [
            {"codigo_interno": r[0], "numero_inpi": r[1]} for r in patentes
        ],
    }
