"use client";

import { useState } from "react";

import { Button, ErrorNote, Input, Modal, Select, Textarea } from "@/components/ui";
import { useCreateProject } from "@/lib/hooks";
import { PROJECT_STATUS_LABELS } from "./ProjectsTable";

/** Dialog to create a new R&D project. */
export function NewProjectModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const create = useCreateProject();
  const [title, setTitle] = useState("");
  const [area, setArea] = useState("");
  const [status, setStatus] = useState("PLANNED");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [objective, setObjective] = useState("");

  const reset = () => {
    setTitle("");
    setArea("");
    setStatus("PLANNED");
    setStartDate("");
    setEndDate("");
    setObjective("");
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Novo projeto de P&D"
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
                  technology_area: area || null,
                  status,
                  start_date: startDate || null,
                  end_date: endDate || null,
                  objective: objective || null,
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
        <Input label="Título" value={title} onChange={(e) => setTitle(e.target.value)} />
        <Input
          label="Área tecnológica (opcional)"
          value={area}
          onChange={(e) => setArea(e.target.value)}
        />
        <Select label="Situação" value={status} onChange={(e) => setStatus(e.target.value)}>
          {Object.entries(PROJECT_STATUS_LABELS).map(([k, label]) => (
            <option key={k} value={k}>
              {label}
            </option>
          ))}
        </Select>
        <div className="grid gap-3 sm:grid-cols-2">
          <Input
            label="Início (opcional)"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
          <Input
            label="Fim (opcional)"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </div>
        <Textarea
          label="Objetivo (opcional)"
          rows={3}
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
        />
      </div>
    </Modal>
  );
}
