"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/app/auth-context";

type NavItem = {
  href: string;
  label: string;
  perm: string | null;
  icon: string;
  children?: { href: string; label: string; perm: string | null }[];
};

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Visão Geral", perm: null, icon: "grid" },
  { href: "/clientes", label: "Clientes", perm: "COMPANY_VIEW", icon: "users" },
  { href: "/marcas", label: "Marcas", perm: "MARCAS_SEARCH", icon: "tag" },
  { href: "/patentes", label: "Patentes", perm: "PATENTES_SEARCH", icon: "file" },
  {
    href: "/monitoramento",
    label: "Monitoramento",
    perm: "MARCAS_VIEW",
    icon: "radar",
  },
  {
    href: "/analises",
    label: "Análises IA",
    perm: "MARCAS_SEARCH",
    icon: "sparkles",
  },
  {
    href: "/relatorios",
    label: "Relatórios",
    perm: "RELATORIOS_VIEW",
    icon: "chart",
  },
  {
    href: "/admin",
    label: "Administração",
    perm: "SYNC_VIEW",
    icon: "settings",
    children: [
      { href: "/admin", label: "Sincronização INPI", perm: "SYNC_VIEW" },
      { href: "/admin/usuarios", label: "Usuários", perm: "USER_VIEW" },
      { href: "/admin/tenants", label: "Tenants", perm: "TENANT_VIEW" },
      { href: "/admin/modulos", label: "Módulos & Papéis", perm: "MODULE_VIEW" },
    ],
  },
];

function Icon({ name }: { name: string }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  switch (name) {
    case "grid":
      return (
        <svg {...common}>
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
        </svg>
      );
    case "users":
      return (
        <svg {...common}>
          <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
      );
    case "tag":
      return (
        <svg {...common}>
          <path d="M20.59 13.41 13.42 20.6a2 2 0 0 1-2.83 0L3 13V3h10l7.59 7.59a2 2 0 0 1 0 2.82Z" />
          <circle cx="7.5" cy="7.5" r="1.5" />
        </svg>
      );
    case "file":
      return (
        <svg {...common}>
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
          <path d="M14 2v6h6" />
        </svg>
      );
    case "radar":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
          <circle cx="12" cy="12" r="4" />
          <path d="M12 12 19 5" />
        </svg>
      );
    case "sparkles":
      return (
        <svg {...common}>
          <path d="M12 3v4M12 17v4M3 12h4M17 12h4" />
          <path d="m6.3 6.3 2.4 2.4M15.3 15.3l2.4 2.4M17.7 6.3l-2.4 2.4M8.7 15.3l-2.4 2.4" />
          <circle cx="12" cy="12" r="2.5" />
        </svg>
      );
    case "chart":
      return (
        <svg {...common}>
          <path d="M3 3v18h18" />
          <path d="M7 15l3-3 3 3 5-6" />
        </svg>
      );
    case "settings":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
        </svg>
      );
    default:
      return null;
  }
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout, has } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [adminOpen, setAdminOpen] = useState(pathname.startsWith("/admin"));

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  useEffect(() => {
    setAdminOpen(pathname.startsWith("/admin"));
    setOpen(false);
  }, [pathname]);

  if (loading || !user) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-slate-500">Carregando…</p>
      </main>
    );
  }

  const visibleNav = NAV.filter((n) => !n.perm || has(n.perm));

  return (
    <div className="min-h-screen lg:flex">
      {/* Mobile top bar */}
      <div className="flex items-center justify-between border-b border-gray-100 bg-white px-4 py-3 lg:hidden">
        <button
          onClick={() => setOpen(true)}
          className="rounded-lg border border-gray-200 p-2 text-slate-600"
          aria-label="Abrir menu"
        >
          ☰
        </button>
        <span className="font-bold text-brand-700">IntelliINPI</span>
        <span className="w-9" />
      </div>

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 transform overflow-y-auto scrollbar-thin bg-sidebar text-slate-200 transition-transform lg:static lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-16 items-center gap-2 px-5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
            II
          </span>
          <span className="text-lg font-bold text-white">IntelliINPI</span>
        </div>

        <nav className="mt-2 space-y-1 px-3 pb-24">
          {visibleNav.map((n) => {
            const active =
              n.href === "/admin"
                ? pathname === "/admin"
                : pathname.startsWith(n.href);
            if (n.children) {
              return (
                <div key={n.href}>
                  <button
                    onClick={() => {
                      if (!pathname.startsWith("/admin")) {
                        router.push("/admin");
                      } else {
                        setAdminOpen((v) => !v);
                      }
                    }}
                    className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                      pathname.startsWith("/admin")
                        ? "bg-sidebar-hover text-white"
                        : "text-sidebar-muted hover:bg-sidebar-light hover:text-white"
                    }`}
                  >
                    <Icon name={n.icon} />
                    <span className="flex-1 text-left">{n.label}</span>
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      className={`transition-transform ${
                        adminOpen ? "rotate-180" : ""
                      }`}
                    >
                      <path d="m6 9 6 6 6-6" />
                    </svg>
                  </button>
                  {adminOpen && (
                    <div className="mt-1 space-y-1 pl-9">
                      {n.children
                        .filter((c) => !c.perm || has(c.perm))
                        .map((c) => (
                          <Link
                            key={c.href}
                            href={c.href}
                            className={`block rounded-lg px-3 py-1.5 text-sm transition ${
                              pathname === c.href
                                ? "text-white"
                                : "text-sidebar-muted hover:text-white"
                            }`}
                          >
                            {c.label}
                          </Link>
                        ))}
                    </div>
                  )}
                </div>
              );
            }
            return (
              <Link
                key={n.href}
                href={n.href}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  active
                    ? "bg-sidebar-hover text-white"
                    : "text-sidebar-muted hover:bg-sidebar-light hover:text-white"
                }`}
              >
                <Icon name={n.icon} />
                {n.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Overlay (mobile) */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/50 lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Main */}
      <div className="flex-1">
        <header className="sticky top-0 z-20 border-b border-gray-100 bg-white/90 backdrop-blur">
          <div className="flex items-center justify-between px-4 py-3 lg:px-8">
            <div>
              <p className="text-sm font-semibold text-slate-800">
                {visibleNav.find((n) => pathname.startsWith(n.href))?.label ||
                  "Painel"}
              </p>
              <p className="text-xs text-slate-400">
                Plataforma de Propriedade Industrial
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="hidden text-right sm:block">
                <p className="text-sm font-medium text-slate-800">{user.name}</p>
                <p className="text-xs text-slate-500">
                  {user.is_master_admin
                    ? "Master Admin"
                    : user.tenant_name || "Sem tenant"}
                </p>
              </div>
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white">
                {user.name.charAt(0).toUpperCase()}
              </div>
              <button
                onClick={() => logout().then(() => router.push("/login"))}
                className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
              >
                Sair
              </button>
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-7xl px-4 py-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
