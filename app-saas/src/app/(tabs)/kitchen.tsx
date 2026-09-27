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

import { Alert } from "@/lib/alert";

import { RecipeCardSwipeable } from "@/components/recipe-card-swipeable";
import { RecipeGroceriesSheet } from "@/components/recipe-groceries-sheet";
import { RecipePlanModal } from "@/components/recipe-plan-modal";
import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { SupermarketStoreModal } from "@/components/supermarket-store-modal";
import { CartReviewModal } from "@/components/cart-review-modal";
import { GroceryItemEditModal } from "@/components/grocery-item-edit-modal";
import { GroceryItemSwipeable } from "@/components/grocery-item-swipeable";
import {
  confirmPickup,
  createCartJob,
  deleteCartJob,
  getActiveCartJob,
  GroceryToCartJobRead,
  OptimizationStrategy,
  SupermarketStore,
} from "@/lib/supermarket-api";
import {
  addRecipeToGroceries,
  confirmRecipeCooked,
  GroceryItemRead,
  listGroceryItems,
  listPantryItems,
  listRecipes,
  PantryItemRead,
  RecipeRead,
  scheduleMealPlan,
  updateGroceryItem,
} from "@/lib/api";
import { deleteGroceryItem } from "@/lib/groceries";

type KitchenSection = "groceries" | "recipes" | "pantry";

export default function KitchenScreen() {
  const [activeSection, setActiveSection] = useState<KitchenSection>("groceries");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [groceries, setGroceries] = useState<GroceryItemRead[]>([]);
  const [recipes, setRecipes] = useState<RecipeRead[]>([]);
  const [pantryItems, setPantryItems] = useState<PantryItemRead[]>([]);

  // Interactivity state: shaking, bottom sheets & modals
  const [shakingRecipeId, setShakingRecipeId] = useState<number | null>(null);
  const [groceriesSheetRecipe, setGroceriesSheetRecipe] = useState<RecipeRead | null>(null);
  const [planModalRecipe, setPlanModalRecipe] = useState<RecipeRead | null>(null);

  const [showDriveModal, setShowDriveModal] = useState(false);
  const [preparingDrive, setPreparingDrive] = useState(false);
  const [activeCartJob, setActiveCartJob] = useState<GroceryToCartJobRead | null>(null);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [editingGroceryItem, setEditingGroceryItem] = useState<GroceryItemRead | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const [gData, rData, pData, activeCart] = await Promise.all([
        listGroceryItems().catch((e) => {
          console.error("Failed to load groceries:", e);
          throw e;
        }),
        listRecipes().catch((e) => {
          console.error("Failed to load recipes:", e);
          return [];
        }),
        listPantryItems().catch((e) => {
          console.error("Failed to load pantry:", e);
          return [];
        }),
        getActiveCartJob().catch((e) => {
          console.error("Failed to load active cart job:", e);
          return null;
        }),
      ]);
      setGroceries(gData);
      setRecipes(rData);
      setPantryItems(pData);
      setActiveCartJob(activeCart);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur de chargement");
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

  async function handleStartDriveCart(
    store: SupermarketStore,
    externalId: string,
    _label: string,
    strategy: OptimizationStrategy,
  ) {
    setShowDriveModal(false);
    setPreparingDrive(true);
    try {
      const job = await createCartJob({
        store,
        external_store_id: externalId,
        optimization_strategy: strategy,
      });
      setActiveCartJob(job);
      setShowReviewModal(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Impossible de préparer le panier drive.";
      Alert.alert("Erreur", msg);
    } finally {
      setPreparingDrive(false);
    }
  }

  async function handleToggleGrocery(id: number) {
    const item = groceries.find((g) => g.id === id);
    if (!item) return;
    const next = !item.checked;
    setGroceries((prev) =>
      prev.map((g) => (g.id === id ? { ...g, checked: next } : g)),
    );
    try {
      await updateGroceryItem(id, { checked: next });
    } catch {
      setGroceries((prev) =>
        prev.map((g) => (g.id === id ? { ...g, checked: item.checked } : g)),
      );
      Alert.alert("Erreur", "Impossible de mettre à jour l'article.");
    }
  }

  function handleDeleteGrocery(id: number) {
    Alert.alert("Supprimer", "Retirer cet article de la liste ?", [
      { text: "Annuler", style: "cancel" },
      {
        text: "Supprimer",
        style: "destructive",
        onPress: async () => {
          try {
            await deleteGroceryItem(id);
            setGroceries((prev) => prev.filter((g) => g.id !== id));
          } catch {
            Alert.alert("Erreur", "Impossible de supprimer l'article.");
          }
        },
      },
    ]);
  }

  async function handleConfirmPickupFromBanner() {
    if (!activeCartJob) return;
    Alert.alert(
      "Confirmer le retrait",
      "Avez-vous bien récupéré votre commande Drive ? Vos articles seront automatiquement ajoutés à votre garde-manger.",
      [
        { text: "Annuler", style: "cancel" },
        {
          text: "Confirmer",
          onPress: async () => {
            try {
              await confirmPickup(activeCartJob.id);
              Alert.alert("Succès", "Commande confirmée ! Votre garde-manger a été mis à jour.");
              await loadData();
            } catch (err: unknown) {
              const msg = err instanceof Error ? err.message : "Erreur lors de la confirmation.";
              Alert.alert("Erreur", msg);
            }
          },
        },
      ],
    );
  }

  async function handleDeleteActiveCartJob() {
    if (!activeCartJob) return;
    Alert.alert(
      "Abandonner le panier drive",
      "Voulez-vous supprimer ce panier drive ? Vos articles resteront dans votre liste de courses.",
      [
        { text: "Annuler", style: "cancel" },
        {
          text: "Supprimer",
          style: "destructive",
          onPress: async () => {
            try {
              await deleteCartJob(activeCartJob.id);
              setActiveCartJob(null);
              await loadData();
              Alert.alert("Panier supprimé", "Le panier drive a été abandonné.");
            } catch (err: unknown) {
              const msg = err instanceof Error ? err.message : "Erreur lors de la suppression.";
              Alert.alert("Erreur", msg);
            }
          },
        },
      ],
    );
  }

  async function handleSaveGroceryEdit(
    id: number,
    payload: {
      name: string;
      quantity: number;
      unit: string;
      category?: string | null;
    },
  ) {
    try {
      const updated = await updateGroceryItem(id, payload);
      setGroceries((prev) =>
        prev.map((g) => (g.id === id ? updated : g)),
      );
      setEditingGroceryItem(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Impossible de modifier l'article.";
      Alert.alert("Erreur", msg);
    }
  }

  async function handleCookShort(recipe: RecipeRead) {
    try {
      const res = await confirmRecipeCooked(recipe.id);
      const updatedPantry = await listPantryItems();
      setPantryItems(updatedPantry);

      if (res.missing_ingredients && res.missing_ingredients.length > 0) {
        setShakingRecipeId(recipe.id);
        setTimeout(() => setShakingRecipeId(null), 350);
        Alert.alert(
          "Cuisiné !",
          `« ${recipe.name} » a été enregistrée comme cuisinée. Attention : ${res.missing_ingredients.length} ingrédient(s) n'étaient pas en stock dans votre garde-manger.`
        );
      } else {
        Alert.alert(
          "Cuisiné !",
          `Les ingrédients pour « ${recipe.name} » ont été décomptés du garde-manger.`
        );
      }
    } catch (err) {
      Alert.alert("Erreur", err instanceof Error ? err.message : "Impossible de confirmer la préparation.");
    }
  }

  function handlePlanLong(recipe: RecipeRead) {
    setPlanModalRecipe(recipe);
  }

  function handleGroceriesSwipe(recipe: RecipeRead) {
    setGroceriesSheetRecipe(recipe);
  }

  async function handleConfirmAddToGroceries(ingredientIds: number[], servings: number) {
    if (!groceriesSheetRecipe) return;
    try {
      const res = await addRecipeToGroceries(groceriesSheetRecipe.id, {
        ingredient_ids: ingredientIds,
        servings_override: servings,
      });
      const updatedGroceries = await listGroceryItems();
      setGroceries(updatedGroceries);
      Alert.alert("Succès", `${res.added_count} ingrédient(s) ajouté(s) à la liste de courses.`);
    } catch (err) {
      Alert.alert("Erreur", err instanceof Error ? err.message : "Impossible d'ajouter aux courses.");
    }
  }

  async function handleConfirmSchedule(plannedAt: string, autoAddMissing: boolean) {
    if (!planModalRecipe) return;
    await scheduleMealPlan({
      recipe_id: planModalRecipe.id,
      planned_at: plannedAt,
      auto_add_missing_ingredients: autoAddMissing,
    });
    if (autoAddMissing) {
      const updatedGroceries = await listGroceryItems();
      setGroceries(updatedGroceries);
    }
    Alert.alert("Planifié", `Le repas « ${planModalRecipe.name} » a été ajouté à votre agenda.`);
  }

  const remainingGroceries = groceries.filter((g) => !g.checked).length;
  const lowStockPantry = pantryItems.filter((p) => p.quantity <= p.min_quantity).length;

  return (
    <Screen>
      <ScrollView
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        <ScreenHeader
          title="Cuisine & Repas"
          subtitle="Courses, recettes et stocks"
          showProfileButton={true}
        />



        {error ? (
          <View className="mb-4 rounded-xl bg-red-50 p-3">
            <Text className="text-sm text-red-600">{error}</Text>
          </View>
        ) : null}

        {/* Segmented Control */}
        <View className="mb-6 flex-row rounded-2xl bg-slate-100 p-1.5 shadow-sm">
          <Pressable
            testID="kitchen-tab-groceries"
            accessibilityRole="button"
            onPress={() => setActiveSection("groceries")}
            className={`flex-1 flex-row items-center justify-center py-2.5 rounded-xl ${
              activeSection === "groceries" ? "bg-white shadow-sm" : ""
            }`}
          >
            <Ionicons
              name="cart-outline"
              size={18}
              color={activeSection === "groceries" ? "#059669" : "#64748b"}
            />
            <Text
              className={`ml-1.5 text-xs font-semibold ${
                activeSection === "groceries" ? "text-slate-900" : "text-slate-600"
              }`}
            >
              Courses
            </Text>
            {remainingGroceries > 0 && (
              <View className="ml-1.5 rounded-full bg-emerald-100 px-1.5 py-0.2">
                <Text className="text-[10px] font-bold text-emerald-800">
                  {remainingGroceries}
                </Text>
              </View>
            )}
          </Pressable>

          <Pressable
            testID="kitchen-tab-recipes"
            accessibilityRole="button"
            onPress={() => setActiveSection("recipes")}
            className={`flex-1 flex-row items-center justify-center py-2.5 rounded-xl ${
              activeSection === "recipes" ? "bg-white shadow-sm" : ""
            }`}
          >
            <Ionicons
              name="restaurant-outline"
              size={18}
              color={activeSection === "recipes" ? "#059669" : "#64748b"}
            />
            <Text
              className={`ml-1.5 text-xs font-semibold ${
                activeSection === "recipes" ? "text-slate-900" : "text-slate-600"
              }`}
            >
              Recettes
            </Text>
            <View className="ml-1.5 rounded-full bg-slate-200 px-1.5 py-0.2">
              <Text className="text-[10px] font-bold text-slate-700">{recipes.length}</Text>
            </View>
          </Pressable>

          <Pressable
            testID="kitchen-tab-pantry"
            accessibilityRole="button"
            onPress={() => setActiveSection("pantry")}
            className={`flex-1 flex-row items-center justify-center py-2.5 rounded-xl ${
              activeSection === "pantry" ? "bg-white shadow-sm" : ""
            }`}
          >
            <Ionicons
              name="cube-outline"
              size={18}
              color={activeSection === "pantry" ? "#059669" : "#64748b"}
            />
            <Text
              className={`ml-1.5 text-xs font-semibold ${
                activeSection === "pantry" ? "text-slate-900" : "text-slate-600"
              }`}
            >
              Stock
            </Text>
            {lowStockPantry > 0 && (
              <View className="ml-1.5 rounded-full bg-amber-100 px-1.5 py-0.2">
                <Text className="text-[10px] font-bold text-amber-800">{lowStockPantry}</Text>
              </View>
            )}
          </Pressable>
        </View>

        {loading ? (
          <View className="py-12 items-center">
            <ActivityIndicator color="#10b981" />
          </View>
        ) : (
          <>
            {/* VIEW 1: COURSES */}
            {activeSection === "groceries" && (
              <View className="mb-8">
                {/* Actions row: Row 1 for adding/searching */}
                <View className="mb-3 flex-row items-center gap-2.5">
                  <Pressable
                    onPress={() => router.push("/new-grocery")}
                    className="flex-1 flex-row items-center justify-center rounded-xl bg-emerald-600 py-2.5 active:bg-emerald-700 shadow-sm"
                  >
                    <Ionicons name="add" size={18} color="#ffffff" />
                    <Text className="ml-1.5 text-xs font-semibold text-white">Ajouter un article</Text>
                  </Pressable>

                  <Pressable
                    onPress={() => router.push("/supermarket-search")}
                    className="flex-1 flex-row items-center justify-center rounded-xl border border-slate-200 bg-white py-2.5 active:bg-slate-50 shadow-xs"
                  >
                    <Ionicons name="search-outline" size={16} color="#475569" />
                    <Text className="ml-1.5 text-xs font-semibold text-slate-700">Rechercher</Text>
                  </Pressable>
                </View>

                {/* Drive section: either Active Cart Banner or "Préparer mon Drive" button */}
                {activeCartJob ? (
                  <View className="mb-4 rounded-2xl border border-emerald-200 bg-emerald-50/90 p-3.5 shadow-sm">
                    <View className="flex-row items-center justify-between">
                      <View className="flex-row items-center flex-1 mr-2">
                        <View className="h-9 w-9 items-center justify-center rounded-xl bg-emerald-600">
                          <Ionicons name="cart" size={18} color="#ffffff" />
                        </View>
                        <View className="ml-3 flex-1">
                          <Text className="text-xs font-semibold uppercase tracking-wider text-emerald-800">
                            Panier Drive actif • {activeCartJob.store.toUpperCase()}
                          </Text>
                          <Text className="text-xs text-emerald-700">
                            {activeCartJob.status === "synced"
                              ? "Prêt pour commande ou retrait"
                              : "En cours de revue"}
                            {activeCartJob.estimated_total_cents != null
                              ? ` • ${(activeCartJob.estimated_total_cents / 100).toFixed(2)} €`
                              : ""}
                          </Text>
                        </View>
                      </View>
                      <View className="flex-row items-center gap-1.5">
                        <Pressable
                          onPress={() => setShowReviewModal(true)}
                          className="rounded-lg bg-white px-2.5 py-1.5 border border-emerald-200 active:bg-emerald-100 shadow-sm"
                        >
                          <Text className="text-xs font-semibold text-emerald-800">Voir</Text>
                        </Pressable>
                        {activeCartJob.status === "synced" && (
                          <Pressable
                            onPress={handleConfirmPickupFromBanner}
                            className="rounded-lg bg-emerald-600 px-2.5 py-1.5 active:bg-emerald-700 shadow-sm"
                          >
                            <Text className="text-xs font-semibold text-white">Retiré</Text>
                          </Pressable>
                        )}
                        <Pressable
                          onPress={handleDeleteActiveCartJob}
                          className="rounded-lg bg-white p-1.5 border border-red-200 active:bg-red-50 shadow-sm"
                          hitSlop={6}
                        >
                          <Ionicons name="trash-outline" size={15} color="#dc2626" />
                        </Pressable>
                      </View>
                    </View>
                  </View>
                ) : (
                  <Pressable
                    onPress={() => setShowDriveModal(true)}
                    disabled={preparingDrive || groceries.length === 0}
                    className={`mb-4 flex-row items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50/90 px-4 py-2.5 shadow-xs active:bg-emerald-100 ${
                      groceries.length === 0 ? "opacity-50" : ""
                    }`}
                  >
                    <View className="flex-row items-center flex-1 mr-2">
                      <View className="h-8 w-8 items-center justify-center rounded-lg bg-emerald-600">
                        {preparingDrive ? (
                          <ActivityIndicator size="small" color="#ffffff" />
                        ) : (
                          <Ionicons name="cart" size={17} color="#ffffff" />
                        )}
                      </View>
                      <View className="ml-3 flex-1">
                        <Text className="text-xs font-bold text-emerald-900">
                          {preparingDrive ? "Préparation du panier..." : "Préparer mon Drive"}
                        </Text>
                        <Text className="text-[11px] text-emerald-700" numberOfLines={1}>
                          {remainingGroceries > 0
                            ? `${remainingGroceries} article(s) à commander chez votre commerçant`
                            : "Optimisation de panier automatique"}
                        </Text>
                      </View>
                    </View>
                    <Ionicons name="chevron-forward" size={16} color="#059669" />
                  </Pressable>
                )}

                {groceries.length === 0 ? (
                  <View className="rounded-2xl border border-slate-100 bg-white p-6 items-center justify-center shadow-sm">
                    <Ionicons name="cart-outline" size={36} color="#94a3b8" />
                    <Text className="mt-2 text-sm font-semibold text-slate-700">
                      Liste de courses vide
                    </Text>
                    <Text className="mt-1 text-center text-xs text-slate-400">
                      Ajoute des articles ou génère la liste automatiquement depuis tes plannings repas.
                    </Text>
                  </View>
                ) : (
                  <View className="rounded-2xl border border-slate-100 bg-white p-2 shadow-sm">
                    {groceries.map((item, index) => {
                      const isLast = index === groceries.length - 1;
                      const isInDriveCart = Boolean(
                        item.in_cart ||
                          activeCartJob?.items?.some(
                            (jobItem) =>
                              jobItem.grocery_item_id === item.id ||
                              jobItem.name.trim().toLowerCase() ===
                                item.name.trim().toLowerCase(),
                          ),
                      );
                      return (
                        <View
                          key={item.id}
                          className={!isLast ? "border-b border-slate-50" : ""}
                        >
                          <GroceryItemSwipeable
                            item={{ ...item, in_cart: isInDriveCart }}
                            onToggleChecked={handleToggleGrocery}
                            onRemove={() => handleDeleteGrocery(item.id)}
                            onOpenEdit={() => setEditingGroceryItem(item)}
                          />
                        </View>
                      );
                    })}
                  </View>
                )}
              </View>
            )}

            {/* VIEW 2: RECETTES */}
            {activeSection === "recipes" && (
              <View className="mb-8">
                <View className="mb-4 flex-row items-center justify-between">
                  <Text className="text-sm font-semibold text-slate-700">
                    Mes fiches recettes ({recipes.length})
                  </Text>
                  <Pressable
                    onPress={() => router.push("/new-recipe")}
                    className="flex-row items-center rounded-xl bg-emerald-600 px-3 py-1.5 active:bg-emerald-700"
                  >
                    <Ionicons name="add" size={16} color="#ffffff" />
                    <Text className="ml-1 text-xs font-semibold text-white">Nouvelle</Text>
                  </Pressable>
                </View>

                {recipes.length === 0 ? (
                  <View className="rounded-2xl border border-slate-100 bg-white p-6 items-center justify-center shadow-sm">
                    <Ionicons name="restaurant-outline" size={36} color="#94a3b8" />
                    <Text className="mt-2 text-sm font-semibold text-slate-700">
                      Aucune recette enregistrée
                    </Text>
                    <Text className="mt-1 text-center text-xs text-slate-400">
                      {"Demande à l'IA d'en inventer une selon ce qu'il te reste dans le frigo !"}
                    </Text>
                  </View>
                ) : (
                  <View className="gap-3">
                    {recipes.map((rec) => (
                      <RecipeCardSwipeable
                        key={rec.id}
                        recipe={rec}
                        onCookShort={handleCookShort}
                        onPlanLong={handlePlanLong}
                        onGroceriesSwipe={handleGroceriesSwipe}
                        onPressCard={(id) => router.push(`/recipe/${id}`)}
                        isShaking={shakingRecipeId === rec.id}
                      />
                    ))}
                  </View>
                )}
              </View>
            )}

            {/* VIEW 3: GARDE-MANGER */}
            {activeSection === "pantry" && (
              <View className="mb-8">
                <View className="mb-4 flex-row items-center justify-between">
                  <Text className="text-sm font-semibold text-slate-700">
                    Stocks & Épicerie ({pantryItems.length})
                  </Text>
                  <Pressable
                    onPress={() => router.push("/new-pantry")}
                    className="flex-row items-center rounded-xl bg-emerald-600 px-3 py-1.5 active:bg-emerald-700"
                  >
                    <Ionicons name="add" size={16} color="#ffffff" />
                    <Text className="ml-1 text-xs font-semibold text-white">Ajouter</Text>
                  </Pressable>
                </View>

                {pantryItems.length === 0 ? (
                  <View className="rounded-2xl border border-slate-100 bg-white p-6 items-center justify-center shadow-sm">
                    <Ionicons name="archive-outline" size={36} color="#94a3b8" />
                    <Text className="mt-2 text-sm font-semibold text-slate-700">
                      Garde-manger vide
                    </Text>
                    <Text className="mt-1 text-center text-xs text-slate-400">
                      Enregistre tes denrées pour être alerté avant rupture de stock.
                    </Text>
                  </View>
                ) : (
                  <View className="rounded-2xl border border-slate-100 bg-white p-2 shadow-sm">
                    {pantryItems.map((p, index) => {
                      const isLast = index === pantryItems.length - 1;
                      const isLow = p.quantity <= p.min_quantity;
                      return (
                        <View
                          key={p.id}
                          className={`flex-row items-center justify-between p-3 ${
                            !isLast ? "border-b border-slate-50" : ""
                          }`}
                        >
                          <View className="flex-1 mr-2">
                            <Text className="text-sm font-semibold text-slate-900">{p.name}</Text>
                            <Text className="text-xs text-slate-400">
                              Emplacement : {p.location || "Cuisine"}
                              {p.expires_at ? ` • Expire le ${p.expires_at}` : ""}
                            </Text>
                          </View>
                          <View className="items-end">
                            <Text className="text-sm font-bold text-slate-800">
                              {p.quantity} {p.unit}
                            </Text>
                            {isLow && (
                              <View className="mt-0.5 rounded-full bg-amber-100 px-2 py-0.2">
                                <Text className="text-[10px] font-bold text-amber-700">
                                  Stock faible
                                </Text>
                              </View>
                            )}
                          </View>
                        </View>
                      );
                    })}
                  </View>
                )}
              </View>
            )}
          </>
        )}
      </ScrollView>

      <RecipeGroceriesSheet
        visible={groceriesSheetRecipe !== null}
        recipe={groceriesSheetRecipe}
        pantryItems={pantryItems}
        onClose={() => setGroceriesSheetRecipe(null)}
        onConfirmAdd={handleConfirmAddToGroceries}
      />

      <RecipePlanModal
        visible={planModalRecipe !== null}
        recipe={planModalRecipe}
        onClose={() => setPlanModalRecipe(null)}
        onSchedule={handleConfirmSchedule}
      />

      <SupermarketStoreModal
        visible={showDriveModal}
        onClose={() => setShowDriveModal(false)}
        onSelect={handleStartDriveCart}
      />

      <CartReviewModal
        visible={showReviewModal && activeCartJob !== null}
        job={activeCartJob}
        onClose={() => setShowReviewModal(false)}
        onRefreshJob={loadData}
        onPickupConfirmed={loadData}
        onDeleteJob={loadData}
      />

      <GroceryItemEditModal
        visible={editingGroceryItem !== null}
        item={editingGroceryItem}
        onClose={() => setEditingGroceryItem(null)}
        onSave={handleSaveGroceryEdit}
      />
    </Screen>
  );
}
