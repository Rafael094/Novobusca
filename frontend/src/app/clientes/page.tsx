"use client";

import { useState } from "react";
import Link from "next/link";

import AppShell from "@/components/AppShell";
import {
  Badge,
  Button,
  Card,
  CardBody,
  EmptyRow,
  ErrorNote,
  Input,
  Modal,
  Pagination,
  Spinner,
  Table,
  Tabs,
  Td,
  Th,
} from "@/components/ui";
import {
  useCompanies,
  useCreateCompany,
  useCreateCustomer,
  useCreatePerson,
  useCustomers,
  useDeleteCompany,
  useDeleteCustomer,
  usePeople,
  useUpdateCompany,
  useUpdateCustomer,
  useUpdatePerson,
} from "@/lib/hooks";
import type { Company, Customer, Person } from "@/lib/types";
import {
  maskCnpj,
  maskCpf,
  maskCpfCnpj,
  maskEmail,
  maskPhone,
  maskUf,
} from "@/lib/masks";

export default function ClientesPage() {
  const [tab, setTab] = useState("companies");
  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Clientes</h1>
        <p className="text-sm text-slate-500">
          Empresas, clientes e pessoas vinculados ao seu tenant.
        </p>
      </div>

      <Card>
        <Tabs
          active={tab}
          onChange={setTab}
          tabs={[
            { id: "companies", label: "Empresas" },
            { id: "customers", label: "Clientes" },
            { id: "people", label: "Pessoas" },
          ]}
        />
        <CardBody>
          {tab === "companies" && <CompaniesTab />}
          {tab === "customers" && <CustomersTab />}
          {tab === "people" && <PeopleTab />}
        </CardBody>
      </Card>
    </AppShell>
  );
}

type CompanyForm = {
  company_name: string;
  social_reason: string;
  external_id: string;
  cnpj: string;
  email: string;
  phone: string;
};

const EMPTY_COMPANY: CompanyForm = {
  company_name: "",
  social_reason: "",
  external_id: "",
  cnpj: "",
  email: "",
  phone: "",
};

// --- Companies --------------------------------------------------------------
function CompaniesTab() {
  const [q, setQ] = useState("");
  const [active, setActive] = useState("");
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState<Company | null>(null);
  const [form, setForm] = useState<CompanyForm>(EMPTY_COMPANY);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading, error: qError } = useCompanies({
    q: q || undefined,
    active: active === "" ? undefined : active === "true",
    page,
    page_size: 20,
  });
  const create = useCreateCompany();
  const update = useUpdateCompany();
  const remove = useDeleteCompany();

  const isSaving = create.isPending || update.isPending;

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_COMPANY);
    setError(null);
    setModal(true);
  }

  function openEdit(c: Company) {
    setEditing(c);
    setForm({
      company_name: c.company_name,
      social_reason: c.social_reason ?? "",
      external_id: c.external_id ?? "",
      cnpj: c.cnpj ? maskCnpj(c.cnpj) : "",
      email: c.email ?? "",
      phone: c.phone ? maskPhone(c.phone) : "",
    });
    setError(null);
    setModal(true);
  }

  async function submit() {
    setError(null);
    try {
      const payload = {
        company_name: form.company_name,
        social_reason: form.social_reason || null,
        external_id: form.external_id || null,
        cnpj: form.cnpj || null,
        email: form.email || null,
        phone: form.phone || null,
      };
      if (editing) {
        await update.mutateAsync({ id: editing.id, ...payload });
      } else {
        await create.mutateAsync(payload);
      }
      setModal(false);
      setEditing(null);
      setForm(EMPTY_COMPANY);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar.");
    }
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          placeholder="Buscar empresa, CNPJ…"
          className="min-w-[220px] flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-brand-500"
        />
        <select
          value={active}
          onChange={(e) => {
            setActive(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-brand-500"
        >
          <option value="">Todos os status</option>
          <option value="true">Ativos</option>
          <option value="false">Inativos</option>
        </select>
        <Button onClick={openCreate}>+ Nova empresa</Button>
      </div>

      {qError && (
        <div className="mb-3">
          <ErrorNote>
            {qError instanceof Error ? qError.message : "Erro ao carregar."}
          </ErrorNote>
        </div>
      )}

      <div className="rounded-xl border border-gray-100">
        <Table>
          <thead className="bg-slate-50">
            <tr>
              <Th>Empresa</Th>
              <Th>CNPJ</Th>
              <Th>External ID</Th>
              <Th>Clientes</Th>
              <Th>Unidades</Th>
              <Th>Status</Th>
              <Th />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading && (
              <tr>
                <td colSpan={7} className="px-4 py-6">
                  <Spinner />
                </td>
              </tr>
            )}
            {data?.items.map((c) => (
              <tr key={c.id} className="hover:bg-slate-50">
                <Td className="font-medium text-slate-700">
                  {c.company_name}
                  {c.social_reason && (
                    <span className="block text-xs text-slate-400">
                      {c.social_reason}
                    </span>
                  )}
                </Td>
                <Td>{c.cnpj ? maskCnpj(c.cnpj) : "—"}</Td>
                <Td>{c.external_id || "—"}</Td>
                <Td>{c.customer_count}</Td>
                <Td>{c.unity_count}</Td>
                <Td>
                  <Badge tone={c.active ? "green" : "slate"}>
                    {c.active ? "Ativo" : "Inativo"}
                  </Badge>
                </Td>
                <Td>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => openEdit(c)}
                      className="text-xs font-medium text-brand-600 hover:underline"
                    >
                      Editar
                    </button>
                    <button
                      onClick={() => remove.mutate(c.id)}
                      className="text-xs font-medium text-red-600 hover:underline"
                    >
                      Desativar
                    </button>
                  </div>
                </Td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <EmptyRow colSpan={7} message="Nenhuma empresa encontrada." />
            )}
          </tbody>
        </Table>
        <Pagination
          page={page}
          pageSize={20}
          total={data?.pagination.total ?? 0}
          onPage={setPage}
        />
      </div>

      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title={editing ? "Editar empresa" : "Nova empresa"}
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
            label="Nome da empresa"
            value={form.company_name}
            onChange={(e) => setForm({ ...form, company_name: e.target.value })}
          />
          <Input
            label="Razão social"
            value={form.social_reason}
            onChange={(e) => setForm({ ...form, social_reason: e.target.value })}
          />
          <Input
            label="External ID"
            placeholder="Chave no sistema de origem (ERP)"
            value={form.external_id}
            onChange={(e) => setForm({ ...form, external_id: e.target.value })}
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
          {error && <ErrorNote>{error}</ErrorNote>}
        </div>
      </Modal>
    </div>
  );
}

// --- Customers --------------------------------------------------------------
type CustomerForm = {
  name: string;
  code: string;
  document: string;
  email: string;
  phone: string;
};

const EMPTY_CUSTOMER: CustomerForm = {
  name: "",
  code: "",
  document: "",
  email: "",
  phone: "",
};

function CustomersTab() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [form, setForm] = useState<CustomerForm>(EMPTY_CUSTOMER);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading, error: qError } = useCustomers({
    q: q || undefined,
    page,
    page_size: 20,
  });
  const create = useCreateCustomer();
  const update = useUpdateCustomer();
  const remove = useDeleteCustomer();

  const isSaving = create.isPending || update.isPending;

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_CUSTOMER);
    setError(null);
    setModal(true);
  }

  function openEdit(c: Customer) {
    setEditing(c);
    setForm({
      name: c.name,
      code: c.code ?? "",
      document: c.document ? maskCpfCnpj(c.document) : "",
      email: c.email ?? "",
      phone: c.phone ? maskPhone(c.phone) : "",
    });
    setError(null);
    setModal(true);
  }

  async function submit() {
    setError(null);
    try {
      const payload = {
        name: form.name,
        code: form.code || null,
        document: form.document || null,
        email: form.email || null,
        phone: form.phone || null,
      };
      if (editing) {
        await update.mutateAsync({ id: editing.id, ...payload });
      } else {
        await create.mutateAsync(payload);
      }
      setModal(false);
      setEditing(null);
      setForm(EMPTY_CUSTOMER);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar.");
    }
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          placeholder="Buscar cliente…"
          className="min-w-[220px] flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-brand-500"
        />
        <Button onClick={openCreate}>+ Novo cliente</Button>
      </div>

      {qError && (
        <div className="mb-3">
          <ErrorNote>
            {qError instanceof Error ? qError.message : "Erro ao carregar."}
          </ErrorNote>
        </div>
      )}

      <div className="rounded-xl border border-gray-100">
        <Table>
          <thead className="bg-slate-50">
            <tr>
              <Th>Nome</Th>
              <Th>Código</Th>
              <Th>Documento</Th>
              <Th>Empresa</Th>
              <Th>Status</Th>
              <Th />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-6">
                  <Spinner />
                </td>
              </tr>
            )}
            {data?.items.map((c) => (
              <tr key={c.id} className="hover:bg-slate-50">
                <Td className="font-medium text-slate-700">{c.name}</Td>
                <Td>{c.code || "—"}</Td>
                <Td>{c.document ? maskCpfCnpj(c.document) : "—"}</Td>
                <Td>{c.company_name || "—"}</Td>
                <Td>
                  <Badge tone={c.active ? "green" : "slate"}>
                    {c.active ? "Ativo" : "Inativo"}
                  </Badge>
                </Td>
                <Td>
                  <div className="flex items-center gap-3">
                    <Link
                      href={`/clientes/${c.id}`}
                      className="text-xs font-medium text-brand-600 hover:underline"
                    >
                      Abrir
                    </Link>
                    <button
                      onClick={() => openEdit(c)}
                      className="text-xs font-medium text-slate-500 hover:underline"
                    >
                      Editar
                    </button>
                    <button
                      onClick={() => remove.mutate(c.id)}
                      className="text-xs font-medium text-red-600 hover:underline"
                    >
                      Desativar
                    </button>
                  </div>
                </Td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <EmptyRow colSpan={6} message="Nenhum cliente encontrado." />
            )}
          </tbody>
        </Table>
        <Pagination
          page={page}
          pageSize={20}
          total={data?.pagination.total ?? 0}
          onPage={setPage}
        />
      </div>

      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title={editing ? "Editar cliente" : "Novo cliente"}
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
            label="Nome"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <Input
            label="Código interno"
            value={form.code}
            onChange={(e) => setForm({ ...form, code: e.target.value })}
          />
          <Input
            label="CPF/CNPJ"
            inputMode="numeric"
            placeholder="000.000.000-00"
            maxLength={18}
            value={form.document}
            onChange={(e) =>
              setForm({ ...form, document: maskCpfCnpj(e.target.value) })
            }
          />
          <Input
            label="E-mail"
            type="email"
            placeholder="cliente@empresa.com.br"
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
          {error && <ErrorNote>{error}</ErrorNote>}
        </div>
      </Modal>
    </div>
  );
}

// --- People -----------------------------------------------------------------
type PersonForm = {
  name: string;
  cpf: string;
  email: string;
  cell_phone: string;
  responsibility: string;
  job_title: string;
};

const EMPTY_PERSON: PersonForm = {
  name: "",
  cpf: "",
  email: "",
  cell_phone: "",
  responsibility: "",
  job_title: "",
};

function PeopleTab() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState<Person | null>(null);
  const [form, setForm] = useState<PersonForm>(EMPTY_PERSON);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading, error: qError } = usePeople({
    q: q || undefined,
    page,
  });
  const create = useCreatePerson();
  const update = useUpdatePerson();

  const isSaving = create.isPending || update.isPending;

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_PERSON);
    setError(null);
    setModal(true);
  }

  function openEdit(p: Person) {
    setEditing(p);
    setForm({
      name: p.name,
      cpf: p.cpf ? maskCpfCnpj(p.cpf) : "",
      email: p.email ?? "",
      cell_phone: p.cell_phone ? maskPhone(p.cell_phone) : "",
      responsibility: p.responsibility ?? "",
      job_title: p.job_title ?? "",
    });
    setError(null);
    setModal(true);
  }

  async function submit() {
    setError(null);
    try {
      const payload = {
        name: form.name,
        cpf: form.cpf || null,
        email: form.email || null,
        cell_phone: form.cell_phone || null,
        responsibility: form.responsibility || null,
        job_title: form.job_title || null,
      };
      if (editing) {
        await update.mutateAsync({ id: editing.id, ...payload });
      } else {
        await create.mutateAsync(payload);
      }
      setModal(false);
      setEditing(null);
      setForm(EMPTY_PERSON);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar.");
    }
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          placeholder="Buscar pessoa…"
          className="min-w-[220px] flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-brand-500"
        />
        <Button onClick={openCreate}>+ Nova pessoa</Button>
      </div>

      {qError && (
        <div className="mb-3">
          <ErrorNote>
            {qError instanceof Error ? qError.message : "Erro ao carregar."}
          </ErrorNote>
        </div>
      )}

      <div className="rounded-xl border border-gray-100">
        <Table>
          <thead className="bg-slate-50">
            <tr>
              <Th>Nome</Th>
              <Th>CPF</Th>
              <Th>Cargo</Th>
              <Th>E-mail</Th>
              <Th>Celular</Th>
              <Th>Status</Th>
              <Th />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading && (
              <tr>
                <td colSpan={7} className="px-4 py-6">
                  <Spinner />
                </td>
              </tr>
            )}
            {data?.items.map((p) => (
              <tr key={p.id} className="hover:bg-slate-50">
                <Td className="font-medium text-slate-700">{p.name}</Td>
                <Td>{p.cpf ? maskCpfCnpj(p.cpf) : "—"}</Td>
                <Td>{p.job_title || "—"}</Td>
                <Td>{p.email || "—"}</Td>
                <Td>{p.cell_phone ? maskPhone(p.cell_phone) : "—"}</Td>
                <Td>
                  <Badge tone={p.active ? "green" : "slate"}>
                    {p.active ? "Ativo" : "Inativo"}
                  </Badge>
                </Td>
                <Td>
                  <button
                    onClick={() => openEdit(p)}
                    className="text-xs font-medium text-brand-600 hover:underline"
                  >
                    Editar
                  </button>
                </Td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <EmptyRow colSpan={7} message="Nenhuma pessoa encontrada." />
            )}
          </tbody>
        </Table>
        <Pagination
          page={page}
          pageSize={20}
          total={data?.pagination.total ?? 0}
          onPage={setPage}
        />
      </div>

      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title={editing ? "Editar pessoa" : "Nova pessoa"}
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
            label="Nome"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <Input
            label="CPF"
            inputMode="numeric"
            placeholder="000.000.000-00"
            maxLength={14}
            value={form.cpf}
            onChange={(e) =>
              setForm({ ...form, cpf: maskCpfCnpj(e.target.value) })
            }
          />
          <Input
            label="Cargo"
            value={form.job_title}
            onChange={(e) => setForm({ ...form, job_title: e.target.value })}
          />
          <Input
            label="Responsabilidade"
            placeholder="Ex.: Diretor, Responsável técnico…"
            value={form.responsibility}
            onChange={(e) =>
              setForm({ ...form, responsibility: e.target.value })
            }
          />
          <Input
            label="E-mail"
            type="email"
            placeholder="pessoa@empresa.com.br"
            value={form.email}
            onChange={(e) =>
              setForm({ ...form, email: maskEmail(e.target.value) })
            }
          />
          <Input
            label="Celular"
            inputMode="tel"
            placeholder="(00) 00000-0000"
            maxLength={16}
            value={form.cell_phone}
            onChange={(e) =>
              setForm({ ...form, cell_phone: maskPhone(e.target.value) })
            }
          />
          {error && <ErrorNote>{error}</ErrorNote>}
        </div>
      </Modal>
    </div>
  );
}
