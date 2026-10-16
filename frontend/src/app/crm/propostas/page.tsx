"use client";

/**
 * CRM — Propostas comerciais (``/crm/propostas``).
 *
 * The full proposal lifecycle: create, register the actual send, register the
 * return, move to negotiation, approve/reject and cancel. Dates are stamped by
 * the backend (``sent_at`` / ``replied_at`` / ``decision_at``), never simulated
 * in the browser.
 *
 * Recorded limitation: PDF generation, e-mail delivery, e-signature and billing
 * are NOT implemented — the UI says so instead of faking the action.
 */

import { useState } from "react";

import AppShell from "@/components/AppShell";
import PageHeader from "@/components/PageHeader";
import {
  Badge,
  Button,
  Card,
  EmptyRow,
  ErrorNote,
  Input,
  Modal,
  Pagination,
  Select,
  Spinner,
  Table,
  Td,
  Textarea,
  Th,
  statusTone,
} from "@/components/ui";
import {
  useChangeProposalStatus,
  useCreateProposal,
  useCustomers,
  useDeleteProposal,
  useOpportunities,
  useProposals,
} from "@/lib/hooks";
import {
  PROPOSAL_STATUS_LABELS,
  type Proposal,
  type ProposalStatus,
} from "@/lib/types";

const STATUSES: ProposalStatus[] = [
  "DRAFT",
  "PENDING_SEND",
  "SENT",
  "AWAITING_REPLY",
  "NEGOTIATION",
  "APPROVED",
  "REJECTED",
  "EXPIRED",
  "CANCELLED",
];

type Form = {
  title: string;
  description: string;
  services: string;
  total_value: string;
  valid_until: string;
  opportunity_id: string;
  customer_id: string;
};

const EMPTY_FORM: Form = {
  title: "",
  description: "",
  services: "",
  total_value: "",
  valid_until: "",
  opportunity_id: "",
  customer_id: "",
};

function currency(value: string | null): string {
  if (!value) return "—";
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "—";
  return numeric.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function PropostasPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState<Form>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [decision, setDecision] = useState<{
    proposal: Proposal;
    status: ProposalStatus;
  } | null>(null);
  const [decisionNotes, setDecisionNotes] = useState("");

  const { data, isLoading, error: qError } = useProposals({
    q: q || undefined,
    status: status || undefined,
    page,
    page_size: 20,
  });
  const opportunities = useOpportunities({ page_size: 100 });
  const customers = useCustomers({ page: 1, page_size: 100 });
  const create = useCreateProposal();
  const changeStatus = useChangeProposalStatus();
  const remove = useDeleteProposal();

  async function submitCreate() {
    setError(null);
    if (!form.title.trim()) {
      setError("Informe o título da proposta.");
      return;
    }
    try {
      await create.mutateAsync({
        title: form.title,
        description: form.description || null,
        services: form.services || null,
        total_value: form.total_value || null,
        valid_until: form.valid_until || null,
        opportunity_id: form.opportunity_id || null,
        customer_id: form.customer_id || null,
      });
      setModal(false);
      setForm(EMPTY_FORM);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar.");
    }
  }

  async function move(proposal: Proposal, next: ProposalStatus, opts?: {
    mark_sent?: boolean;
    mark_reply?: boolean;
    decision_notes?: string;
  }) {
    setError(null);
    try {
      await changeStatus.mutateAsync({ id: proposal.id, status: next, ...opts });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao atualizar status.");
    }
  }

  return (
    <AppShell>
      <PageHeader
        breadcrumb="CRM"
        title="Propostas comerciais"
        description="Prepare, envie e acompanhe as propostas do tenant. A aprovação comercial é registrada aqui; o registro de marcas e patentes acontece nos módulos próprios."
        actions={<Button onClick={() => setModal(true)}>+ Nova proposta</Button>}
      />

      <div className="mb-4 rounded-lg bg-amber-50 px-4 py-3 text-xs text-amber-800">
        Geração de PDF, envio por e-mail, assinatura eletrônica e cobrança ainda
        não estão implementados. Registre abaixo o envio e o retorno reais da
        proposta.
      </div>

      <Card className="mb-4">
        <div className="flex flex-wrap items-center gap-3 px-5 py-4">
          <Input
            placeholder="Buscar por título ou código…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
            className="max-w-xs"
          />
          <Select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
            className="max-w-[220px]"
            aria-label="Status"
          >
            <option value="">Todos os status</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {PROPOSAL_STATUS_LABELS[s]}
              </option>
            ))}
          </Select>
        </div>
      </Card>

      {isLoading && <Spinner />}
      {qError && (
        <ErrorNote>
          {qError instanceof Error ? qError.message : "Erro ao carregar."}
        </ErrorNote>
      )}
      {error && <ErrorNote>{error}</ErrorNote>}

      {data && (
        <Card>
          <Table>
            <thead className="border-b border-gray-100 bg-slate-50/60">
              <tr>
                <Th>Código</Th>
                <Th>Proposta</Th>
                <Th>Cliente / oportunidade</Th>
                <Th>Status</Th>
                <Th>Valor</Th>
                <Th>Validade</Th>
                <Th>Ações</Th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((p) => (
                <tr key={p.id} className="border-b border-gray-50 hover:bg-slate-50">
                  <Td className="font-mono text-xs text-slate-500">{p.code}</Td>
                  <Td>
                    <p className="font-medium text-slate-700">{p.title}</p>
                    {p.owner_name && (
                      <p className="text-xs text-slate-400">{p.owner_name}</p>
                    )}
                  </Td>
                  <Td>
                    <p>{p.customer_name || "—"}</p>
                    {p.opportunity_title && (
                      <p className="text-xs text-slate-400">
                        {p.opportunity_title}
                      </p>
                    )}
                  </Td>
                  <Td>
                    <div className="flex flex-col gap-1">
                      <Badge tone={statusTone(p.status)}>
                        {PROPOSAL_STATUS_LABELS[p.status]}
                      </Badge>
                      {p.is_overdue && <Badge tone="red">Vencida</Badge>}
                    </div>
                  </Td>
                  <Td>{currency(p.total_value)}</Td>
                  <Td>
                    <span className="text-xs text-slate-500">
                      {p.valid_until
                        ? new Date(p.valid_until).toLocaleDateString("pt-BR")
                        : "—"}
                    </span>
                  </Td>
                  <Td>
                    <div className="flex flex-wrap items-center gap-2">
                      {(p.status === "DRAFT" || p.status === "PENDING_SEND") && (
                        <button
                          className="text-xs font-medium text-brand-600 hover:underline"
                          onClick={() => move(p, "SENT", { mark_sent: true })}
                        >
                          Registrar envio
                        </button>
                      )}
                      {(p.status === "SENT" || p.status === "NEGOTIATION") && (
                        <>
                          <button
                            className="text-xs font-medium text-brand-600 hover:underline"
                            onClick={() =>
                              move(p, "AWAITING_REPLY", { mark_reply: true })
                            }
                          >
                            Registrar retorno
                          </button>
                          <button
                            className="text-xs font-medium text-slate-500 hover:underline"
                            onClick={() => move(p, "NEGOTIATION")}
                          >
                            Negociar
                          </button>
                        </>
                      )}
                      {p.status !== "APPROVED" &&
                        p.status !== "CANCELLED" &&
                        p.status !== "REJECTED" && (
                          <button
                            className="text-xs font-medium text-emerald-600 hover:underline"
                            onClick={() => {
                              setDecision({ proposal: p, status: "APPROVED" });
                              setDecisionNotes("");
                            }}
                          >
                            Aprovar
                          </button>
                        )}
                      {p.status !== "CANCELLED" && p.status !== "APPROVED" && (
                        <button
                          className="text-xs font-medium text-red-600 hover:underline"
                          onClick={() => {
                            setDecision({ proposal: p, status: "REJECTED" });
                            setDecisionNotes("");
                          }}
                        >
                          Recusar
                        </button>
                      )}
                      <button
                        className="text-xs font-medium text-slate-400 hover:underline"
                        onClick={() => {
                          if (
                            typeof window !== "undefined" &&
                            window.confirm("Desativar esta proposta?")
                          ) {
                            remove.mutate(p.id);
                          }
                        }}
                      >
                        Excluir
                      </button>
                    </div>
                  </Td>
                </tr>
              ))}
              {data.items.length === 0 && (
                <EmptyRow
                  colSpan={7}
                  message="Nenhuma proposta encontrada. Crie a primeira proposta comercial."
                />
              )}
            </tbody>
          </Table>
          <Pagination
            page={page}
            pageSize={20}
            total={data.pagination.total}
            onPage={setPage}
          />
        </Card>
      )}



      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title="Nova proposta"
        footer={
          <>
            <Button variant="secondary" onClick={() => setModal(false)}>
              Cancelar
            </Button>
            <Button onClick={submitCreate} disabled={create.isPending}>
              {create.isPending ? "Salvando…" : "Salvar"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <Input
            label="Título *"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="Ex.: Proposta de registro de marca"
          />
          <Select
            label="Oportunidade vinculada"
            value={form.opportunity_id}
            onChange={(e) =>
              setForm({ ...form, opportunity_id: e.target.value })
            }
          >
            <option value="">Sem vínculo</option>
            {(opportunities.data?.items ?? []).map((o) => (
              <option key={o.id} value={o.id}>
                {o.code} — {o.title}
              </option>
            ))}
          </Select>
          <Select
            label="Cliente vinculado"
            value={form.customer_id}
            onChange={(e) => setForm({ ...form, customer_id: e.target.value })}
          >
            <option value="">Sem vínculo</option>
            {(customers.data?.items ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
          <Input
            label="Valor total (R$)"
            inputMode="decimal"
            value={form.total_value}
            onChange={(e) => setForm({ ...form, total_value: e.target.value })}
          />
          <Input
            label="Válida até"
            type="date"
            value={form.valid_until}
            onChange={(e) => setForm({ ...form, valid_until: e.target.value })}
          />
          <Textarea
            label="Serviços oferecidos"
            rows={3}
            value={form.services}
            onChange={(e) => setForm({ ...form, services: e.target.value })}
            placeholder="Um serviço por linha"
          />
          <Textarea
            label="Descrição"
            rows={3}
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          {error && <ErrorNote>{error}</ErrorNote>}
        </div>
      </Modal>

      <Modal
        open={!!decision}
        onClose={() => setDecision(null)}
        title={
          decision?.status === "APPROVED"
            ? "Aprovar proposta"
            : "Recusar proposta"
        }
        footer={
          <>
            <Button variant="secondary" onClick={() => setDecision(null)}>
              Cancelar
            </Button>
            <Button
              variant={decision?.status === "APPROVED" ? "primary" : "danger"}
              disabled={changeStatus.isPending}
              onClick={async () => {
                if (!decision) return;
                await move(decision.proposal, decision.status, {
                  decision_notes: decisionNotes || undefined,
                });
                setDecision(null);
              }}
            >
              {changeStatus.isPending ? "Salvando…" : "Confirmar"}
            </Button>
          </>
        }
      >
        <p className="text-sm text-slate-600">
          {decision?.status === "APPROVED"
            ? "A aprovação registra a decisão comercial. Ela não cria marcas nem patentes e não executa serviços — se o cliente ainda não existir, converta a oportunidade antes."
            : "A recusa encerra a proposta mantendo todo o histórico do relacionamento."}
        </p>
        <Textarea
          className="mt-3"
          label="Observações da decisão"
          rows={3}
          value={decisionNotes}
          onChange={(e) => setDecisionNotes(e.target.value)}
        />
        {error && <ErrorNote>{error}</ErrorNote>}
      </Modal>
    </AppShell>
  );
}

