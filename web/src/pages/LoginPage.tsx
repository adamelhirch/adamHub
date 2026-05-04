import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth";

export default function LoginPage() {
  const { user, loading, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (loading) {
    return null;
  }
  if (user) {
    const from = (location.state as { from?: string } | null)?.from ?? "/";
    return <Navigate to={from} replace />;
  }

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email.trim(), password);
      navigate(((location.state as { from?: string } | null)?.from ?? "/"), { replace: true });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || "Connexion impossible.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-gradient-to-br from-blue-50 via-white to-indigo-50">
      <div className="w-full max-w-sm rounded-3xl bg-white/85 p-6 shadow-xl border border-white/60 backdrop-blur-xl space-y-5">
        <div>
          <h1 className="text-2xl font-bold text-black">AdamHUB</h1>
          <p className="text-sm text-apple-gray-500 mt-1">Connecte-toi pour accéder à ton hub.</p>
        </div>
        <form onSubmit={onSubmit} className="space-y-3">
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wider text-apple-gray-500">Email</span>
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-xl border border-apple-gray-200 bg-white px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            />
          </label>
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wider text-apple-gray-500">Mot de passe</span>
            <input
              type="password"
              autoComplete="current-password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-xl border border-apple-gray-200 bg-white px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            />
          </label>
          {error && <p className="text-xs text-red-500">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-apple-blue py-2.5 text-sm font-semibold text-white hover:bg-blue-600 disabled:opacity-60"
          >
            {submitting ? "Connexion…" : "Se connecter"}
          </button>
        </form>
        <p className="text-xs text-apple-gray-500 text-center">
          Pas encore de compte ?{" "}
          <Link to="/register" className="font-semibold text-apple-blue hover:underline">
            Crée-en un
          </Link>
        </p>
      </div>
    </div>
  );
}
