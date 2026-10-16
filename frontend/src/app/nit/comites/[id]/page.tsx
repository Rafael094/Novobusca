"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
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
  Spinner,
} from "@/components/ui";
import { useNitCommittee, useNitMeetings } from "@/lib/hooks";
import { useAuth } from "@/app/auth-context";
import { AddMemberModal } from "./AddMemberModal";
import { NewMeetingModal } from "./NewMeetingModal";
import { MeetingCard } from "./MeetingCard";

export default function CommitteeDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? null;
  const { has } = useAuth();
  const { data, isLoading, error } = useNitCommittee(id);
  const [openMember, setOpenMember] = useState(false);
  const [openMeeting, setOpenMeeting] = useState(false);

  const canManage = has("NIT_COMMITTEE_MANAGE");
  const canManageMeetings = has("NIT_COMMITTEE_MEETING_MANAGE");

  return (
    <AppShell>
      <div className="mb-4">
        <Link href="/nit/comites" className="text-sm text-brand-700 hover:underline">
          ← Voltar para comitês
        </Link>
      </div>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}
      {isLoading ? <Spinner /> : null}

      {data ? (
        <>
          <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                {data.code}
              </p>
              <h1 className="text-2xl font-bold text-slate-800">{data.name}</h1>
              <p className="text-sm text-slate-500">
                Quórum mínimo: {data.quorum} ·{" "}
                {data.simple_majority ? "maioria simples" : "sem maioria exigida"}
              </p>
            </div>
            {canManage && (
              <Button variant="secondary" onClick={() => setOpenMember(true)}>
                Adicionar membro
              </Button>
            )}
          </div>

          <Card className="mb-6">
            <CardHeader title="Membros" />
            <CardBody>
              {data.members.length === 0 ? (
                <EmptyState title="Nenhum membro cadastrado" />
              ) : (
                <ul className="divide-y divide-gray-50">
                  {data.members.map((m) => (
                    <li
                      key={m.id}
                      className="flex items-center justify-between py-2"
                    >
                      <span className="text-sm text-slate-700">
                        {m.name}
                        {m.role_title ? ` — ${m.role_title}` : ""}
                      </span>
                      <Badge tone={m.kind === "VOTING" ? "blue" : "slate"}>
                        {m.kind === "VOTING" ? "Votante" : "Consultivo"}
                      </Badge>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Reuniões e pautas"
              action={
                canManageMeetings ? (
                  <Button variant="secondary" onClick={() => setOpenMeeting(true)}>
                    Nova reunião
                  </Button>
                ) : undefined
              }
            />
            <CardBody>
              <MeetingsSection committeeId={data.id} members={data.members} />
            </CardBody>
          </Card>

          <AddMemberModal
            committeeId={data.id}
            open={openMember}
            onClose={() => setOpenMember(false)}
          />
          <NewMeetingModal
            committeeId={data.id}
            open={openMeeting}
            onClose={() => setOpenMeeting(false)}
          />
        </>
      ) : null}
    </AppShell>
  );
}

function MeetingsSection({
  committeeId,
  members,
}: {
  committeeId: string;
  members: { id: string; name: string }[];
}) {
  const { data, isLoading } = useNitMeetings(committeeId);
  if (isLoading) return <Spinner />;
  if (!data || data.length === 0) {
    return <EmptyState title="Nenhuma reunião registrada" />;
  }
  return (
    <div className="space-y-4">
      {data.map((meeting) => (
        <MeetingCard key={meeting.id} meeting={meeting} members={members} />
      ))}
    </div>
  );
}
