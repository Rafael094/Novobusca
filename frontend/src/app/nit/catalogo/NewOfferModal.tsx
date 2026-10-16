"use client";

import { useState } from "react";

import {
  Button,
  ErrorNote,
  Input,
  Modal,
  Select,
  Textarea,
} from "@/components/ui";
import { useCreateNitOffer } from "@/lib/hooks";

export const MODALITY_LABELS: Record<string, string> = {
  LICENSING: "Licenciamento",
  ASSIGNMENT: "Cessão",
  CO_DEVELOPMENT: "Codesenvolvimento",
  SERVICE: "Serviço",
  OTHER: "Outro",
};

export const OFFER_STATUS_LABELS: Record<string, string> = {
  DRAFT: "Rascunho",
  PUBLISHED: "Publicado",
  SUSPENDED: "Suspenso",
  CLOSED: "Encerrado",
};

/** Dialog to create a new technology offer (starts as DRAFT). */
export function NewOfferModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useCreateNitOffer();
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [area, setArea] = useState("");
  const [modality, setModality] = useState("LICENSING");

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Nova oferta tecnológica"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            disabled={!title.trim() || create.isPending}
            onClick={() =>
              create.mutate(
                {
                  title,
                  public_summary: summary || null,
                  technology_area: area || null,
                  modality,
                },
                {
                  onSuccess: () => {
                    setTitle("");
                    setSummary("");
                    setArea("");
                    onClose();
                  },
                },
              )
            }
          >
            {create.isPending ? "Criando…" : "Criar"}
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
        <Input label="Título" value={title} onChange={(e) => setTitle(e.target.value)} />
        <Textarea
          label="Descrição pública"
          rows={3}
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
        />
        <Input
          label="Área tecnológica"
          value={area}
          onChange={(e) => setArea(e.target.value)}
        />
        <Select
          label="Modalidade"
          value={modality}
          onChange={(e) => setModality(e.target.value)}
        >
          {Object.entries(MODALITY_LABELS).map(([k, label]) => (
            <option key={k} value={k}>
              {label}
            </option>
          ))}
        </Select>
      </div>
    </Modal>
  );
}
