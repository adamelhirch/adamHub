import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";

import { RecipeGroceriesSheet } from "@/components/recipe-groceries-sheet";
import { RecipePlanModal } from "@/components/recipe-plan-modal";
import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import {
  addRecipeToGroceries,
  confirmRecipeCooked,
  deleteRecipe,
  getRecipe,
  listPantryItems,
  PantryItemRead,
  RecipeRead,
  scheduleMealPlan,
  unconfirmRecipeCooked,
  updateRecipe,
} from "@/lib/api";

function formatQuantity(quantity: number): string {
  const rounded = Math.round(quantity * 100) / 100;
  return String(rounded);
}

export default function RecipeDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const recipeId = Number(id);
  const invalidId = !Number.isFinite(recipeId);

  const [recipe, setRecipe] = useState<RecipeRead | null>(null);
  const [pantryItems, setPantryItems] = useState<PantryItemRead[]>([]);
  const [loading, setLoading] = useState(() => !invalidId);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(invalidId ? "Recette introuvable." : null);

  // Servings Stepper State
  const [servings, setServings] = useState(2);

  // Cook State
  const [cooking, setCooking] = useState(false);
  const [isCooked, setIsCooked] = useState(false);

  // Sheet & Modal Visibility
  const [groceriesSheetVisible, setGroceriesSheetVisible] = useState(false);
  const [planModalVisible, setPlanModalVisible] = useState(false);

  // Inline Instructions Editing State
  const [isEditingInstructions, setIsEditingInstructions] = useState(false);
  const [instructionText, setInstructionText] = useState("");
  const [savingInstructions, setSavingInstructions] = useState(false);

  useEffect(() => {
    if (invalidId) return;
    let active = true;

    Promise.all([
      getRecipe(recipeId),
      listPantryItems().catch(() => []),
    ])
      .then(([recData, pData]) => {
        if (active) {
          setRecipe(recData);
          setServings(recData.servings || 2);
          setInstructionText(recData.instructions || "");
          setPantryItems(pData);
        }
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
      ]
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

  async function handleToggleCook() {
    if (!recipe) return;
    setCooking(true);
    try {
      if (!isCooked) {
        const res = await confirmRecipeCooked(recipe.id, { servings_override: servings });
        setIsCooked(true);
        const updatedPantry = await listPantryItems();
        setPantryItems(updatedPantry);

        if (res.missing_ingredients && res.missing_ingredients.length > 0) {
          Alert.alert(
            "Cuisiné avec déficit",
            `Recette cuisinée pour ${servings} personnes. Il vous manquait ${res.missing_ingredients.length} ingrédient(s).`,
            [
              { text: "OK" },
              {
                text: "Ajouter aux courses",
                onPress: () => setGroceriesSheetVisible(true),
              },
            ]
          );
        } else {
          Alert.alert("Bon appétit !", "Les ingrédients ont été décomptés de votre garde-manger.");
        }
      } else {
        await unconfirmRecipeCooked(recipe.id);
        setIsCooked(false);
        const updatedPantry = await listPantryItems();
        setPantryItems(updatedPantry);
        Alert.alert("Annulé", "La cuisson a été annulée et le stock du garde-manger a été restauré.");
      }
    } catch (err) {
      Alert.alert("Erreur", err instanceof Error ? err.message : "Erreur lors de la confirmation");
    } finally {
      setCooking(false);
    }
  }

  async function handleSaveInstructions() {
    if (!recipe) return;
    setSavingInstructions(true);
    try {
      const updated = await updateRecipe(recipe.id, { instructions: instructionText });
      setRecipe(updated);
      setIsEditingInstructions(false);
      Alert.alert("Enregistré", "Instructions mises à jour avec succès.");
    } catch (err) {
      Alert.alert("Erreur", err instanceof Error ? err.message : "Impossible d'enregistrer.");
    } finally {
      setSavingInstructions(false);
    }
  }

  async function handleConfirmAddToGroceries(ingredientIds: number[], targetServings: number) {
    if (!recipe) return;
    try {
      const res = await addRecipeToGroceries(recipe.id, {
        ingredient_ids: ingredientIds,
        servings_override: targetServings,
      });
      Alert.alert("Ajouté aux courses", `${res.added_count} article(s) ajouté(s) à votre liste de courses.`);
    } catch (err) {
      Alert.alert("Erreur", err instanceof Error ? err.message : "Erreur d'ajout aux courses.");
    }
  }

  async function handleConfirmSchedule(plannedAt: string, autoAddMissing: boolean) {
    if (!recipe) return;
    await scheduleMealPlan({
      recipe_id: recipe.id,
      planned_at: plannedAt,
      servings_override: servings,
      auto_add_missing_ingredients: autoAddMissing,
    });
    Alert.alert("Repas planifié", `« ${recipe.name} » a été ajouté à votre agenda.`);
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
            {error ?? "Cette recette n'existe pas."}
          </Text>
        </View>
      </Screen>
    );
  }

  const baseServings = recipe.servings > 0 ? recipe.servings : 1;
  const ratio = servings / baseServings;
  const totalMinutes = (recipe.prep_minutes || 0) + (recipe.cook_minutes || 0);

  return (
    <Screen>
      <ScrollView showsVerticalScrollIndicator={false}>
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

        {/* Action Buttons Row */}
        <View className="mb-6 flex-row gap-2">
          <Pressable
            onPress={handleToggleCook}
            disabled={cooking}
            className={`flex-1 flex-row items-center justify-center rounded-2xl py-3 shadow-sm active:opacity-90 ${
              isCooked ? "bg-amber-600" : "bg-emerald-600"
            }`}
          >
            {cooking ? (
              <ActivityIndicator color="#ffffff" size="small" />
            ) : (
              <>
                <Ionicons
                  name={isCooked ? "arrow-undo-outline" : "restaurant-outline"}
                  size={18}
                  color="#ffffff"
                />
                <Text className="ml-1.5 text-xs font-bold text-white">
                  {isCooked ? "Annuler cuisine" : "Cuisiner"}
                </Text>
              </>
            )}
          </Pressable>

          <Pressable
            onPress={() => setGroceriesSheetVisible(true)}
            className="flex-1 flex-row items-center justify-center rounded-2xl border border-slate-200 bg-white py-3 shadow-sm active:bg-slate-50"
          >
            <Ionicons name="cart-outline" size={18} color="#059669" />
            <Text className="ml-1.5 text-xs font-bold text-slate-800">Courses</Text>
          </Pressable>

          <Pressable
            onPress={() => setPlanModalVisible(true)}
            className="flex-1 flex-row items-center justify-center rounded-2xl border border-slate-200 bg-white py-3 shadow-sm active:bg-slate-50"
          >
            <Ionicons name="calendar-outline" size={18} color="#4f46e5" />
            <Text className="ml-1.5 text-xs font-bold text-slate-800">Planifier</Text>
          </Pressable>
        </View>

        {/* Time and Interactive Servings Stepper */}
        <View className="mb-6 flex-row gap-3">
          <View className="flex-1 rounded-2xl border border-slate-100 bg-white p-3 shadow-sm">
            <Text className="text-xs font-medium uppercase tracking-wide text-slate-400">Temps</Text>
            <Text className="mt-1 text-lg font-bold text-slate-900">
              {totalMinutes} min
              {recipe.prep_minutes > 0 && recipe.cook_minutes > 0
                ? ` (${recipe.prep_minutes} + ${recipe.cook_minutes})`
                : ""}
            </Text>
          </View>

          <View className="flex-1 rounded-2xl border border-slate-100 bg-white p-3 shadow-sm">
            <Text className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Portions
            </Text>
            <View className="mt-1 flex-row items-center justify-between">
              <Text className="text-lg font-bold text-slate-900">
                {servings} {servings > 1 ? "pers." : "pers."}
              </Text>
              <View className="flex-row items-center gap-1">
                <Pressable
                  onPress={() => setServings((s) => Math.max(1, s - 1))}
                  className="h-7 w-7 items-center justify-center rounded-full bg-slate-100 border border-slate-200 active:bg-slate-200"
                >
                  <Ionicons name="remove" size={14} color="#0f172a" />
                </Pressable>
                <Pressable
                  onPress={() => setServings((s) => Math.min(24, s + 1))}
                  className="h-7 w-7 items-center justify-center rounded-full bg-slate-100 border border-slate-200 active:bg-slate-200"
                >
                  <Ionicons name="add" size={14} color="#0f172a" />
                </Pressable>
              </View>
            </View>
          </View>
        </View>

        {recipe.tags && recipe.tags.length > 0 ? (
          <View className="mb-6 flex-row flex-wrap gap-2">
            {recipe.tags.map((tag) => (
              <View key={tag} className="rounded-full bg-emerald-50 px-3 py-1">
                <Text className="text-xs font-semibold text-emerald-700">{tag}</Text>
              </View>
            ))}
          </View>
        ) : null}

        {/* Scaled Ingredients List */}
        <View className="mb-2 flex-row items-center justify-between">
          <Text className="text-sm font-bold text-slate-700">Ingrédients</Text>
          {ratio !== 1 && (
            <Text className="text-xs font-semibold text-emerald-600">
              Ajusté pour {servings} pers. (x{Math.round(ratio * 100) / 100})
            </Text>
          )}
        </View>
        <View className="mb-6 rounded-2xl border border-slate-100 bg-white p-4 shadow-sm">
          {!recipe.ingredients || recipe.ingredients.length === 0 ? (
            <Text className="text-sm text-slate-500">Aucun ingrédient renseigné.</Text>
          ) : (
            recipe.ingredients.map((ingredient, index) => {
              const scaledQuantity = (ingredient.quantity || 0) * ratio;
              return (
                <View
                  key={ingredient.id}
                  className={`flex-row items-start py-2.5 ${
                    index > 0 ? "border-t border-slate-100" : ""
                  }`}
                >
                  <View className="mr-3 mt-1.5 h-2 w-2 rounded-full bg-emerald-500" />
                  <View className="flex-1">
                    <Text className="text-base font-semibold text-slate-900">
                      {ingredient.name}
                    </Text>
                    {ingredient.note ? (
                      <Text className="text-xs text-slate-400">{ingredient.note}</Text>
                    ) : null}
                  </View>
                  <Text className="text-sm font-bold text-slate-600">
                    {formatQuantity(scaledQuantity)} {ingredient.unit}
                  </Text>
                </View>
              );
            })
          )}
        </View>

        {/* Instructions with In-Place Editor */}
        <View className="mb-2 flex-row items-center justify-between">
          <Text className="text-sm font-bold text-slate-700">Instructions</Text>
          {!isEditingInstructions ? (
            <Pressable
              onPress={() => setIsEditingInstructions(true)}
              hitSlop={8}
              className="flex-row items-center"
            >
              <Ionicons name="pencil" size={14} color="#059669" />
              <Text className="ml-1 text-xs font-bold text-emerald-600">Modifier</Text>
            </Pressable>
          ) : (
            <View className="flex-row items-center gap-2">
              <Pressable
                onPress={() => {
                  setInstructionText(recipe.instructions || "");
                  setIsEditingInstructions(false);
                }}
                hitSlop={8}
              >
                <Text className="text-xs font-semibold text-slate-400">Annuler</Text>
              </Pressable>
              <Pressable
                onPress={handleSaveInstructions}
                disabled={savingInstructions}
                hitSlop={8}
                className="flex-row items-center rounded-lg bg-emerald-600 px-2.5 py-1"
              >
                {savingInstructions ? (
                  <ActivityIndicator size="small" color="#ffffff" />
                ) : (
                  <>
                    <Ionicons name="checkmark" size={14} color="#ffffff" />
                    <Text className="ml-1 text-xs font-bold text-white">Enregistrer</Text>
                  </>
                )}
              </Pressable>
            </View>
          )}
        </View>

        <View className="mb-6 rounded-2xl border border-slate-100 bg-white p-4 shadow-sm">
          {isEditingInstructions ? (
            <TextInput
              multiline
              value={instructionText}
              onChangeText={setInstructionText}
              className="min-h-[120px] text-base leading-relaxed text-slate-800"
              placeholder="Saisissez les instructions de la recette..."
              placeholderTextColor="#94a3b8"
              autoFocus
            />
          ) : recipe.steps && recipe.steps.length > 0 ? (
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

        {/* Delete Button */}
        <Pressable
          onPress={confirmDelete}
          disabled={deleting}
          className="mb-8 w-full flex-row items-center justify-center rounded-2xl border border-red-200 bg-red-50 py-3.5 active:bg-red-100"
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
      </ScrollView>

      {/* Groceries Bottom Sheet */}
      <RecipeGroceriesSheet
        visible={groceriesSheetVisible}
        recipe={recipe}
        pantryItems={pantryItems}
        onClose={() => setGroceriesSheetVisible(false)}
        onConfirmAdd={handleConfirmAddToGroceries}
      />

      {/* Plan Modal */}
      <RecipePlanModal
        visible={planModalVisible}
        recipe={recipe}
        onClose={() => setPlanModalVisible(false)}
        onSchedule={handleConfirmSchedule}
      />
    </Screen>
  );
}
