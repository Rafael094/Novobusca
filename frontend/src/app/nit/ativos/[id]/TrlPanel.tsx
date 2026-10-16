"use client";

import { useState } from "react";

import {
  Badge,
  Button,
  EmptyState,
  ErrorNote,
  Input,
  Modal,
  Spinner,
  Textarea,
} from "@/components/ui";
import { useNitTrlHistory, useRecordNitTrl } from "@/lib/hooks";
import { useAuth } from "@/app/auth-context";

/** TRL (maturity) panel: append-only history + record form for authorized users. */
export function TrlPanel({
  disclosureId,
  assetId,
}: {
  disclosureId?: string;
  assetId?: string;
}) {
  const { has } = useAuth();
  const { data, isLoading, error } = useNitTrlHistory({
    disclosure_id: disclosureId,
    asset_id: assetId,
  });
  const [open, setOpen] = useState(false);
  const canManage = has("NIT_TRL_MANAGE");

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-700">Maturidade tecnológica (TRL)</p>
        {canManage && <Button onClick={() => setOpen(true)}>Registrar TRL</Button>}
      </div>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}
      {isLoading ? (
        <Spinner />
      ) : data && data.length > 0 ? (
        <ol className="space-y-3 border-l border-gray-100 pl-4">
          {data.map((t) => (
            <li key={t.id} className="text-sm">
              <p className="text-slate-700">
                <Badge tone="blue">TRL {t.level}</Badge>
                {t.previous_level ? (
                  <span className="ml-2 text-xs text-slate-400">
                    (anterior: {t.previous_level})
                  </span>
                ) : null}
              </p>
              <p className="mt-1 text-slate-600">{t.rationale}</p>
              {t.evidence && (
                <p className="text-xs text-slate-400">Evidência: {t.evidence}</p>
              )}
              <p className="text-xs text-slate-400">
                {new Date(t.created_at).toLocaleString("pt-BR")}
              </p>
            </li>
          ))}
        </ol>
      ) : (
        <EmptyState
          title="Sem nível TRL registrado"
          description="O nível é sempre atribuído por um avaliador, com justificativa."
        />
      )}

      <RecordTrlModal
        disclosureId={disclosureId}
        assetId={assetId}
        open={open}
        onClose={() => setOpen(false)}
      />
    </div>
  );
}

function RecordTrlModal({
  disclosureId,
  assetId,
  open,
  onClose,
}: {
  disclosureId?: string;
  assetId?: string;
  open: boolean;
  onClose: () => void;
}) {
  const record = useRecordNitTrl();
  const [level, setLevel] = useState("3");
  const [rationale, setRationale] = useState("");
  const [evidence, setEvidence] = useState("");

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Registrar nível TRL"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            disabled={!rationale.trim() || record.isPending}
            onClick={() =>
              record.mutate(
                {
                  disclosure_id: disclosureId ?? null,
                  asset_id: assetId ?? null,
                  level: Number(level),
                  rationale,
                  evidence: evidence || null,
                },
                {
                  onSuccess: () => {
                    setRationale("");
                    setEvidence("");
                    onClose();
                  },
                },
              )
            }
          >
            {record.isPending ? "Salvando…" : "Registrar"}
          </Button>
        </>
      }
    >
      {record.error ? (
        <div className="mb-3">
          <ErrorNote>{(record.error as Error).message}</ErrorNote>
        </div>
      ) : null}
      <div className="space-y-3">
        <Input
          label="Nível (1–9)"
          type="number"
          min={1}
          max={9}
          value={level}
          onChange={(e) => setLevel(e.target.value)}
        />
        <Textarea
          label="Justificativa"
          rows={3}
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
        />
        <Textarea
          label="Evidência (opcional)"
          rows={2}
          value={evidence}
          onChange={(e) => setEvidence(e.target.value)}
        />
      </div>
    </Modal>
  );
}
