"use client";

import { useState } from "react";

import {
  Button,
  ErrorNote,
  Input,
  Modal,
  Textarea,
} from "@/components/ui";
import { useRegisterInterest } from "@/lib/hooks";

export const INTEREST_STATUS_LABELS: Record<string, string> = {
  NEW: "Nova",
  QUALIFYING: "Em qualificação",
  IN_NEGOTIATION: "Em negociação",
  DECLINED: "Recusada",
  CONVERTED: "Convertida",
};

/** Dialog to register a company's expression of interest in an offer. */
export function RegisterInterestModal({
  offerId,
  open,
  onClose,
}: {
  offerId: string;
  open: boolean;
  onClose: () => void;
}) {
  const register = useRegisterInterest(offerId);
  const [org, setOrg] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Registrar manifestação de interesse"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            disabled={!org.trim() || register.isPending}
            onClick={() =>
              register.mutate(
                {
                  organization_name: org,
                  contact_email: email || null,
                  message: message || null,
                },
                {
                  onSuccess: () => {
                    setOrg("");
                    setEmail("");
                    setMessage("");
                    onClose();
                  },
                },
              )
            }
          >
            {register.isPending ? "Enviando…" : "Registrar"}
          </Button>
        </>
      }
    >
      {register.error ? (
        <div className="mb-3">
          <ErrorNote>{(register.error as Error).message}</ErrorNote>
        </div>
      ) : null}
      <div className="space-y-3">
        <Input label="Organização" value={org} onChange={(e) => setOrg(e.target.value)} />
        <Input
          label="E-mail de contato"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Textarea
          label="Mensagem"
          rows={3}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
      </div>
    </Modal>
  );
}
