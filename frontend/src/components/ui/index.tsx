"use client";

/**
 * Shared UI primitives implementing the Cerbero design system:
 * light/dark surfaces driven by CSS custom properties (globals.css), blue
 * (#1A22CF) primary actions and semantic status badges. Every surface uses the
 * theme variables so the components flip automatically in dark mode (body.dark).
 */

import { useEffect, type ReactNode } from "react";

// --- Card -------------------------------------------------------------------
export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border shadow-card ${className}`}
      style={{ background: "var(--bg-card)", borderColor: "var(--border-color)" }}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div
      className="flex items-start justify-between gap-3 border-b px-5 py-4"
      style={{ borderColor: "var(--border-color)" }}
    >
      <div>
        <h2 className="font-semibold" style={{ color: "var(--text-main)" }}>
          {title}
        </h2>
        {subtitle && (
          <p className="mt-0.5 text-sm" style={{ color: "var(--text-muted)" }}>
            {subtitle}
          </p>
        )}
      </div>
      {action}
    </div>
  );
}

export function CardBody({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`p-5 ${className}`}>{children}</div>;
}

// --- Badge ------------------------------------------------------------------
export type BadgeTone =
  | "green"
  | "amber"
  | "red"
  | "blue"
  | "slate"
  | "orange";

const BADGE_TONES: Record<BadgeTone, string> = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  amber: "bg-amber-50 text-amber-700 ring-amber-600/20",
  orange: "bg-orange-50 text-orange-700 ring-orange-600/20",
  red: "bg-red-50 text-red-700 ring-red-600/20",
  blue: "bg-brand-50 text-brand-700 ring-brand-600/20",
  slate: "bg-slate-100 text-slate-600 ring-slate-500/20",
};

export function Badge({
  children,
  tone = "slate",
}: {
  children: ReactNode;
  tone?: BadgeTone;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${BADGE_TONES[tone]}`}
    >
      {children}
    </span>
  );
}

/** Map a free-form status string to a semantic badge tone. */
export function statusTone(status: string | null | undefined): BadgeTone {
  const s = (status || "").toUpperCase();
  if (["COMPLETED", "IMPORTED", "OK", "ACTIVE", "ATIVO"].includes(s)) return "green";
  if (["RUNNING", "PENDING", "PROCESSING"].includes(s)) return "amber";
  if (["FAILED", "ERROR", "CRITICAL"].includes(s)) return "red";
  return "slate";
}

// --- Button -----------------------------------------------------------------
type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-brand-600 text-white hover:bg-brand-700 focus-visible:ring-brand-500",
  secondary:
    "border hover:bg-brand-50 focus-visible:ring-brand-500",
  ghost: "hover:bg-brand-50 focus-visible:ring-brand-400",
  danger: "bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-500",
};

const BUTTON_VARIANT_STYLE: Partial<Record<ButtonVariant, React.CSSProperties>> = {
  secondary: {
    background: "var(--bg-card)",
    borderColor: "var(--border-color)",
    color: "var(--text-main)",
  },
  ghost: { color: "var(--text-muted)" },
};

export function Button({
  children,
  variant = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
}) {
  return (
    <button
      {...props}
      style={{ ...BUTTON_VARIANT_STYLE[variant], ...(props.style || {}) }}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-60 ${BUTTON_VARIANTS[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

// --- Inputs -----------------------------------------------------------------
const FIELD_CLASS =
  "w-full rounded-lg border px-3 py-2 text-sm outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100";
const FIELD_STYLE: React.CSSProperties = {
  background: "var(--bg-input)",
  borderColor: "var(--border-color)",
  color: "var(--text-main)",
};

export function Input({
  label,
  className = "",
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { label?: string }) {
  return (
    <label className="block">
      {label && (
        <span className="mb-1 block text-sm font-medium" style={{ color: "var(--text-main)" }}>
          {label}
        </span>
      )}
      <input {...props} style={FIELD_STYLE} className={`${FIELD_CLASS} ${className}`} />
    </label>
  );
}

export function Textarea({
  label,
  className = "",
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: string }) {
  return (
    <label className="block">
      {label && (
        <span className="mb-1 block text-sm font-medium" style={{ color: "var(--text-main)" }}>
          {label}
        </span>
      )}
      <textarea {...props} style={FIELD_STYLE} className={`${FIELD_CLASS} ${className}`} />
    </label>
  );
}

export function Select({
  label,
  className = "",
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement> & { label?: string }) {
  return (
    <label className="block">
      {label && (
        <span className="mb-1 block text-sm font-medium" style={{ color: "var(--text-main)" }}>
          {label}
        </span>
      )}
      <select {...props} style={FIELD_STYLE} className={`${FIELD_CLASS} ${className}`}>
        {children}
      </select>
    </label>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3">
      <span className="text-sm text-slate-700">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition ${
          checked ? "bg-brand-600" : "bg-slate-300"
        }`}
      >
        <span
          className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition ${
            checked ? "translate-x-5" : "translate-x-0.5"
          }`}
        />
      </button>
    </label>
  );
}

// --- Modal ------------------------------------------------------------------
export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        className="relative z-10 w-full max-w-lg rounded-xl border shadow-soft"
        style={{ background: "var(--bg-card)", borderColor: "var(--border-color)" }}
      >
        <div
          className="flex items-center justify-between border-b px-5 py-4"
          style={{ borderColor: "var(--border-color)" }}
        >
          <h3 className="font-semibold" style={{ color: "var(--text-main)" }}>
            {title}
          </h3>
          <button
            onClick={onClose}
            className="rounded-lg p-1 hover:text-brand-500"
            style={{ color: "var(--text-muted)" }}
            aria-label="Fechar"
          >
            ✕
          </button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto scrollbar-thin px-5 py-4">
          {children}
        </div>
        {footer && (
          <div
            className="flex justify-end gap-2 border-t px-5 py-4"
            style={{ borderColor: "var(--border-color)" }}
          >
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

// --- Table ------------------------------------------------------------------
export function Table({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto scrollbar-thin">
      <table className="min-w-full text-sm">{children}</table>
    </div>
  );
}

export function Th({
  children,
  className = "",
}: {
  children?: ReactNode;
  className?: string;
}) {
  return (
    <th
      className={`whitespace-nowrap px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide ${className}`}
      style={{ color: "var(--text-muted)" }}
    >
      {children}
    </th>
  );
}

export function Td({
  children,
  className = "",
}: {
  children?: ReactNode;
  className?: string;
}) {
  return (
    <td
      className={`px-4 py-3 align-middle ${className}`}
      style={{ color: "var(--text-muted)" }}
    >
      {children}
    </td>
  );
}

export function EmptyRow({ colSpan, message }: { colSpan: number; message: string }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-4 py-10 text-center" style={{ color: "var(--text-faint)" }}>
        {message}
      </td>
    </tr>
  );
}

// --- Pagination -------------------------------------------------------------
export function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  return (
    <div
      className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3 text-sm"
      style={{ borderColor: "var(--border-color)", color: "var(--text-muted)" }}
    >
      <span>
        {from}–{to} de {total.toLocaleString("pt-BR")}
      </span>
      <div className="flex items-center gap-1">
        <Button
          variant="secondary"
          className="px-3 py-1.5"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          Anterior
        </Button>
        <span className="px-2" style={{ color: "var(--text-main)" }}>
          {page} / {totalPages}
        </span>
        <Button
          variant="secondary"
          className="px-3 py-1.5"
          disabled={page >= totalPages}
          onClick={() => onPage(page + 1)}
        >
          Próxima
        </Button>
      </div>
    </div>
  );
}

// --- Tabs -------------------------------------------------------------------
export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: string; label: string }[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1 border-b" style={{ borderColor: "var(--border-color)" }}>
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition ${
            active === t.id
              ? "border-brand-600 text-brand-700"
              : "border-transparent hover:border-brand-300"
          }`}
          style={active === t.id ? undefined : { color: "var(--text-muted)" }}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

// --- Misc -------------------------------------------------------------------
export function EmptyState({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 py-12 text-center">
      <p className="font-medium" style={{ color: "var(--text-main)" }}>{title}</p>
      {description && (
        <p className="text-sm" style={{ color: "var(--text-faint)" }}>{description}</p>
      )}
    </div>
  );
}

export function Spinner({ label = "Carregando…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-6 text-sm" style={{ color: "var(--text-muted)" }}>
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
      {label}
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
      {children}
    </p>
  );
}

// --- Monitoring toggle ------------------------------------------------------
/**
 * Selective-monitoring switch shown on each marca/patente row (section 4).
 *
 * Monitoring is NEVER global or automatic: this control only toggles the
 * specific record the user is looking at. ``disabled`` is used when the user
 * lacks the ``MARCAS_MONITOR`` / ``PATENTES_MONITOR`` permission.
 */
export function MonitoramentoToggle({
  active,
  busy = false,
  disabled = false,
  onChange,
}: {
  active: boolean;
  busy?: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
}) {
  const title = disabled
    ? "Sem permissão para monitorar"
    : active
      ? "Desativar monitoramento desta marca"
      : "Ativar monitoramento desta marca";
  return (
    <button
      type="button"
      role="switch"
      aria-checked={active}
      aria-label="Monitoramento"
      title={title}
      disabled={disabled || busy}
      onClick={(e) => {
        e.stopPropagation();
        onChange(!active);
      }}
      className={`inline-flex items-center gap-2 rounded-full px-2 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${
        active
          ? "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/20"
          : "bg-slate-100 text-slate-500 ring-1 ring-inset ring-slate-400/20"
      }`}
    >
      <span
        className={`relative h-4 w-7 shrink-0 rounded-full transition ${
          active ? "bg-emerald-500" : "bg-slate-300"
        }`}
      >
        <span
          className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all ${
            active ? "left-3.5" : "left-0.5"
          }`}
        />
      </span>
      {busy ? "…" : active ? "Monitorada" : "Monitorar"}
    </button>
  );
}
