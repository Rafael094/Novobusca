"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import AppShell from "@/components/AppShell";
import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorNote,
  Spinner,
  statusTone,
} from "@/components/ui";
import { useNitAsset } from "@/lib/hooks";
import { STATUS_LABELS, TYPE_LABELS } from "../NewAssetModal";
import { DocumentsPanel } from "../../comunicacoes/[id]/DocumentsPanel";
import { TrlPanel } from "./TrlPanel";

export default function AssetDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? null;
  const { data, isLoading, error } = useNitAsset(id);

  return (
    <AppShell>
      <div className="mb-4">
        <Link href="/nit/ativos" className="text-sm text-brand-700 hover:underline">
          ← Voltar para o portfólio
        </Link>
      </div>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}
      {isLoading ? <Spinner /> : null}

      {data ? (
        <>
          <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                {data.code}
              </p>
              <h1 className="text-2xl font-bold text-slate-800">{data.title}</h1>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone={statusTone(data.status)}>
                {STATUS_LABELS[data.status] || data.status}
              </Badge>
              <Badge tone="slate">{data.confidentiality_level}</Badge>
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2 space-y-6">
              <Card>
                <CardHeader title="Detalhes do ativo" />
                <CardBody className="space-y-4">
                  <Field
                    label="Tipo"
                    value={TYPE_LABELS[data.asset_type] || data.asset_type}
                  />
                  <Field label="Descrição" value={data.description} />
                  <Field label="Área tecnológica" value={data.technology_area} />
                  <div className="grid gap-4 sm:grid-cols-3">
                    <Field label="Depósito" value={fmt(data.deposited_at)} />
                    <Field label="Concessão" value={fmt(data.granted_at)} />
                    <Field label="Vigência" value={fmt(data.expires_at)} />
                  </div>
                </CardBody>
              </Card>

              <Card>
                <CardHeader
                  title="Documentos"
                  subtitle="Acesso restrito conforme nível de sigilo e ACL"
                />
                <CardBody>
                  <DocumentsPanel assetId={data.id} />
                </CardBody>
              </Card>

              <Card>
                <CardHeader
                  title="Maturidade tecnológica (TRL)"
                  subtitle="Histórico append-only com justificativa e evidência"
                />
                <CardBody>
                  <TrlPanel assetId={data.id} />
                </CardBody>
              </Card>
            </div>

            <Card>
              <CardHeader title="Vínculos públicos (INPI)" />
              <CardBody>
                {data.public_links.length === 0 ? (
                  <EmptyState
                    title="Sem vínculo"
                    description="O ativo é interno e não referencia registro público."
                  />
                ) : (
                  <ul className="space-y-2">
                    {data.public_links.map((l) => (
                      <li
                        key={l.id}
                        className="rounded-lg border border-gray-100 px-3 py-2"
                      >
                        <p className="text-sm font-medium text-slate-700">
                          {l.external_ref}
                        </p>
                        <p className="text-xs text-slate-400">
                          {l.source === "INPI_MARCA" ? "Marca" : "Patente"} ·{" "}
                          sincronizado em{" "}
                          {new Date(l.synced_at).toLocaleDateString("pt-BR")}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </CardBody>
            </Card>
          </div>
        </>
      ) : null}
    </AppShell>
  );
}

function fmt(value: string | null): string | null {
  return value ? new Date(value).toLocaleDateString("pt-BR") : null;
}

function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p className="mt-0.5 whitespace-pre-wrap text-sm text-slate-700">
        {value || "—"}
      </p>
    </div>
  );
}
