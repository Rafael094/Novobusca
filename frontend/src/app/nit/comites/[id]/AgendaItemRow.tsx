"use client";

import { useState } from "react";

import {
  Badge,
  Button,
  ErrorNote,
  Select,
} from "@/components/ui";
import { useCastVote, useDecideItem, useItemVotes } from "@/lib/hooks";
import { useAuth } from "@/app/auth-context";
import type { NitAgendaItem } from "@/lib/types";

const OUTCOME_LABELS: Record<string, string> = {
  APPROVED: "Aprovado",
  REJECTED: "Rejeitado",
  DEFERRED: "Adiado",
};

/** One agenda item: vote tally, vote casting and final decision controls. */
export function AgendaItemRow({
  item,
  members,
}: {
  item: NitAgendaItem;
  members: { id: string; name: string }[];
}) {
  const { has } = useAuth();
  const { data: tally } = useItemVotes(item.id);
  const castVote = useCastVote(item.id);
  const decide = useDecideItem(item.id);
  const [memberId, setMemberId] = useState(members[0]?.id ?? "");
  const [vote, setVote] = useState("APPROVE");
  const [conflict, setConflict] = useState(false);
  const [outcome, setOutcome] = useState("APPROVED");

  const canVote = has("NIT_COMMITTEE_VOTE");
  const canDecide = has("NIT_COMMITTEE_DECIDE");

  return (
    <li className="rounded-lg border border-gray-100 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium text-slate-700">{item.title}</p>
        <Badge tone={item.status === "DECIDED" ? "green" : "amber"}>
          {item.status === "DECIDED" ? "Decidido" : "Pendente"}
        </Badge>
      </div>

      {tally ? (
        <p className="mt-1 text-xs text-slate-500">
          Aprovações {tally.approvals} · Rejeições {tally.rejections} · Abstenções{" "}
          {tally.abstentions} · Impedidos {tally.impeded} · Quórum{" "}
          {tally.valid}/{tally.quorum}
        </p>
      ) : null}

      {canVote && members.length > 0 ? (
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <div className="min-w-[160px]">
            <Select
              label="Membro"
              value={memberId}
              onChange={(e) => setMemberId(e.target.value)}
            >
              {members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="min-w-[130px]">
            <Select
              label="Voto"
              value={vote}
              onChange={(e) => setVote(e.target.value)}
            >
              <option value="APPROVE">Aprovar</option>
              <option value="REJECT">Rejeitar</option>
              <option value="ABSTAIN">Abster-se</option>
            </Select>
          </div>
          <label className="flex items-center gap-2 pb-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={conflict}
              onChange={(e) => setConflict(e.target.checked)}
            />
            Conflito de interesse
          </label>
          <Button
            variant="secondary"
            disabled={castVote.isPending}
            onClick={() =>
              castVote.mutate({
                member_id: memberId,
                vote,
                conflict_of_interest: conflict,
              })
            }
          >
            {castVote.isPending ? "Registrando…" : "Votar"}
          </Button>
        </div>
      ) : null}

      {canDecide && item.status !== "DECIDED" ? (
        <div className="mt-3 flex flex-wrap items-end gap-2 border-t border-gray-50 pt-3">
          <div className="min-w-[160px]">
            <Select
              label="Decisão"
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
            >
              <option value="APPROVED">Aprovar</option>
              <option value="REJECTED">Rejeitar</option>
              <option value="DEFERRED">Adiar</option>
            </Select>
          </div>
          <Button
            disabled={decide.isPending}
            onClick={() => decide.mutate({ outcome })}
          >
            {decide.isPending ? "Registrando…" : "Registrar decisão"}
          </Button>
        </div>
      ) : null}

      {castVote.error ? (
        <div className="mt-2">
          <ErrorNote>{(castVote.error as Error).message}</ErrorNote>
        </div>
      ) : null}
      {decide.error ? (
        <div className="mt-2">
          <ErrorNote>{(decide.error as Error).message}</ErrorNote>
        </div>
      ) : null}
    </li>
  );
}
