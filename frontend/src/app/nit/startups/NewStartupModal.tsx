"use client";

import { useState } from "react";

import { Button, ErrorNote, Input, Modal, Select, Textarea } from "@/components/ui";
import { useCreateStartup, useNitProjects } from "@/lib/hooks";
import { STARTUP_STATUS_LABELS } from "./StartupsTable";

/** Dialog to create a new startup / spin-off. */
export function NewStartupModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const create = useCreateStartup();
  const { data: projects } = useNitProjects({ page: 1, page_size: 100 });
  const [name, setName] = useState("");
  const [cnpj, setCnpj] = useState("");
  const [status, setStatus] = useState("IDEATION");
  const [stage, setStage] = useState("");
  const [projectId, setProjectId] = useState("");
  const [description, setDescription] = useState("");

  const reset = () => {
    setName("");
    setCnpj("");
    setStatus("IDEATION");
    setStage("");
    setProjectId("");
    setDescription("");
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Nova startup"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            disabled={!name.trim() || create.isPending}
            onClick={() =>
              create.mutate(
                {
                  name,
                  cnpj: cnpj || null,
                  status,
                  stage: stage || null,
                  project_id: projectId || null,
                  description: description || null,
                },
                {
                  onSuccess: () => {
                    reset();
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
        <Input label="Nome" value={name} onChange={(e) => setName(e.target.value)} />
        <Input
          label="CNPJ (opcional)"
          value={cnpj}
          onChange={(e) => setCnpj(e.target.value)}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <Select label="Situação" value={status} onChange={(e) => setStatus(e.target.value)}>
            {Object.entries(STARTUP_STATUS_LABELS).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </Select>
          <Input
            label="Estágio (opcional)"
            placeholder="Ex.: MVP"
            value={stage}
            onChange={(e) => setStage(e.target.value)}
          />
        </div>
        <Select
          label="Projeto de origem (opcional)"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        >
          <option value="">Nenhum</option>
          {projects?.items.map((p) => (
            <option key={p.id} value={p.id}>
              {p.code} — {p.title}
            </option>
          ))}
        </Select>
        <Textarea
          label="Descrição (opcional)"
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
    </Modal>
  );
}
