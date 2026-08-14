import { Ionicons } from "@expo/vector-icons";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, Pressable, RefreshControl, Text, View } from "react-native";

import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { listRecipes, type RecipeRead } from "@/lib/recipes";

export default function RecipesScreen() {
  const [recipes, setRecipes] = useState<RecipeRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await listRecipes();
      setRecipes(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue");
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      setLoading(true);
      setError(null);
      listRecipes()
        .then((data) => {
          if (cancelled) return;
          setRecipes(data);
        })
        .catch((err) => {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "Une erreur est survenue");
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
      return () => {
        cancelled = true;
      };
    }, []),
  );

  async function handleRefresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  return (
    <Screen
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={handleRefresh}
          tintColor="#059669"
          colors={["#059669"]}
        />
      }
    >
      <View className="mb-6 flex-row items-center justify-between">
        <ScreenHeader title="Recettes" subtitle="Votre carnet de recettes" />
        <Pressable
          onPress={() => router.push("/new-recipe")}
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
        <View className="flex-1 items-center justify-center py-12">
          <ActivityIndicator size="large" color="#059669" />
        </View>
      ) : recipes.length === 0 ? (
        <View className="flex-1 items-center justify-center py-12">
          <Text className="text-base text-slate-500">Aucune recette pour l&apos;instant.</Text>
          <Pressable onPress={() => router.push("/new-recipe")} className="mt-2 py-2">
            <Text className="text-base font-semibold text-emerald-600">
              Créer une nouvelle recette
            </Text>
          </Pressable>
        </View>
      ) : (
        recipes.map((recipe) => {
          const totalMinutes = recipe.prep_minutes + recipe.cook_minutes;
          const ingredientCount = recipe.ingredients.length;
          return (
            <Pressable
              key={recipe.id}
              onPress={() =>
                router.push({ pathname: "/recipe/[id]", params: { id: recipe.id } })
              }
              className="mb-3 rounded-2xl border border-slate-100 bg-white p-4"
            >
              <Text className="text-base font-semibold text-slate-900">{recipe.name}</Text>
              <Text className="mt-0.5 text-sm text-slate-400">
                {totalMinutes} min · {recipe.servings} portion
                {recipe.servings > 1 ? "s" : ""} · {ingredientCount} ingrédient
                {ingredientCount > 1 ? "s" : ""}
              </Text>
            </Pressable>
          );
        })
      )}
    </Screen>
  );
}
