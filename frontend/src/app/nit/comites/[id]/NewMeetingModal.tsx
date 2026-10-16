"use client";

import { useState } from "react";

import {
  Button,
  ErrorNote,
  Input,
  Modal,
} from "@/components/ui";
import { useCreateNitMeeting } from "@/lib/hooks";

/** Dialog to schedule a new committee meeting. */
export function NewMeetingModal({
  committeeId,
  open,
  onClose,
}: {
  committeeId: string;
  open: boolean;
  onClose: () => void;
}) {
  const create = useCreateNitMeeting(committeeId);
  const [title, setTitle] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [location, setLocation] = useState("");

  function submit() {
    if (!scheduledAt) return;
    create.mutate(
      {
        title,
        scheduled_at: new Date(scheduledAt).toISOString(),
        location: location || null,
      },
      {
        onSuccess: () => {
          setTitle("");
          setScheduledAt("");
          setLocation("");
          onClose();
        },
      },
    );
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Nova reunião"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            disabled={!title.trim() || !scheduledAt || create.isPending}
            onClick={submit}
          >
            {create.isPending ? "Criando…" : "Agendar"}
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
        <Input
          label="Data e hora"
          type="datetime-local"
          value={scheduledAt}
          onChange={(e) => setScheduledAt(e.target.value)}
        />
        <Input
          label="Local (opcional)"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
        />
      </div>
    </Modal>
  );
}
