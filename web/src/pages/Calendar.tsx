import { useEffect, useMemo, useState } from "react";

import { API, formatApiError, type CalendarItem, type MealPlan } from "../api";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function CalendarPage() {
  const [agenda, setAgenda] = useState<CalendarItem[]>([]);
  const [mealPlans, setMealPlans] = useState<MealPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [updatingMealId, setUpdatingMealId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const day = useMemo(() => todayIso(), []);

  const loadAgendaAndMeals = async () => {
    const [agendaRows, mealRows] = await Promise.all([
      API.calendar.agenda(day),
      API.mealPlans.list({ date_from: day, date_to: day, limit: 100 }),
    ]);
    setAgenda(agendaRows);
    setMealPlans(mealRows);
  };

  useEffect(() => {
    loadAgendaAndMeals()
      .then(() => setError(null))
      .catch((err) => setError(formatApiError(err)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [day]);

  const onSync = async () => {
    setSyncing(true);
    try {
      await API.calendar.sync();
      await loadAgendaAndMeals();
      setError(null);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setSyncing(false);
    }
  };

  const onMealStatusToggle = async (meal: MealPlan) => {
    setUpdatingMealId(meal.id);
    try {
      if (meal.cooked) {
        await API.mealPlans.unconfirmCooked(meal.id);
      } else {
        await API.mealPlans.confirmCooked(meal.id, "confirmed from web");
      }
      await loadAgendaAndMeals();
      setError(null);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setUpdatingMealId(null);
    }
  };

  return (
    <div className="p-8 space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Calendrier</h1>
          <p className="text-foreground/60">Agenda unifie, date {day}</p>
        </div>
        <button
          type="button"
          className="px-4 py-2 rounded-lg bg-[--color-primary] text-white disabled:opacity-60"
          onClick={onSync}
          disabled={syncing}
        >
          {syncing ? "Sync..." : "Sync calendrier"}
        </button>
      </header>

      {loading && <p>Chargement agenda...</p>}
      {error && <p className="text-red-500">Erreur API: {error}</p>}
      {!loading && !error && agenda.length === 0 && <p className="text-foreground/60">Aucun item pour aujourd'hui.</p>}
      {!loading && !error && agenda.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Agenda du jour</h2>
          {agenda.map((item) => (
            <article key={item.id} className="rounded-xl border p-4 bg-[--color-card] dark:bg-[--color-dark-card]">
              <div className="flex items-center justify-between">
                <strong>{item.title}</strong>
                <span className="text-xs text-foreground/60">
                  {item.source} · {item.completed ? "done" : "open"}
                </span>
              </div>
              <p className="text-sm text-foreground/70 mt-1">
                {new Date(item.start_at).toLocaleString("fr-FR")} - {new Date(item.end_at).toLocaleString("fr-FR")}
              </p>
            </article>
          ))}
        </section>
      )}

      {!loading && (
        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Repas du jour</h2>
          {mealPlans.length === 0 && <p className="text-foreground/60">Aucun meal plan sur cette date.</p>}
          {mealPlans.map((meal) => (
            <article key={meal.id} className="rounded-xl border p-4 bg-[--color-card] dark:bg-[--color-dark-card]">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <strong>
                    {meal.slot} · {meal.recipe_name}
                  </strong>
                  <p className="text-xs text-foreground/60 mt-1">
                    #{meal.id} · {meal.cooked ? "cooked" : "not cooked"}
                  </p>
                </div>
                <button
                  type="button"
                  className="rounded-lg border px-3 py-1 text-sm disabled:opacity-60"
                  onClick={() => void onMealStatusToggle(meal)}
                  disabled={updatingMealId === meal.id}
                >
                  {updatingMealId === meal.id ? "..." : meal.cooked ? "Unconfirm cooked" : "Confirm cooked"}
                </button>
              </div>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
