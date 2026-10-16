"use client";

import { useState } from "react";

import {
  Button,
  ErrorNote,
  Input,
  Modal,
} from "@/components/ui";
import { useCreateNitContract } from "@/lib/hooks";

/** Dialog to create a new contract (starts as DRAFT). */
export function NewContractModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const create = useCreateNitContract();
  const [title, setTitle] = useState("");
  const [amount, setAmount] = useState("");

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Novo contrato"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            disabled={!title.trim() || create.isPending}
            onClick={() =>
              create.mutate(
                { title, registered_amount: amount || null },
                {
                  onSuccess: () => {
                    setTitle("");
                    setAmount("");
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
          label="Valor registrado (opcional)"
          type="text"
          placeholder="Ex.: 15000.00"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
      </div>
    </Modal>
  );
}
