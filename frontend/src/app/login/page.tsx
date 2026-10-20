"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/app/auth-context";

export default function LoginPage() {
  const { login, user, loading } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!loading && user) {
    router.replace("/dashboard");
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no login.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-500 to-brand-700 px-4">
      <div className="w-full max-w-md rounded-2xl border border-gray-100 bg-white p-8 shadow-soft">
        <div className="mb-6 text-center">
          <span className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-500 text-lg font-bold text-white">
            II
          </span>
          <h1 className="text-2xl font-bold text-brand-700">IntelliINPI</h1>
          <p className="mt-1 text-sm text-slate-500">
            Pesquisa de marcas e patentes do INPI
          </p>
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              E-mail
            </label>
            <input
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
              placeholder="voce@empresa.com.br"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Senha
            </label>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
              placeholder="••••••••"
            />
          </div>

          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}

          <button type="submit" disabled={submitting} className="btn-primary w-full justify-center">
            {submitting ? "Entrando…" : "Entrar"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-400">
          Acesso restrito. O tenant é resolvido automaticamente pela sua conta.
        </p>
      </div>
    </main>
  );
}
