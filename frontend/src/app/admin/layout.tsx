"use client";

/**
 * Guard for the administrative area.
 *
 * "Administração" left the sidebar and moved into the user dropdown, so this
 * layout is what keeps the screens reachable *and* protected:
 *
 * * a user without an administrative permission sees an explicit "no access"
 *   message instead of a silently broken screen;
 * * the backend keeps enforcing the same rule on every ``/api/admin/*``
 *   endpoint — this guard is UX, not the security boundary.
 */

import Link from "next/link";

import { useAuth } from "@/app/auth-context";
import AppShell from "@/components/AppShell";
import { ADMIN_PERMISSION } from "@/components/UserMenu";

/** Any one of these grants access to the administrative area. */
const ADMIN_PERMISSIONS = [
  ADMIN_PERMISSION,
  "USER_VIEW",
  "TENANT_VIEW",
  "MODULE_VIEW",
  "ROLE_VIEW",
  "AUDIT_VIEW",
];

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, has } = useAuth();
  const allowed =
    !!user && (user.is_master_admin || ADMIN_PERMISSIONS.some((p) => has(p)));

  if (user && !allowed) {
    return (
      <AppShell>
        <div className="mx-auto max-w-xl rounded-xl border border-gray-100 bg-white p-8 text-center shadow-card">
          <h1 className="text-lg font-semibold text-slate-800">
            Acesso restrito
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            Sua conta não possui permissão administrativa. Solicite acesso ao
            administrador do tenant.
          </p>
          <Link
            href="/dashboard"
            className="mt-4 inline-flex rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >
            Voltar à Visão Geral
          </Link>
        </div>
      </AppShell>
    );
  }

  return <AppShell>{children}</AppShell>;
}
