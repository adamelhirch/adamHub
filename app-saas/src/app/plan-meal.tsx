import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";

import { PrimaryButton } from "@/components/primary-button";
import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { createMealPlan, listRecipes, type RecipeRead } from "@/lib/api";
import { toISODate } from "@/lib/date";

type Slot = "breakfast" | "lunch" | "dinner";

const SLOTS: { value: Slot; label: string }[] = [
  { value: "breakfast", label: "Petit-déjeuner" },
  { value: "lunch", label: "Déjeuner" },
  { value: "dinner", label: "Dîner" },
];

function formatChipLabel(date: Date): string {
  const label = new Intl.DateTimeFormat("fr-FR", {
    weekday: "short",
    day: "numeric",
  }).format(date);
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export default function PlanMealScreen() {
  const [days] = useState<string[]>(() => {
    const today = new Date();
    return Array.from({ length: 7 }, (_, index) => {
      const day = new Date(today);
      day.setDate(today.getDate() + index);
      return toISODate(day);
    });
  });
  const [selectedDate, setSelectedDate] = useState<string | null>(days[0] ?? null);
  const [slot, setSlot] = useState<Slot | null>(null);
  const [selectedRecipeId, setSelectedRecipeId] = useState<number | null>(null);
  const [recipes, setRecipes] = useState<RecipeRead[]>([]);
  const [loadingRecipes, setLoadingRecipes] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listRecipes()
      .then((data) => {
        if (active) setRecipes(data);
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof Error ? err.message : "Une erreur est survenue");
        }
      })
      .finally(() => {
        if (active) setLoadingRecipes(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const canSubmit =
    selectedDate !== null && slot !== null && selectedRecipeId !== null;

  async function handleSubmit() {
    if (selectedDate === null || slot === null || selectedRecipeId === null) return;
    setSubmitting(true);
    setError(null);
    try {
      await createMealPlan({
        recipe_id: selectedRecipeId,
        planned_for: selectedDate,
        slot,
      });
      router.back();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Screen>
      <Pressable
        onPress={() => router.back()}
        hitSlop={12}
        className="mb-4 h-10 w-10 items-center justify-center rounded-full"
      >
        <Ionicons name="arrow-back" size={24} color="#0f172a" />
      </Pressable>

      <ScreenHeader
        title="Planifier un repas"
        subtitle="Choisissez un jour, un moment et une recette"
      />

      {error ? (
        <View className="mb-4 rounded-xl bg-red-50 px-4 py-3">
          <Text className="text-sm text-red-600">{error}</Text>
        </View>
      ) : null}

      <Text className="mb-2 text-sm font-medium text-slate-700">Jour</Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerClassName="gap-2"
        className="mb-5"
      >
        {days.map((date) => {
          const selected = date === selectedDate;
          return (
            <Pressable
              key={date}
              onPress={() => setSelectedDate(date)}
              className={`rounded-xl border px-3 py-2.5 ${
                selected ? "border-emerald-600 bg-emerald-600" : "border-slate-200 bg-white"
              }`}
            >
              <Text
                className={`text-sm font-semibold ${selected ? "text-white" : "text-slate-700"}`}
              >
                {formatChipLabel(new Date(`${date}T00:00:00`))}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>

      <Text className="mb-2 text-sm font-medium text-slate-700">Moment</Text>
      <View className="mb-5 flex-row gap-2">
        {SLOTS.map((s) => {
          const selected = slot === s.value;
          return (
            <Pressable
              key={s.value}
              onPress={() => setSlot(s.value)}
              className={`flex-1 items-center rounded-xl border py-2.5 ${
                selected ? "border-emerald-600 bg-emerald-600" : "border-slate-200 bg-white"
              }`}
            >
              <Text
                className={`text-sm font-semibold ${selected ? "text-white" : "text-slate-700"}`}
              >
                {s.label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <Text className="mb-2 text-sm font-medium text-slate-700">Recette</Text>
      {loadingRecipes ? (
        <View className="py-12 items-center">
          <ActivityIndicator color="#10b981" />
        </View>
      ) : recipes.length === 0 ? (
        <View className="mb-4 rounded-2xl border border-slate-100 bg-white p-4">
          <Text className="text-center text-base text-slate-500">
            Aucune recette pour l&apos;instant.
          </Text>
        </View>
      ) : (
        recipes.map((recipe) => {
          const selected = recipe.id === selectedRecipeId;
          const totalMinutes = recipe.prep_minutes + recipe.cook_minutes;
          return (
            <Pressable
              key={recipe.id}
              onPress={() => setSelectedRecipeId(recipe.id)}
              className={`mb-3 rounded-2xl border bg-white p-4 ${
                selected ? "border-emerald-500 bg-emerald-50" : "border-slate-100"
              }`}
            >
              <Text className="text-base font-semibold text-slate-900">{recipe.name}</Text>
              <Text className="mt-0.5 text-sm text-slate-400">
                {totalMinutes} min · {recipe.servings} portions
              </Text>
            </Pressable>
          );
        })
      )}

      <Pressable onPress={() => router.push("/new-recipe")} className="mb-8 items-center py-2">
        <Text className="text-base font-semibold text-emerald-600">
          Créer une nouvelle recette
        </Text>
      </Pressable>

      <PrimaryButton
        label="Planifier ce repas"
        onPress={handleSubmit}
        loading={submitting}
        disabled={!canSubmit}
      />
    </Screen>
  );
}
