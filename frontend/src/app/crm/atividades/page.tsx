"use client";

/**
 * CRM — Atividades e follow-ups (``/crm/atividades``).
 *
 * The commercial timeline: calls, meetings, e-mails and tasks, each one linked
 * to an opportunity, a proposal, a client or a company. Completing a follow-up
 * stamps ``completed_at`` on the backend.
 *
 * Recorded limitation: no automatic e-mail/WhatsApp integration exists, so the
 * screen only *records* the interactions the operator performed.
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
  useCreateCrmActivity,
  useCrmActivities,
  useDeleteCrmActivity,
  useOpportunities,
  useProposals,
  useUpdateCrmActivity,
} from "@/lib/hooks";
import {
  ACTIVITY_KINDS,
  ACTIVITY_KIND_LABELS,
  ACTIVITY_OUTCOME_LABELS,
  type ActivityKind,
  type CrmActivity,
} from "@/lib/types";

type SubjectKind = "OPPORTUNITY" | "PROPOSAL";

type Form = {
  kind: ActivityKind;
  subject_type: SubjectKind;
  subject_id: string;
  title: string;
  notes: string;
  due_at: string;
};

const EMPTY_FORM: Form = {
  kind: "CALL",
  subject_type: "OPPORTUNITY",
  subject_id: "",
  title: "",
  notes: "",
  due_at: "",
};

export default function AtividadesPage() {
  const [pendingOnly, setPendingOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState<Form>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading, error: qError } = useCrmActivities({
    pending_only: pendingOnly || undefined,
    page,
    page_size: 20,
  });
  const opportunities = useOpportunities({ page_size: 100 });
  const proposals = useProposals({ page: 1, page_size: 100 });
  const create = useCreateCrmActivity();
  const update = useUpdateCrmActivity();
  const remove = useDeleteCrmActivity();

  async function submit() {
    setError(null);
    if (!form.subject_id) {
      setError("Selecione a oportunidade ou a proposta relacionada.");
      return;
    }
    if (!form.title.trim()) {
      setError("Informe o título da atividade.");
      return;
    }
    try {
      await create.mutateAsync({
        kind: form.kind,
        subject_type: form.subject_type,
        subject_id: form.subject_id,
        title: form.title,
        notes: form.notes || null,
        due_at: form.due_at ? new Date(form.due_at).toISOString() : null,
      });
      setModal(false);
      setForm(EMPTY_FORM);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar.");
    }
  }

  async function complete(activity: CrmActivity, outcome: string) {
    try {
      await update.mutateAsync({ id: activity.id, outcome });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao atualizar.");
    }
  }

  return (
    <AppShell>
      <PageHeader
        breadcrumb="CRM"
        title="Atividades e follow-ups"
        description="Registre ligações, reuniões, e-mails e tarefas vinculadas às suas oportunidades e propostas."
        actions={<Button onClick={() => setModal(true)}>+ Nova atividade</Button>}
      />

      <Card className="mb-4">
        <div className="flex flex-wrap items-center gap-3 px-5 py-4">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={pendingOnly}
              onChange={(e) => {
                setPendingOnly(e.target.checked);
                setPage(1);
              }}
              className="h-4 w-4 rounded border-gray-300"
            />
            Somente pendentes
          </label>
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
                <Th>Tipo</Th>
                <Th>Atividade</Th>
                <Th>Vínculo</Th>
                <Th>Situação</Th>
                <Th>Vencimento</Th>
                <Th>Ações</Th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((a) => (
                <tr key={a.id} className="border-b border-gray-50 hover:bg-slate-50">
                  <Td>
                    <Badge tone="slate">{ACTIVITY_KIND_LABELS[a.kind]}</Badge>
                  </Td>
                  <Td>
                    <p className="font-medium text-slate-700">{a.title}</p>
                    {a.notes && (
                      <p className="max-w-md truncate text-xs text-slate-400">
                        {a.notes}
                      </p>
                    )}
                  </Td>
                  <Td className="text-xs text-slate-500">
                    {a.subject_type === "OPPORTUNITY"
                      ? "Oportunidade"
                      : a.subject_type === "PROPOSAL"
                        ? "Proposta"
                        : a.subject_type === "CUSTOMER"
                          ? "Cliente"
                          : "Empresa"}
                  </Td>
                  <Td>
                    <Badge tone={statusTone(a.outcome)}>
                      {ACTIVITY_OUTCOME_LABELS[a.outcome]}
                    </Badge>
                  </Td>
                  <Td className="text-xs text-slate-500">
                    {a.due_at
                      ? new Date(a.due_at).toLocaleDateString("pt-BR")
                      : "—"}
                  </Td>
                  <Td>
                    <div className="flex flex-wrap items-center gap-2">
                      {a.outcome === "PENDING" && (
                        <>
                          <button
                            className="text-xs font-medium text-emerald-600 hover:underline"
                            onClick={() => complete(a, "DONE")}
                          >
                            Concluir
                          </button>
                          <button
                            className="text-xs font-medium text-slate-500 hover:underline"
                            onClick={() => complete(a, "NO_ANSWER")}
                          >
                            Sem resposta
                          </button>
                        </>
                      )}
                      <button
                        className="text-xs font-medium text-slate-400 hover:underline"
                        onClick={() => {
                          if (
                            typeof window !== "undefined" &&
                            window.confirm("Remover esta atividade?")
                          ) {
                            remove.mutate(a.id);
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
                  colSpan={6}
                  message="Nenhuma atividade registrada. Crie o primeiro follow-up comercial."
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
        title="Nova atividade"
        footer={
          <>
            <Button variant="secondary" onClick={() => setModal(false)}>
              Cancelar
            </Button>
            <Button onClick={submit} disabled={create.isPending}>
              {create.isPending ? "Salvando…" : "Salvar"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <Select
            label="Tipo"
            value={form.kind}
            onChange={(e) =>
              setForm({ ...form, kind: e.target.value as ActivityKind })
            }
          >
            {ACTIVITY_KINDS.map((k) => (
              <option key={k} value={k}>
                {ACTIVITY_KIND_LABELS[k]}
              </option>
            ))}
          </Select>
          <Select
            label="Vincular a"
            value={form.subject_type}
            onChange={(e) =>
              setForm({
                ...form,
                subject_type: e.target.value as SubjectKind,
                subject_id: "",
              })
            }
          >
            <option value="OPPORTUNITY">Oportunidade</option>
            <option value="PROPOSAL">Proposta</option>
          </Select>
          <Select
            label="Registro *"
            value={form.subject_id}
            onChange={(e) => setForm({ ...form, subject_id: e.target.value })}
          >
            <option value="">Selecione…</option>
            {form.subject_type === "OPPORTUNITY"
              ? (opportunities.data?.items ?? []).map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.code} — {o.title}
                  </option>
                ))
              : (proposals.data?.items ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.code} — {p.title}
                  </option>
                ))}
          </Select>
          <Input
            label="Título *"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="Ex.: Ligar para apresentar a proposta"
          />
          <Input
            label="Vencimento / data de acompanhamento"
            type="date"
            value={form.due_at}
            onChange={(e) => setForm({ ...form, due_at: e.target.value })}
          />
          <Textarea
            label="Anotações"
            rows={3}
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
          />
          {error && <ErrorNote>{error}</ErrorNote>}
        </div>
      </Modal>
    </AppShell>
  );
}

