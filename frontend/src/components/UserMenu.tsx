"use client";

/**
 * UserMenu — the header's user dropdown.
 *
 * It is the single place where the account actions live now that
 * "Administração" is no longer a sidebar entry. The admin item is rendered only
 * when the user actually holds an administrative permission **and** the backend
 * keeps enforcing the same rule (see the ``/api/admin/*`` routers), so hiding it
 * here is a convenience, never the security boundary.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/app/auth-context";

/** Permission that gates the administrative area (matches ``AppShell``). */
export const ADMIN_PERMISSION = "SYNC_VIEW";

export function UserMenu() {
  const { user, logout, has } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function onClick(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  if (!user) return null;

  const canAdmin = has(ADMIN_PERMISSION) || user.is_master_admin;
  const initials = user.name?.trim().charAt(0).toUpperCase() || "?";

  async function handleLogout() {
    setOpen(false);
    await logout();
    router.push("/login");
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Menu do usuário"
        className="flex items-center gap-3 rounded-lg px-1 py-1 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
      >
        <div className="hidden text-right sm:block">
          <p className="text-sm font-medium text-slate-800">{user.name}</p>
          <p className="text-xs text-slate-500">
            {user.is_master_admin ? "Master Admin" : user.tenant_name || "Sem tenant"}
          </p>
        </div>
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white">
          {initials}
        </span>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          className={`hidden text-slate-400 transition-transform sm:block ${
            open ? "rotate-180" : ""
          }`}
          aria-hidden="true"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 w-64 overflow-hidden rounded-xl border border-gray-100 bg-white shadow-soft"
        >
          <div className="border-b border-gray-100 px-4 py-3">
            <p className="truncate text-sm font-semibold text-slate-800">
              {user.name}
            </p>
            <p className="truncate text-xs text-slate-500">{user.email}</p>
            <p className="mt-1 text-xs text-slate-400">
              {user.is_master_admin
                ? "Master Admin"
                : user.tenant_name || "Sem tenant"}
            </p>
          </div>

          <div className="py-1">
            <Link
              href="/perfil"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="block px-4 py-2 text-sm text-slate-600 transition hover:bg-slate-50 hover:text-slate-800"
            >
              Meu perfil
            </Link>

            {canAdmin && (
              <>
                <Link
                  href="/admin/usuarios"
                  role="menuitem"
                  onClick={() => setOpen(false)}
                  className="block px-4 py-2 text-sm text-slate-600 transition hover:bg-slate-50 hover:text-slate-800"
                >
                  Usuários
                </Link>
                <Link
                  href="/admin"
                  role="menuitem"
                  onClick={() => setOpen(false)}
                  className="block px-4 py-2 text-sm font-medium text-brand-700 transition hover:bg-brand-50"
                >
                  Administração
                </Link>
              </>
            )}
          </div>

          <div className="border-t border-gray-100 py-1">
            <button
              type="button"
              role="menuitem"
              onClick={handleLogout}
              className="block w-full px-4 py-2 text-left text-sm text-slate-600 transition hover:bg-slate-50 hover:text-slate-800"
            >
              Sair
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default UserMenu;
