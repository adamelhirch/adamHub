import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";

import { Field } from "@/components/field";
import { PrimaryButton } from "@/components/primary-button";
import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { createGroceryItem } from "@/lib/groceries";

export default function NewGroceryScreen() {
  const [name, setName] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [unit, setUnit] = useState("item");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleSubmit() {
    if (loading) return;
    setError(null);

    const trimmedName = name.trim();
    if (!trimmedName) {
      setError("Veuillez renseigner un nom.");
      return;
    }

    const parsedQuantity = parseFloat(quantity);
    const payload: { name: string; quantity: number; unit: string; category?: string } = {
      name: trimmedName,
      quantity: Number.isFinite(parsedQuantity) && parsedQuantity >= 0 ? parsedQuantity : 1,
      unit: unit.trim() || "item",
    };
    const trimmedCategory = category.trim();
    if (trimmedCategory.length > 0) {
      payload.category = trimmedCategory;
    }

    setLoading(true);
    createGroceryItem(payload)
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

      <ScreenHeader title="Nouvel article" subtitle="Ajoutez un article à votre liste de courses." />

      {error ? (
        <View className="mb-4 rounded-xl bg-red-50 px-4 py-3">
          <Text className="text-sm text-red-600">{error}</Text>
        </View>
      ) : null}

      <Field label="Nom" value={name} onChangeText={setName} placeholder="Ex. : Lait" />
      <View className="flex-row gap-3">
        <View className="flex-1">
          <Field
            label="Quantité"
            value={quantity}
            onChangeText={setQuantity}
            keyboardType="numeric"
            placeholder="1"
          />
        </View>
        <View className="flex-1">
          <Field
            label="Unité"
            value={unit}
            onChangeText={setUnit}
            placeholder="item"
          />
        </View>
      </View>
      <Field
        label="Catégorie (optionnel)"
        value={category}
        onChangeText={setCategory}
        placeholder="Ex. : Produits laitiers"
      />

      <PrimaryButton label="Ajouter à la liste" onPress={handleSubmit} loading={loading} />
    </Screen>
  );
}
