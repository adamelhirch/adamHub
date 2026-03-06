import { useEffect, useState } from "react";

import { API, formatApiError, type GroceryItem, type PantryItem, type PantryOverview } from "../api";

export default function PantryPage() {
  const [overview, setOverview] = useState<PantryOverview | null>(null);
  const [groceries, setGroceries] = useState<GroceryItem[]>([]);
  const [pantryItems, setPantryItems] = useState<PantryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatingItemId, setUpdatingItemId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const [ov, groceryRows, pantryRows] = await Promise.all([
        API.pantry.getOverview(7),
        API.groceries.listItems({ checked: false, limit: 30 }),
        API.pantry.listItems({ limit: 50 }),
      ]);
      setOverview(ov);
      setGroceries(groceryRows);
      setPantryItems(pantryRows);
      setError(null);
    } catch (err) {
      setError(formatApiError(err));
    }
  };

  useEffect(() => {
    loadData().finally(() => setLoading(false));
  }, []);

  const onCheckGrocery = async (itemId: number) => {
    setUpdatingItemId(itemId);
    try {
      await API.groceries.updateItem(itemId, { checked: true });
      await loadData();
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setUpdatingItemId(null);
    }
  };

  if (loading) return <div className="p-8">Chargement pantry & courses...</div>;
  if (error || !overview) return <div className="p-8 text-red-500">Erreur API: {error ?? "inconnue"}</div>;

  return (
    <div className="p-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Pantry & Courses</h1>
        <p className="text-foreground/60">Vue reliee stock + liste de courses</p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <article className="rounded-2xl border p-4 bg-[--color-card] dark:bg-[--color-dark-card]">
          <h2 className="text-sm text-foreground/60">Items pantry</h2>
          <p className="text-2xl font-semibold">{overview.total_items}</p>
        </article>
        <article className="rounded-2xl border p-4 bg-[--color-card] dark:bg-[--color-dark-card]">
          <h2 className="text-sm text-foreground/60">Low stock</h2>
          <p className="text-2xl font-semibold">{overview.low_stock_items}</p>
        </article>
        <article className="rounded-2xl border p-4 bg-[--color-card] dark:bg-[--color-dark-card]">
          <h2 className="text-sm text-foreground/60">Expire &lt; 7j</h2>
          <p className="text-2xl font-semibold">{overview.expiring_within_7_days}</p>
        </article>
      </div>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Stock pantry</h2>
        {pantryItems.length === 0 && <p className="text-foreground/60">Pantry vide.</p>}
        {pantryItems.map((item) => (
          <article key={item.id} className="rounded-xl border p-4 bg-[--color-card] dark:bg-[--color-dark-card]">
            <div className="flex items-center justify-between">
              <strong>{item.name}</strong>
              <span className="text-sm text-foreground/60">
                {item.quantity} {item.unit}
              </span>
            </div>
          </article>
        ))}
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Courses non cochees</h2>
        {groceries.length === 0 && <p className="text-foreground/60">Aucun item en attente.</p>}
        {groceries.map((item) => (
          <article key={item.id} className="rounded-xl border p-4 bg-[--color-card] dark:bg-[--color-dark-card]">
            <div className="flex items-start justify-between gap-3">
              <div>
                <strong>{item.name}</strong>
                <p className="text-sm text-foreground/60">
                  {item.quantity} {item.unit}
                </p>
              </div>
              <button
                type="button"
                className="rounded-lg border px-3 py-1 text-sm disabled:opacity-60"
                onClick={() => void onCheckGrocery(item.id)}
                disabled={updatingItemId === item.id}
              >
                {updatingItemId === item.id ? "..." : "Check item"}
              </button>
            </div>
            {item.category && <p className="text-xs text-foreground/60 mt-1">Categorie: {item.category}</p>}
          </article>
        ))}
      </section>
    </div>
  );
}
