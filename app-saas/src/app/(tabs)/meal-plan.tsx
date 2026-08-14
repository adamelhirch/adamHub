import { Ionicons } from "@expo/vector-icons";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { listMealPlans, syncMealPlanGroceries, type MealPlanRead } from "@/lib/api";
import { toISODate } from "@/lib/date";

const SLOT_LABELS: Record<string, string> = {
  breakfast: "Petit-déjeuner",
  lunch: "Déjeuner",
  dinner: "Dîner",
};

type MealPlanDay = {
  day: string;
  date: string;
  meals: {
    id: number;
    label: string;
    recipe: string;
    syncedGroceryAt: string | null;
  }[];
};

function formatDayLabel(dateKey: string): { day: string; date: string } {
  const label = new Intl.DateTimeFormat("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date(`${dateKey}T00:00:00`));
  const capitalized = label.charAt(0).toUpperCase() + label.slice(1);
  const [weekday, ...rest] = capitalized.split(" ");
  return { day: weekday, date: rest.join(" ") };
}

function groupMealPlans(plans: MealPlanRead[]): MealPlanDay[] {
  const groups = new Map<string, MealPlanRead[]>();
  for (const plan of plans) {
    const key = plan.planned_for ?? plan.planned_at.slice(0, 10);
    const dayPlans = groups.get(key) ?? [];
    dayPlans.push(plan);
    groups.set(key, dayPlans);
  }

  return Array.from(groups.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([dateKey, dayPlans]) => {
      dayPlans.sort((a, b) => a.planned_at.localeCompare(b.planned_at));
      const { day, date } = formatDayLabel(dateKey);
      return {
        day,
        date,
        meals: dayPlans.map((plan) => ({
          id: plan.id,
          label: plan.slot ? SLOT_LABELS[plan.slot] : "Repas",
          recipe: plan.recipe_name,
          syncedGroceryAt: plan.synced_grocery_at,
        })),
      };
    });
}

export default function MealPlanScreen() {
  const [plans, setPlans] = useState<MealPlanRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncingIds, setSyncingIds] = useState<Set<number>>(new Set());
  const [syncErrors, setSyncErrors] = useState<Set<number>>(new Set());
  const [syncCounts, setSyncCounts] = useState<Record<number, number>>({});
  const days = groupMealPlans(plans);

  async function handleSync(id: number) {
    if (syncingIds.has(id)) return;
    setSyncingIds((prev) => new Set(prev).add(id));
    setSyncErrors((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
    try {
      const result = await syncMealPlanGroceries(id);
      setSyncCounts((prev) => ({ ...prev, [id]: result.created_grocery_items }));
      setPlans((prev) =>
        prev.map((plan) =>
          plan.id === id
            ? { ...plan, synced_grocery_at: new Date().toISOString() }
            : plan,
        ),
      );
    } catch {
      setSyncErrors((prev) => new Set(prev).add(id));
    } finally {
      setSyncingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;

      async function load() {
        setLoading(true);
        setError(null);
        try {
          const today = new Date();
          const end = new Date(today);
          end.setDate(today.getDate() + 6);
          const plans = await listMealPlans({
            date_from: toISODate(today),
            date_to: toISODate(end),
          });
          if (!cancelled) setPlans(plans);
        } catch (err) {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "Une erreur est survenue");
          }
        } finally {
          if (!cancelled) setLoading(false);
        }
      }

      load();
      return () => {
        cancelled = true;
      };
    }, []),
  );

  return (
    <Screen>
      <View className="mb-6 flex-row items-center justify-between">
        <ScreenHeader title="Repas" subtitle="Votre plan de la semaine" />
        <Pressable
          onPress={() => router.push("/plan-meal")}
          className="h-11 w-11 items-center justify-center rounded-full bg-emerald-600 active:bg-emerald-700"
        >
          <Ionicons name="add" size={24} color="#ffffff" />
        </Pressable>
      </View>

      {error ? (
        <View className="mb-4 rounded-xl bg-red-50 px-4 py-3">
          <Text className="text-sm text-red-600">{error}</Text>
        </View>
      ) : null}

      {loading ? (
        <View className="py-12 items-center">
          <ActivityIndicator color="#10b981" />
        </View>
      ) : days.length === 0 ? (
        <Text className="text-center text-base text-slate-500">
          Aucun repas planifié cette semaine.
        </Text>
      ) : (
        days.map((day) => (
          <View
            key={`${day.day}-${day.date}`}
            className="mb-4 rounded-2xl border border-slate-100 bg-white p-4"
          >
            <View className="mb-3 flex-row items-center justify-between">
              <Text className="text-lg font-bold text-slate-900">{day.day}</Text>
              <Text className="text-sm text-slate-400">{day.date}</Text>
            </View>
            {day.meals.map((meal) => (
              <View key={meal.id} className="flex-row items-start py-1.5">
                <View className="mr-3 mt-1 h-2 w-2 rounded-full bg-emerald-500" />
                <View className="flex-1">
                  <Text className="text-sm font-medium text-slate-500">{meal.label}</Text>
                  <Text className="text-base text-slate-900">{meal.recipe}</Text>
                </View>
                <View className="ml-3 mt-1 flex-row items-center">
                  {syncCounts[meal.id] != null ? (
                    <Text className="mr-2 text-xs text-emerald-600">
                      +{syncCounts[meal.id]}
                    </Text>
                  ) : null}
                  {syncingIds.has(meal.id) ? (
                    <ActivityIndicator size="small" color="#10b981" />
                  ) : (
                    <Pressable onPress={() => handleSync(meal.id)} hitSlop={8}>
                      {syncErrors.has(meal.id) ? (
                        <Ionicons name="alert-circle-outline" size={20} color="#ef4444" />
                      ) : meal.syncedGroceryAt ? (
                        <Ionicons name="checkmark-circle" size={20} color="#94a3b8" />
                      ) : (
                        <Ionicons name="cart-outline" size={20} color="#059669" />
                      )}
                    </Pressable>
                  )}
                </View>
              </View>
            ))}
          </View>
        ))
      )}
    </Screen>
  );
}
