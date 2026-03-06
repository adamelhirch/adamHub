import { useEffect, useState } from "react";
import { format } from "date-fns";
import { fr } from "date-fns/locale";

import { API, formatApiError, type FinanceMonthSummary } from "../api";

export default function Finances() {
  const [data, setData] = useState<FinanceMonthSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const today = new Date();
    API.finances
      .getSummary(today.getFullYear(), today.getMonth() + 1)
      .then((summary) => {
        setData(summary);
        setError(null);
      })
      .catch((err) => setError(formatApiError(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8">Chargement des finances...</div>;
  if (error || !data) return <div className="p-8 text-red-500">Erreur API: {error ?? "inconnue"}</div>;

  return (
    <div className="p-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Finances</h1>
        <p className="text-foreground/60 capitalize">
          {format(new Date(data.year, data.month - 1, 1), "MMMM yyyy", { locale: fr })}
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <article className="rounded-2xl border p-4 bg-[--color-card] dark:bg-[--color-dark-card]">
          <h2 className="text-sm text-foreground/60">Revenus</h2>
          <p className="text-2xl font-semibold text-emerald-500">{data.income.toFixed(2)} EUR</p>
        </article>
        <article className="rounded-2xl border p-4 bg-[--color-card] dark:bg-[--color-dark-card]">
          <h2 className="text-sm text-foreground/60">Depenses</h2>
          <p className="text-2xl font-semibold">{data.expense.toFixed(2)} EUR</p>
        </article>
        <article className="rounded-2xl border p-4 bg-[--color-card] dark:bg-[--color-dark-card]">
          <h2 className="text-sm text-foreground/60">Net</h2>
          <p className={`text-2xl font-semibold ${data.net >= 0 ? "text-emerald-500" : "text-red-500"}`}>{data.net.toFixed(2)} EUR</p>
        </article>
      </div>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Budgets du mois</h2>
        {data.budgets.length === 0 && <p className="text-foreground/60">Aucun budget defini.</p>}
        {data.budgets.map((budget) => (
          <article key={budget.category} className="rounded-xl border p-4 bg-[--color-card] dark:bg-[--color-dark-card]">
            <div className="flex items-center justify-between">
              <strong>{budget.category}</strong>
              <span className="text-sm text-foreground/60">{budget.status}</span>
            </div>
            <p className="text-sm text-foreground/70 mt-1">
              {budget.spent.toFixed(2)} / {budget.limit.toFixed(2)} EUR
            </p>
          </article>
        ))}
      </section>
    </div>
  );
}
