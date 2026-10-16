"use client";

import Link from "next/link";
import { useState } from "react";

import AppShell from "@/components/AppShell";
import {
  Badge,
  Button,
  Card,
  CardBody,
  EmptyState,
  ErrorNote,
  Input,
  Pagination,
  Select,
  Spinner,
} from "@/components/ui";
import { useNitOffers, useUpdateNitOffer } from "@/lib/hooks";
import { useAuth } from "@/app/auth-context";
import type { NitOffer } from "@/lib/types";
import {
  MODALITY_LABELS,
  NewOfferModal,
  OFFER_STATUS_LABELS,
} from "./NewOfferModal";

export default function NitCatalogPage() {
  const { has } = useAuth();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [openNew, setOpenNew] = useState(false);

  const pageSize = 12;
  const { data, isLoading, error } = useNitOffers({
    q: q || undefined,
    status: status || undefined,
    page,
    page_size: pageSize,
  });

  const canManage = has("NIT_OFFER_MANAGE");

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">
            Catálogo de Tecnologias
          </h1>
          <p className="text-sm text-slate-500">
            Ofertas tecnológicas aptas à divulgação e transferência.
          </p>
        </div>
        {canManage && <Button onClick={() => setOpenNew(true)}>Nova oferta</Button>}
      </div>

      <Card className="mb-4">
        <CardBody className="grid gap-3 sm:grid-cols-2">
          <Input
            label="Buscar"
            value={q}
            onChange={(e) => {
              setPage(1);
              setQ(e.target.value);
            }}
          />
          <Select
            label="Situação"
            value={status}
            onChange={(e) => {
              setPage(1);
              setStatus(e.target.value);
            }}
          >
            <option value="">Todas</option>
            {Object.entries(OFFER_STATUS_LABELS).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </Select>
        </CardBody>
      </Card>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}
      {isLoading ? <Spinner /> : null}

      {data ? (
        <>
          {data.items.length === 0 ? (
            <Card>
              <CardBody>
                <EmptyState title="Nenhuma oferta" />
              </CardBody>
            </Card>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {data.items.map((offer) => (
                <OfferCard key={offer.id} offer={offer} canManage={canManage} />
              ))}
            </div>
          )}
          <div className="mt-4">
            <Pagination
              page={page}
              pageSize={pageSize}
              total={data.total}
              onPage={setPage}
            />
          </div>
        </>
      ) : null}

      <NewOfferModal open={openNew} onClose={() => setOpenNew(false)} />
    </AppShell>
  );
}

function OfferCard({ offer, canManage }: { offer: NitOffer; canManage: boolean }) {
  const update = useUpdateNitOffer(offer.id);
  return (
    <Card>
      <CardBody>
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              {offer.code}
            </p>
            <p className="font-semibold text-slate-800">{offer.title}</p>
          </div>
          <Badge tone={offer.status === "PUBLISHED" ? "green" : "slate"}>
            {OFFER_STATUS_LABELS[offer.status] || offer.status}
          </Badge>
        </div>
        <p className="mt-2 line-clamp-3 text-sm text-slate-500">
          {offer.public_summary || "Sem descrição pública."}
        </p>
        <p className="mt-2 text-xs text-slate-400">
          {MODALITY_LABELS[offer.modality] || offer.modality}
          {offer.technology_area ? ` · ${offer.technology_area}` : ""}
        </p>
        {canManage && (
          <div className="mt-3 flex gap-2">
            {offer.status !== "PUBLISHED" ? (
              <Button
                variant="secondary"
                className="px-3 py-1.5"
                disabled={update.isPending}
                onClick={() => update.mutate({ status: "PUBLISHED" })}
              >
                Publicar
              </Button>
            ) : (
              <Button
                variant="secondary"
                className="px-3 py-1.5"
                disabled={update.isPending}
                onClick={() => update.mutate({ status: "SUSPENDED" })}
              >
                Suspender
              </Button>
            )}
            <Link
              href={`/nit/catalogo/${offer.id}`}
              className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-brand-700 hover:underline"
            >
              Manifestações
            </Link>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
