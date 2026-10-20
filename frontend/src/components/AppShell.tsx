"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/app/auth-context";
import { useTheme } from "@/app/theme-context";
import ChatWidget from "./ChatWidget";
import UserMenu from "./UserMenu";

type NavItem = {
  href: string;
  label: string;
  perm: string | null;
  icon: string;
  children?: { href: string; label: string; perm: string | null }[];
};

/**
 * Sidebar structure (three blocks, no decoration):
 *
 *   1. Visão Geral      — the business dashboard
 *   2. CRM / Clientes   — the commercial hub (clients, funnel, proposals, follow-ups)
 *   3. INPI             — expandable: marca/patente research, monitoring, AI, reports
 *   4. NIT              — expandable: the institutional innovation modules
 *
 * Administração deliberately lives in the user dropdown (``UserMenu``), not here.
 */
const NAV: NavItem[] = [
  { href: "/dashboard", label: "Visão Geral", perm: null, icon: "grid" },
  {
    href: "/crm",
    label: "CRM / Clientes",
    perm: "COMPANY_VIEW",
    icon: "briefcase",
    children: [
      { href: "/crm", label: "Visão comercial", perm: "CRM_DASHBOARD_VIEW" },
      { href: "/crm/oportunidades", label: "Leads e oportunidades", perm: "CRM_OPPORTUNITY_VIEW" },
      { href: "/crm/propostas", label: "Propostas comerciais", perm: "CRM_PROPOSAL_VIEW" },
      { href: "/crm/atividades", label: "Atividades e follow-ups", perm: "CRM_ACTIVITY_VIEW" },
      { href: "/clientes", label: "Clientes e empresas", perm: "COMPANY_VIEW" },
    ],
  },
  {
    href: "/inpi",
    label: "INPI",
    perm: "MARCAS_SEARCH",
    icon: "search",
    children: [
      { href: "/marcas", label: "Marcas", perm: "MARCAS_SEARCH" },
      { href: "/patentes", label: "Patentes", perm: "PATENTES_SEARCH" },
      { href: "/desenhos", label: "Desenhos industriais", perm: "DESENHOS_SEARCH" },
      { href: "/softwares", label: "Programas de computador", perm: "SOFTWARES_SEARCH" },
      { href: "/monitoramento", label: "Monitoramento", perm: "MARCAS_VIEW" },
      { href: "/analises", label: "Análises de IA", perm: "MARCAS_SEARCH" },
      { href: "/relatorios", label: "Relatórios", perm: "RELATORIOS_VIEW" },
    ],
  },
  {
    href: "/nit",
    label: "NIT",
    perm: "NIT_DISCLOSURE_VIEW",
    icon: "flask",
    children: [
      { href: "/nit", label: "Painel do NIT", perm: "NIT_REPORT_VIEW" },
      { href: "/nit/comunicacoes", label: "Comunicações", perm: "NIT_DISCLOSURE_VIEW" },
      { href: "/nit/ativos", label: "Portfólio de Ativos", perm: "NIT_ASSET_VIEW" },
      { href: "/nit/portfolio", label: "Portfólio avançado", perm: "NIT_PORTFOLIO_VIEW" },
      { href: "/nit/comites", label: "Comitês", perm: "NIT_COMMITTEE_VIEW" },
      { href: "/nit/catalogo", label: "Catálogo de Tecnologias", perm: "NIT_OFFER_VIEW" },
      { href: "/nit/negociacoes", label: "Negociações", perm: "NIT_NEGOTIATION_VIEW" },
      { href: "/nit/contratos", label: "Contratos", perm: "NIT_CONTRACT_VIEW" },
      { href: "/nit/projetos", label: "Projetos de P&D", perm: "NIT_PROJECT_VIEW" },
      { href: "/nit/startups", label: "Startups", perm: "NIT_STARTUP_VIEW" },
      { href: "/nit/incubacao", label: "Incubação", perm: "NIT_STARTUP_VIEW" },
      { href: "/nit/indicadores", label: "Indicadores & FORMICT", perm: "NIT_INDICATOR_VIEW" },
      { href: "/nit/notificacoes", label: "Notificações", perm: "NIT_NOTIFICATION_VIEW" },
      { href: "/nit/bi", label: "BI & Relatórios", perm: "NIT_BI_VIEW" },
      { href: "/nit/portais", label: "Portais externos", perm: "NIT_PORTAL_VIEW" },
      { href: "/nit/integracoes", label: "Integrações", perm: "NIT_INTEGRATION_VIEW" },
      { href: "/nit/documentos", label: "Documentos", perm: "NIT_DOCUMENT_VIEW" },
    ],
  },
];

/**
 * Where a grouped entry sends the user when clicked while inactive.
 * ``/inpi`` has no screen of its own, so it defaults to its first child.
 */
const GROUP_LANDING: Record<string, string> = {
  "/inpi": "/marcas",
  "/crm": "/crm",
  "/nit": "/nit",
};

/** Longest-prefix match so "/crm/propostas" highlights the CRM group. */
function findActiveGroup(pathname: string): NavItem | undefined {
  return NAV.filter((n) => n.children)
    .filter((n) => n.children!.some((c) => pathname === c.href || pathname.startsWith(c.href + "/")))
    .sort(
      (a, b) =>
        Math.max(...b.children!.map((c) => c.href.length)) -
        Math.max(...a.children!.map((c) => c.href.length)),
    )[0];
}

/** The deepest child matching the current path (for the header title). */
function findActiveLabel(pathname: string, visible: NavItem[]): string {
  for (const group of visible) {
    if (!group.children) continue;
    const child = group.children
      .filter((c) => pathname === c.href || pathname.startsWith(c.href + "/"))
      .sort((a, b) => b.href.length - a.href.length)[0];
    if (child) return child.label;
  }
  const top = visible
    .filter((n) => pathname.startsWith(n.href))
    .sort((a, b) => b.href.length - a.href.length)[0];
  return top?.label ?? "Painel";
}

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
    case "flask":
      return (
        <svg {...common}>
          <path d="M9 3h6" />
          <path d="M10 3v6.5L5.2 17A2 2 0 0 0 7 20h10a2 2 0 0 0 1.8-3L14 9.5V3" />
          <path d="M7.5 14h9" />
        </svg>
      );
    case "search":
      return (
        <svg {...common}>
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
      );
    case "briefcase":
      return (
        <svg {...common}>
          <rect x="2" y="7" width="20" height="14" rx="2" />
          <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
          <path d="M2 13h20" />
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
  const { user, loading, has } = useAuth();
  const theme = useTheme();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [openGroup, setOpenGroup] = useState<string | null>(
    findActiveGroup(pathname)?.href ?? null,
  );

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  useEffect(() => {
    const match = findActiveGroup(pathname);
    setOpenGroup(match ? match.href : null);
    setOpen(false);
  }, [pathname]);

  if (loading || !user) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-slate-500">Carregando…</p>
      </main>
    );
  }

  const visibleNav = NAV.filter((n) => {
    if (!n.perm || has(n.perm)) return true;
    // A group stays visible when at least one child is permitted.
    return !!n.children?.some((c) => !c.perm || has(c.perm));
  });

  // Deepest matching child, used to highlight the exact sub-item.
  const activeChild = visibleNav
    .flatMap((n) => n.children ?? [])
    .filter(
      (c) => pathname === c.href || pathname.startsWith(`${c.href}/`),
    )
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;

  return (
    <div className="min-h-screen lg:flex">
      {/* Mobile top bar (blue hamburger) */}
      <div
        className="flex items-center justify-between border-b lg:hidden"
        style={{ background: "var(--header-bg)", borderColor: "var(--border-color)" }}
      >
        <button
          onClick={() => setOpen(true)}
          className="flex items-center justify-center bg-brand-500 p-4 text-white hover:bg-brand-700"
          aria-label="Abrir menu"
        >
          <svg width="20" height="15" viewBox="0 0 20 15" fill="currentColor" aria-hidden="true">
            <path d="M0 0H20V2.5H0V0ZM0 6.25H20V8.75H0V6.25ZM0 12.5H20V15H0V12.5Z" />
          </svg>
        </button>
        <span className="font-bold" style={{ color: "var(--primary-color)" }}>
          IntelliINPI
        </span>
        <span className="w-9" />
      </div>

      {/* Sidebar — blue, full-height */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 transform overflow-y-auto scrollbar-thin bg-brand-500 text-white transition-transform lg:static lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        style={{ background: "var(--sidebar-bg)" }}
      >
        <div className="flex h-16 items-center gap-2 px-5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/20 text-sm font-bold text-white">
            II
          </span>
          <span className="text-lg font-bold text-white">IntelliINPI</span>
        </div>

        <nav className="mt-2 space-y-1 px-3 pb-24">
          {visibleNav.map((n) => {
            const active = pathname === n.href || pathname.startsWith(`${n.href}/`);
            if (n.children) {
              const groupOpen = openGroup === n.href;
              const groupActive = findActiveGroup(pathname)?.href === n.href;
              return (
                <div key={n.href}>
                  <button
                    onClick={() => {
                      if (!groupActive) {
                        router.push(GROUP_LANDING[n.href] ?? n.href);
                      } else {
                        setOpenGroup((v) => (v === n.href ? null : n.href));
                      }
                    }}
                    className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-white transition ${
                      groupActive ? "bg-white/20" : "hover:bg-white/20"
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
                      className={`transition-transform ${groupOpen ? "rotate-180" : ""}`}
                    >
                      <path d="m6 9 6 6 6-6" />
                    </svg>
                  </button>
                  {groupOpen && (
                    <div
                      className="mt-1 space-y-0.5 rounded-lg py-1"
                      style={{ background: "var(--sidebar-active-bg)" }}
                    >
                      {n.children
                        .filter((c) => !c.perm || has(c.perm))
                        .map((c) => (
                          <Link
                            key={c.href}
                            href={c.href}
                            className={`block rounded-md px-3 py-2 pl-9 text-sm text-white transition ${
                              activeChild === c.href
                                ? "bg-white/20 font-medium"
                                : "text-white/90 hover:bg-white/20"
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
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-white transition ${
                  active ? "bg-white/20" : "hover:bg-white/20"
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
          className="fixed inset-0 z-30 bg-black/25 lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Main */}
      <div className="flex-1">
        <header
          className="sticky top-0 z-20 border-b"
          style={{
            background: "var(--header-bg)",
            borderColor: "var(--border-color)",
            boxShadow: "3px 3px 19px var(--header-shadow)",
          }}
        >
          <div className="flex items-center justify-between gap-4 px-4 py-3 lg:px-8">
            <div className="min-w-0">
              <p
                className="truncate text-sm font-semibold"
                style={{ color: "var(--text-main)" }}
              >
                {findActiveLabel(pathname, visibleNav)}
              </p>
              <p className="truncate text-xs" style={{ color: "var(--text-muted)" }}>
                Plataforma de Propriedade Industrial
              </p>
            </div>

            <div className="flex items-center gap-3">
              {/* Theme toggle (sun/moon) — identical behaviour to Cerbero */}
              <button
                type="button"
                onClick={theme.toggle}
                aria-label={theme.isDark ? "Modo claro" : "Modo noturno"}
                title={theme.isDark ? "Ativar modo claro" : "Ativar modo noturno"}
                className="flex h-9 w-9 items-center justify-center rounded-full border transition hover:text-brand-500"
                style={{
                  borderColor: "var(--border-color)",
                  color: "var(--text-muted)",
                }}
              >
                {theme.isDark ? (
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="2" />
                    <path
                      d="M12 2v2M12 20v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M2 12h2M20 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                    />
                  </svg>
                ) : (
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path
                      d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                )}
              </button>

              <UserMenu />
            </div>
          </div>
        </header>

        <main className="mx-auto w-full min-w-0 max-w-[1600px] px-4 py-6 lg:px-8">
          {children}
        </main>
      </div>

      {/* Assistente flutuante (chat) */}
      <ChatWidget />
    </div>
  );
}
