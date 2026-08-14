import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";

import { Field } from "@/components/field";
import { PrimaryButton } from "@/components/primary-button";
import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { createRecipe, RecipeCreateInput } from "@/lib/api";

interface IngredientRow {
  name: string;
  quantity: string;
  unit: string;
}

const DEFAULT_INGREDIENT: IngredientRow = { name: "", quantity: "1", unit: "unité" };

export default function NewRecipeScreen() {
  const [name, setName] = useState("");
  const [instructions, setInstructions] = useState("");
  const [servings, setServings] = useState("2");
  const [prepMinutes, setPrepMinutes] = useState("");
  const [cookMinutes, setCookMinutes] = useState("");
  const [ingredients, setIngredients] = useState<IngredientRow[]>([{ ...DEFAULT_INGREDIENT }]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateIngredient(index: number, key: keyof IngredientRow, value: string) {
    setIngredients((prev) =>
      prev.map((row, i) => (i === index ? { ...row, [key]: value } : row)),
    );
  }

  function addIngredient() {
    setIngredients((prev) => [...prev, { ...DEFAULT_INGREDIENT }]);
  }

  function removeIngredient(index: number) {
    setIngredients((prev) => prev.filter((_, i) => i !== index));
  }

  function handleSubmit() {
    if (loading) return;
    setError(null);

    const trimmedName = name.trim();
    const trimmedInstructions = instructions.trim();

    if (!trimmedName || !trimmedInstructions) {
      setError("Veuillez renseigner un nom et des instructions.");
      return;
    }

    const cleanedIngredients = ingredients
      .map((row) => {
        const quantity = parseFloat(row.quantity);
        return {
          name: row.name.trim(),
          quantity: Number.isFinite(quantity) && quantity > 0 ? quantity : 1,
          unit: row.unit.trim() || "unité",
        };
      })
      .filter((row) => row.name.length > 0);

    if (cleanedIngredients.length === 0) {
      setError("Ajoutez au moins un ingrédient.");
      return;
    }

    const parsedServings = parseInt(servings, 10);
    const payload: RecipeCreateInput = {
      name: trimmedName,
      instructions: trimmedInstructions,
      servings: Number.isFinite(parsedServings) && parsedServings > 0 ? parsedServings : 1,
      ingredients: cleanedIngredients,
    };

    if (prepMinutes.trim().length > 0) {
      payload.prep_minutes = Math.max(parseInt(prepMinutes, 10) || 0, 0);
    }
    if (cookMinutes.trim().length > 0) {
      payload.cook_minutes = Math.max(parseInt(cookMinutes, 10) || 0, 0);
    }

    setLoading(true);
    createRecipe(payload)
      .then(() => router.back())
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Une erreur est survenue");
        setLoading(false);
      });
  }

  return (
    <Screen>
      <Pressable
        onPress={() => router.back()}
        hitSlop={8}
        className="mb-2 flex-row items-center self-start rounded-full p-1"
      >
        <Ionicons name="arrow-back" size={24} color="#0f172a" />
      </Pressable>

      <ScreenHeader title="Nouvelle recette" subtitle="Ajoutez une recette à votre carnet." />

      {error ? (
        <View className="mb-4 rounded-xl bg-red-50 px-4 py-3">
          <Text className="text-sm text-red-600">{error}</Text>
        </View>
      ) : null}

      <Field
        label="Nom"
        value={name}
        onChangeText={setName}
        placeholder="Ex. : Risotto aux champignons"
      />
      <Field
        label="Instructions"
        value={instructions}
        onChangeText={setInstructions}
        placeholder="Étapes de préparation…"
        multiline
        numberOfLines={4}
        textAlignVertical="top"
      />

      <View className="flex-row gap-3">
        <View className="flex-1">
          <Field
            label="Portions"
            value={servings}
            onChangeText={setServings}
            keyboardType="numeric"
          />
        </View>
        <View className="flex-1">
          <Field
            label="Préparation (min)"
            value={prepMinutes}
            onChangeText={setPrepMinutes}
            keyboardType="numeric"
          />
        </View>
        <View className="flex-1">
          <Field
            label="Cuisson (min)"
            value={cookMinutes}
            onChangeText={setCookMinutes}
            keyboardType="numeric"
          />
        </View>
      </View>

      <Text className="mb-2 mt-2 text-sm font-medium text-slate-700">Ingrédients</Text>
      {ingredients.map((ingredient, index) => (
        <View key={index} className="mb-2 rounded-xl border border-slate-100 bg-white p-3">
          <View className="mb-1 flex-row items-center justify-between">
            <Text className="text-sm font-medium text-slate-700">Ingrédient {index + 1}</Text>
            {ingredients.length > 1 ? (
              <Pressable onPress={() => removeIngredient(index)} hitSlop={8}>
                <Ionicons name="close-circle-outline" size={22} color="#94a3b8" />
              </Pressable>
            ) : null}
          </View>
          <Field
            label="Nom"
            value={ingredient.name}
            onChangeText={(text) => updateIngredient(index, "name", text)}
            placeholder="Tomates, farine…"
          />
          <View className="flex-row gap-3">
            <View className="flex-1">
              <Field
                label="Quantité"
                value={ingredient.quantity}
                onChangeText={(text) => updateIngredient(index, "quantity", text)}
                keyboardType="numeric"
                placeholder="1"
              />
            </View>
            <View className="flex-1">
              <Field
                label="Unité"
                value={ingredient.unit}
                onChangeText={(text) => updateIngredient(index, "unit", text)}
                placeholder="unité"
              />
            </View>
          </View>
        </View>
      ))}

      <Pressable
        onPress={addIngredient}
        className="mb-6 flex-row items-center justify-center rounded-xl border border-dashed border-emerald-500 bg-emerald-50 px-4 py-3"
      >
        <Ionicons name="add" size={18} color="#059669" />
        <Text className="ml-1 text-sm font-semibold text-emerald-600">Ajouter un ingrédient</Text>
      </Pressable>

      <PrimaryButton label="Créer la recette" onPress={handleSubmit} loading={loading} />
    </Screen>
  );
}
