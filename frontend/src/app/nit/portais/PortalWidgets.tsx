"use client";

import { useState } from "react";

import { Button, ErrorNote, Input, Modal, Select } from "@/components/ui";
import { useCreatePortalAccess, useTriagePortalRequest } from "@/lib/hooks";

export function TriageButton({ requestId }: { requestId: string }) {
  const triage = useTriagePortalRequest();
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState("TRIAGED");
  const [note, setNote] = useState("");

  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        Triar
      </Button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Triagem da solicitação"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button
              disabled={triage.isPending}
              onClick={() =>
                triage.mutate(
                  { id: requestId, payload: { status, note: note || null } },
                  { onSuccess: () => setOpen(false) },
                )
              }
            >
              Salvar
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <Select label="Situação" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="TRIAGED">Triada</option>
            <option value="ACCEPTED">Aceita</option>
            <option value="REJECTED">Rejeitada</option>
          </Select>
          <Input
            label="Observação interna (opcional)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>
      </Modal>
    </>
  );
}

export function NewAccessModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useCreatePortalAccess();
  const [kind, setKind] = useState("RESEARCHER");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [organization, setOrganization] = useState("");
  const [token, setToken] = useState<string | null>(null);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Nova concessão de acesso"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Fechar
          </Button>
          {!token ? (
            <Button
              disabled={!email.trim() || !name.trim() || create.isPending}
              onClick={() =>
                create.mutate(
                  { portal_kind: kind, email, name, organization: organization || null },
                  { onSuccess: (data) => setToken(data.access_token ?? null) },
                )
              }
            >
              Criar
            </Button>
          ) : null}
        </>
      }
    >
      {create.error ? (
        <div className="mb-3">
          <ErrorNote>{(create.error as Error).message}</ErrorNote>
        </div>
      ) : null}
      {token ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <p className="font-medium">Token de acesso (exibido apenas uma vez)</p>
          <p className="mt-1 break-all font-mono text-xs">{token}</p>
          <p className="mt-1 text-xs">
            Compartilhe com o titular. Ele não será exibido novamente.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <Select label="Portal" value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="RESEARCHER">Pesquisador</option>
            <option value="COMPANY">Empresa</option>
          </Select>
          <Input label="Nome" value={name} onChange={(e) => setName(e.target.value)} />
          <Input label="E-mail" value={email} onChange={(e) => setEmail(e.target.value)} />
          <Input
            label="Organização (opcional)"
            value={organization}
            onChange={(e) => setOrganization(e.target.value)}
          />
        </div>
      )}
    </Modal>
  );
}
