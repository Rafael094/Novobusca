"use client";

import { useState } from "react";

import AppShell from "@/components/AppShell";
import { GaugeChart } from "@/components/charts";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  ErrorNote,
  Input,
  Spinner,
  Tabs,
  Toggle,
} from "@/components/ui";
import { useAnalysisStatus, useRunAnalysis } from "@/lib/hooks";
import type { AnalysisReport, RiskLevel } from "@/lib/types";

const RISK_META: Record<RiskLevel, { label: string; tone: "green" | "amber" | "red"; color: string }> = {
  baixo: { label: "Risco Baixo", tone: "green", color: "#10b981" },
  moderado: { label: "Risco Moderado", tone: "amber", color: "#f59e0b" },
  alto: { label: "Risco Alto", tone: "red", color: "#ef4444" },
  critico: { label: "Risco Crítico", tone: "red", color: "#dc2626" },
};

const NICE_CLASSES = [
  "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
  "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
  "21", "22", "23", "24", "25", "26", "27", "28", "29", "30",
  "31", "32", "33", "34", "35", "36", "37", "38", "39", "40",
  "41", "42", "43", "44", "45",
];

export default function AnalisesPage() {
  const [report, setReport] = useState<AnalysisReport | null>(null);

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">
          Análise de Marca com IA
        </h1>
        <p className="text-sm text-slate-500">
          Avaliação de risco de registro cruzada com a base do INPI.
        </p>
      </div>

      {report ? (
        <ReportView report={report} onReset={() => setReport(null)} />
      ) : (
        <Wizard onDone={setReport} />
      )}
    </AppShell>
  );
}

// --- Wizard -----------------------------------------------------------------
function Wizard({ onDone }: { onDone: (r: AnalysisReport) => void }) {
  const status = useAnalysisStatus();
  const run = useRunAnalysis();

  const [brandName, setBrandName] = useState("");
  const [classes, setClasses] = useState<string[]>([]);
  const [holder, setHolder] = useState("");
  const [presentation, setPresentation] = useState("");
  const [nature, setNature] = useState("");
  const [optPatentes, setOptPatentes] = useState(true);
  const [optFonetic, setOptFonetic] = useState(true);
  const [optVisual, setOptVisual] = useState(false);
  const [optStrictNice, setOptStrictNice] = useState(true);

  function toggleClass(c: string) {
    setClasses((prev) =>
      prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c],
    );
  }

  async function submit() {
    const result = await run.mutateAsync({
      brand_name: brandName,
      nice_classes: classes,
      holder: holder || undefined,
      presentation: presentation || undefined,
      nature: nature || undefined,
      options: {
        include_patentes: optPatentes,
        include_fonetic: optFonetic,
        include_visual: optVisual,
        strict_nice: optStrictNice,
      },
    });
    onDone(result);
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Card>
          <CardHeader title="Dados da marca" subtitle="Informe os dados do pedido" />
          <CardBody className="space-y-4">
            <Input
              label="Nome da marca *"
              value={brandName}
              onChange={(e) => setBrandName(e.target.value)}
              placeholder="Ex.: Zeta Labs"
            />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                label="Titular"
                value={holder}
                onChange={(e) => setHolder(e.target.value)}
                placeholder="Razão social / nome"
              />
              <Input
                label="Apresentação"
                value={presentation}
                onChange={(e) => setPresentation(e.target.value)}
                placeholder="Nominativa / Mista / Figurativa"
              />
            </div>
            <Input
              label="Natureza"
              value={nature}
              onChange={(e) => setNature(e.target.value)}
              placeholder="Produto / Serviço"
            />
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Classes NCL"
            subtitle="Selecione as classes de Nice aplicáveis"
            action={
              <Badge tone="blue">{classes.length} selecionada(s)</Badge>
            }
          />
          <CardBody>
            <div className="flex flex-wrap gap-2">
              {NICE_CLASSES.map((c) => {
                const selected = classes.includes(c);
                return (
                  <button
                    key={c}
                    type="button"
                    onClick={() => toggleClass(c)}
                    className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition ${
                      selected
                        ? "border-brand-600 bg-brand-600 text-white"
                        : "border-gray-200 bg-white text-slate-600 hover:border-brand-300"
                    }`}
                  >
                    {c}
                  </button>
                );
              })}
            </div>
          </CardBody>
        </Card>
      </div>

      <div className="space-y-6">
        <Card>
          <CardHeader title="Opções de análise" />
          <CardBody className="space-y-4">
            <Toggle checked={optFonetic} onChange={setOptFonetic} label="Similaridade fonética" />
            <Toggle checked={optVisual} onChange={setOptVisual} label="Similaridade visual" />
            <Toggle checked={optPatentes} onChange={setOptPatentes} label="Incluir patentes" />
            <Toggle
              checked={optStrictNice}
              onChange={setOptStrictNice}
              label="Restringir às classes NCL"
            />
          </CardBody>
        </Card>

        <Card>
          <CardBody className="space-y-3">
            {status.data && !status.data.configured && (
              <ErrorNote>
                Integração IA indisponível: {status.data.message}
              </ErrorNote>
            )}
            <Button
              className="w-full"
              onClick={submit}
              disabled={!brandName || run.isPending}
            >
              {run.isPending ? "Analisando…" : "Executar análise com IA"}
            </Button>
            {run.isError && (
              <ErrorNote>
                {run.error instanceof Error
                  ? run.error.message
                  : "Falha na análise."}
              </ErrorNote>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}


// --- Report -----------------------------------------------------------------
function ReportView({
  report,
  onReset,
}: {
  report: AnalysisReport;
  onReset: () => void;
}) {
  const [tab, setTab] = useState("resumo");
  const meta = RISK_META[report.overall_risk];

  function exportAs(format: "pdf" | "doc") {
    // Client-side export: build a printable document from the real report data.
    const w = window.open("", "_blank");
    if (!w) return;
    const rows = report.similar_brands
      .map(
        (b) =>
          `<tr><td>${b.nome ?? "—"}</td><td>${b.numero_inpi ?? "—"}</td><td>${
            b.similaridade
          }%</td></tr>`,
      )
      .join("");
    w.document.write(`
      <html><head><title>Relatório ${report.brand_name}</title>
      <meta charset="utf-8" />
      <style>body{font-family:sans-serif;padding:32px;color:#0f172a}
      h1{color:#2563eb}table{width:100%;border-collapse:collapse;margin-top:12px}
      td,th{border:1px solid #e2e8f0;padding:8px;text-align:left;font-size:13px}</style>
      </head><body>
      <h1>Relatório de Análise — ${report.brand_name}</h1>
      <p><b>Risco:</b> ${meta.label} (${report.score}/100)</p>
      <p><b>Titular:</b> ${report.holder ?? "—"}</p>
      <p><b>Classes NCL:</b> ${report.nice_classes.join(", ") || "—"}</p>
      <h3>Resumo</h3><p>${report.summary}</p>
      <h3>Marcas similares</h3>
      <table><tr><th>Marca</th><th>Nº INPI</th><th>Similaridade</th></tr>${rows}</table>
      <h3>Recomendações</h3><ul>${report.recommendations
        .map((r) => `<li>${r}</li>`)
        .join("")}</ul>
      </body></html>`);
    w.document.close();
    if (format === "pdf") w.print();
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Badge tone={meta.tone}>{meta.label}</Badge>
          <span className="text-sm text-slate-500">
            {new Date(report.created_at).toLocaleString("pt-BR")}
          </span>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => exportAs("pdf")}>
            Exportar PDF
          </Button>
          <Button variant="secondary" onClick={() => exportAs("doc")}>
            Exportar Word
          </Button>
          <Button onClick={onReset}>Nova análise</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardBody className="flex flex-col items-center gap-3">
            <GaugeChart value={report.score} label="score de risco" color={meta.color} />
            <p className="text-center text-sm text-slate-500">
              {report.conflicts.length} conflito(s) ·{" "}
              {report.similar_brands.length} marca(s) similar(es)
            </p>
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader
            title={`Marca: ${report.brand_name}`}
            subtitle={
              [report.holder, report.nice_classes.join(", ")]
                .filter(Boolean)
                .join(" · ") || undefined
            }
          />
          <CardBody>
            <p className="text-sm leading-relaxed text-slate-600">
              {report.summary}
            </p>
          </CardBody>
        </Card>
      </div>

      <Card>
        <Tabs
          active={tab}
          onChange={setTab}
          tabs={[
            { id: "resumo", label: "Resumo" },
            { id: "conflitos", label: `Conflitos (${report.conflicts.length})` },
            { id: "similares", label: `Marcas Similares (${report.similar_brands.length})` },
            { id: "patentes", label: `Patentes (${report.related_patents.length})` },
            { id: "recomendacoes", label: "Recomendações" },
          ]}
        />
        <CardBody>
          {tab === "resumo" && (
            <SummaryTab report={report} />
          )}
          {tab === "conflitos" && <ConflictsTab report={report} />}
          {tab === "similares" && <SimilarTab report={report} />}
          {tab === "patentes" && <PatentsTab report={report} />}
          {tab === "recomendacoes" && <RecommendationsTab report={report} />}
        </CardBody>
      </Card>
    </div>
  );
}


function SummaryTab({ report }: { report: AnalysisReport }) {
  return (
    <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <Field label="Marca" value={report.brand_name} />
      <Field label="Titular" value={report.holder} />
      <Field label="Classes NCL" value={report.nice_classes.join(", ")} />
      <Field label="Risco geral" value={RISK_META[report.overall_risk].label} />
      <Field label="Score" value={`${report.score}/100`} />
      <Field label="Modelo IA" value={report.model} />
    </dl>
  );
}

function ConflictsTab({ report }: { report: AnalysisReport }) {
  if (report.conflicts.length === 0)
    return <p className="py-4 text-sm text-slate-400">Nenhum conflito identificado.</p>;
  return (
    <div className="space-y-3">
      {report.conflicts.map((c, i) => (
        <div
          key={i}
          className="rounded-lg border border-gray-100 p-4"
        >
          <div className="mb-1 flex items-center justify-between">
            <span className="font-medium text-slate-700">{c.title}</span>
            <Badge tone={RISK_META[c.level].tone}>
              {c.score}/100
            </Badge>
          </div>
          {c.description && (
            <p className="text-sm text-slate-500">{c.description}</p>
          )}
          {c.fonte && (
            <p className="mt-1 text-xs text-slate-400">Fonte: {c.fonte}</p>
          )}
        </div>
      ))}
    </div>
  );
}

function SimilarTab({ report }: { report: AnalysisReport }) {
  if (report.similar_brands.length === 0)
    return <p className="py-4 text-sm text-slate-400">Nenhuma marca similar encontrada.</p>;
  return (
    <div className="scrollbar-thin overflow-x-auto rounded-lg border border-gray-100">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-4 py-2 text-left font-medium text-slate-500">Marca</th>
            <th className="px-4 py-2 text-left font-medium text-slate-500">Nº INPI</th>
            <th className="px-4 py-2 text-left font-medium text-slate-500">Situação</th>
            <th className="px-4 py-2 text-left font-medium text-slate-500">Similaridade</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {report.similar_brands.map((b, i) => (
            <tr key={i}>
              <td className="px-4 py-2 font-medium text-slate-700">{b.nome || "—"}</td>
              <td className="px-4 py-2 text-slate-600">{b.numero_inpi || "—"}</td>
              <td className="px-4 py-2 text-slate-600">{b.situacao || "—"}</td>
              <td className="px-4 py-2">
                <Badge tone={b.similaridade >= 60 ? "red" : b.similaridade >= 30 ? "amber" : "green"}>
                  {b.similaridade}%
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PatentsTab({ report }: { report: AnalysisReport }) {
  if (report.related_patents.length === 0)
    return <p className="py-4 text-sm text-slate-400">Nenhuma patente relacionada.</p>;
  return (
    <ul className="divide-y divide-gray-100">
      {report.related_patents.map((p, i) => (
        <li key={i} className="flex items-center justify-between py-3">
          <div>
            <p className="text-sm font-medium text-slate-700">{p.titulo || "—"}</p>
            <p className="text-xs text-slate-400">{p.numero_inpi || "—"}</p>
          </div>
          <Badge tone="slate">relevância {p.relevancia}</Badge>
        </li>
      ))}
    </ul>
  );
}

function RecommendationsTab({ report }: { report: AnalysisReport }) {
  if (report.recommendations.length === 0)
    return <p className="py-4 text-sm text-slate-400">Sem recomendações.</p>;
  return (
    <ol className="list-inside list-decimal space-y-2 text-sm text-slate-600">
      {report.recommendations.map((r, i) => (
        <li key={i}>{r}</li>
      ))}
    </ol>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium text-slate-700">{value || "—"}</dd>
    </div>
  );
}
