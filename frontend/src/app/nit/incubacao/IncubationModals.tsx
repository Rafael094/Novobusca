"use client";

import { useState } from "react";

import { Button, ErrorNote, Input, Modal, Select } from "@/components/ui";
import {
  useCreateParticipation,
  useCreateProgram,
  useNitStartups,
} from "@/lib/hooks";

export function NewProgramModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const create = useCreateProgram();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Novo programa de incubação"
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
                  description: description || null,
                  start_date: startDate || null,
                  end_date: endDate || null,
                },
                {
                  onSuccess: () => {
                    setName("");
                    setDescription("");
                    setStartDate("");
                    setEndDate("");
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
          label="Descrição (opcional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
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
      </div>
    </Modal>
  );
}

export function EnrollModal({
  programId,
  onClose,
}: {
  programId: string;
  onClose: () => void;
}) {
  const { data: startups } = useNitStartups({ page: 1, page_size: 100 });
  const create = useCreateParticipation(programId);
  const [startupId, setStartupId] = useState("");
  const [entryDate, setEntryDate] = useState("");
  const [notes, setNotes] = useState("");

  return (
    <Modal
      open
      onClose={onClose}
      title="Inscrever startup no programa"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            disabled={!startupId || create.isPending}
            onClick={() =>
              create.mutate(
                { startup_id: startupId, entry_date: entryDate || null, notes: notes || null },
                { onSuccess: onClose },
              )
            }
          >
            {create.isPending ? "Inscrevendo…" : "Inscrever"}
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
        <Select
          label="Startup"
          value={startupId}
          onChange={(e) => setStartupId(e.target.value)}
        >
          <option value="">Selecione…</option>
          {startups?.items.map((s) => (
            <option key={s.id} value={s.id}>
              {s.code} — {s.name}
            </option>
          ))}
        </Select>
        <Input
          label="Data de entrada (opcional)"
          type="date"
          value={entryDate}
          onChange={(e) => setEntryDate(e.target.value)}
        />
        <Input
          label="Observações (opcional)"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
        <p className="text-xs text-slate-400">
          A inscrição marca a startup como &quot;Incubada&quot; apenas como indicador de
          conveniência, sem inferir propriedade.
        </p>
      </div>
    </Modal>
  );
}
