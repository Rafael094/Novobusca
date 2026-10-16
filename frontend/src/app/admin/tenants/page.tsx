"use client";

import { useState } from "react";

import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyRow,
  ErrorNote,
  Input,
  Modal,
  Spinner,
  Table,
  Td,
  Textarea,
  Th,
} from "@/components/ui";
import {
  useAdminTenants,
  useCreateTenant,
  useUpdateTenant,
} from "@/lib/hooks";
import type { AdminTenant } from "@/lib/types";
import { maskCnpj, maskEmail, maskPhone } from "@/lib/masks";
import { useAuth } from "@/app/auth-context";

type TenantForm = {
  social_reason: string;
  company_name: string;
  cnpj: string;
  email: string;
  phone: string;
  active: boolean;
};

const EMPTY_TENANT: TenantForm = {
  social_reason: "",
  company_name: "",
  cnpj: "",
  email: "",
  phone: "",
  active: true,
};

export default function TenantsPage() {
  const { user } = useAuth();
  const tenants = useAdminTenants();
  const create = useCreateTenant();
  const update = useUpdateTenant();
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState<AdminTenant | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<TenantForm>(EMPTY_TENANT);

  const isMaster = user?.is_master_admin ?? false;
  const isSaving = create.isPending || update.isPending;

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_TENANT);
    setError(null);
    setModal(true);
  }

  function openEdit(t: AdminTenant) {
    setEditing(t);
    setForm({
      social_reason: t.social_reason,
      company_name: t.company_name ?? "",
      cnpj: t.cnpj ? maskCnpj(t.cnpj) : "",
      email: t.email ?? "",
      phone: t.phone ? maskPhone(t.phone) : "",
      active: t.active,
    });
    setError(null);
    setModal(true);
  }

  async function submit() {
    setError(null);
    try {
      if (editing) {
        await update.mutateAsync({
          id: editing.id,
          social_reason: form.social_reason,
          company_name: form.company_name || null,
          cnpj: form.cnpj || null,
          email: form.email || null,
          phone: form.phone || null,
          active: form.active,
        });
      } else {
        await create.mutateAsync({
          social_reason: form.social_reason,
          company_name: form.company_name || null,
          cnpj: form.cnpj || null,
          email: form.email || null,
          phone: form.phone || null,
          module_codes: [],
        });
      }
      setModal(false);
      setEditing(null);
      setForm(EMPTY_TENANT);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar.");
    }
  }

  if (!isMaster) {
    return (
      <>
        <Card>
          <Textarea
            label="Acesso restrito"
            value="A gestão de tenants é exclusiva do Master Admin."
            readOnly
          />
        </Card>
      </>
    );
  }

  return (
    <>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Tenants</h1>
          <p className="text-sm text-slate-500">
            Organizações isoladas da plataforma.
          </p>
        </div>
        <Button onClick={openCreate}>+ Novo tenant</Button>
      </div>

      {tenants.error && (
        <div className="mb-3">
          <ErrorNote>
            {tenants.error instanceof Error
              ? tenants.error.message
              : "Erro ao carregar tenants."}
          </ErrorNote>
        </div>
      )}

      <Card>
        <CardHeader title="Tenants cadastrados" />
        <Table>
          <thead className="bg-slate-50">
            <tr>
              <Th>Nome</Th>
              <Th>Razão social</Th>
              <Th>Documento</Th>
              <Th>Usuários</Th>
              <Th>Status</Th>
              <Th />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {tenants.isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-6">
                  <Spinner />
                </td>
              </tr>
            )}
            {tenants.data?.map((t) => (
              <tr key={t.id} className="hover:bg-slate-50">
                <Td className="font-medium text-slate-700">{t.social_reason}</Td>
                <Td>{t.company_name || "—"}</Td>
                <Td>{t.cnpj ? maskCnpj(t.cnpj) : "—"}</Td>
                <Td>{t.user_count}</Td>
                <Td>
                  <Badge tone={t.active ? "green" : "slate"}>
                    {t.active ? "Ativo" : "Inativo"}
                  </Badge>
                </Td>
                <Td>
                  <button
                    onClick={() => openEdit(t)}
                    className="text-xs font-medium text-brand-600 hover:underline"
                  >
                    Editar
                  </button>
                </Td>
              </tr>
            ))}
            {tenants.data && tenants.data.length === 0 && (
              <EmptyRow colSpan={6} message="Nenhum tenant encontrado." />
            )}
          </tbody>
        </Table>
      </Card>

      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title={editing ? "Editar tenant" : "Novo tenant"}
        footer={
          <>
            <Button variant="secondary" onClick={() => setModal(false)}>
              Cancelar
            </Button>
            <Button onClick={submit} disabled={isSaving}>
              {isSaving ? "Salvando…" : "Salvar"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <Input
            label="Razão social"
            value={form.social_reason}
            onChange={(e) =>
              setForm({ ...form, social_reason: e.target.value })
            }
          />
          <Input
            label="Nome fantasia"
            value={form.company_name}
            onChange={(e) => setForm({ ...form, company_name: e.target.value })}
          />
          <Input
            label="CNPJ"
            inputMode="numeric"
            placeholder="00.000.000/0000-00"
            maxLength={18}
            value={form.cnpj}
            onChange={(e) =>
              setForm({ ...form, cnpj: maskCnpj(e.target.value) })
            }
          />
          <Input
            label="E-mail"
            type="email"
            placeholder="contato@empresa.com.br"
            value={form.email}
            onChange={(e) =>
              setForm({ ...form, email: maskEmail(e.target.value) })
            }
          />
          <Input
            label="Telefone"
            inputMode="tel"
            placeholder="(00) 00000-0000"
            maxLength={16}
            value={form.phone}
            onChange={(e) =>
              setForm({ ...form, phone: maskPhone(e.target.value) })
            }
          />
          {editing && (
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={form.active}
                onChange={(e) =>
                  setForm({ ...form, active: e.target.checked })
                }
              />
              Tenant ativo
            </label>
          )}
          {error && <ErrorNote>{error}</ErrorNote>}
        </div>
      </Modal>
    </>
  );
}
