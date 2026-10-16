"use client";

import { useState } from "react";

import AppShell from "@/components/AppShell";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorNote,
  Select,
  Spinner,
} from "@/components/ui";
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNitNotifications,
  useNitNotificationPreferences,
  useUpsertNotificationPreference,
} from "@/lib/hooks";

const KINDS = [
  "DISCLOSURE_STATUS",
  "EVALUATION_ASSIGNED",
  "NEGOTIATION_UPDATE",
  "OBLIGATION_DUE",
  "PORTAL_REQUEST",
  "GENERIC",
];

export default function NotificationsPage() {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useNitNotifications({
    unread_only: unreadOnly || undefined,
    page,
    page_size: 20,
  });
  const markRead = useMarkNotificationRead();
  const markAll = useMarkAllNotificationsRead();

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Notificações</h1>
          <p className="text-sm text-slate-500">
            Avisos in-app endereçados a você. E-mails são apenas enfileirados até que um
            provedor real os envie.
          </p>
        </div>
        <div className="flex items-end gap-3">
          <label className="flex items-center gap-2 pb-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={unreadOnly}
              onChange={(e) => {
                setPage(1);
                setUnreadOnly(e.target.checked);
              }}
            />
            Somente não lidas
          </label>
          <Button variant="secondary" onClick={() => markAll.mutate()} disabled={markAll.isPending}>
            Marcar todas como lidas
          </Button>
        </div>
      </div>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}
      {isLoading ? <Spinner /> : null}

      {data ? (
        <Card className="mb-6">
          <CardHeader
            title="Caixa de entrada"
            subtitle={`${data.unread} não lida(s) de ${data.total}`}
          />
          <CardBody className="p-0">
            {data.items.length === 0 ? (
              <div className="p-5">
                <EmptyState title="Nenhuma notificação" />
              </div>
            ) : (
              <ul className="divide-y divide-gray-50">
                {data.items.map((n) => (
                  <li
                    key={n.id}
                    className={`flex items-start justify-between gap-3 px-5 py-3 ${
                      n.read_at ? "" : "bg-brand-50/40"
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge
                          tone={
                            n.severity === "CRITICAL"
                              ? "red"
                              : n.severity === "WARNING"
                                ? "amber"
                                : "slate"
                          }
                        >
                          {n.kind}
                        </Badge>
                        <span className="font-medium text-slate-800">{n.title}</span>
                      </div>
                      {n.body ? (
                        <p className="mt-1 text-sm text-slate-500">{n.body}</p>
                      ) : null}
                      <p className="mt-1 text-xs text-slate-400">
                        {new Date(n.created_at).toLocaleString("pt-BR")}
                      </p>
                    </div>
                    {n.read_at ? (
                      <span className="text-xs text-slate-400">Lida</span>
                    ) : (
                      <Button
                        variant="secondary"
                        onClick={() => markRead.mutate(n.id)}
                        disabled={markRead.isPending}
                      >
                        Marcar lida
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      ) : null}

      <Card>
        <CardHeader title="Preferências de e-mail" subtitle="E-mail é opt-in por tipo" />
        <CardBody>
          <PreferenceEditor />
        </CardBody>
      </Card>
    </AppShell>
  );
}

function PreferenceEditor() {
  const { data: prefs } = useNitNotificationPreferences();
  const upsert = useUpsertNotificationPreference();
  const [kind, setKind] = useState("GENERIC");
  const existing = prefs?.find((p) => p.kind === kind);
  const [emailEnabled, setEmailEnabled] = useState(false);

  return (
    <div className="grid gap-3 sm:grid-cols-4">
      <Select label="Tipo" value={kind} onChange={(e) => setKind(e.target.value)}>
        {KINDS.map((k) => (
          <option key={k} value={k}>
            {k}
          </option>
        ))}
      </Select>
      <label className="flex items-end gap-2 pb-2 text-sm text-slate-600">
        <input
          type="checkbox"
          checked={emailEnabled}
          onChange={(e) => setEmailEnabled(e.target.checked)}
        />
        Receber por e-mail
      </label>
      <div className="flex items-end text-xs text-slate-400">
        Atual: {existing ? (existing.email_enabled ? "ativo" : "inativo") : "não definido"}
      </div>
      <div className="flex items-end">
        <Button
          disabled={upsert.isPending}
          onClick={() =>
            upsert.mutate({
              kind,
              in_app_enabled: true,
              email_enabled: emailEnabled,
            })
          }
        >
          Salvar preferência
        </Button>
      </div>
    </div>
  );
}
