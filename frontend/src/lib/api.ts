/**
 * Typed API client for the IntelliINPI backend.
 *
 * - Stores access/refresh tokens in localStorage.
 * - Automatically attaches the Bearer token.
 * - Transparently refreshes the access token once on 401 and retries.
 * - Never sends a tenant id: tenancy is derived server-side from the token.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const ACCESS_KEY = "intelliinpi.access_token";
const REFRESH_KEY = "intelliinpi.refresh_token";

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

export type MeResponse = {
  id: string;
  name: string;
  email: string;
  is_master_admin: boolean;
  tenant_id: string | null;
  tenant_name: string | null;
  person_id: string | null;
  roles: string[];
  modules: string[];
  permissions: string[];
  resources: string[];
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// --- Token storage ----------------------------------------------------------
export const tokens = {
  get access() {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(REFRESH_KEY);
  },
  set(t: TokenResponse) {
    window.localStorage.setItem(ACCESS_KEY, t.access_token);
    window.localStorage.setItem(REFRESH_KEY, t.refresh_token);
  },
  clear() {
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
  },
};

// --- Core fetch -------------------------------------------------------------
async function parse<T>(res: Response): Promise<T> {
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail =
      (body && (body.detail || body.message)) || `Erro ${res.status}`;
    throw new ApiError(
      res.status,
      typeof detail === "string" ? detail : JSON.stringify(detail),
    );
  }
  return body as T;
}

let refreshing: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  const refresh_token = tokens.refresh;
  if (!refresh_token) return false;
  if (refreshing) return refreshing;
  refreshing = (async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token }),
      });
      if (!res.ok) {
        tokens.clear();
        return false;
      }
      const data = (await res.json()) as TokenResponse;
      tokens.set(data);
      return true;
    } catch {
      tokens.clear();
      return false;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(options.headers || {});
  const access = tokens.access;
  if (access) headers.set("Authorization", `Bearer ${access}`);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (res.status === 401 && retry) {
    const ok = await refreshAccessToken();
    if (ok) return apiFetch<T>(path, options, false);
  }
  return parse<T>(res);
}

/**
 * Fetch a binary resource (e.g. an image) with auth and return an object URL.
 * The caller is responsible for calling `URL.revokeObjectURL` when done.
 * Throws `ApiError` on non-2xx (so callers can treat 404 as "no image").
 */
export async function fetchBlobUrl(path: string, retry = true): Promise<string> {
  const headers = new Headers();
  const access = tokens.access;
  if (access) headers.set("Authorization", `Bearer ${access}`);

  const res = await fetch(`${API_BASE_URL}${path}`, { headers });

  if (res.status === 401 && retry) {
    const ok = await refreshAccessToken();
    if (ok) return fetchBlobUrl(path, false);
  }
  if (!res.ok) throw new ApiError(res.status, `Erro ${res.status}`);

  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

// --- Auth -------------------------------------------------------------------
export const auth = {
  login(email: string, password: string) {
    return apiFetch<TokenResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },
  async loginAndStore(email: string, password: string) {
    const t = await auth.login(email, password);
    tokens.set(t);
    return t;
  },
  me() {
    return apiFetch<MeResponse>("/api/auth/me");
  },
  async logout() {
    const refresh_token = tokens.refresh;
    try {
      if (refresh_token) {
        await apiFetch("/api/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token }),
        });
      }
    } finally {
      tokens.clear();
    }
  },
};
