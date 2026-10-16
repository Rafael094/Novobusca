"use client";

import { Card, CardBody, CardHeader } from "@/components/ui";

export function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardBody>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
        <p className="mt-1 text-2xl font-bold text-slate-800">{value}</p>
      </CardBody>
    </Card>
  );
}

export function GroupCard({
  title,
  data,
}: {
  title: string;
  data: Record<string, number>;
}) {
  const entries = Object.entries(data);
  return (
    <Card>
      <CardHeader title={title} />
      <CardBody>
        {entries.length === 0 ? (
          <p className="text-sm text-slate-400">Sem dados.</p>
        ) : (
          <ul className="divide-y divide-gray-50">
            {entries.map(([k, v]) => (
              <li key={k} className="flex items-center justify-between py-1.5 text-sm">
                <span className="text-slate-600">{k}</span>
                <span className="font-medium text-slate-800">{v}</span>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

export function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="text-slate-700">{value}</dd>
    </div>
  );
}

export function fmtMoney(v: string) {
  return `R$ ${Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`;
}
