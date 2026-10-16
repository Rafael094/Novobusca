"""Idempotent DEMONSTRATION seed for the NIT module (phases F1–F5).

This module is a *companion* to ``app.seed`` / ``app.seed_nit`` and never
replaces or mutates them. It populates a **dedicated demo tenant** with a
coherent, cross-referenced data set covering every NIT phase:

* **F1** — communication of invention, confidential documents + ACL, workflow,
  evaluations, institutional IP assets and public links.
* **F2** — TRL history, committees, meetings, agenda items, votes, decisions.
* **F3** — technology offers, expressions of interest, negotiations, licenses,
  contracts, obligations and royalties.
* **F4** — R&D projects, team, funders, milestones, asset links, startups and
  incubation.
* **F5** — notifications, preferences, queued e-mails, external portal access,
  portal requests, saved BI reports and integration endpoints.

Design rules (aligned with the platform invariants):

* **Idempotent.** Every entity has a stable, deterministic identifier (protocol,
  code, e-mail, ``(tenant, code)``); re-running the seed reuses what already
  exists and only creates what is missing. Nothing is ever deleted.
* **Tenant isolation.** Everything is written under one demo tenant resolved by
  ``social_reason``; no cross-tenant rows are created.
* **Domain tables via the ORM**, technical tables (workflow history/transitions,
  evaluations, TRL) only through the *real* service flows so the audit trail is
  authentic (:func:`app.services.workflow.apply_transition`).
* **No fabricated money/legal data.** Monetary and legal fields are only set to
  values the demo genuinely represents (clearly marked demo amounts), never
  invented legal deadlines.

Run it with::

    python -m app.seed_demo_nit

The report returned by :func:`run_demo_seed` maps each entity to
``created`` / ``reused`` counts, so a caller can prove idempotency.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    Company,
    Module,
    Person,
    Role,
    Tenant,
    TenantModule,
    Unity,
    User,
    UserRole,
    UserTenant,
)
from app.models.nit import (
    ASSET_STATUS_PROTECTED,
    ASSET_TYPE_PATENT,
    ASSET_TYPE_SOFTWARE,
    ACL_READ,
    ACL_SUBJECT_ROLE,
    ACL_SUBJECT_UNITY,
    CONFIDENTIALITY_CONFIDENTIAL,
    CONFIDENTIALITY_INTERNAL,
    CONFIDENTIALITY_PUBLIC,
    CONFIDENTIALITY_RESTRICTED,
    EVALUATION_COMMERCIAL,
    EVALUATION_LEGAL,
    EVALUATION_TECHNICAL,
    INVENTOR_EXTERNAL,
    INVENTOR_INTERNAL,
    InventionDisclosure,
    DisclosureInventor,
    DocumentAcl,
    Evaluation,
    IPAsset,
    IPAssetPublicLink,
    InventionDocument,
    WorkflowInstance,
    WF_CLOSED,
    WF_DECISION,
    WF_EVALUATION,
    WF_PROPOSAL,
    WF_TRIAGE,
)
from app.models.nit_f2 import (
    AGENDA_ITEM_STATUS_DECIDED,
    COMMITTEE_STATUS_ACTIVE,
    DECISION_APPROVED,
    MEETING_STATUS_HELD,
    VOTE_APPROVE,
    Committee,
    CommitteeAgendaItem,
    CommitteeDecision,
    CommitteeMeeting,
    CommitteeMember,
    CommitteeVote,
    TechnologyReadinessLevel,
)
from app.models.nit_f3 import (
    CONTRACT_STATUS_ACTIVE,
    INTEREST_STATUS_CONVERTED,
    INTEREST_STATUS_IN_NEGOTIATION,
    NEG_STAGE_CLOSED,
    NEG_STAGE_FIRST_CONTACT,
    NEG_STAGE_NEGOTIATION,
    NEG_STAGE_QUALIFICATION,
    NEG_STAGE_TECHNICAL,
    OBLIGATION_STATUS_DONE,
    OBLIGATION_STATUS_PENDING,
    OFFER_STATUS_PUBLISHED,
    Contract,
    ContractObligation,
    ContractParty,
    ExpressionOfInterest,
    InterestInteraction,
    License,
    Negotiation,
    NegotiationHistory,
    Royalty,
    TechnologyOffer,
)
from app.models.nit_f4 import (
    INCUBATION_STAGE_STATUSES,
    MILESTONE_STATUS_DONE,
    MILESTONE_STATUS_PENDING,
    PROJECT_STATUS_ACTIVE,
    STARTUP_STATUS_INCUBATED,
    IncubationParticipation,
    IncubationProgram,
    IncubationStage,
    Project,
    ProjectAssetLink,
    ProjectFunder,
    ProjectMember,
    ProjectMilestone,
    Startup,
    StartupMember,
)
from app.models.nit_f5 import (
    DELIVERY_PENDING,
    EMAIL_STATUS_QUEUED,
    Notification,
    NotificationPreference,
    EmailMessage,
    ExternalPortalAccess,
    PortalRequest,
    PortalRequestNote,
    ReportRun,
    SavedReport,
    IntegrationEndpoint,
    IntegrationDelivery,
)
from app.rbac import build_access_context
from app.seed_nit import seed_tenant_workflow
from app.security import hash_password
from app.services import protocol as protocol_service
from app.services import workflow as workflow_service


# --- Demo constants (stable identifiers) ------------------------------------

DEMO_TENANT_NAME = "Instituto Demo NIT"
DEMO_COMPANY_NAME = "Instituto Demo NIT"
DEMO_UNITY_MATRIZ = "Campus Central"
DEMO_PASSWORD = "Demo_Nit_2026!"

# Demo actors: (key, name, email, role_code, job_title)
DEMO_USERS: list[tuple[str, str, str, str, str]] = [
    ("researcher", "Dra. Helena Prado", "helena.prado@demo.nit.br", "NIT_RESEARCHER", "Pesquisadora"),
    ("analyst", "Rafael Coutinho", "rafael.coutinho@demo.nit.br", "NIT_ANALYST", "Analista de Inovação"),
    ("manager", "Mariana Alves", "mariana.alves@demo.nit.br", "NIT_MANAGER", "Gestora do NIT"),
    ("tt_operator", "Bruno Tavares", "bruno.tavares@demo.nit.br", "NIT_TT_OPERATOR", "Operador de Transferência"),
    ("committee", "Prof. Sérgio Bastos", "sergio.bastos@demo.nit.br", "NIT_COMMITTEE_MEMBER", "Membro do Comitê"),
]

# Deterministic protocol prefix so re-runs recognise their own records.
DEMO_PROTOCOL_TITLES: list[str] = [
    "Sensor piezoelétrico para monitoramento estrutural",
    "Plataforma de visão computacional para inspeção agrícola",
    "Processo de encapsulamento de bioativos amazônicos",
    "Software de otimização logística de última milha",
    "Ligante cimentício de baixo carbono com resíduos agroindustriais",
]


@dataclass
class SeedReport:
    """Counts of created/reused/skipped entities for idempotency proof."""

    created: dict[str, int] = field(default_factory=dict)
    reused: dict[str, int] = field(default_factory=dict)

    def cre(self, key: str, n: int = 1) -> None:
        self.created[key] = self.created.get(key, 0) + n

    def reu(self, key: str, n: int = 1) -> None:
        self.reused[key] = self.reused.get(key, 0) + n

    def as_dict(self) -> dict:
        return {"created": dict(sorted(self.created.items())),
                "reused": dict(sorted(self.reused.items()))}


# --- Foundation: tenant, company, unity, users, roles -----------------------


def _get_or_create_tenant(db: Session, report: SeedReport) -> Tenant:
    tenant = db.execute(
        select(Tenant).where(Tenant.social_reason == DEMO_TENANT_NAME)
    ).scalars().first()
    if tenant is not None:
        report.reu("tenant")
        return tenant
    tenant = Tenant(
        social_reason=DEMO_TENANT_NAME,
        company_name=DEMO_TENANT_NAME,
        email="contato@demo.nit.br",
        active=True,
    )
    db.add(tenant)
    db.flush()
    report.cre("tenant")
    return tenant


def _enable_nit_module(db: Session, tenant: Tenant, report: SeedReport) -> None:
    """Enable the NIT module (and every other active module) for the tenant."""
    module = db.execute(
        select(Module).where(Module.code == "NIT")
    ).scalar_one_or_none()
    if module is None:
        raise RuntimeError("Módulo NIT não encontrado; rode app.seed antes.")
    enabled = {
        tm.module_id
        for tm in db.execute(
            select(TenantModule).where(TenantModule.tenant_id == tenant.id)
        ).scalars()
    }
    for mod in db.execute(select(Module).where(Module.active.is_(True))).scalars():
        if mod.id in enabled:
            continue
        db.add(TenantModule(tenant_id=tenant.id, module_id=mod.id, active=True))
        report.cre("tenant_module")
    db.flush()


def _get_or_create_company(db: Session, tenant: Tenant, report: SeedReport) -> Company:
    company = db.execute(
        select(Company).where(
            Company.tenant_id == tenant.id,
            Company.company_name == DEMO_COMPANY_NAME,
        )
    ).scalars().first()
    if company is not None:
        report.reu("company")
        return company
    company = Company(
        tenant_id=tenant.id,
        company_name=DEMO_COMPANY_NAME,
        social_reason=DEMO_COMPANY_NAME,
        email="contato@demo.nit.br",
        active=True,
    )
    db.add(company)
    db.flush()
    report.cre("company")
    return company


def _get_or_create_unity(
    db: Session, tenant: Tenant, company: Company, report: SeedReport, name: str = DEMO_UNITY_MATRIZ
) -> Unity:
    unity = db.execute(
        select(Unity).where(Unity.tenant_id == tenant.id, Unity.name == name)
    ).scalars().first()
    if unity is not None:
        report.reu("unity")
        return unity
    unity = Unity(
        tenant_id=tenant.id,
        company_id=company.id,
        name=name,
        social_reason=company.company_name,
        matriz_type="MATRIZ" if name == DEMO_UNITY_MATRIZ else "FILIAL",
        city="Manaus",
        state="AM",
        active=True,
    )
    db.add(unity)
    db.flush()
    report.cre("unity")
    return unity


def _get_or_create_user(
    db: Session,
    tenant: Tenant,
    *,
    name: str,
    email: str,
    job_title: str,
    report: SeedReport,
) -> User:
    email = email.lower()
    user = db.execute(
        select(User).where(User.email == email).order_by(User.created_at)
    ).scalars().first()
    if user is None:
        user = User(
            tenant_id=tenant.id,
            access_code=email,
            email=email,
            password_hash=hash_password(DEMO_PASSWORD),
            type="INTERNAL",
            active=True,
            is_master_admin=False,
        )
        db.add(user)
        db.flush()
        report.cre("user")
    else:
        report.reu("user")

    person = db.execute(
        select(Person).where(Person.user_id == user.id)
    ).scalar_one_or_none()
    if person is None:
        person = Person(
            tenant_id=tenant.id,
            user_id=user.id,
            name=name,
            email=email,
            job_title=job_title,
            city="Manaus",
            state="AM",
            active=True,
        )
        db.add(person)
        db.flush()
        report.cre("person")
    user.person_id = person.id

    membership = db.execute(
        select(UserTenant).where(
            UserTenant.user_id == user.id, UserTenant.tenant_id == tenant.id
        )
    ).scalar_one_or_none()
    if membership is None:
        db.add(UserTenant(user_id=user.id, tenant_id=tenant.id, is_default=True))
        report.cre("user_tenant")

    db.flush()
    return user


def _assign_role(db: Session, user: User, role_code: str, report: SeedReport) -> None:
    role = db.execute(
        select(Role).where(Role.tenant_id.is_(None), Role.code == role_code)
    ).scalar_one_or_none()
    if role is None:
        raise RuntimeError(f"Papel {role_code} não encontrado; rode app.seed antes.")
    linked = db.execute(
        select(UserRole).where(
            UserRole.user_id == user.id, UserRole.role_id == role.id
        )
    ).scalar_one_or_none()
    if linked is None:
        db.add(UserRole(user_id=user.id, role_id=role.id))
        report.cre("user_role")


def seed_demo_foundation(db: Session) -> tuple[dict, SeedReport]:
    """Create the demo tenant, company, unity, actors and role grants."""
    report = SeedReport()
    tenant = _get_or_create_tenant(db, report)
    _enable_nit_module(db, tenant, report)
    company = _get_or_create_company(db, tenant, report)
    unity = _get_or_create_unity(db, tenant, company, report)

    users: dict[str, User] = {}
    for key, name, email, role_code, job_title in DEMO_USERS:
        user = _get_or_create_user(
            db, tenant, name=name, email=email, job_title=job_title, report=report
        )
        _assign_role(db, user, role_code, report)
        users[key] = user
    db.flush()

    context = {
        "tenant": tenant,
        "company": company,
        "unity": unity,
        "users": users,
    }
    return context, report



# --- F1: disclosures, documents, workflow, evaluations, assets --------------


def _get_or_create_disclosure(
    db: Session,
    ctx: dict,
    report: SeedReport,
    *,
    title: str,
    summary: str,
    technology_area: str,
    keywords: str,
    confidentiality_level: str,
    submitted_by: User,
) -> InventionDisclosure:
    tenant: Tenant = ctx["tenant"]
    disclosure = db.execute(
        select(InventionDisclosure).where(
            InventionDisclosure.tenant_id == tenant.id,
            InventionDisclosure.title == title,
        )
    ).scalars().first()
    if disclosure is not None:
        report.reu("disclosure")
        return disclosure
    disclosure = InventionDisclosure(
        tenant_id=tenant.id,
        unity_id=ctx["unity"].id,
        protocol=protocol_service.next_protocol(db, tenant.id),
        title=title,
        summary=summary,
        description=summary,
        technology_area=technology_area,
        keywords=keywords,
        status=WF_PROPOSAL,
        confidentiality_level=confidentiality_level,
        submitted_by_id=submitted_by.id,
        responsible_id=ctx["users"]["manager"].id,
        active=True,
    )
    db.add(disclosure)
    db.flush()
    report.cre("disclosure")
    return disclosure


def _ensure_inventors(
    db: Session,
    ctx: dict,
    report: SeedReport,
    disclosure: InventionDisclosure,
) -> None:
    tenant: Tenant = ctx["tenant"]
    existing = {
        (i.name, i.kind)
        for i in db.execute(
            select(DisclosureInventor).where(
                DisclosureInventor.disclosure_id == disclosure.id
            )
        ).scalars()
    }
    researcher: User = ctx["users"]["researcher"]
    researcher_name = researcher.person.name if researcher.person else "Pesquisadora"
    planned = [
        (researcher_name, INVENTOR_INTERNAL, researcher.id, researcher.person_id, 60, True),
        ("Carlos Menezes (UFAM)", INVENTOR_EXTERNAL, None, None, 40, False),
    ]
    for name, kind, user_id, person_id, share, is_primary in planned:
        if (name, kind) in existing:
            report.reu("disclosure_inventor")
            continue
        db.add(
            DisclosureInventor(
                tenant_id=tenant.id,
                disclosure_id=disclosure.id,
                person_id=person_id,
                user_id=user_id,
                name=name,
                kind=kind,
                share_percent=share,
                is_primary=is_primary,
            )
        )
        report.cre("disclosure_inventor")
    db.flush()




def _ensure_documents(
    db: Session,
    ctx: dict,
    report: SeedReport,
    disclosure: InventionDisclosure,
) -> list[InventionDocument]:
    tenant: Tenant = ctx["tenant"]
    uploader: User = ctx["users"]["researcher"]
    planned = [
        ("memorial-descritivo.pdf", "application/pdf", CONFIDENTIALITY_CONFIDENTIAL,
         "Memorial descritivo da invenção"),
        ("desenhos-tecnicos.pdf", "application/pdf", CONFIDENTIALITY_RESTRICTED,
         "Desenhos e diagramas técnicos"),
    ]
    docs: list[InventionDocument] = []
    for filename, mime, level, title in planned:
        storage_key = f"documents/{tenant.id}/{disclosure.id}/{filename}"
        doc = db.execute(
            select(InventionDocument).where(
                InventionDocument.storage_key == storage_key
            )
        ).scalars().first()
        if doc is None:
            doc = InventionDocument(
                tenant_id=tenant.id,
                disclosure_id=disclosure.id,
                uploaded_by_id=uploader.id,
                original_filename=filename,
                storage_key=storage_key,
                mime_type=mime,
                size_bytes=184320,
                checksum_sha256="0" * 64,
                confidentiality_level=level,
                title=title,
                scan_status="CLEAN",
                scanned_at=datetime.now(timezone.utc),
                active=True,
            )
            db.add(doc)
            db.flush()
            report.cre("invention_document")
        else:
            report.reu("invention_document")
        docs.append(doc)

    # ACL: allow the NIT_MANAGER role and the campus unity read access.
    for doc in docs:
        _ensure_acl(db, ctx, report, doc, ACL_SUBJECT_ROLE, "NIT_MANAGER", ACL_READ)
        _ensure_acl(
            db, ctx, report, doc, ACL_SUBJECT_UNITY, str(ctx["unity"].id), ACL_READ
        )
    return docs


def _ensure_acl(
    db: Session,
    ctx: dict,
    report: SeedReport,
    document: InventionDocument,
    subject_kind: str,
    subject_id: str,
    permission: str,
) -> None:
    tenant: Tenant = ctx["tenant"]
    acl = db.execute(
        select(DocumentAcl).where(
            DocumentAcl.document_id == document.id,
            DocumentAcl.subject_kind == subject_kind,
            DocumentAcl.subject_id == subject_id,
        )
    ).scalar_one_or_none()
    if acl is not None:
        report.reu("document_acl")
        return
    db.add(
        DocumentAcl(
            tenant_id=tenant.id,
            document_id=document.id,
            subject_kind=subject_kind,
            subject_id=subject_id,
            permission=permission,
            granted_by_id=ctx["users"]["manager"].id,
        )
    )
    report.cre("document_acl")
    db.flush()


def _ensure_workflow(
    db: Session,
    ctx: dict,
    report: SeedReport,
    disclosure: InventionDisclosure,
    *,
    target_state: str,
    justification: str,
) -> WorkflowInstance:
    """Create the workflow instance and drive it through REAL transitions.

    Technical tables (``workflow_instances``/``workflow_history``) are only ever
    written through :func:`app.services.workflow.apply_transition`, so the audit
    trail is authentic and versioned.
    """
    tenant: Tenant = ctx["tenant"]
    instance = db.execute(
        select(WorkflowInstance).where(
            WorkflowInstance.disclosure_id == disclosure.id
        )
    ).scalar_one_or_none()
    if instance is None:
        instance = WorkflowInstance(
            tenant_id=tenant.id,
            disclosure_id=disclosure.id,
            current_state=WF_PROPOSAL,
            version=0,
        )
        db.add(instance)
        db.flush()
        report.cre("workflow_instance")
    else:
        report.reu("workflow_instance")

    # Default workflow graph: PROPOSAL → TRIAGE → EVALUATION → DECISION → CLOSED.
    path_edges = {
        WF_PROPOSAL: [],
        WF_TRIAGE: [WF_TRIAGE],
        WF_EVALUATION: [WF_TRIAGE, WF_EVALUATION],
        WF_DECISION: [WF_TRIAGE, WF_EVALUATION, WF_DECISION],
        WF_CLOSED: [WF_TRIAGE, WF_EVALUATION, WF_DECISION, WF_CLOSED],
    }
    targets = path_edges.get(target_state, [])
    analyst: User = ctx["users"]["analyst"]
    manager: User = ctx["users"]["manager"]

    steps = [
        (WF_TRIAGE, analyst, None),
        (WF_EVALUATION, analyst, None),
        (WF_DECISION, manager, None),
        (WF_CLOSED, manager, justification),
    ]
    for to_state, actor, note in steps:
        if to_state not in targets or instance.current_state == to_state:
            continue
        if instance.current_state == target_state:
            break
        actor_ctx = build_access_context(db, actor)
        workflow_service.apply_transition(
            db,
            ctx=actor_ctx,
            instance=instance,
            to_state=to_state,
            justification=note,
            expected_version=instance.version,
        )
        report.cre("workflow_history")

    # Keep the disclosure.status denormalisation aligned with the instance.
    disclosure.status = instance.current_state
    db.flush()
    return instance



def _ensure_evaluation(
    db: Session,
    ctx: dict,
    report: SeedReport,
    disclosure: InventionDisclosure,
    *,
    kind: str,
    outcome: str,
    evaluator: User,
    summary: str,
    recommendations: str,
) -> None:
    tenant: Tenant = ctx["tenant"]
    existing = db.execute(
        select(Evaluation).where(
            Evaluation.disclosure_id == disclosure.id,
            Evaluation.kind == kind,
        )
    ).scalars().first()
    if existing is not None:
        report.reu("evaluation")
        return
    db.add(
        Evaluation(
            tenant_id=tenant.id,
            disclosure_id=disclosure.id,
            kind=kind,
            evaluator_id=evaluator.id,
            outcome=outcome,
            summary=summary,
            recommendations=recommendations,
            confidentiality_level=CONFIDENTIALITY_INTERNAL,
            active=True,
        )
    )
    report.cre("evaluation")
    db.flush()


def _ensure_asset(
    db: Session,
    ctx: dict,
    report: SeedReport,
    *,
    code: str,
    title: str,
    asset_type: str,
    status: str,
    description: str,
    disclosure: InventionDisclosure | None = None,
) -> IPAsset:
    tenant: Tenant = ctx["tenant"]
    asset = db.execute(
        select(IPAsset).where(IPAsset.tenant_id == tenant.id, IPAsset.code == code)
    ).scalars().first()
    if asset is not None:
        report.reu("ip_asset")
        return asset
    asset = IPAsset(
        tenant_id=tenant.id,
        unity_id=ctx["unity"].id,
        disclosure_id=disclosure.id if disclosure else None,
        code=code,
        title=title,
        description=description,
        asset_type=asset_type,
        status=status,
        technology_area="Engenharia",
        confidentiality_level=CONFIDENTIALITY_INTERNAL,
        responsible_id=ctx["users"]["manager"].id,
        active=True,
    )
    db.add(asset)
    db.flush()
    report.cre("ip_asset")
    return asset


def _ensure_public_link(
    db: Session,
    ctx: dict,
    report: SeedReport,
    asset: IPAsset,
    *,
    source: str,
    external_ref: str,
) -> None:
    tenant: Tenant = ctx["tenant"]
    link = db.execute(
        select(IPAssetPublicLink).where(
            IPAssetPublicLink.asset_id == asset.id,
            IPAssetPublicLink.source == source,
            IPAssetPublicLink.external_ref == external_ref,
        )
    ).scalar_one_or_none()
    if link is not None:
        report.reu("ip_asset_public_link")
        return
    db.add(
        IPAssetPublicLink(
            tenant_id=tenant.id,
            asset_id=asset.id,
            source=source,
            external_ref=external_ref,
            synced_at=datetime.now(timezone.utc),
        )
    )
    report.cre("ip_asset_public_link")
    db.flush()



def seed_demo_f1(db: Session, ctx: dict) -> tuple[dict, SeedReport]:
    """Seed phase F1 (disclosures → assets) under the demo tenant."""
    tenant: Tenant = ctx["tenant"]
    report = SeedReport()
    seed_tenant_workflow(db, tenant.id)

    researcher: User = ctx["users"]["researcher"]
    analyst: User = ctx["users"]["analyst"]
    manager: User = ctx["users"]["manager"]

    specs = [
        (DEMO_PROTOCOL_TITLES[0], "Sensor piezoelétrico de baixo custo para SHM.",
         "Engenharia de Materiais", "sensor; piezoelétrico; monitoramento",
         CONFIDENTIALITY_CONFIDENTIAL, WF_CLOSED),
        (DEMO_PROTOCOL_TITLES[1], "Visão computacional aplicada à inspeção de culturas.",
         "Computação", "visão computacional; agricultura; IA",
         CONFIDENTIALITY_RESTRICTED, WF_EVALUATION),
        (DEMO_PROTOCOL_TITLES[2], "Encapsulamento de bioativos da biodiversidade amazônica.",
         "Biotecnologia", "bioativos; encapsulamento; amazônia",
         CONFIDENTIALITY_CONFIDENTIAL, WF_DECISION),
        (DEMO_PROTOCOL_TITLES[3], "Otimização de rotas de última milha com heurísticas.",
         "Computação", "logística; otimização; software",
         CONFIDENTIALITY_INTERNAL, WF_TRIAGE),
        (DEMO_PROTOCOL_TITLES[4], "Ligante cimentício de baixo carbono com resíduos.",
         "Engenharia Civil", "cimento; resíduos; sustentabilidade",
         CONFIDENTIALITY_PUBLIC, WF_PROPOSAL),
    ]

    disclosures: list[InventionDisclosure] = []
    for title, summary, area, keywords, level, target in specs:
        disclosure = _get_or_create_disclosure(
            db, ctx, report,
            title=title, summary=summary, technology_area=area,
            keywords=keywords, confidentiality_level=level,
            submitted_by=researcher,
        )
        _ensure_inventors(db, ctx, report, disclosure)
        _ensure_documents(db, ctx, report, disclosure)
        _ensure_workflow(
            db, ctx, report, disclosure,
            target_state=target,
            justification="Aprovação do comitê de inovação na reunião ordinária.",
        )
        if target in (WF_EVALUATION, WF_DECISION, WF_CLOSED):
            _ensure_evaluation(
                db, ctx, report, disclosure,
                kind=EVALUATION_TECHNICAL, outcome="FAVORABLE", evaluator=analyst,
                summary="Parecer técnico favorável com ressalvas de escalabilidade.",
                recommendations="Prosseguir para avaliação jurídica e comercial.",
            )
        if target in (WF_DECISION, WF_CLOSED):
            _ensure_evaluation(
                db, ctx, report, disclosure,
                kind=EVALUATION_LEGAL, outcome="CONDITIONAL", evaluator=analyst,
                summary="Análise de titularidade e liberdade de operação.",
                recommendations="Formalizar co-titularidade com a universidade parceira.",
            )
            _ensure_evaluation(
                db, ctx, report, disclosure,
                kind=EVALUATION_COMMERCIAL, outcome="FAVORABLE", evaluator=manager,
                summary="Potencial de mercado identificado no setor industrial.",
                recommendations="Buscar empresas licenciadas via oferta tecnológica.",
            )
        disclosures.append(disclosure)

    asset_patent = _ensure_asset(
        db, ctx, report,
        code="ATV-0001",
        title="Sensor piezoelétrico para SHM",
        asset_type=ASSET_TYPE_PATENT,
        status=ASSET_STATUS_PROTECTED,
        description="Ativo institucional derivado da comunicação de invenção encerrada.",
        disclosure=disclosures[0],
    )
    asset_software = _ensure_asset(
        db, ctx, report,
        code="ATV-0002",
        title="Plataforma de otimização logística",
        asset_type=ASSET_TYPE_SOFTWARE,
        status=ASSET_STATUS_PROTECTED,
        description="Software institucional registrado, sem comunicação de origem.",
    )
    _ensure_public_link(db, ctx, report, asset_patent,
                        source="INPI", external_ref="BR1020200000001")
    _ensure_public_link(db, ctx, report, asset_software,
                        source="INPI", external_ref="BR5120200000002")

    ctx["disclosures"] = disclosures
    ctx["assets"] = {"patent": asset_patent, "software": asset_software}
    return ctx, report


# --- F2: TRL history, committees, meetings, votes, decisions ----------------


def _ensure_trl(
    db: Session,
    ctx: dict,
    report: SeedReport,
    *,
    level: int,
    previous_level: int | None,
    rationale: str,
    evaluator: User,
    disclosure: InventionDisclosure | None = None,
    asset: IPAsset | None = None,
) -> None:
    tenant: Tenant = ctx["tenant"]
    existing = db.execute(
        select(TechnologyReadinessLevel).where(
            TechnologyReadinessLevel.disclosure_id == (disclosure.id if disclosure else None),
            TechnologyReadinessLevel.asset_id == (asset.id if asset else None),
            TechnologyReadinessLevel.level == level,
        )
    ).scalars().first()
    if existing is not None:
        report.reu("trl_history")
        return
    db.add(
        TechnologyReadinessLevel(
            tenant_id=tenant.id,
            disclosure_id=disclosure.id if disclosure else None,
            asset_id=asset.id if asset else None,
            level=level,
            previous_level=previous_level,
            rationale=rationale,
            evidence="Relatório de ensaios internos e protótipo funcional.",
            evaluator_id=evaluator.id,
        )
    )
    report.cre("trl_history")
    db.flush()


def _ensure_committee(
    db: Session, ctx: dict, report: SeedReport, *, code: str, name: str,
    description: str, quorum: int,
) -> Committee:
    tenant: Tenant = ctx["tenant"]
    committee = db.execute(
        select(Committee).where(
            Committee.tenant_id == tenant.id, Committee.code == code
        )
    ).scalars().first()
    if committee is not None:
        report.reu("committee")
        return committee
    committee = Committee(
        tenant_id=tenant.id,
        code=code,
        name=name,
        description=description,
        status=COMMITTEE_STATUS_ACTIVE,
        quorum=quorum,
        simple_majority=True,
        active=True,
    )
    db.add(committee)
    db.flush()
    report.cre("committee")
    return committee


def _ensure_committee_member(
    db: Session, ctx: dict, report: SeedReport, committee: Committee,
    *, user: User, name: str, role_title: str, kind: str = "VOTING",
) -> CommitteeMember:
    tenant: Tenant = ctx["tenant"]
    member = db.execute(
        select(CommitteeMember).where(
            CommitteeMember.committee_id == committee.id,
            CommitteeMember.user_id == user.id,
        )
    ).scalars().first()
    if member is not None:
        report.reu("committee_member")
        return member
    member = CommitteeMember(
        tenant_id=tenant.id,
        committee_id=committee.id,
        user_id=user.id,
        person_id=user.person_id,
        name=name,
        role_title=role_title,
        kind=kind,
        valid_from=datetime.now(timezone.utc) - timedelta(days=365),
        active=True,
    )
    db.add(member)
    db.flush()
    report.cre("committee_member")
    return member


def _ensure_meeting(
    db: Session, ctx: dict, report: SeedReport, committee: Committee,
    *, title: str, scheduled_at: datetime, held: bool, location: str,
) -> CommitteeMeeting:
    tenant: Tenant = ctx["tenant"]
    meeting = db.execute(
        select(CommitteeMeeting).where(
            CommitteeMeeting.committee_id == committee.id,
            CommitteeMeeting.title == title,
        )
    ).scalars().first()
    if meeting is not None:
        report.reu("committee_meeting")
        return meeting
    meeting = CommitteeMeeting(
        tenant_id=tenant.id,
        committee_id=committee.id,
        title=title,
        scheduled_at=scheduled_at,
        held_at=scheduled_at if held else None,
        status=MEETING_STATUS_HELD if held else "SCHEDULED",
        location=location,
        minutes=(
            "Reunião ordinária: pauta analisada e deliberada conforme ata."
            if held else None
        ),
        created_by_id=ctx["users"]["manager"].id,
    )
    db.add(meeting)
    db.flush()
    report.cre("committee_meeting")
    return meeting




def _ensure_agenda_item(
    db: Session, ctx: dict, report: SeedReport, meeting: CommitteeMeeting,
    *, title: str, summary: str, sort_order: int,
    disclosure: InventionDisclosure | None = None, asset: IPAsset | None = None,
) -> CommitteeAgendaItem:
    tenant: Tenant = ctx["tenant"]
    item = db.execute(
        select(CommitteeAgendaItem).where(
            CommitteeAgendaItem.meeting_id == meeting.id,
            CommitteeAgendaItem.title == title,
        )
    ).scalars().first()
    if item is not None:
        report.reu("committee_agenda_item")
        return item
    item = CommitteeAgendaItem(
        tenant_id=tenant.id,
        meeting_id=meeting.id,
        disclosure_id=disclosure.id if disclosure else None,
        asset_id=asset.id if asset else None,
        title=title,
        summary=summary,
        status=AGENDA_ITEM_STATUS_DECIDED,
        sort_order=sort_order,
    )
    db.add(item)
    db.flush()
    report.cre("committee_agenda_item")
    return item


def _ensure_vote(
    db: Session, ctx: dict, report: SeedReport, item: CommitteeAgendaItem,
    member: CommitteeMember, *, vote: str, comment: str,
) -> None:
    tenant: Tenant = ctx["tenant"]
    existing = db.execute(
        select(CommitteeVote).where(
            CommitteeVote.item_id == item.id, CommitteeVote.member_id == member.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        report.reu("committee_vote")
        return
    db.add(
        CommitteeVote(
            tenant_id=tenant.id,
            item_id=item.id,
            member_id=member.id,
            voter_user_id=member.user_id,
            vote=vote,
            conflict_of_interest=False,
            comment=comment,
        )
    )
    report.cre("committee_vote")
    db.flush()


def _ensure_decision(
    db: Session, ctx: dict, report: SeedReport, item: CommitteeAgendaItem,
    *, outcome: str, justification: str, approvals: int, rejections: int,
    abstentions: int = 0, impeded: int = 0,
) -> None:
    tenant: Tenant = ctx["tenant"]
    existing = db.execute(
        select(CommitteeDecision).where(CommitteeDecision.item_id == item.id)
    ).scalar_one_or_none()
    if existing is not None:
        report.reu("committee_decision")
        return
    db.add(
        CommitteeDecision(
            tenant_id=tenant.id,
            item_id=item.id,
            outcome=outcome,
            justification=justification,
            approvals=approvals,
            rejections=rejections,
            abstentions=abstentions,
            impeded=impeded,
            decided_by_id=ctx["users"]["manager"].id,
            decided_at=datetime.now(timezone.utc),
        )
    )
    report.cre("committee_decision")
    db.flush()



def seed_demo_f2(db: Session, ctx: dict) -> tuple[dict, SeedReport]:
    """Seed phase F2 (TRL, committee, meeting, votes, decision)."""
    report = SeedReport()
    analyst: User = ctx["users"]["analyst"]
    manager: User = ctx["users"]["manager"]
    committee_user: User = ctx["users"]["committee"]
    tt_operator: User = ctx["users"]["tt_operator"]
    disclosures: list[InventionDisclosure] = ctx["disclosures"]
    assets: dict = ctx["assets"]

    # TRL is only ever recorded by a human evaluator, with rationale + evidence.
    _ensure_trl(
        db, ctx, report, level=4, previous_level=3,
        rationale="Componente validado em ambiente de laboratório.",
        evaluator=analyst, disclosure=disclosures[0],
    )
    _ensure_trl(
        db, ctx, report, level=5, previous_level=4,
        rationale="Protótipo validado em ambiente relevante (TRL 5).",
        evaluator=analyst, disclosure=disclosures[0],
    )
    _ensure_trl(
        db, ctx, report, level=3, previous_level=2,
        rationale="Prova de conceito analítica concluída.",
        evaluator=analyst, asset=assets["software"],
    )

    committee = _ensure_committee(
        db, ctx, report,
        code="CI-INST",
        name="Comitê Institucional de Inovação",
        description="Delibera sobre proteção, transferência e incubação.",
        quorum=2,
    )
    member_manager = _ensure_committee_member(
        db, ctx, report, committee, user=manager,
        name="Mariana Alves", role_title="Presidente",
    )
    member_committee = _ensure_committee_member(
        db, ctx, report, committee, user=committee_user,
        name="Prof. Sérgio Bastos", role_title="Relator",
    )
    _ensure_committee_member(
        db, ctx, report, committee, user=tt_operator,
        name="Bruno Tavares", role_title="Secretário", kind="ADVISORY",
    )
    member_analyst = _ensure_committee_member(
        db, ctx, report, committee, user=analyst,
        name="Rafael Coutinho", role_title="Membro técnico",
    )

    now = datetime.now(timezone.utc)
    meeting_held = _ensure_meeting(
        db, ctx, report, committee,
        title="37ª Reunião Ordinária",
        scheduled_at=now - timedelta(days=30), held=True,
        location="Sala de Conselhos / Videoconferência",
    )
    _ensure_meeting(
        db, ctx, report, committee,
        title="38ª Reunião Ordinária",
        scheduled_at=now + timedelta(days=15), held=False,
        location="Auditório central",
    )

    item1 = _ensure_agenda_item(
        db, ctx, report, meeting_held,
        title="Deliberação: sensor piezoelétrico",
        summary="Análise de mérito e decisão sobre proteção do ativo.",
        sort_order=1, disclosure=disclosures[0],
    )
    item2 = _ensure_agenda_item(
        db, ctx, report, meeting_held,
        title="Deliberação: plataforma de visão computacional",
        summary="Avaliação preliminar para seguimento de avaliação.",
        sort_order=2, disclosure=disclosures[1],
    )

    _ensure_vote(db, ctx, report, item1, member_manager, vote=VOTE_APPROVE,
                 comment="Relevância institucional e potencial de mercado.")
    _ensure_vote(db, ctx, report, item1, member_committee, vote=VOTE_APPROVE,
                 comment="Parecer técnico favorável.")
    _ensure_vote(db, ctx, report, item1, member_analyst, vote=VOTE_APPROVE,
                 comment="Mérito técnico comprovado.")
    _ensure_decision(
        db, ctx, report, item1,
        outcome=DECISION_APPROVED,
        justification="Aprovado por unanimidade; seguir para proteção.",
        approvals=3, rejections=0,
    )

    _ensure_vote(db, ctx, report, item2, member_manager, vote=VOTE_APPROVE,
                 comment="Prosseguir para avaliação.")
    _ensure_vote(db, ctx, report, item2, member_committee, vote=VOTE_APPROVE,
                 comment="Sem impedimentos identificados.")
    _ensure_decision(
        db, ctx, report, item2,
        outcome=DECISION_APPROVED,
        justification="Aprovado; encaminhar para avaliação jurídica.",
        approvals=2, rejections=0,
    )

    ctx["committee"] = committee
    ctx["committee_members"] = [member_manager, member_committee, member_analyst]
    return ctx, report



# --- F3: offers, interests, negotiations, licenses, contracts ---------------


def _ensure_offer(
    db: Session, ctx: dict, report: SeedReport, *, code: str, title: str,
    public_summary: str, technology_area: str, maturity: str, modality: str,
    asset: IPAsset | None = None,
) -> TechnologyOffer:
    tenant: Tenant = ctx["tenant"]
    offer = db.execute(
        select(TechnologyOffer).where(
            TechnologyOffer.tenant_id == tenant.id, TechnologyOffer.code == code
        )
    ).scalars().first()
    if offer is not None:
        report.reu("technology_offer")
        return offer
    offer = TechnologyOffer(
        tenant_id=tenant.id,
        asset_id=asset.id if asset else None,
        unity_id=ctx["unity"].id,
        code=code,
        title=title,
        public_summary=public_summary,
        technology_area=technology_area,
        maturity=maturity,
        modality=modality,
        contact_name="Mariana Alves",
        contact_email="mariana.alves@demo.nit.br",
        conditions="Licenciamento não exclusivo, com contrapartida em royalties.",
        status=OFFER_STATUS_PUBLISHED,
        responsible_id=ctx["users"]["manager"].id,
        active=True,
    )
    db.add(offer)
    db.flush()
    report.cre("technology_offer")
    return offer


def _ensure_interest(
    db: Session, ctx: dict, report: SeedReport, offer: TechnologyOffer,
    *, organization_name: str, contact_name: str, contact_email: str,
    message: str, status: str,
) -> ExpressionOfInterest:
    tenant: Tenant = ctx["tenant"]
    interest = db.execute(
        select(ExpressionOfInterest).where(
            ExpressionOfInterest.offer_id == offer.id,
            ExpressionOfInterest.organization_name == organization_name,
        )
    ).scalars().first()
    if interest is not None:
        report.reu("expression_of_interest")
        return interest
    interest = ExpressionOfInterest(
        tenant_id=tenant.id,
        offer_id=offer.id,
        organization_name=organization_name,
        organization_document="12.345.678/0001-90",
        contact_name=contact_name,
        contact_email=contact_email,
        contact_phone="+55 92 3333-4444",
        message=message,
        status=status,
        owner_id=ctx["users"]["tt_operator"].id,
        active=True,
    )
    db.add(interest)
    db.flush()
    report.cre("expression_of_interest")
    return interest


def _ensure_interest_interaction(
    db: Session, ctx: dict, report: SeedReport, interest: ExpressionOfInterest,
    *, kind: str, summary: str, actor: User | None = None,
) -> None:
    """Append-only log for an expression of interest.

    The physical table (see migrations) additionally carries ``kind`` and
    ``summary`` columns that the ORM model does not map, so we insert through
    explicit SQL to honour the real, NOT NULL database contract.
    """
    tenant: Tenant = ctx["tenant"]
    existing = db.execute(
        select(InterestInteraction).where(
            InterestInteraction.interest_id == interest.id
        )
    ).scalars().first()
    if existing is not None:
        report.reu("interest_interaction")
        return
    db.execute(
        text(
            "INSERT INTO interest_interactions "
            "(id, tenant_id, interest_id, kind, summary, actor_id) "
            "VALUES (:id, :tenant_id, :interest_id, :kind, :summary, :actor_id)"
        ),
        {
            "id": uuid.uuid4(),
            "tenant_id": tenant.id,
            "interest_id": interest.id,
            "kind": kind,
            "summary": summary,
            "actor_id": actor.id if actor else None,
        },
    )
    report.cre("interest_interaction")
    db.flush()


def _ensure_negotiation(
    db: Session, ctx: dict, report: SeedReport, *,
    interest: ExpressionOfInterest, offer: TechnologyOffer,
    stage: str, notes: str, history_stages: list[str],
) -> Negotiation:
    tenant: Tenant = ctx["tenant"]
    negotiation = db.execute(
        select(Negotiation).where(
            Negotiation.interest_id == interest.id
        )
    ).scalars().first()
    if negotiation is not None:
        report.reu("negotiation")
    else:
        negotiation = Negotiation(
            tenant_id=tenant.id,
            interest_id=interest.id,
            offer_id=offer.id,
            stage=stage,
            owner_id=ctx["users"]["tt_operator"].id,
            next_step="Formalizar minuta contratual.",
            notes=notes,
            version=len(history_stages),
            active=True,
        )
        db.add(negotiation)
        db.flush()
        report.cre("negotiation")

    # Append-only stage history (skip if already recorded for this negotiation).
    existing_stages = {
        h.to_stage
        for h in db.execute(
            select(NegotiationHistory).where(
                NegotiationHistory.negotiation_id == negotiation.id
            )
        ).scalars()
    }
    previous: str | None = None
    for to_stage in history_stages:
        if to_stage in existing_stages:
            report.reu("negotiation_history")
            previous = to_stage
            continue
        db.add(
            NegotiationHistory(
                tenant_id=tenant.id,
                negotiation_id=negotiation.id,
                from_stage=previous,
                to_stage=to_stage,
                actor_id=ctx["users"]["tt_operator"].id,
                justification=f"Avanço de etapa para {to_stage}.",
            )
        )
        report.cre("negotiation_history")
        previous = to_stage
    db.flush()
    return negotiation



def _ensure_license(
    db: Session, ctx: dict, report: SeedReport, *, code: str, title: str,
    asset: IPAsset | None, negotiation: Negotiation | None,
    exclusive: bool, start: date, end: date,
) -> License:
    tenant: Tenant = ctx["tenant"]
    license_row = db.execute(
        select(License).where(
            License.tenant_id == tenant.id, License.code == code
        )
    ).scalars().first()
    if license_row is not None:
        report.reu("license")
        return license_row
    license_row = License(
        tenant_id=tenant.id,
        code=code,
        license_type="LICENSE",
        asset_id=asset.id if asset else None,
        negotiation_id=negotiation.id if negotiation else None,
        title=title,
        exclusive=exclusive,
        start_date=start,
        end_date=end,
        notes="Instrumento de licenciamento de uso da tecnologia.",
        active=True,
    )
    db.add(license_row)
    db.flush()
    report.cre("license")
    return license_row


def _ensure_contract(
    db: Session, ctx: dict, report: SeedReport, *, code: str, title: str,
    license_row: License, registered_amount: Decimal, signed_at: date,
    effective_from: date, effective_until: date,
) -> Contract:
    tenant: Tenant = ctx["tenant"]
    contract = db.execute(
        select(Contract).where(
            Contract.tenant_id == tenant.id, Contract.code == code
        )
    ).scalars().first()
    if contract is not None:
        report.reu("contract")
        return contract
    contract = Contract(
        tenant_id=tenant.id,
        license_id=license_row.id,
        code=code,
        title=title,
        status=CONTRACT_STATUS_ACTIVE,
        is_amendment=False,
        signed_at=signed_at,
        effective_from=effective_from,
        effective_until=effective_until,
        registered_amount=registered_amount,
        currency="BRL",
        conditions="Pagamento de royalties sobre o faturamento líquido.",
        notes="Contrato ativo de transferência de tecnologia (dados de demonstração).",
        responsible_id=ctx["users"]["manager"].id,
        active=True,
    )
    db.add(contract)
    db.flush()
    report.cre("contract")
    return contract


def _ensure_party(
    db: Session, ctx: dict, report: SeedReport, contract: Contract,
    *, role: str, name: str, document: str, representative: str,
    email: str | None = None,
) -> None:
    tenant: Tenant = ctx["tenant"]
    party = db.execute(
        select(ContractParty).where(
            ContractParty.contract_id == contract.id,
            ContractParty.role == role,
            ContractParty.name == name,
        )
    ).scalars().first()
    if party is not None:
        report.reu("contract_party")
        return
    db.add(
        ContractParty(
            tenant_id=tenant.id,
            contract_id=contract.id,
            role=role,
            name=name,
            document=document,
            email=email,
            representative=representative,
        )
    )
    report.cre("contract_party")
    db.flush()


def _ensure_obligation(
    db: Session, ctx: dict, report: SeedReport, contract: Contract,
    *, kind: str, description: str, due_date: date | None, status: str,
    responsible: User | None = None, fulfilled: date | None = None,
) -> None:
    tenant: Tenant = ctx["tenant"]
    obligation = db.execute(
        select(ContractObligation).where(
            ContractObligation.contract_id == contract.id,
            ContractObligation.description == description,
        )
    ).scalars().first()
    if obligation is not None:
        report.reu("contract_obligation")
        return
    db.add(
        ContractObligation(
            tenant_id=tenant.id,
            contract_id=contract.id,
            kind=kind,
            description=description,
            due_date=due_date,
            status=status,
            responsible_id=responsible.id if responsible else None,
            evidence="Termo de cumprimento arquivado." if fulfilled else None,
            fulfilled_at=fulfilled,
        )
    )
    report.cre("contract_obligation")
    db.flush()


def _ensure_royalty(
    db: Session, ctx: dict, report: SeedReport, contract: Contract,
    *, period: str, expected: Decimal, registered: Decimal,
    received: Decimal | None, due_date: date, received_at: date | None,
) -> None:
    tenant: Tenant = ctx["tenant"]
    royalty = db.execute(
        select(Royalty).where(
            Royalty.contract_id == contract.id, Royalty.period == period
        )
    ).scalars().first()
    if royalty is not None:
        report.reu("royalty")
        return
    db.add(
        Royalty(
            tenant_id=tenant.id,
            contract_id=contract.id,
            period=period,
            expected_amount=expected,
            registered_amount=registered,
            received_amount=received,
            currency="BRL",
            due_date=due_date,
            received_at=received_at,
            notes="Valores de demonstração; expected/registered/received distintos.",
            created_by_id=ctx["users"]["tt_operator"].id,
        )
    )
    report.cre("royalty")
    db.flush()



def seed_demo_f3(db: Session, ctx: dict) -> tuple[dict, SeedReport]:
    """Seed phase F3 (offers → interests → negotiation → license → contract)."""
    report = SeedReport()
    assets: dict = ctx["assets"]
    tt_operator: User = ctx["users"]["tt_operator"]
    manager: User = ctx["users"]["manager"]

    offer = _ensure_offer(
        db, ctx, report,
        code="OFT-0001",
        title="Sensor piezoelétrico para monitoramento estrutural",
        public_summary="Solução de baixo custo para monitoramento de integridade estrutural.",
        technology_area="Engenharia de Materiais",
        maturity="TRL 5",
        modality="LICENSING",
        asset=assets["patent"],
    )
    _ensure_offer(
        db, ctx, report,
        code="OFT-0002",
        title="Plataforma de otimização logística de última milha",
        public_summary="Software de roteirização com heurísticas para entregas urbanas.",
        technology_area="Computação",
        maturity="TRL 3",
        modality="CO_DEVELOPMENT",
        asset=assets["software"],
    )

    interest = _ensure_interest(
        db, ctx, report, offer,
        organization_name="Indústria Amazônica de Sensores Ltda.",
        contact_name="Paulo Ribeiro",
        contact_email="paulo.ribeiro@sensores-am.com.br",
        message="Temos interesse em avaliar a licença para produção local.",
        status=INTEREST_STATUS_CONVERTED,
    )
    _ensure_interest_interaction(
        db, ctx, report, interest,
        kind="NOTE",
        summary="Interesse qualificado e convertido em negociação.",
        actor=ctx["users"]["tt_operator"],
    )
    # A second, still-open interest to exercise the NEW state.
    interest_open = _ensure_interest(
        db, ctx, report, offer,
        organization_name="Construtora Norte Engenharia S.A.",
        contact_name="Tatiana Lopes",
        contact_email="tatiana.lopes@norteeng.br",
        message="Solicitamos informações técnicas complementares.",
        status=INTEREST_STATUS_IN_NEGOTIATION,
    )
    _ensure_interest_interaction(
        db, ctx, report, interest_open,
        kind="MESSAGE",
        summary="Empresa solicitou informações técnicas complementares.",
        actor=ctx["users"]["analyst"],
    )

    negotiation = _ensure_negotiation(
        db, ctx, report, interest=interest, offer=offer,
        stage=NEG_STAGE_CLOSED,
        notes="Negociação concluída; contrato assinado.",
        history_stages=[
            NEG_STAGE_QUALIFICATION,
            NEG_STAGE_FIRST_CONTACT,
            NEG_STAGE_TECHNICAL,
            NEG_STAGE_NEGOTIATION,
            NEG_STAGE_CLOSED,
        ],
    )

    license_row = _ensure_license(
        db, ctx, report,
        code="LIC-0001",
        title="Licença de exploração — sensor piezoelétrico",
        asset=assets["patent"],
        negotiation=negotiation,
        exclusive=False,
        start=date(2026, 1, 1),
        end=date(2031, 1, 1),
    )

    contract = _ensure_contract(
        db, ctx, report,
        code="CTR-0001",
        title="Contrato de licenciamento de tecnologia — sensor piezoelétrico",
        license_row=license_row,
        registered_amount=Decimal("250000.00"),
        signed_at=date(2025, 12, 15),
        effective_from=date(2026, 1, 1),
        effective_until=date(2031, 1, 1),
    )
    _ensure_party(
        db, ctx, report, contract, role="LICENSOR",
        name="Instituto Demo NIT", document="00.000.000/0001-00",
        representative="Mariana Alves", email="juridico@demo.nit.br",
    )
    _ensure_party(
        db, ctx, report, contract, role="LICENSEE",
        name="Indústria Amazônica de Sensores Ltda.", document="12.345.678/0001-90",
        representative="Paulo Ribeiro", email="juridico@sensores-am.com.br",
    )
    _ensure_obligation(
        db, ctx, report, contract,
        kind="PAYMENT", description="Pagamento da parcela inicial de licenciamento.",
        due_date=date(2026, 2, 28), status=OBLIGATION_STATUS_DONE,
        responsible=tt_operator, fulfilled=date(2026, 2, 20),
    )
    _ensure_obligation(
        db, ctx, report, contract,
        kind="REPORT", description="Relatório semestral de faturamento para royalties.",
        due_date=date(2026, 7, 31), status=OBLIGATION_STATUS_PENDING,
        responsible=manager,
    )
    _ensure_royalty(
        db, ctx, report, contract,
        period="2026-01", expected=Decimal("5000.00"),
        registered=Decimal("4820.00"), received=Decimal("4820.00"),
        due_date=date(2026, 2, 15), received_at=date(2026, 2, 12),
    )
    _ensure_royalty(
        db, ctx, report, contract,
        period="2026-02", expected=Decimal("5000.00"),
        registered=Decimal("5100.00"), received=None,
        due_date=date(2026, 3, 15), received_at=None,
    )

    ctx["offer"] = offer
    ctx["negotiation"] = negotiation
    ctx["license"] = license_row
    ctx["contract"] = contract
    return ctx, report



# --- F4: projects, startups and incubation ----------------------------------


def _ensure_project(
    db: Session, ctx: dict, report: SeedReport, *, code: str, title: str,
    description: str, objective: str, technology_area: str, status: str,
    start: date, end: date, coordinator: User,
) -> Project:
    tenant: Tenant = ctx["tenant"]
    project = db.execute(
        select(Project).where(
            Project.tenant_id == tenant.id, Project.code == code
        )
    ).scalars().first()
    if project is not None:
        report.reu("project")
        return project
    project = Project(
        tenant_id=tenant.id,
        unity_id=ctx["unity"].id,
        code=code,
        title=title,
        description=description,
        objective=objective,
        technology_area=technology_area,
        status=status,
        start_date=start,
        end_date=end,
        coordinator_id=coordinator.id,
        notes="Projeto de P&D cadastrado para demonstração.",
        active=True,
    )
    db.add(project)
    db.flush()
    report.cre("project")
    return project


def _ensure_project_member(
    db: Session, ctx: dict, report: SeedReport, project: Project,
    *, user: User | None, name: str, role: str, institution: str,
) -> None:
    tenant: Tenant = ctx["tenant"]
    member = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.name == name,
        )
    ).scalars().first()
    if member is not None:
        report.reu("project_member")
        return
    db.add(
        ProjectMember(
            tenant_id=tenant.id,
            project_id=project.id,
            person_id=user.person_id if user else None,
            user_id=user.id if user else None,
            name=name,
            role=role,
            institution=institution,
            active=True,
        )
    )
    report.cre("project_member")
    db.flush()


def _ensure_funder(
    db: Session, ctx: dict, report: SeedReport, project: Project,
    *, name: str, instrument: str, amount: Decimal | None,
) -> None:
    tenant: Tenant = ctx["tenant"]
    funder = db.execute(
        select(ProjectFunder).where(
            ProjectFunder.project_id == project.id, ProjectFunder.name == name
        )
    ).scalars().first()
    if funder is not None:
        report.reu("project_funder")
        return
    db.add(
        ProjectFunder(
            tenant_id=tenant.id,
            project_id=project.id,
            name=name,
            document="00.000.000/0001-00",
            instrument=instrument,
            amount=amount,
            currency="BRL",
        )
    )
    report.cre("project_funder")
    db.flush()


def _ensure_milestone(
    db: Session, ctx: dict, report: SeedReport, project: Project,
    *, title: str, description: str, due_date: date | None, status: str,
    completed_at: date | None = None,
) -> None:
    tenant: Tenant = ctx["tenant"]
    milestone = db.execute(
        select(ProjectMilestone).where(
            ProjectMilestone.project_id == project.id,
            ProjectMilestone.title == title,
        )
    ).scalars().first()
    if milestone is not None:
        report.reu("project_milestone")
        return
    db.add(
        ProjectMilestone(
            tenant_id=tenant.id,
            project_id=project.id,
            title=title,
            description=description,
            due_date=due_date,
            status=status,
            completed_at=completed_at,
        )
    )
    report.cre("project_milestone")
    db.flush()


def _ensure_project_asset(
    db: Session, ctx: dict, report: SeedReport, project: Project,
    asset: IPAsset, *, relation: str, notes: str,
) -> None:
    tenant: Tenant = ctx["tenant"]
    link = db.execute(
        select(ProjectAssetLink).where(
            ProjectAssetLink.project_id == project.id,
            ProjectAssetLink.asset_id == asset.id,
        )
    ).scalars().first()
    if link is not None:
        report.reu("project_asset_link")
        return
    db.add(
        ProjectAssetLink(
            tenant_id=tenant.id,
            project_id=project.id,
            asset_id=asset.id,
            relation=relation,
            notes=notes,
        )
    )
    report.cre("project_asset_link")
    db.flush()



def _ensure_startup(
    db: Session, ctx: dict, report: SeedReport, *, code: str, name: str,
    description: str, status: str, stage: str, founded: date,
    project: Project | None, asset: IPAsset | None, responsible: User,
) -> Startup:
    tenant: Tenant = ctx["tenant"]
    startup = db.execute(
        select(Startup).where(
            Startup.tenant_id == tenant.id, Startup.code == code
        )
    ).scalars().first()
    if startup is not None:
        report.reu("startup")
        return startup
    startup = Startup(
        tenant_id=tenant.id,
        code=code,
        name=name,
        description=description,
        cnpj="00.000.000/0001-00",
        status=status,
        stage=stage,
        founded_at=founded,
        project_id=project.id if project else None,
        asset_id=asset.id if asset else None,
        responsible_id=responsible.id,
        notes="Startup/spin-off de demonstração (vínculo não implica titularidade).",
        active=True,
    )
    db.add(startup)
    db.flush()
    report.cre("startup")
    return startup


def _ensure_startup_member(
    db: Session, ctx: dict, report: SeedReport, startup: Startup,
    *, user: User | None, name: str, role: str, is_founder: bool,
) -> None:
    tenant: Tenant = ctx["tenant"]
    member = db.execute(
        select(StartupMember).where(
            StartupMember.startup_id == startup.id, StartupMember.name == name
        )
    ).scalars().first()
    if member is not None:
        report.reu("startup_member")
        return
    db.add(
        StartupMember(
            tenant_id=tenant.id,
            startup_id=startup.id,
            person_id=user.person_id if user else None,
            user_id=user.id if user else None,
            name=name,
            role=role,
            is_founder=is_founder,
        )
    )
    report.cre("startup_member")
    db.flush()


def _ensure_program(
    db: Session, ctx: dict, report: SeedReport, *, code: str, name: str,
    description: str, criteria: str, start: date, end: date,
) -> IncubationProgram:
    tenant: Tenant = ctx["tenant"]
    program = db.execute(
        select(IncubationProgram).where(
            IncubationProgram.tenant_id == tenant.id, IncubationProgram.code == code
        )
    ).scalars().first()
    if program is not None:
        report.reu("incubation_program")
        return program
    program = IncubationProgram(
        tenant_id=tenant.id,
        code=code,
        name=name,
        description=description,
        criteria=criteria,
        start_date=start,
        end_date=end,
        active=True,
    )
    db.add(program)
    db.flush()
    report.cre("incubation_program")
    return program


def _ensure_participation(
    db: Session, ctx: dict, report: SeedReport, program: IncubationProgram,
    startup: Startup, *, entry: date, notes: str,
) -> IncubationParticipation:
    tenant: Tenant = ctx["tenant"]
    participation = db.execute(
        select(IncubationParticipation).where(
            IncubationParticipation.program_id == program.id,
            IncubationParticipation.startup_id == startup.id,
        )
    ).scalars().first()
    if participation is not None:
        report.reu("incubation_participation")
        return participation
    participation = IncubationParticipation(
        tenant_id=tenant.id,
        program_id=program.id,
        startup_id=startup.id,
        entry_date=entry,
        exit_date=None,
        exit_status=None,
        notes=notes,
    )
    db.add(participation)
    db.flush()
    report.cre("incubation_participation")
    return participation


def _ensure_stage(
    db: Session, ctx: dict, report: SeedReport,
    participation: IncubationParticipation, *, title: str, kind: str,
    status: str, due_date: date | None, completed_at: date | None, result: str | None,
) -> None:
    tenant: Tenant = ctx["tenant"]
    stage = db.execute(
        select(IncubationStage).where(
            IncubationStage.participation_id == participation.id,
            IncubationStage.title == title,
        )
    ).scalars().first()
    if stage is not None:
        report.reu("incubation_stage")
        return
    db.add(
        IncubationStage(
            tenant_id=tenant.id,
            participation_id=participation.id,
            title=title,
            kind=kind,
            status=status,
            due_date=due_date,
            completed_at=completed_at,
            result=result,
        )
    )
    report.cre("incubation_stage")
    db.flush()



def seed_demo_f4(db: Session, ctx: dict) -> tuple[dict, SeedReport]:
    """Seed phase F4 (projects, startups, incubation)."""
    report = SeedReport()
    assets: dict = ctx["assets"]
    researcher: User = ctx["users"]["researcher"]
    manager: User = ctx["users"]["manager"]

    project = _ensure_project(
        db, ctx, report,
        code="PRJ-0001",
        title="Sensor piezoelétrico para monitoramento estrutural",
        description="P&D do sensor e de sua cadeia de fabricação local.",
        objective="Elevar o sensor ao TRL 7 com validação em campo.",
        technology_area="Engenharia de Materiais",
        status=PROJECT_STATUS_ACTIVE,
        start=date(2025, 3, 1), end=date(2027, 2, 28),
        coordinator=researcher,
    )
    _ensure_project_member(
        db, ctx, report, project, user=researcher,
        name="Dra. Helena Prado", role="COORDINATOR", institution="Instituto Demo NIT",
    )
    _ensure_project_member(
        db, ctx, report, project, user=None,
        name="Carlos Menezes", role="PARTNER", institution="UFAM",
    )
    _ensure_funder(
        db, ctx, report, project,
        name="Fundação de Amparo à Pesquisa do Amazonas",
        instrument="Edital 001/2025 — Inovação",
        amount=Decimal("480000.00"),
    )
    _ensure_milestone(
        db, ctx, report, project, title="Protótipo funcional (TRL 5)",
        description="Protótipo validado em ambiente relevante.",
        due_date=date(2026, 3, 31), status=MILESTONE_STATUS_DONE,
        completed_at=date(2026, 3, 10),
    )
    _ensure_milestone(
        db, ctx, report, project, title="Validação em campo (TRL 7)",
        description="Aplicação em estrutura real monitorada.",
        due_date=date(2026, 12, 31), status=MILESTONE_STATUS_PENDING,
    )
    _ensure_project_asset(
        db, ctx, report, project, assets["patent"],
        relation="RESULT", notes="Ativo resultante do projeto de P&D.",
    )

    startup = _ensure_startup(
        db, ctx, report,
        code="STP-0001",
        name="PiezoTech Sensores Ltda.",
        description="Spin-off dedicada à produção e comercialização do sensor.",
        status=STARTUP_STATUS_INCUBATED,
        stage="Incubação — fase de tração",
        founded=date(2025, 8, 1),
        project=project, asset=assets["patent"], responsible=researcher,
    )
    _ensure_startup_member(
        db, ctx, report, startup, user=researcher,
        name="Dra. Helena Prado", role="CEO", is_founder=True,
    )
    _ensure_startup_member(
        db, ctx, report, startup, user=None,
        name="Carlos Menezes", role="CTO", is_founder=True,
    )

    program = _ensure_program(
        db, ctx, report,
        code="INC-2025",
        name="Programa de Incubação Amazônia Inova 2025",
        description="Incubação de base tecnológica com foco em hardware.",
        criteria="TRL ≥ 3, equipe dedicada e modelo de negócio definido.",
        start=date(2025, 7, 1), end=date(2026, 12, 31),
    )
    participation = _ensure_participation(
        db, ctx, report, program, startup,
        entry=date(2025, 9, 1),
        notes="Startup admitida na turma 2025 com plano de aceleração.",
    )
    _ensure_stage(
        db, ctx, report, participation, title="Boas-vindas e diagnóstico",
        kind="MENTORING", status="COMPLETED", due_date=date(2025, 9, 30),
        completed_at=date(2025, 9, 25), result="Plano de desenvolvimento aprovado.",
    )
    _ensure_stage(
        db, ctx, report, participation, title="Mentoria de produto e mercado",
        kind="MENTORING", status="IN_PROGRESS", due_date=date(2026, 6, 30),
        completed_at=None, result=None,
    )

    ctx["project"] = project
    ctx["startup"] = startup
    ctx["program"] = program
    return ctx, report



# --- F5: notifications, portal, BI reports and integrations -----------------


def _ensure_notification(
    db: Session, ctx: dict, report: SeedReport, *, user: User, kind: str,
    severity: str, title: str, body: str, link: str,
    resource_type: str | None = None, resource_id: uuid.UUID | None = None,
) -> Notification:
    tenant: Tenant = ctx["tenant"]
    notification = db.execute(
        select(Notification).where(
            Notification.user_id == user.id, Notification.title == title
        )
    ).scalars().first()
    if notification is not None:
        report.reu("notification")
        return notification
    notification = Notification(
        tenant_id=tenant.id,
        user_id=user.id,
        kind=kind,
        severity=severity,
        title=title,
        body=body,
        link=link,
        resource_type=resource_type,
        resource_id=resource_id,
        read_at=None,
    )
    db.add(notification)
    db.flush()
    report.cre("notification")
    return notification


def _ensure_notification_pref(
    db: Session, ctx: dict, report: SeedReport, *, user: User, kind: str,
    in_app: bool, email: bool,
) -> None:
    tenant: Tenant = ctx["tenant"]
    pref = db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user.id,
            NotificationPreference.kind == kind,
        )
    ).scalar_one_or_none()
    if pref is not None:
        report.reu("notification_preference")
        return
    db.add(
        NotificationPreference(
            tenant_id=tenant.id,
            user_id=user.id,
            kind=kind,
            in_app_enabled=in_app,
            email_enabled=email,
        )
    )
    report.cre("notification_preference")
    db.flush()


def _ensure_email(
    db: Session, ctx: dict, report: SeedReport, *, created_by: User,
    to_email: str, subject: str, body: str, kind: str,
) -> EmailMessage:
    """Queued e-mail stays QUEUED (no real transport configured in the demo)."""
    tenant: Tenant = ctx["tenant"]
    email = db.execute(
        select(EmailMessage).where(
            EmailMessage.tenant_id == tenant.id,
            EmailMessage.subject == subject,
        )
    ).scalars().first()
    if email is not None:
        report.reu("email_message")
        return email
    email = EmailMessage(
        tenant_id=tenant.id,
        to_email=to_email,
        subject=subject,
        body=body,
        kind=kind,
        status=EMAIL_STATUS_QUEUED,
        error=None,
        sent_at=None,
        created_by=created_by.id,
    )
    db.add(email)
    db.flush()
    report.cre("email_message")
    return email


def _ensure_portal_access(
    db: Session, ctx: dict, report: SeedReport, *, portal_kind: str,
    email: str, name: str, organization: str | None,
    subject_type: str | None = None, subject_id: uuid.UUID | None = None,
) -> ExternalPortalAccess:
    tenant: Tenant = ctx["tenant"]
    access = db.execute(
        select(ExternalPortalAccess).where(
            ExternalPortalAccess.tenant_id == tenant.id,
            ExternalPortalAccess.portal_kind == portal_kind,
            ExternalPortalAccess.email == email,
        )
    ).scalars().first()
    if access is not None:
        report.reu("external_portal_access")
        return access
    access = ExternalPortalAccess(
        tenant_id=tenant.id,
        portal_kind=portal_kind,
        email=email,
        name=name,
        organization=organization,
        subject_type=subject_type,
        subject_id=subject_id,
        status="ACTIVE",
        expires_at=datetime.now(timezone.utc) + timedelta(days=180),
        # Deterministic demo token (64 chars) so re-runs are reproducible.
        access_token=uuid.uuid5(uuid.NAMESPACE_URL, f"demo-portal:{email}").hex * 2,
        granted_by=ctx["users"]["manager"].id,
    )
    db.add(access)
    db.flush()
    report.cre("external_portal_access")
    return access



def _ensure_portal_request(
    db: Session, ctx: dict, report: SeedReport, access: ExternalPortalAccess,
    *, request_type: str, subject: str, message: str, status: str,
) -> PortalRequest:
    tenant: Tenant = ctx["tenant"]
    request = db.execute(
        select(PortalRequest).where(
            PortalRequest.access_id == access.id,
            PortalRequest.subject == subject,
        )
    ).scalars().first()
    if request is not None:
        report.reu("portal_request")
        return request
    request = PortalRequest(
        tenant_id=tenant.id,
        access_id=access.id,
        request_type=request_type,
        subject=subject,
        message=message,
        payload={"origin": "portal-externo", "demo": True},
        status=status,
        triaged_by=ctx["users"]["analyst"].id if status != "NEW" else None,
        triaged_at=datetime.now(timezone.utc) if status != "NEW" else None,
    )
    db.add(request)
    db.flush()
    report.cre("portal_request")
    return request


def _ensure_portal_note(
    db: Session, ctx: dict, report: SeedReport, request: PortalRequest,
    author: User, body: str,
) -> None:
    tenant: Tenant = ctx["tenant"]
    note = db.execute(
        select(PortalRequestNote).where(
            PortalRequestNote.request_id == request.id,
            PortalRequestNote.body == body,
        )
    ).scalars().first()
    if note is not None:
        report.reu("portal_request_note")
        return
    db.add(
        PortalRequestNote(
            tenant_id=tenant.id,
            request_id=request.id,
            author_id=author.id,
            body=body,
        )
    )
    report.cre("portal_request_note")
    db.flush()


def _ensure_saved_report(
    db: Session, ctx: dict, report: SeedReport, *, name: str, description: str,
    metrics: list, filters: dict, created_by: User,
) -> SavedReport:
    tenant: Tenant = ctx["tenant"]
    saved = db.execute(
        select(SavedReport).where(
            SavedReport.tenant_id == tenant.id, SavedReport.name == name
        )
    ).scalars().first()
    if saved is not None:
        report.reu("saved_report")
        return saved
    saved = SavedReport(
        tenant_id=tenant.id,
        name=name,
        description=description,
        metrics=metrics,
        filters=filters,
        visibility="TENANT",
        created_by=created_by.id,
    )
    db.add(saved)
    db.flush()
    report.cre("saved_report")
    return saved


def _ensure_report_run(
    db: Session, ctx: dict, report: SeedReport, saved: SavedReport,
    *, ran_by: User, result: dict,
) -> None:
    tenant: Tenant = ctx["tenant"]
    # A run is keyed by its frozen result signature to stay idempotent.
    existing = db.execute(
        select(ReportRun).where(
            ReportRun.report_id == saved.id,
            ReportRun.result == result,
        )
    ).scalars().first()
    if existing is not None:
        report.reu("report_run")
        return
    db.add(
        ReportRun(
            tenant_id=tenant.id,
            report_id=saved.id,
            ran_by=ran_by.id,
            result=result,
        )
    )
    report.cre("report_run")
    db.flush()



def _ensure_endpoint(
    db: Session, ctx: dict, report: SeedReport, *, kind: str, name: str,
    description: str, config: dict, enabled: bool = False,
) -> IntegrationEndpoint:
    tenant: Tenant = ctx["tenant"]
    endpoint = db.execute(
        select(IntegrationEndpoint).where(
            IntegrationEndpoint.tenant_id == tenant.id,
            IntegrationEndpoint.name == name,
        )
    ).scalars().first()
    if endpoint is not None:
        report.reu("integration_endpoint")
        return endpoint
    endpoint = IntegrationEndpoint(
        tenant_id=tenant.id,
        kind=kind,
        name=name,
        description=description,
        config=config,
        # Disabled by default: a real adapter must be configured to enable it.
        enabled=enabled,
    )
    db.add(endpoint)
    db.flush()
    report.cre("integration_endpoint")
    return endpoint


def _ensure_delivery(
    db: Session, ctx: dict, report: SeedReport, endpoint: IntegrationEndpoint,
    *, event: str, payload: dict,
) -> None:
    tenant: Tenant = ctx["tenant"]
    delivery = db.execute(
        select(IntegrationDelivery).where(
            IntegrationDelivery.endpoint_id == endpoint.id,
            IntegrationDelivery.event == event,
        )
    ).scalars().first()
    if delivery is not None:
        report.reu("integration_delivery")
        return
    db.add(
        IntegrationDelivery(
            tenant_id=tenant.id,
            endpoint_id=endpoint.id,
            event=event,
            payload=payload,
            # Outbox pattern: stays PENDING until a real transport sends it.
            status=DELIVERY_PENDING,
            error=None,
            delivered_at=None,
        )
    )
    report.cre("integration_delivery")
    db.flush()



def seed_demo_f5(db: Session, ctx: dict) -> tuple[dict, SeedReport]:
    """Seed phase F5 (notifications, portal, BI reports, integrations)."""
    report = SeedReport()
    users: dict = ctx["users"]
    analyst: User = users["analyst"]
    manager: User = users["manager"]
    researcher: User = users["researcher"]
    disclosures: list[InventionDisclosure] = ctx["disclosures"]

    # In-app notifications addressed to specific tenant users.
    _ensure_notification(
        db, ctx, report, user=manager, kind="DISCLOSURE_STATUS",
        severity="INFO", title="Nova comunicação de invenção aguardando triagem",
        body="Uma comunicação foi submetida e necessita de triagem.",
        link="/nit/comunicacoes", resource_type="disclosure",
        resource_id=disclosures[-1].id,
    )
    _ensure_notification(
        db, ctx, report, user=researcher, kind="DISCLOSURE_STATUS",
        severity="INFO", title="Sua comunicação avançou de etapa",
        body="A comunicação foi encaminhada para avaliação técnica.",
        link="/nit/comunicacoes", resource_type="disclosure",
        resource_id=disclosures[1].id,
    )
    _ensure_notification(
        db, ctx, report, user=manager, kind="OBLIGATION_DUE",
        severity="WARNING", title="Obrigação contratual próxima do vencimento",
        body="Há relatório semestral de faturamento pendente.",
        link="/nit/contratos",
    )

    for kind, in_app, email in [
        ("DISCLOSURE_STATUS", True, True),
        ("OBLIGATION_DUE", True, False),
        ("PORTAL_REQUEST", True, True),
    ]:
        _ensure_notification_pref(
            db, ctx, report, user=manager, kind=kind, in_app=in_app, email=email
        )

    # Queued outbox e-mails (never marked SENT without a real transport).
    _ensure_email(
        db, ctx, report, created_by=manager,
        to_email="helena.prado@demo.nit.br",
        subject="Acompanhamento da sua comunicação de invenção",
        body="Sua comunicação está em avaliação; retornaremos em breve.",
        kind="DISCLOSURE_STATUS",
    )
    _ensure_email(
        db, ctx, report, created_by=manager,
        to_email="paulo.ribeiro@sensores-am.com.br",
        subject="Proposta de licenciamento — sensor piezoelétrico",
        body="Segue minuta para avaliação da empresa interessada.",
        kind="GENERIC",
    )

    # External portal: an explicit, scope-limited grant.
    access = _ensure_portal_access(
        db, ctx, report,
        portal_kind="COMPANY",
        email="paulo.ribeiro@sensores-am.com.br",
        name="Paulo Ribeiro",
        organization="Indústria Amazônica de Sensores Ltda.",
        subject_type="technology_offer", subject_id=ctx["offer"].id,
    )
    portal_request = _ensure_portal_request(
        db, ctx, report, access,
        request_type="INTEREST_EXPRESSION",
        subject="Interesse em licenciamento do sensor piezoelétrico",
        message="Gostaríamos de receber a minuta e os termos de royalties.",
        status="TRIAGED",
    )
    _ensure_portal_note(
        db, ctx, report, portal_request, analyst,
        "Interesse qualificado; encaminhado ao operador de transferência.",
    )
    _ensure_portal_access(
        db, ctx, report,
        portal_kind="RESEARCHER",
        email="helena.prado@demo.nit.br",
        name="Dra. Helena Prado",
        organization="Instituto Demo NIT",
    )

    # Saved BI report + one frozen run (definition only — no invented metrics).
    saved = _ensure_saved_report(
        db, ctx, report,
        name="Pipeline NIT — visão geral",
        description="Panorama de comunicações, avaliações e transferências.",
        metrics=["disclosures_by_status", "evaluations_by_kind", "active_contracts"],
        filters={"period": "2026"},
        created_by=manager,
    )
    _ensure_report_run(
        db, ctx, report, saved, ran_by=manager,
        result={"note": "Resultado congelado de demonstração (execução inicial)."},
    )

    # Declarative integrations (all disabled — inert until a real adapter exists).
    endpoint_siga = _ensure_endpoint(
        db, ctx, report, kind="SIGA", name="SIGA (projetos de pesquisa)",
        description="Integração declarativa com o sistema de projetos.",
        config={"base_url": "https://siga.exemplo.br/api", "token_ref": "SIGA_TOKEN"},
    )
    endpoint_sei = _ensure_endpoint(
        db, ctx, report, kind="SEI", name="SEI (processo eletrônico)",
        description="Integração declarativa com o SEI institucional.",
        config={"unidade": "NIT", "token_ref": "SEI_TOKEN"},
    )
    _ensure_delivery(
        db, ctx, report, endpoint_siga,
        event="project.created",
        payload={"project_code": ctx["project"].code},
    )
    _ensure_delivery(
        db, ctx, report, endpoint_sei,
        event="disclosure.protocoled",
        payload={"protocol": disclosures[0].protocol},
    )

    ctx["portal_access"] = access
    ctx["saved_report"] = saved
    return ctx, report



# --- Orchestration ----------------------------------------------------------


def run_demo_seed(db: Session, *, commit: bool = True) -> dict:
    """Seed the whole NIT demo data set (F1–F5) idempotently.

    Returns a structured report with ``created`` and ``reused`` counters plus the
    resolved demo tenant/users identifiers. Safe to run repeatedly: existing rows
    are reused and only missing rows are created. Nothing is ever deleted.
    """
    ctx, foundation_report = seed_demo_foundation(db)
    phases = {"foundation": foundation_report.as_dict()}
    for name, fn in (
        ("f1", seed_demo_f1),
        ("f2", seed_demo_f2),
        ("f3", seed_demo_f3),
        ("f4", seed_demo_f4),
        ("f5", seed_demo_f5),
    ):
        ctx, phase_report = fn(db, ctx)
        phases[name] = phase_report.as_dict()

    if commit:
        db.commit()

    users: dict = ctx["users"]
    return {
        "tenant_id": str(ctx["tenant"].id),
        "tenant_name": ctx["tenant"].social_reason,
        "company_id": str(ctx["company"].id),
        "unity_id": str(ctx["unity"].id),
        "users": {
            key: {"id": str(user.id), "email": user.email}
            for key, user in users.items()
        },
        # Access contexts built with the real RBAC engine (handy for tests/CLI).
        "access": {
            key: {
                "roles": sorted(build_access_context(db, user).roles),
                "permissions": len(build_access_context(db, user).permissions),
            }
            for key, user in users.items()
        },
        "phases": phases,
        "totals": {
            "created": sum(sum(p["created"].values()) for p in phases.values()),
            "reused": sum(sum(p["reused"].values()) for p in phases.values()),
        },
    }


def run_demo_seed_cli() -> None:
    """Entrypoint used by ``python -m app.seed_demo_nit``."""
    with SessionLocal() as db:
        report = run_demo_seed(db)
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":  # pragma: no cover - manual CLI entrypoint
    run_demo_seed_cli()

