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
import { useCreateNitAsset } from "@/lib/hooks";

export const TYPE_LABELS: Record<string, string> = {
  PATENT: "Patente",
  TRADEMARK: "Marca",
  SOFTWARE: "Software",
  CULTIVAR: "Cultivar",
  KNOWHOW: "Know-how",
  OTHER: "Outro",
};

export const STATUS_LABELS: Record<string, string> = {
  PROSPECT: "Prospectivo",
  PROTECTED: "Protegido",
  LICENSED: "Licenciado",
  TRANSFERRED: "Transferido",
  ARCHIVED: "Arquivado",
};

/** Dialog to create an institutional asset with an optional public INPI link. */
export function NewAssetModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const create = useCreateNitAsset();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [assetType, setAssetType] = useState("OTHER");
  const [status, setStatus] = useState("PROSPECT");
  const [area, setArea] = useState("");
  const [ref, setRef] = useState("");
  const [source, setSource] = useState("INPI_PATENTE");

  function submit() {
    create.mutate(
      {
        title,
        description: description || null,
        asset_type: assetType,
        status,
        technology_area: area || null,
        public_links: ref ? [{ source, external_ref: ref, label: null }] : [],
      },
      {
        onSuccess: () => {
          setTitle("");
          setDescription("");
          setArea("");
          setRef("");
          onClose();
        },
      },
    );
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Novo ativo institucional"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={submit} disabled={!title.trim() || create.isPending}>
            {create.isPending ? "Salvando…" : "Criar"}
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
        <Input
          label="Título"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <Textarea
          label="Descrição"
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <Select
            label="Tipo"
            value={assetType}
            onChange={(e) => setAssetType(e.target.value)}
          >
            {Object.entries(TYPE_LABELS).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </Select>
          <Select
            label="Situação"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            {Object.entries(STATUS_LABELS).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </Select>
        </div>
        <Input
          label="Área tecnológica"
          value={area}
          onChange={(e) => setArea(e.target.value)}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <Select
            label="Vínculo público (opcional)"
            value={source}
            onChange={(e) => setSource(e.target.value)}
          >
            <option value="INPI_PATENTE">Patente INPI</option>
            <option value="INPI_MARCA">Marca INPI</option>
          </Select>
          <Input
            label="Código INPI"
            placeholder="Ex.: BR102020000001"
            value={ref}
            onChange={(e) => setRef(e.target.value)}
          />
        </div>
      </div>
    </Modal>
  );
}
