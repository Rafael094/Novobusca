"use client";

import { useState } from "react";

import AppShell from "@/components/AppShell";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyRow,
  ErrorNote,
  Input,
  Modal,
  Select,
  Spinner,
  Table,
  Td,
  Th,
} from "@/components/ui";
import {
  useAdminRoles,
  useAdminTenants,
  useAdminUsers,
  useCreateUser,
  useDeactivateUser,
  useUpdateUser,
} from "@/lib/hooks";
import type { AdminUser } from "@/lib/types";
import { maskEmail } from "@/lib/masks";
import { useAuth } from "@/app/auth-context";

export default function UsuariosPage() {
  const { user } = useAuth();
  const users = useAdminUsers();
  const tenants = useAdminTenants();
  const roles = useAdminRoles();
  const create = useCreateUser();
  const update = useUpdateUser();
  const deactivate = useDeactivateUser();

  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    access_code: "",
    email: "",
    password: "",
    tenant_id: "",
    role_ids: [] as string[],
  });

  const isMaster = user?.is_master_admin ?? false;
  const isSaving = create.isPending || update.isPending;

  function openCreate() {
    setEditing(null);
    setForm({ access_code: "", email: "", password: "", tenant_id: "", role_ids: [] });
    setError(null);
    setModal(true);
  }

  function openEdit(u: AdminUser) {
    setEditing(u);
    setForm({
      access_code: u.access_code,
      email: u.email,
      password: "",
      tenant_id: u.tenant_id ?? "",
      role_ids: u.roles.map((r) => r.id),
    });
    setError(null);
    setModal(true);
  }

  async function submit() {
    setError(null);
    try {
      if (editing) {
        // ``UserUpdate`` accepts access_code/email/active/role_ids.
        await update.mutateAsync({
          id: editing.id,
          access_code: form.access_code,
          email: form.email,
          role_ids: form.role_ids,
        });
      } else {
        await create.mutateAsync({
          access_code: form.access_code || form.email,
          email: form.email,
          name: form.email.split("@")[0],
          password: form.password,
          tenant_id: form.tenant_id || undefined,
          role_ids: form.role_ids,
        });
      }
      setModal(false);
      setEditing(null);
      setForm({ access_code: "", email: "", password: "", tenant_id: "", role_ids: [] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar.");
    }
  }

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Usuários</h1>
          <p className="text-sm text-slate-500">
            Gestão de usuários vinculados ao tenant.
          </p>
        </div>
        <Button onClick={openCreate}>+ Novo usuário</Button>
      </div>

      <Card>
        <CardHeader title="Usuários cadastrados" />
        <Table>
          <thead className="bg-slate-50">
            <tr>
              <Th>Nome</Th>
              <Th>E-mail</Th>
              <Th>Tenant</Th>
              <Th>Papéis</Th>
              <Th>Status</Th>
              <Th />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {users.isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-6">
                  <Spinner />
                </td>
              </tr>
            )}
            {users.data?.map((u) => (
              <tr key={u.id} className="hover:bg-slate-50">
                <Td className="font-medium text-slate-700">{u.email}</Td>
                <Td>{u.access_code}</Td>
                <Td>{u.is_master_admin ? "—" : u.tenant_name || "—"}</Td>
                <Td>
                  <div className="flex flex-wrap gap-1">
                    {u.roles.map((r) => (
                      <Badge key={r.id} tone="blue">
                        {r.code}
                      </Badge>
                    ))}
                    {u.roles.length === 0 && "—"}
                  </div>
                </Td>
                <Td>
                  <Badge tone={u.active ? "green" : "slate"}>
                    {u.active ? "Ativo" : "Inativo"}
                  </Badge>
                </Td>
                <Td>
                  <div className="flex gap-2">
                    <button
                      onClick={() => openEdit(u)}
                      className="text-xs font-medium text-brand-600 hover:underline"
                    >
                      Editar
                    </button>
                    <button
                      onClick={() => update.mutate({ id: u.id, active: !u.active })}
                      className="text-xs font-medium text-brand-600 hover:underline"
                    >
                      {u.active ? "Suspender" : "Ativar"}
                    </button>
                    {!u.is_master_admin && (
                      <button
                        onClick={() => deactivate.mutate(u.id)}
                        className="text-xs font-medium text-red-600 hover:underline"
                      >
                        Excluir
                      </button>
                    )}
                  </div>
                </Td>
              </tr>
            ))}
            {users.data && users.data.length === 0 && (
              <EmptyRow colSpan={6} message="Nenhum usuário encontrado." />
            )}
          </tbody>
        </Table>
      </Card>

      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title={editing ? "Editar usuário" : "Novo usuário"}
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
            label="Login (AccessCode)"
            placeholder="Deixe em branco para usar o e-mail"
            value={form.access_code}
            onChange={(e) => setForm({ ...form, access_code: e.target.value })}
          />
          <Input
            label="E-mail"
            type="email"
            placeholder="usuario@empresa.com.br"
            value={form.email}
            onChange={(e) =>
              setForm({ ...form, email: maskEmail(e.target.value) })
            }
          />
          {!editing && (
            <Input
              label="Senha (mín. 8)"
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          )}
          {isMaster && !editing && (
            <Select
              label="Tenant"
              value={form.tenant_id}
              onChange={(e) => setForm({ ...form, tenant_id: e.target.value })}
            >
              <option value="">Selecione…</option>
              {tenants.data?.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.social_reason}
                </option>
              ))}
            </Select>
          )}
          <div>
            <span className="mb-1 block text-sm font-medium text-slate-700">
              Papéis
            </span>
            <div className="flex flex-wrap gap-2">
              {roles.data?.map((r) => {
                const selected = form.role_ids.includes(r.id);
                return (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() =>
                      setForm({
                        ...form,
                        role_ids: selected
                          ? form.role_ids.filter((x) => x !== r.id)
                          : [...form.role_ids, r.id],
                      })
                    }
                    className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
                      selected
                        ? "border-brand-600 bg-brand-600 text-white"
                        : "border-gray-200 text-slate-600 hover:border-brand-300"
                    }`}
                  >
                    {r.name}
                  </button>
                );
              })}
            </div>
          </div>
          {error && <ErrorNote>{error}</ErrorNote>}
        </div>
      </Modal>
    </AppShell>
  );
}
