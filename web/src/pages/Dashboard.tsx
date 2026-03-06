import { useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { AlertCircle, CheckCircle2, CreditCard, TrendingUp } from "lucide-react";

import { API, formatApiError, type FinanceMonthSummary } from "../api";
import { getApiConfig, saveApiConfig } from "../config";

type LoadState = "idle" | "loading" | "ready" | "error";

export default function Dashboard() {
  const [summary, setSummary] = useState<FinanceMonthSummary | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [config, setConfig] = useState(() => getApiConfig());

  const today = useMemo(() => new Date(), []);

  const loadSummary = async () => {
    setState("loading");
    try {
      const data = await API.finances.getSummary(today.getFullYear(), today.getMonth() + 1);
      setSummary(data);
      setError(null);
      setState("ready");
    } catch (err) {
      setError(formatApiError(err));
      setSummary(null);
      setState("error");
    }
  };

  useEffect(() => {
    void loadSummary();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSaveConfig = () => {
    const saved = saveApiConfig(config);
    setConfig(saved);
    setToast("Configuration API sauvegardee");
    window.setTimeout(() => setToast(null), 1800);
  };

  const onTestConnection = async () => {
    try {
      await API.auth.check();
      setToast("Connexion API OK");
      setError(null);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      window.setTimeout(() => setToast(null), 1800);
    }
  };

  const currentMonthName = format(today, "MMMM yyyy", { locale: fr });
  const totalBudgetLimit = summary?.budgets.reduce((acc, b) => acc + b.limit, 0) ?? 0;
  const globalPercentage = totalBudgetLimit > 0 && summary ? (summary.expense / totalBudgetLimit) * 100 : 0;

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8 animate-in fade-in duration-500">
      <header className="space-y-4">
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-4xl font-bold tracking-tight">Bonjour Adam.</h1>
            <p className="text-foreground/60 text-lg mt-1 capitalize">{currentMonthName}</p>
          </div>
          <button
            type="button"
            className="rounded-lg border px-4 py-2 text-sm hover:bg-black/5 dark:hover:bg-white/10"
            onClick={() => void loadSummary()}
          >
            Rafraichir
          </button>
        </div>

        <section className="rounded-2xl border p-4 bg-[--color-card] dark:bg-[--color-dark-card]">
          <h2 className="font-semibold mb-3">Configuration API</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="text-sm">
              <span className="block text-foreground/60 mb-1">API URL</span>
              <input
                className="w-full rounded-lg border px-3 py-2 bg-transparent"
                value={config.apiUrl}
                onChange={(e) => setConfig((prev) => ({ ...prev, apiUrl: e.target.value }))}
              />
            </label>
            <label className="text-sm">
              <span className="block text-foreground/60 mb-1">API key</span>
              <input
                className="w-full rounded-lg border px-3 py-2 bg-transparent"
                value={config.apiKey}
                onChange={(e) => setConfig((prev) => ({ ...prev, apiKey: e.target.value }))}
                type="password"
              />
            </label>
          </div>
          <div className="flex gap-2 mt-3">
            <button type="button" className="rounded-lg bg-[--color-primary] text-white px-4 py-2" onClick={onSaveConfig}>
              Sauver
            </button>
            <button type="button" className="rounded-lg border px-4 py-2" onClick={() => void onTestConnection()}>
              Tester connexion
            </button>
          </div>
        </section>
      </header>

      {toast && <p className="text-sm text-emerald-500">{toast}</p>}

      {state === "loading" && (
        <div className="p-8 flex items-center justify-center h-full">
          <div className="animate-pulse flex flex-col items-center">
            <div className="w-12 h-12 border-4 border-[--color-primary] border-t-transparent rounded-full animate-spin" />
            <p className="mt-4 text-foreground/50 font-medium">Chargement des donnees...</p>
          </div>
        </div>
      )}

      {state === "error" && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-2xl p-6 flex items-start gap-4">
          <AlertCircle className="w-6 h-6 text-red-500 shrink-0" />
          <div>
            <h3 className="text-red-500 font-semibold text-lg">Erreur de connexion</h3>
            <p className="text-red-500/80 mt-1">{error}</p>
            <p className="text-sm mt-4 text-foreground/50">Verifie API URL, API key, backend FastAPI et CORS.</p>
          </div>
        </div>
      )}

      {state === "ready" && summary && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-[--color-card] dark:bg-[--color-dark-card] rounded-3xl p-6 shadow-sm border border-[--color-border] dark:border-[--color-dark-border]">
              <div className="flex items-center gap-3 text-foreground/60 mb-2">
                <CreditCard className="w-5 h-5" />
                <h2 className="font-medium">Depenses du mois</h2>
              </div>
              <p className="text-4xl font-bold">{summary.expense.toFixed(2)} EUR</p>
              <div className="mt-4 h-2 w-full bg-black/5 dark:bg-white/10 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    globalPercentage > 90 ? "bg-red-500" : globalPercentage > 75 ? "bg-orange-500" : "bg-[--color-primary]"
                  }`}
                  style={{ width: `${Math.min(globalPercentage, 100)}%` }}
                />
              </div>
              <p className="text-sm text-foreground/50 mt-2 text-right">{globalPercentage.toFixed(0)}% du budget total</p>
            </div>

            <div className="bg-[--color-card] dark:bg-[--color-dark-card] rounded-3xl p-6 shadow-sm border border-[--color-border] dark:border-[--color-dark-border]">
              <div className="flex items-center gap-3 text-foreground/60 mb-2">
                <TrendingUp className="w-5 h-5" />
                <h2 className="font-medium">Revenus (Mois)</h2>
              </div>
              <p className="text-4xl font-bold text-emerald-500">{summary.income.toFixed(2)} EUR</p>
            </div>

            <div className="bg-gradient-to-br from-[--color-primary] to-purple-600 rounded-3xl p-6 shadow-lg shadow-[--color-primary]/20 text-white flex flex-col justify-center">
              <h2 className="font-medium opacity-80 mb-1">Net theorique</h2>
              <p className="text-4xl font-bold">{summary.net.toFixed(2)} EUR</p>
              <p className="text-sm opacity-80 mt-2">Revenus - depenses</p>
            </div>
          </div>

          <div>
            <h2 className="text-2xl font-semibold mb-6">Suivi des budgets</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {summary.budgets.map((budget) => (
                <div
                  key={budget.category}
                  className="bg-[--color-card] dark:bg-[--color-dark-card] rounded-2xl p-5 shadow-sm border border-[--color-border] dark:border-[--color-dark-border] flex flex-col"
                >
                  <div className="flex justify-between items-start mb-4">
                    <h3 className="font-semibold text-lg">{budget.category}</h3>
                    {budget.status === "ok" && <CheckCircle2 className="w-5 h-5 text-emerald-500" />}
                    {(budget.status === "warning" || budget.status === "exceeded") && (
                      <AlertCircle className={`w-5 h-5 ${budget.status === "warning" ? "text-orange-500" : "text-red-500"}`} />
                    )}
                  </div>

                  <p className="text-2xl font-bold mb-1">{budget.spent.toFixed(2)} EUR</p>
                  <p className="text-sm text-foreground/60 mb-4">sur {budget.limit.toFixed(2)} EUR</p>

                  <div className="mt-auto">
                    <div className="h-1.5 w-full bg-black/5 dark:bg-white/10 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-1000 ${
                          budget.status === "exceeded" ? "bg-red-500" : budget.status === "warning" ? "bg-orange-500" : "bg-emerald-500"
                        }`}
                        style={{ width: `${Math.min(budget.percentage_used, 100)}%` }}
                      />
                    </div>
                    <p className="text-xs text-right mt-2 font-medium text-foreground/50">{budget.percentage_used.toFixed(0)}% utilise</p>
                  </div>
                </div>
              ))}
              {summary.budgets.length === 0 && (
                <div className="col-span-full py-12 text-center border-2 border-dashed border-[--color-border] dark:border-[--color-dark-border] rounded-3xl">
                  <p className="text-foreground/50 font-medium">Aucun budget defini pour ce mois.</p>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
