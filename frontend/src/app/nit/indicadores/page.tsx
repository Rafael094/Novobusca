"use client";

import { useState } from "react";

import AppShell from "@/components/AppShell";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  ErrorNote,
  Input,
  Spinner,
} from "@/components/ui";
import { useAuth } from "@/app/auth-context";
import { useNitFormict, useNitIndicators } from "@/lib/hooks";
import { GroupCard, Item, MetricCard, fmtMoney } from "./IndicatorWidgets";

export default function IndicatorsPage() {
  const { has } = useAuth();
  const [days, setDays] = useState(30);
  const { data, isLoading, error } = useNitIndicators({ days });
  const { data: formict } = useNitFormict();

  const canExport = has("NIT_FORMICT_EXPORT");

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Indicadores & FORMICT</h1>
          <p className="text-sm text-slate-500">
            Indicadores derivados exclusivamente de consultas reais ao acervo do tenant.
          </p>
        </div>
        <div className="w-40">
          <Input
            label="Janela (dias)"
            type="number"
            value={days}
            onChange={(e) => setDays(Number(e.target.value) || 30)}
          />
        </div>
      </div>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}
      {isLoading ? <Spinner /> : null}

      {data ? (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard label="Comunicações" value={data.disclosure_total} />
            <MetricCard label="Avaliações pendentes" value={data.pending_evaluations} />
            <MetricCard label="Ativos" value={data.assets_total} />
            <MetricCard label="Ofertas publicadas" value={data.offers_published} />
            <MetricCard label="Negociações em curso" value={data.negotiations_in_progress} />
            <MetricCard label="Contratos vigentes" value={data.contracts_active} />
            <MetricCard label="Projetos ativos" value={data.projects_active} />
            <MetricCard label="Startups incubadas" value={data.startups_incubated} />
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <GroupCard title="Comunicações por situação" data={data.disclosures_by_status} />
            <GroupCard title="Comunicações por área" data={data.disclosures_by_area} />
            <GroupCard title="Ativos por estágio" data={data.assets_by_stage} />
          </div>

          <Card className="mt-6">
            <CardHeader
              title="Tempo médio de triagem"
              subtitle="Dias entre submissão e primeira triagem (registros encerrados)"
            />
            <CardBody>
              <p className="text-2xl font-semibold text-slate-800">
                {data.average_triage_days != null
                  ? `${data.average_triage_days.toFixed(1)} dias`
                  : "Sem dados suficientes"}
              </p>
            </CardBody>
          </Card>
        </>
      ) : null}

      {formict ? (
        <Card className="mt-6 border-amber-100">
          <CardHeader
            title="Relatório de apoio FORMICT"
            subtitle="Documento interno de apoio — não substitui o envio oficial"
            action={
              canExport ? (
                <Button
                  variant="secondary"
                  onClick={() => window.open("/api/nit/formict/export", "_blank")}
                >
                  Exportar CSV
                </Button>
              ) : undefined
            }
          />
          <CardBody>
            <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
              {formict.disclaimer}
            </div>
            <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
              <Item label="Contratos vigentes" value={String(formict.contracts_active)} />
              <Item label="Contratos totais" value={String(formict.contracts_total)} />
              <Item label="Valor registrado" value={fmtMoney(formict.total_registered)} />
              <Item label="Valor recebido" value={fmtMoney(formict.total_received)} />
              <Item
                label="Tecnologias ofertadas"
                value={String(formict.technologies_offered)}
              />
              <Item
                label="Transferências efetivas"
                value={String(formict.transfers_effective)}
              />
              <Item label="Projetos ativos" value={String(formict.projects_active)} />
              <Item label="Startups apoiadas" value={String(formict.startups_supported)} />
              <Item
                label="Gerado em"
                value={new Date(formict.generated_at).toLocaleString("pt-BR")}
              />
            </dl>
          </CardBody>
        </Card>
      ) : null}
    </AppShell>
  );
}
