"use client";

/**
 * PageHeader — the shared title block used by every screen.
 *
 * Keeping it in one place is what makes the modules feel like a single product:
 * same title scale, same description style, same action placement. Screens must
 * not re-implement their own header markup.
 */

import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
  actions,
  breadcrumb,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  breadcrumb?: string;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {breadcrumb && (
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">
            {breadcrumb}
          </p>
        )}
        <h1 className="text-2xl font-bold text-slate-800">{title}</h1>
        {description && (
          <p className="mt-1 max-w-3xl text-sm text-slate-500">{description}</p>
        )}
      </div>
      {actions && (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
      )}
    </div>
  );
}

export default PageHeader;
