"use client";

import { useState } from "react";

import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorNote,
  Input,
  Modal,
  Select,
  Spinner,
  Textarea,
} from "@/components/ui";
import {
  useCreateObligation,
  useCreateRoyalty,
  useNitObligations,
  useNitRoyalties,
  useNitRoyaltySummary,
  useUpdateObligation,
} from "@/lib/hooks";

const OBLIGATION_STATUS_LABELS: Record<string, string> = {
  PENDING: "Pendente",
  DONE: "Cumprida",
  LATE: "Atrasada",
  WAIVED: "Dispensada",
};

/** Contract obligations with an add dialog and status transitions. */
export function ObligationsCard({ contractId }: { contractId: string }) {
  const { data, isLoading } = useNitObligations(contractId);
  const update = useUpdateObligation();
  const [open, setOpen] = useState(false);

  return (
    <Card>
      <CardHeader
        title="Obrigações"
        action={
          <Button variant="secondary" onClick={() => setOpen(true)}>
            Nova obrigação
          </Button>
        }
      />
      <CardBody>
        {isLoading ? (
          <Spinner />
        ) : data && data.length > 0 ? (
          <ul className="divide-y divide-gray-50">
            {data.map((o) => (
              <li
                key={o.id}
                className="flex flex-wrap items-center justify-between gap-2 py-3"
              >
                <div>
                  <p className="text-sm text-slate-700">{o.description}</p>
                  <p className="text-xs text-slate-400">
                    {o.kind}
                    {o.due_date
                      ? ` · vence em ${new Date(o.due_date).toLocaleDateString("pt-BR")}`
                      : " · sem prazo"}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    tone={
                      o.status === "DONE"
                        ? "green"
                        : o.status === "LATE"
                          ? "red"
                          : o.status === "WAIVED"
                            ? "slate"
                            : "amber"
                    }
                  >
                    {OBLIGATION_STATUS_LABELS[o.status] || o.status}
                  </Badge>
                  {o.status === "PENDING" && (
                    <Button
                      variant="secondary"
                      className="px-3 py-1.5"
                      disabled={update.isPending}
                      onClick={() =>
                        update.mutate({ id: o.id, payload: { status: "DONE" } })
                      }
                    >
                      Marcar cumprida
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState title="Nenhuma obrigação" />
        )}

        <NewObligationModal
          contractId={contractId}
          open={open}
          onClose={() => setOpen(false)}
        />
      </CardBody>
    </Card>
  );
}

function NewObligationModal({
  contractId,
  open,
  onClose,
}: {
  contractId: string;
  open: boolean;
  onClose: () => void;
}) {
  const create = useCreateObligation(contractId);
  const [kind, setKind] = useState("DELIVERY");
  const [description, setDescription] = useState("");
  const [due, setDue] = useState("");

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Nova obrigação"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            disabled={!description.trim() || create.isPending}
            onClick={() =>
              create.mutate(
                { kind, description, due_date: due || null },
                {
                  onSuccess: () => {
                    setDescription("");
                    setDue("");
                    onClose();
                  },
                },
              )
            }
          >
            {create.isPending ? "Salvando…" : "Adicionar"}
          </Button>
        </>
      }
    >
      {create.error ? (
        <div className="mb-3">
          <ErrorNote>{(create.error as Error).message}</ErrorNote>
        </div>
      ) : null}
      <div className="space-y-3">
        <Select label="Tipo" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="DELIVERY">Entrega</option>
          <option value="PAYMENT">Pagamento</option>
          <option value="REPORT">Relatório</option>
          <option value="TRAINING">Treinamento</option>
          <option value="COMPLIANCE">Conformidade</option>
          <option value="OTHER">Outro</option>
        </Select>
        <Textarea
          label="Descrição"
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <Input
          label="Vencimento (opcional)"
          type="date"
          value={due}
          onChange={(e) => setDue(e.target.value)}
        />
      </div>
    </Modal>
  );
}
