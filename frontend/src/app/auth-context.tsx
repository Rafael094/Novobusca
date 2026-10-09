"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { auth, tokens, type MeResponse } from "@/lib/api";

type AuthState = {
  user: MeResponse | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  has: (permission: string) => boolean;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadUser() {
    if (!tokens.access && !tokens.refresh) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await auth.me();
      setUser(me);
    } catch {
      tokens.clear();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function login(email: string, password: string) {
    setError(null);
    try {
      await auth.loginAndStore(email, password);
      await loadUser();
    } catch (e) {
      const message = e instanceof Error ? e.message : "Falha no login";
      setError(message);
      throw e;
    }
  }

  async function logout() {
    await auth.logout();
    setUser(null);
  }

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      error,
      login,
      logout,
      refresh: loadUser,
      has: (permission: string) =>
        !!user && (user.is_master_admin || user.permissions.includes(permission)),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [user, loading, error],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
