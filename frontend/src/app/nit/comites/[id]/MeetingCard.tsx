"use client";

import { useState } from "react";

import {
  Badge,
  Button,
  ErrorNote,
  Input,
  Spinner,
} from "@/components/ui";
import {
  useAddAgendaItem,
  useNitAgendaItems,
} from "@/lib/hooks";
import { useAuth } from "@/app/auth-context";
import { AgendaItemRow } from "./AgendaItemRow";

/** A meeting card: agenda items, add-item form and per-item voting/decision. */
export function MeetingCard({
  meeting,
  members,
}: {
  meeting: { id: string; title: string; scheduled_at: string; status: string };
  members: { id: string; name: string }[];
}) {
  const { has } = useAuth();
  const { data: items, isLoading } = useNitAgendaItems(meeting.id);
  const addItem = useAddAgendaItem(meeting.id);
  const [title, setTitle] = useState("");

  const canManage = has("NIT_COMMITTEE_MEETING_MANAGE");

  return (
    <div className="rounded-lg border border-gray-100">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-50 px-4 py-3">
        <div>
          <p className="text-sm font-medium text-slate-700">{meeting.title}</p>
          <p className="text-xs text-slate-400">
            {new Date(meeting.scheduled_at).toLocaleString("pt-BR")} ·{" "}
            <Badge tone="slate">{meeting.status}</Badge>
          </p>
        </div>
      </div>

      <div className="px-4 py-3">
        {isLoading ? (
          <Spinner />
        ) : items && items.length > 0 ? (
          <ul className="space-y-3">
            {items.map((item) => (
              <AgendaItemRow key={item.id} item={item} members={members} />
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-400">Nenhum item de pauta.</p>
        )}

        {canManage && (
          <div className="mt-4 flex flex-wrap items-end gap-2">
            <div className="min-w-[240px] flex-1">
              <Input
                label="Adicionar item à pauta"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <Button
              variant="secondary"
              disabled={!title.trim() || addItem.isPending}
              onClick={() =>
                addItem.mutate(
                  { title },
                  { onSuccess: () => setTitle("") },
                )
              }
            >
              {addItem.isPending ? "Adicionando…" : "Adicionar"}
            </Button>
          </div>
        )}
        {addItem.error ? (
          <div className="mt-3">
            <ErrorNote>{(addItem.error as Error).message}</ErrorNote>
          </div>
        ) : null}
      </div>
    </div>
  );
}
