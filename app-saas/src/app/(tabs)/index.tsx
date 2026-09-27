import { Ionicons } from "@expo/vector-icons";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  View,
} from "react-native";

import { Screen } from "@/components/screen";
import {
  GroceryItemRead,
  listGroceryItems,
  listMealPlans,
  listPantryItems,
  MealPlanRead,
  PantryItemRead,
  confirmRecipeCooked,
} from "@/lib/api";
import {
  listSupermarketConnections,
  SupermarketConnectionRead,
} from "@/lib/supermarket-api";
import { me } from "@/lib/auth";
import { Alert } from "@/lib/alert";

function formatTodayDate(): string {
  const date = new Date();
  return new Intl.DateTimeFormat("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(date);
}

export default function DashboardHomeScreen() {
  const [userName, setUserName] = useState<string>("Gourmet");
  const [groceries, setGroceries] = useState<GroceryItemRead[]>([]);
  const [pantryItems, setPantryItems] = useState<PantryItemRead[]>([]);
  const [todayMeals, setTodayMeals] = useState<MealPlanRead[]>([]);
  const [connections, setConnections] = useState<SupermarketConnectionRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const todayStr = new Date().toISOString().split("T")[0];
      const [userData, groceriesData, pantryData, mealsData, connData] =
        await Promise.all([
          me().catch(() => null),
          listGroceryItems().catch(() => []),
          listPantryItems().catch(() => []),
          listMealPlans({ date_from: todayStr, date_to: todayStr }).catch(() => []),
          listSupermarketConnections().catch(() => []),
        ]);

      if (userData?.display_name) {
        setUserName(userData.display_name.split(" ")[0]);
      }
      setGroceries(groceriesData);
      setPantryItems(pantryData);
      setTodayMeals(mealsData);
      setConnections(connData);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Erreur lors du chargement des données",
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [loadData]),
  );

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadData();
  }, [loadData]);

  const uncheckedGroceriesCount = groceries.filter((g) => !g.checked).length;
  const lowStockPantryCount = pantryItems.filter(
    (p) => p.quantity <= p.min_quantity,
  ).length;

  const nextMeal = todayMeals.find((m) => !m.cooked) || todayMeals[0];
  const activeConnections = connections.filter((c) => c.is_active);

  async function handleCookNextMeal(meal: MealPlanRead) {
    try {
      await confirmRecipeCooked(meal.recipe_id, {
        servings_override: meal.servings_override ?? undefined,
      });
      Alert.alert(
        "Bon appétit !",
        `La recette ${meal.recipe_name} a été marquée comme cuisinée. Vos stocks de garde-manger ont été mis à jour.`,
      );
      loadData();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erreur lors de la validation";
      Alert.alert("Erreur", msg);
    }
  }

  return (
    <Screen
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          tintColor="#10b981"
          colors={["#10b981"]}
        />
      }
    >
      {/* Header */}
      <View className="mb-4">
        <Text className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
          {formatTodayDate()}
        </Text>
        <Text className="text-2xl font-bold text-slate-100 mt-0.5">
          Bonjour, {userName} 👋
        </Text>
      </View>

      {error ? (
        <View className="mb-4 rounded-xl bg-red-950/40 border border-red-800 p-3">
          <Text className="text-xs text-red-300">{error}</Text>
        </View>
      ) : null}

      {loading ? (
        <View className="flex-1 items-center justify-center py-16">
          <ActivityIndicator size="large" color="#10b981" />
        </View>
      ) : (
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ gap: 16, paddingBottom: 24 }}>
          {/* Bento Stats Grid */}
          <View className="flex-row gap-3">
            {/* Courses Card */}
            <Pressable
              onPress={() => router.push("/(tabs)/groceries")}
              className="flex-1 bg-slate-900 border border-slate-800 rounded-2xl p-3.5 active:bg-slate-800/80"
            >
              <View className="w-8 h-8 rounded-lg bg-emerald-500/20 items-center justify-center mb-2">
                <Ionicons name="cart" size={18} color="#10b981" />
              </View>
              <Text className="text-2xl font-bold text-slate-100">
                {uncheckedGroceriesCount}
              </Text>
              <Text className="text-xs text-slate-400 mt-0.5">
                À acheter
              </Text>
            </Pressable>

            {/* Garde-manger Card */}
            <Pressable
              onPress={() => router.push("/(tabs)/pantry")}
              className="flex-1 bg-slate-900 border border-slate-800 rounded-2xl p-3.5 active:bg-slate-800/80"
            >
              <View className="w-8 h-8 rounded-lg bg-sky-500/20 items-center justify-center mb-2">
                <Ionicons name="cube" size={18} color="#38bdf8" />
              </View>
              <Text className="text-2xl font-bold text-slate-100">
                {pantryItems.length}
              </Text>
              <Text className="text-xs text-slate-400 mt-0.5">
                {lowStockPantryCount > 0
                  ? `${lowStockPantryCount} en stock bas`
                  : "Produits en stock"}
              </Text>
            </Pressable>
          </View>

          {/* Supermarket Drive Banner */}
          <Pressable
            onPress={() => router.push("/supermarket-connect" as any)}
            className="bg-slate-900 border border-slate-800 rounded-2xl p-4 active:bg-slate-800/60"
          >
            <View className="flex-row items-center justify-between">
              <View className="flex-row items-center gap-3">
                <View className="w-10 h-10 rounded-xl bg-blue-500/20 items-center justify-center">
                  <Ionicons name="storefront" size={20} color="#3b82f6" />
                </View>
                <View>
                  <Text className="text-sm font-bold text-slate-100">
                    Supermarchés Drive
                  </Text>
                  <Text className="text-xs text-slate-400">
                    {activeConnections.length > 0
                      ? `${activeConnections.length} enseigne(s) connectée(s)`
                      : "Connecter Leclerc, Carrefour, Auchan..."}
                  </Text>
                </View>
              </View>
              <View className="flex-row items-center gap-1 bg-slate-800 px-2.5 py-1.5 rounded-lg">
                <Text className="text-xs font-semibold text-emerald-400">
                  {activeConnections.length > 0 ? "Gérer" : "Connecter"}
                </Text>
                <Ionicons name="chevron-forward" size={14} color="#10b981" />
              </View>
            </View>
          </Pressable>

          {/* Next Planned Meal Card */}
          <View className="bg-slate-900 border border-slate-800 rounded-2xl p-4 gap-3">
            <View className="flex-row items-center justify-between">
              <View className="flex-row items-center gap-2">
                <Ionicons name="restaurant" size={18} color="#f59e0b" />
                <Text className="text-sm font-bold text-slate-100">
                  Prochain repas
                </Text>
              </View>
              <Pressable
                onPress={() => router.push("/plan-meal")}
                hitSlop={8}
              >
                <Text className="text-xs font-semibold text-emerald-400">
                  Planifier
                </Text>
              </Pressable>
            </View>

            {nextMeal ? (
              <View className="bg-slate-950/60 rounded-xl p-3.5 gap-2.5 border border-slate-800/60">
                <View className="flex-row items-center justify-between">
                  <Text className="text-base font-bold text-slate-100 flex-1 mr-2">
                    {nextMeal.recipe_name}
                  </Text>
                  <View className="bg-amber-500/20 px-2 py-0.5 rounded-full">
                    <Text className="text-[10px] font-semibold text-amber-300 uppercase">
                      {nextMeal.slot ?? "Repas"}
                    </Text>
                  </View>
                </View>

                {nextMeal.note ? (
                  <Text className="text-xs text-slate-400 italic">
                    « {nextMeal.note} »
                  </Text>
                ) : null}

                <View className="flex-row items-center justify-between pt-1 border-t border-slate-800/50">
                  <Pressable
                    onPress={() =>
                      router.push({
                        pathname: "/recipe/[id]",
                        params: { id: nextMeal.recipe_id },
                      })
                    }
                    className="flex-row items-center gap-1"
                  >
                    <Ionicons name="book-outline" size={14} color="#38bdf8" />
                    <Text className="text-xs text-sky-400">Voir la recette</Text>
                  </Pressable>

                  {!nextMeal.cooked ? (
                    <Pressable
                      onPress={() => handleCookNextMeal(nextMeal)}
                      className="bg-emerald-600 active:bg-emerald-700 px-3 py-1.5 rounded-lg flex-row items-center gap-1.5"
                    >
                      <Ionicons name="checkmark-circle-outline" size={14} color="#ffffff" />
                      <Text className="text-xs font-bold text-white">Cuisiner</Text>
                    </Pressable>
                  ) : (
                    <Text className="text-xs text-emerald-400">Cuisiné ✓</Text>
                  )}
                </View>
              </View>
            ) : (
              <View className="py-4 items-center justify-center gap-2">
                <Text className="text-xs text-slate-400">
                  Aucun repas prévu pour aujourd&apos;hui.
                </Text>
                <Pressable
                  onPress={() => router.push("/plan-meal")}
                  className="bg-slate-800 px-3 py-1.5 rounded-lg active:bg-slate-700"
                >
                  <Text className="text-xs font-semibold text-emerald-400">
                    + Choisir une recette
                  </Text>
                </Pressable>
              </View>
            )}
          </View>

          {/* Quick Action Grid */}
          <View className="gap-2">
            <Text className="text-xs font-semibold uppercase tracking-wider text-slate-400 px-1">
              Raccourcis
            </Text>
            <View className="flex-row flex-wrap gap-2.5">
              <Pressable
                onPress={() => router.push("/new-grocery")}
                className="flex-1 min-w-[45%] bg-slate-900 border border-slate-800 rounded-xl p-3 flex-row items-center gap-2.5 active:bg-slate-800"
              >
                <Ionicons name="add-circle" size={20} color="#10b981" />
                <Text className="text-xs font-medium text-slate-200">
                  + Article courses
                </Text>
              </Pressable>

              <Pressable
                onPress={() => router.push("/barcode-scanner")}
                className="flex-1 min-w-[45%] bg-slate-900 border border-slate-800 rounded-xl p-3 flex-row items-center gap-2.5 active:bg-slate-800"
              >
                <Ionicons name="barcode-outline" size={20} color="#38bdf8" />
                <Text className="text-xs font-medium text-slate-200">
                  Scanner code-barres
                </Text>
              </Pressable>

              <Pressable
                onPress={() => router.push("/new-recipe")}
                className="flex-1 min-w-[45%] bg-slate-900 border border-slate-800 rounded-xl p-3 flex-row items-center gap-2.5 active:bg-slate-800"
              >
                <Ionicons name="restaurant-outline" size={20} color="#f59e0b" />
                <Text className="text-xs font-medium text-slate-200">
                  Nouvelle recette
                </Text>
              </Pressable>

              <Pressable
                onPress={() => router.push("/assistant")}
                className="flex-1 min-w-[45%] bg-slate-900 border border-slate-800 rounded-xl p-3 flex-row items-center gap-2.5 active:bg-slate-800"
              >
                <Ionicons name="sparkles" size={20} color="#a855f7" />
                <Text className="text-xs font-medium text-slate-200">
                  Idée recette IA
                </Text>
              </Pressable>
            </View>
          </View>
        </ScrollView>
      )}
    </Screen>
  );
}
