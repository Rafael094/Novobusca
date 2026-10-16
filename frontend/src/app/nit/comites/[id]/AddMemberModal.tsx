"use client";

import { useState } from "react";

import {
  Button,
  ErrorNote,
  Input,
  Modal,
  Select,
} from "@/components/ui";
import { useAddCommitteeMember } from "@/lib/hooks";

/** Dialog to add a member to a committee. */
export function AddMemberModal({
  committeeId,
  open,
  onClose,
}: {
  committeeId: string;
  open: boolean;
  onClose: () => void;
}) {
  const add = useAddCommitteeMember(committeeId);
  const [name, setName] = useState("");
  const [roleTitle, setRoleTitle] = useState("");
  const [kind, setKind] = useState("VOTING");

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Adicionar membro"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            disabled={!name.trim() || add.isPending}
            onClick={() =>
              add.mutate(
                { name, role_title: roleTitle || null, kind },
                {
                  onSuccess: () => {
                    setName("");
                    setRoleTitle("");
                    onClose();
                  },
                },
              )
            }
          >
            {add.isPending ? "Adicionando…" : "Adicionar"}
          </Button>
        </>
      }
    >
      {add.error ? (
        <div className="mb-3">
          <ErrorNote>{(add.error as Error).message}</ErrorNote>
        </div>
      ) : null}
      <div className="space-y-3">
        <Input
          label="Nome"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Input
          label="Cargo/função (opcional)"
          value={roleTitle}
          onChange={(e) => setRoleTitle(e.target.value)}
        />
        <Select
          label="Tipo"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          <option value="VOTING">Votante</option>
          <option value="ADVISORY">Consultivo</option>
        </Select>
      </div>
    </Modal>
  );
}
