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
import { useCreateNitDisclosure } from "@/lib/hooks";

/** Dialog to submit a new communication of invention (protocol generated server-side). */
export function NewDisclosureModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const create = useCreateNitDisclosure();
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [area, setArea] = useState("");
  const [keywords, setKeywords] = useState("");
  const [level, setLevel] = useState("INTERNAL");
  const [inventorName, setInventorName] = useState("");

  function submit() {
    create.mutate(
      {
        title,
        summary: summary || null,
        technology_area: area || null,
        keywords: keywords || null,
        confidentiality_level: level,
        inventors: inventorName
          ? [{ name: inventorName, kind: "INTERNAL", is_primary: true }]
          : [],
      },
      {
        onSuccess: () => {
          setTitle("");
          setSummary("");
          setArea("");
          setKeywords("");
          setInventorName("");
          onClose();
        },
      },
    );
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Nova comunicação de invenção"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={submit} disabled={!title.trim() || create.isPending}>
            {create.isPending ? "Enviando…" : "Registrar"}
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
          label="Título da invenção"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <Textarea
          label="Resumo"
          rows={3}
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
        />
        <Input
          label="Área tecnológica"
          value={area}
          onChange={(e) => setArea(e.target.value)}
        />
        <Input
          label="Palavras-chave"
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
        />
        <Select
          label="Nível de sigilo"
          value={level}
          onChange={(e) => setLevel(e.target.value)}
        >
          <option value="PUBLIC">Público</option>
          <option value="INTERNAL">Interno</option>
          <option value="RESTRICTED">Restrito</option>
          <option value="CONFIDENTIAL">Confidencial</option>
        </Select>
        <Input
          label="Inventor principal (opcional)"
          value={inventorName}
          onChange={(e) => setInventorName(e.target.value)}
        />
      </div>
    </Modal>
  );
}
