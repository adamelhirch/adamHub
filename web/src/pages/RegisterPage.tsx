import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth";

export default function RegisterPage() {
  const { user, loading, register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (loading) {
    return null;
  }
  if (user) {
    return <Navigate to="/" replace />;
  }

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await register(email.trim(), password, displayName.trim());
      navigate("/", { replace: true });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || "Création de compte impossible.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-gradient-to-br from-blue-50 via-white to-indigo-50">
      <div className="w-full max-w-sm rounded-3xl bg-white/85 p-6 shadow-xl border border-white/60 backdrop-blur-xl space-y-5">
        <div>
          <h1 className="text-2xl font-bold text-black">Créer un compte</h1>
          <p className="text-sm text-apple-gray-500 mt-1">Choisis un email et un mot de passe.</p>
        </div>
        <form onSubmit={onSubmit} className="space-y-3">
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wider text-apple-gray-500">Prénom</span>
            <input
              type="text"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Ex: Léo"
              className="mt-1 w-full rounded-xl border border-apple-gray-200 bg-white px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            />
          </label>
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
              autoComplete="new-password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-xl border border-apple-gray-200 bg-white px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            />
            <span className="text-[11px] text-apple-gray-400">Au moins 6 caractères.</span>
          </label>
          {error && <p className="text-xs text-red-500">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-apple-blue py-2.5 text-sm font-semibold text-white hover:bg-blue-600 disabled:opacity-60"
          >
            {submitting ? "Création…" : "Créer mon compte"}
          </button>
        </form>
        <p className="text-xs text-apple-gray-500 text-center">
          Tu as déjà un compte ?{" "}
          <Link to="/login" className="font-semibold text-apple-blue hover:underline">
            Se connecter
          </Link>
        </p>
      </div>
    </div>
  );
}
