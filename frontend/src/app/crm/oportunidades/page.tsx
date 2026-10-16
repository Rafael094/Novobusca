"use client";

/**
 * CRM — Leads e oportunidades (``/crm/oportunidades``).
 *
 * Table view of the funnel with search, stage filter and the lifecycle actions
 * that matter day to day: move stage, mark as lost (with a reason) and convert a
 * won opportunity into a client without duplicating it.
 */

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

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
  useChangeOpportunityStage,
  useConvertOpportunity,
  useCreateOpportunity,
  useDeleteOpportunity,
  useOpportunities,
} from "@/lib/hooks";
import {
  OPPORTUNITY_STAGE_LABELS,
  type Opportunity,
  type OpportunityStage,
} from "@/lib/types";

const STAGES: OpportunityStage[] = [
  "NEW",
  "QUALIFICATION",
  "PROPOSAL",
  "SENT",
  "NEGOTIATION",
  "WON",
  "LOST",
];

type Form = {
  title: string;
  lead_name: string;
  service_interest: string;
  estimated_value: string;
  next_action: string;
  stage: OpportunityStage;
};

const EMPTY_FORM: Form = {
  title: "",
  lead_name: "",
  service_interest: "",
  estimated_value: "",
  next_action: "",
  stage: "NEW",
};

export default function OportunidadesPage() {
  // ``useSearchParams`` requires a Suspense boundary during prerendering.
  return (
    <Suspense fallback={<AppShell><Spinner /></AppShell>}>
      <OportunidadesContent />
    </Suspense>
  );
}

function OportunidadesContent() {
  const params = useSearchParams();
  const [q, setQ] = useState("");
  const [stage, setStage] = useState(params.get("stage") ?? "");
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState(false);
  const [converting, setConverting] = useState<Opportunity | null>(null);
  const [losing, setLosing] = useState<Opportunity | null>(null);
  const [lostReason, setLostReason] = useState("");
  const [form, setForm] = useState<Form>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading, error: qError } = useOpportunities({
    q: q || undefined,
    stage: stage || undefined,
    page,
    page_size: 20,
  });
  const create = useCreateOpportunity();
  const changeStage = useChangeOpportunityStage();
  const convert = useConvertOpportunity();
  const remove = useDeleteOpportunity();

  async function submitCreate() {
    setError(null);
    if (!form.title.trim()) {
      setError("Informe o título da oportunidade.");
      return;
    }
    try {
      await create.mutateAsync({
        title: form.title,
        lead_name: form.lead_name || null,
        service_interest: form.service_interest || null,
        estimated_value: form.estimated_value || null,
        next_action: form.next_action || null,
        stage: form.stage,
      });
      setModal(false);
      setForm(EMPTY_FORM);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar.");
    }
  }

  async function submitLost() {
    if (!losing) return;
    setError(null);
    try {
      await changeStage.mutateAsync({
        id: losing.id,
        stage: "LOST",
        lost_reason: lostReason,
      });
      setLosing(null);
      setLostReason("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao registrar perda.");
    }
  }

  async function submitConvert(opp: Opportunity) {
    setError(null);
    try {
      await convert.mutateAsync({ id: opp.id, name: opp.lead_name || opp.title });
      setConverting(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao converter.");
    }
  }

  return (
    <AppShell>
      <PageHeader
        breadcrumb="CRM"
        title="Leads e oportunidades"
        description="Acompanhe o funil comercial: qualifique o lead, prepare a proposta e converta o negócio em cliente."
        actions={
          <Button onClick={() => setModal(true)}>+ Nova oportunidade</Button>
        }
      />

      <Card className="mb-4">
        <div className="flex flex-wrap items-center gap-3 px-5 py-4">
          <Input
            placeholder="Buscar por título, lead ou código…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
            className="max-w-xs"
          />
          <Select
            value={stage}
            onChange={(e) => {
              setStage(e.target.value);
              setPage(1);
            }}
            className="max-w-[220px]"
            aria-label="Etapa"
          >
            <option value="">Todas as etapas</option>
            {STAGES.map((s) => (
              <option key={s} value={s}>
                {OPPORTUNITY_STAGE_LABELS[s]}
              </option>
            ))}
          </Select>
          {stage && (
            <Button variant="ghost" onClick={() => setStage("")}>
              Limpar filtro
            </Button>
          )}
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
                <Th>Oportunidade</Th>
                <Th>Contato / cliente</Th>
                <Th>Etapa</Th>
                <Th>Valor estimado</Th>
                <Th>Próxima ação</Th>
                <Th>Ações</Th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((o) => (
                <tr key={o.id} className="border-b border-gray-50 hover:bg-slate-50">
                  <Td className="font-mono text-xs text-slate-500">{o.code}</Td>
                  <Td>
                    <p className="font-medium text-slate-700">{o.title}</p>
                    <p className="text-xs text-slate-400">
                      {o.proposal_count} proposta(s)
                      {o.owner_name ? ` · ${o.owner_name}` : ""}
                    </p>
                  </Td>
                  <Td>{o.customer_name || o.lead_name || o.contact_name || "—"}</Td>
                  <Td>
                    <Badge tone={statusTone(o.stage)}>
                      {OPPORTUNITY_STAGE_LABELS[o.stage]}
                    </Badge>
                  </Td>
                  <Td>
                    {o.estimated_value
                      ? Number(o.estimated_value).toLocaleString("pt-BR", {
                          style: "currency",
                          currency: "BRL",
                        })
                      : "—"}
                  </Td>
                  <Td>
                    <span className="text-xs text-slate-500">
                      {o.next_action || "—"}
                    </span>
                  </Td>
                  <Td>
                    <div className="flex flex-wrap items-center gap-2">
                      {o.stage !== "WON" && o.stage !== "LOST" && (
                        <>
                          <button
                            className="text-xs font-medium text-brand-600 hover:underline"
                            onClick={() => setConverting(o)}
                          >
                            Converter
                          </button>
                          <button
                            className="text-xs font-medium text-slate-500 hover:underline"
                            onClick={() => setLosing(o)}
                          >
                            Perder
                          </button>
                        </>
                      )}
                      <button
                        className="text-xs font-medium text-slate-400 hover:underline"
                        onClick={() => {
                          if (
                            typeof window !== "undefined" &&
                            window.confirm(
                              "Desativar esta oportunidade? O histórico é preservado.",
                            )
                          ) {
                            remove.mutate(o.id);
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
                  message="Nenhuma oportunidade encontrada. Cadastre o primeiro lead para começar."
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
        title="Nova oportunidade"
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
            placeholder="Ex.: Registro de marca da nova linha de produtos"
          />
          <Input
            label="Lead / empresa"
            value={form.lead_name}
            onChange={(e) => setForm({ ...form, lead_name: e.target.value })}
            placeholder="Nome do contato ou da organização"
          />
          <Input
            label="Serviço de interesse"
            value={form.service_interest}
            onChange={(e) =>
              setForm({ ...form, service_interest: e.target.value })
            }
            placeholder="Ex.: Registro de marca, patente, contratos"
          />
          <Input
            label="Valor estimado (R$)"
            inputMode="decimal"
            value={form.estimated_value}
            onChange={(e) =>
              setForm({ ...form, estimated_value: e.target.value })
            }
          />
          <Input
            label="Próxima ação"
            value={form.next_action}
            onChange={(e) => setForm({ ...form, next_action: e.target.value })}
            placeholder="Ex.: Enviar proposta até sexta"
          />
          <Select
            label="Etapa inicial"
            value={form.stage}
            onChange={(e) =>
              setForm({ ...form, stage: e.target.value as OpportunityStage })
            }
          >
            {STAGES.map((s) => (
              <option key={s} value={s}>
                {OPPORTUNITY_STAGE_LABELS[s]}
              </option>
            ))}
          </Select>
          {error && <ErrorNote>{error}</ErrorNote>}
        </div>
      </Modal>

      <Modal
        open={!!converting}
        onClose={() => setConverting(null)}
        title="Converter em cliente"
        footer={
          <>
            <Button variant="secondary" onClick={() => setConverting(null)}>
              Cancelar
            </Button>
            <Button
              onClick={() => converting && submitConvert(converting)}
              disabled={convert.isPending}
            >
              {convert.isPending ? "Convertendo…" : "Converter"}
            </Button>
          </>
        }
      >
        <p className="text-sm text-slate-600">
          A conversão cria ou reaproveita um cliente do tenant (sem duplicar) e
          vincula as propostas desta oportunidade. A aprovação comercial{" "}
          <strong>não</strong> registra marcas nem patentes — isso continua sendo
          feito nos módulos do INPI/NIT.
        </p>
        {converting && (
          <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
            Cliente a vincular:{" "}
            <strong>{converting.lead_name || converting.title}</strong>
          </p>
        )}
        {error && <ErrorNote>{error}</ErrorNote>}
      </Modal>

      <Modal
        open={!!losing}
        onClose={() => setLosing(null)}
        title="Registrar perda"
        footer={
          <>
            <Button variant="secondary" onClick={() => setLosing(null)}>
              Cancelar
            </Button>
            <Button
              variant="danger"
              onClick={submitLost}
              disabled={changeStage.isPending || !lostReason.trim()}
            >
              {changeStage.isPending ? "Salvando…" : "Marcar como perdida"}
            </Button>
          </>
        }
      >
        <Textarea
          label="Motivo da perda *"
          rows={3}
          value={lostReason}
          onChange={(e) => setLostReason(e.target.value)}
          placeholder="Ex.: Sem orçamento no período"
        />
        {error && <ErrorNote>{error}</ErrorNote>}
      </Modal>
    </AppShell>
  );
}

