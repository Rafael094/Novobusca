"use client";

import { API_BASE_URL, ApiError, tokens } from "./api";

/** Download the NIT portfolio as a CSV through the authenticated endpoint. */
export async function downloadNitPortfolio() {
  const headers = new Headers();
  const access = tokens.access;
  if (access) headers.set("Authorization", `Bearer ${access}`);
  const res = await fetch(`${API_BASE_URL}/api/nit/portfolio/export`, { headers });
  if (!res.ok) {
    throw new ApiError(res.status, `Erro ${res.status}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "portfolio_nit.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
