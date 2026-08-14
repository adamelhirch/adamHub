import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Alert, Pressable, Text, View } from "react-native";

import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { deleteRecipe, getRecipe, type RecipeRead } from "@/lib/recipes";

function formatQuantity(quantity: number): string {
  const rounded = Math.round(quantity * 100) / 100;
  return String(rounded);
}

export default function RecipeDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const recipeId = Number(id);
  const invalidId = !Number.isFinite(recipeId);
  const [recipe, setRecipe] = useState<RecipeRead | null>(null);
  const [loading, setLoading] = useState(() => !invalidId);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(invalidId ? "Recette introuvable." : null);

  useEffect(() => {
    if (invalidId) return;
    let active = true;
    getRecipe(recipeId)
      .then((data) => {
        if (active) setRecipe(data);
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof Error ? err.message : "Une erreur est survenue");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id, invalidId, recipeId]);

  function confirmDelete() {
    if (!recipe) return;
    Alert.alert(
      "Supprimer la recette",
      `Voulez-vous vraiment supprimer « ${recipe.name} » ? Cette action est définitive.`,
      [
        { text: "Annuler", style: "cancel" },
        { text: "Supprimer", style: "destructive", onPress: handleDelete },
      ],
    );
  }

  async function handleDelete() {
    if (!recipe) return;
    setDeleting(true);
    setError(null);
    try {
      await deleteRecipe(recipe.id);
      router.back();
    } catch (err) {
      setDeleting(false);
      setError(err instanceof Error ? err.message : "Une erreur est survenue");
    }
  }

  if (loading) {
    return (
      <Screen>
        <View className="flex-1 items-center justify-center py-12">
          <ActivityIndicator size="large" color="#059669" />
        </View>
      </Screen>
    );
  }

  if (!recipe) {
    return (
      <Screen>
        <Pressable
          onPress={() => router.back()}
          hitSlop={8}
          className="mb-2 flex-row items-center self-start rounded-full p-1"
        >
          <Ionicons name="arrow-back" size={24} color="#0f172a" />
        </Pressable>
        <View className="flex-1 items-center justify-center py-12">
          <Text className="text-base text-slate-500">
            {error ?? "Cette recette n&apos;existe pas."}
          </Text>
        </View>
      </Screen>
    );
  }

  const totalMinutes = recipe.prep_minutes + recipe.cook_minutes;

  return (
    <Screen>
      <Pressable
        onPress={() => router.back()}
        hitSlop={8}
        className="mb-2 flex-row items-center self-start rounded-full p-1"
      >
        <Ionicons name="arrow-back" size={24} color="#0f172a" />
      </Pressable>

      <ScreenHeader title={recipe.name} subtitle={recipe.description ?? undefined} />

      {error ? (
        <View className="mb-4 rounded-xl bg-red-50 px-4 py-3">
          <Text className="text-sm text-red-600">{error}</Text>
        </View>
      ) : null}

      <View className="mb-6 flex-row gap-3">
        <View className="flex-1 rounded-2xl border border-slate-100 bg-white p-3">
          <Text className="text-xs font-medium uppercase tracking-wide text-slate-400">Temps</Text>
          <Text className="mt-1 text-lg font-bold text-slate-900">
            {totalMinutes} min
            {recipe.prep_minutes > 0 && recipe.cook_minutes > 0
              ? ` (${recipe.prep_minutes} + ${recipe.cook_minutes})`
              : ""}
          </Text>
        </View>
        <View className="flex-1 rounded-2xl border border-slate-100 bg-white p-3">
          <Text className="text-xs font-medium uppercase tracking-wide text-slate-400">
            Portions
          </Text>
          <Text className="mt-1 text-lg font-bold text-slate-900">{recipe.servings}</Text>
        </View>
      </View>

      {recipe.tags.length > 0 ? (
        <View className="mb-6 flex-row flex-wrap gap-2">
          {recipe.tags.map((tag) => (
            <View key={tag} className="rounded-full bg-emerald-50 px-3 py-1">
              <Text className="text-xs font-semibold text-emerald-700">{tag}</Text>
            </View>
          ))}
        </View>
      ) : null}

      <Text className="mb-2 text-sm font-medium text-slate-700">Ingrédients</Text>
      <View className="mb-6 rounded-2xl border border-slate-100 bg-white p-4">
        {recipe.ingredients.length === 0 ? (
          <Text className="text-sm text-slate-500">Aucun ingrédient renseigné.</Text>
        ) : (
          recipe.ingredients.map((ingredient, index) => (
            <View
              key={ingredient.id}
              className={`flex-row items-start py-2 ${index > 0 ? "border-t border-slate-100" : ""}`}
            >
              <View className="mr-3 mt-1 h-2 w-2 rounded-full bg-emerald-500" />
              <View className="flex-1">
                <Text className="text-base text-slate-900">{ingredient.name}</Text>
                {ingredient.note ? (
                  <Text className="text-sm text-slate-400">{ingredient.note}</Text>
                ) : null}
              </View>
              <Text className="text-sm font-medium text-slate-500">
                {formatQuantity(ingredient.quantity)} {ingredient.unit}
              </Text>
            </View>
          ))
        )}
      </View>

      <Text className="mb-2 text-sm font-medium text-slate-700">Instructions</Text>
      <View className="mb-6 rounded-2xl border border-slate-100 bg-white p-4">
        {recipe.steps.length > 0 ? (
          recipe.steps.map((step, index) => (
            <View key={index} className="mb-3 flex-row items-start">
              <Text className="mr-3 text-sm font-bold text-emerald-600">{index + 1}.</Text>
              <Text className="flex-1 text-base leading-relaxed text-slate-700">{step}</Text>
            </View>
          ))
        ) : recipe.instructions ? (
          <Text className="text-base leading-relaxed text-slate-700">{recipe.instructions}</Text>
        ) : (
          <Text className="text-sm text-slate-500">Aucune instruction renseignée.</Text>
        )}
      </View>

      <Pressable
        onPress={confirmDelete}
        disabled={deleting}
        className="mb-6 w-full flex-row items-center justify-center rounded-xl border border-red-200 bg-red-50 py-3.5 active:bg-red-100"
      >
        {deleting ? (
          <ActivityIndicator color="#dc2626" />
        ) : (
          <>
            <Ionicons name="trash-outline" size={18} color="#dc2626" />
            <Text className="ml-2 text-base font-semibold text-red-600">
              Supprimer la recette
            </Text>
          </>
        )}
      </Pressable>
    </Screen>
  );
}
