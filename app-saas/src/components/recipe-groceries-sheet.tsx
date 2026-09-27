import { Ionicons } from "@expo/vector-icons";
import React, { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  Text,
  View,
} from "react-native";

import { PantryItemRead } from "@/lib/api";
import { RecipeRead } from "@/lib/recipes";

export interface RecipeGroceriesSheetProps {
  visible: boolean;
  recipe: RecipeRead | null;
  pantryItems: PantryItemRead[];
  onClose: () => void;
  onConfirmAdd: (ingredientIds: number[], servings: number) => Promise<void>;
}

function normalize(str: string): string {
  return str.trim().toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

export function RecipeGroceriesSheet(props: RecipeGroceriesSheetProps) {
  if (!props.visible || !props.recipe) return null;

  return (
    <RecipeGroceriesSheetContent
      {...props}
      recipe={props.recipe}
    />
  );
}

function RecipeGroceriesSheetContent({
  visible,
  recipe,
  pantryItems,
  onClose,
  onConfirmAdd,
}: RecipeGroceriesSheetProps & { recipe: RecipeRead }) {
  const [servings, setServings] = useState(recipe.servings || 2);
  const [submitting, setSubmitting] = useState(false);

  // Compute pantry availability map
  const pantryMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const item of pantryItems) {
      const key = `${normalize(item.name)}_${(item.unit || "item").toLowerCase()}`;
      map.set(key, (map.get(key) || 0) + (item.quantity || 0));
    }
    return map;
  }, [pantryItems]);

  const [selectedIds, setSelectedIds] = useState<Set<number>>(() => {
    const preSelected = new Set<number>();
    for (const ing of recipe.ingredients || []) {
      const key = `${normalize(ing.name)}_${(ing.unit || "item").toLowerCase()}`;
      const available = pantryMap.get(key) || 0;
      if (available < (ing.quantity || 0)) {
        preSelected.add(ing.id);
      }
    }
    if (preSelected.size === 0 && recipe.ingredients?.length) {
      recipe.ingredients.forEach((ing) => preSelected.add(ing.id));
    }
    return preSelected;
  });

  const baseServings = recipe.servings > 0 ? recipe.servings : 1;
  const ratio = servings / baseServings;

  function toggleIngredient(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function toggleAll() {
    if (selectedIds.size === recipe?.ingredients?.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(recipe?.ingredients?.map((i) => i.id) || []));
    }
  }

  async function handleSubmit() {
    if (selectedIds.size === 0) return;
    setSubmitting(true);
    try {
      await onConfirmAdd(Array.from(selectedIds), servings);
      onClose();
    } catch {
      // Handled by parent or toast
    } finally {
      setSubmitting(false);
    }
  }

  const allSelected = selectedIds.size === (recipe.ingredients?.length || 0);

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View className="flex-1 justify-end bg-black/50">
        <Pressable className="flex-1" onPress={onClose} />
        <View className="max-h-[85%] rounded-t-3xl bg-white px-5 pb-8 pt-4 shadow-xl">
          {/* Handle bar */}
          <View className="mb-3 h-1 w-12 self-center rounded-full bg-slate-300" />

          {/* Header */}
          <View className="mb-4 flex-row items-center justify-between">
            <View className="flex-1 pr-2">
              <Text className="text-xl font-bold text-slate-900" numberOfLines={1}>
                Ajouter aux courses
              </Text>
              <Text className="text-xs text-slate-500" numberOfLines={1}>
                {recipe.name}
              </Text>
            </View>
            <Pressable
              onPress={onClose}
              hitSlop={8}
              className="h-8 w-8 items-center justify-center rounded-full bg-slate-100"
            >
              <Ionicons name="close" size={18} color="#64748b" />
            </Pressable>
          </View>

          {/* Servings Stepper */}
          <View className="mb-4 flex-row items-center justify-between rounded-2xl bg-slate-50 p-3">
            <View>
              <Text className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Portions à prévoir
              </Text>
              <Text className="text-base font-bold text-slate-900">
                {servings} {servings > 1 ? "personnes" : "personne"}
              </Text>
            </View>
            <View className="flex-row items-center gap-2">
              <Pressable
                onPress={() => setServings((s) => Math.max(1, s - 1))}
                className="h-8 w-8 items-center justify-center rounded-full bg-white border border-slate-200 shadow-sm active:bg-slate-100"
              >
                <Ionicons name="remove" size={16} color="#0f172a" />
              </Pressable>
              <Text className="w-6 text-center font-bold text-slate-900">{servings}</Text>
              <Pressable
                onPress={() => setServings((s) => Math.min(20, s + 1))}
                className="h-8 w-8 items-center justify-center rounded-full bg-white border border-slate-200 shadow-sm active:bg-slate-100"
              >
                <Ionicons name="add" size={16} color="#0f172a" />
              </Pressable>
            </View>
          </View>

          {/* Select all toggle */}
          <View className="mb-2 flex-row items-center justify-between">
            <Text className="text-xs font-semibold text-slate-500">
              Ingrédients sélectionnés ({selectedIds.size}/{recipe.ingredients?.length || 0})
            </Text>
            <Pressable onPress={toggleAll} hitSlop={8}>
              <Text className="text-xs font-bold text-emerald-600">
                {allSelected ? "Tout désélectionner" : "Tout sélectionner"}
              </Text>
            </Pressable>
          </View>

          {/* Ingredients list */}
          <ScrollView className="mb-4 max-h-72" showsVerticalScrollIndicator={false}>
            {(recipe.ingredients || []).map((ing) => {
              const key = `${normalize(ing.name)}_${(ing.unit || "item").toLowerCase()}`;
              const available = pantryMap.get(key) || 0;
              const scaledQty = Math.round((ing.quantity || 0) * ratio * 10) / 10;
              const isMissing = available < scaledQty;
              const isChecked = selectedIds.has(ing.id);

              return (
                <Pressable
                  key={ing.id}
                  onPress={() => toggleIngredient(ing.id)}
                  className={`mb-2 flex-row items-center justify-between rounded-xl border p-3 ${
                    isChecked ? "border-emerald-500 bg-emerald-50/40" : "border-slate-100 bg-white"
                  }`}
                >
                  <View className="flex-1 flex-row items-center pr-2">
                    <View
                      className={`mr-3 h-5 w-5 items-center justify-center rounded-md border ${
                        isChecked ? "border-emerald-600 bg-emerald-600" : "border-slate-300 bg-white"
                      }`}
                    >
                      {isChecked ? <Ionicons name="checkmark" size={14} color="#ffffff" /> : null}
                    </View>
                    <View className="flex-1">
                      <Text
                        className={`text-sm font-semibold ${
                          isChecked ? "text-slate-900" : "text-slate-600"
                        }`}
                      >
                        {ing.name}
                      </Text>
                      <View className="flex-row items-center gap-1.5 mt-0.5">
                        {isMissing ? (
                          <View className="rounded bg-rose-50 px-1.5 py-0.2">
                            <Text className="text-[10px] font-bold text-rose-600">
                              {available === 0 ? "Manquant" : `Déficit (stock: ${available} ${ing.unit})`}
                            </Text>
                          </View>
                        ) : (
                          <View className="rounded bg-emerald-50 px-1.5 py-0.2">
                            <Text className="text-[10px] font-bold text-emerald-700">
                              En stock ({available} {ing.unit})
                            </Text>
                          </View>
                        )}
                      </View>
                    </View>
                  </View>

                  <Text className="text-sm font-bold text-slate-700">
                    {scaledQty} {ing.unit}
                  </Text>
                </Pressable>
              );
            })}
          </ScrollView>

          {/* Submit Button */}
          <Pressable
            onPress={handleSubmit}
            disabled={submitting || selectedIds.size === 0}
            className={`flex-row items-center justify-center rounded-2xl py-3.5 shadow-sm ${
              selectedIds.size === 0 ? "bg-slate-300" : "bg-emerald-600 active:bg-emerald-700"
            }`}
          >
            {submitting ? (
              <ActivityIndicator color="#ffffff" />
            ) : (
              <>
                <Ionicons name="cart" size={18} color="#ffffff" />
                <Text className="ml-2 text-base font-bold text-white">
                  Ajouter {selectedIds.size} ingrédient{selectedIds.size > 1 ? "s" : ""} aux courses
                </Text>
              </>
            )}
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}
