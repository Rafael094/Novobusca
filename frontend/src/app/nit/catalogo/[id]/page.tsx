"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import AppShell from "@/components/AppShell";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorNote,
  Spinner,
} from "@/components/ui";
import {
  useCreateNegotiation,
  useNitInterests,
  useNitOffers,
} from "@/lib/hooks";
import { useAuth } from "@/app/auth-context";
import { INTEREST_STATUS_LABELS, RegisterInterestModal } from "./RegisterInterestModal";

export default function OfferDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? null;
  const { has } = useAuth();
  const offers = useNitOffers({ page_size: 100 });
  const offer = offers.data?.items.find((o) => o.id === id) ?? null;

  const { data: interests, isLoading } = useNitInterests({
    offer_id: id ?? undefined,
  });
  const [openNew, setOpenNew] = useState(false);
  const [startingNegFor, setStartingNegFor] = useState<string | null>(null);
  const createNeg = useCreateNegotiation();

  const canCreate = has("NIT_INTEREST_CREATE");
  const canManage = has("NIT_NEGOTIATION_MANAGE");

  return (
    <AppShell>
      <div className="mb-4">
        <Link href="/nit/catalogo" className="text-sm text-brand-700 hover:underline">
          ← Voltar ao catálogo
        </Link>
      </div>

      {offers.isLoading ? <Spinner /> : null}
      {offer ? (
        <>
          <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                {offer.code}
              </p>
              <h1 className="text-2xl font-bold text-slate-800">{offer.title}</h1>
              <p className="mt-1 max-w-3xl text-sm text-slate-500">
                {offer.public_summary || "Sem descrição pública."}
              </p>
            </div>
            <Badge tone={offer.status === "PUBLISHED" ? "green" : "slate"}>
              {offer.status}
            </Badge>
          </div>

          <Card>
            <CardHeader
              title="Manifestações de interesse"
              subtitle="Visíveis apenas aos usuários autorizados do NIT"
              action={
                canCreate && offer.status === "PUBLISHED" ? (
                  <Button variant="secondary" onClick={() => setOpenNew(true)}>
                    Registrar interesse
                  </Button>
                ) : undefined
              }
            />
            <CardBody>
              {isLoading ? (
                <Spinner />
              ) : interests && interests.items.length > 0 ? (
                <ul className="divide-y divide-gray-50">
                  {interests.items.map((i) => (
                    <li
                      key={i.id}
                      className="flex flex-wrap items-center justify-between gap-2 py-3"
                    >
                      <div>
                        <p className="text-sm font-medium text-slate-700">
                          {i.organization_name}
                        </p>
                        <p className="text-xs text-slate-400">
                          {i.contact_email || "sem e-mail"} ·{" "}
                          {new Date(i.created_at).toLocaleDateString("pt-BR")}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge tone={i.status === "CONVERTED" ? "green" : "blue"}>
                          {INTEREST_STATUS_LABELS[i.status] || i.status}
                        </Badge>
                        {canManage && i.status !== "CONVERTED" && (
                          <Button
                            variant="secondary"
                            className="px-3 py-1.5"
                            disabled={createNeg.isPending}
                            onClick={() => {
                              setStartingNegFor(i.id);
                              createNeg.mutate(
                                { interest_id: i.id },
                                { onSettled: () => setStartingNegFor(null) },
                              );
                            }}
                          >
                            {startingNegFor === i.id ? "Iniciando…" : "Iniciar negociação"}
                          </Button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState
                  title="Nenhuma manifestação"
                  description="Somente ofertas publicadas recebem manifestações de interesse."
                />
              )}
              {createNeg.error ? (
                <div className="mt-3">
                  <ErrorNote>{(createNeg.error as Error).message}</ErrorNote>
                </div>
              ) : null}
              {createNeg.isSuccess ? (
                <p className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                  Negociação iniciada. Veja em <strong>Negociações</strong>.
                </p>
              ) : null}
            </CardBody>
          </Card>

          <RegisterInterestModal
            offerId={offer.id}
            open={openNew}
            onClose={() => setOpenNew(false)}
          />
        </>
      ) : null}
    </AppShell>
  );
}
