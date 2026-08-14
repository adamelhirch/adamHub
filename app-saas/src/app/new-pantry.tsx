import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";

import { Field } from "@/components/field";
import { PrimaryButton } from "@/components/primary-button";
import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { createPantryItem, type PantryItemCreateInput } from "@/lib/pantry";

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export default function NewPantryScreen() {
  const [name, setName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unit, setUnit] = useState("");
  const [category, setCategory] = useState("");
  const [minQuantity, setMinQuantity] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
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

    const expiresTrimmed = expiresAt.trim();
    if (expiresTrimmed && !DATE_RE.test(expiresTrimmed)) {
      setError("Date d'expiration invalide (format AAAA-MM-JJ).");
      return;
    }

    const payload: PantryItemCreateInput = {
      name: trimmedName,
      quantity: 0,
      unit: unit.trim() || "item",
    };

    const parsedQuantity = parseFloat(quantity);
    if (Number.isFinite(parsedQuantity) && parsedQuantity >= 0) {
      payload.quantity = parsedQuantity;
    }

    const trimmedCategory = category.trim();
    if (trimmedCategory) {
      payload.category = trimmedCategory;
    }

    const parsedMinQuantity = parseFloat(minQuantity);
    if (minQuantity.trim() && Number.isFinite(parsedMinQuantity) && parsedMinQuantity >= 0) {
      payload.min_quantity = parsedMinQuantity;
    }

    if (expiresTrimmed) {
      payload.expires_at = expiresTrimmed;
    }

    setLoading(true);
    createPantryItem(payload)
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

      <ScreenHeader title="Nouvel article" subtitle="Ajoutez un article à votre garde-manger." />

      {error ? (
        <View className="mb-4 rounded-xl bg-red-50 px-4 py-3">
          <Text className="text-sm text-red-600">{error}</Text>
        </View>
      ) : null}

      <Field
        label="Nom"
        value={name}
        onChangeText={setName}
        placeholder="Ex. : Riz basmati"
      />
      <View className="flex-row gap-3">
        <View className="flex-1">
          <Field
            label="Quantité"
            value={quantity}
            onChangeText={setQuantity}
            keyboardType="decimal-pad"
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
        placeholder="Ex. : Épicerie"
      />

      <View className="flex-row gap-3">
        <View className="flex-1">
          <Field
            label="Quantité minimale (optionnel)"
            value={minQuantity}
            onChangeText={setMinQuantity}
            keyboardType="decimal-pad"
            placeholder="0"
          />
        </View>
        <View className="flex-1">
          <Field
            label="Date d'expiration (optionnel)"
            value={expiresAt}
            onChangeText={setExpiresAt}
            placeholder="AAAA-MM-JJ"
          />
        </View>
      </View>

      <PrimaryButton label="Ajouter l'article" onPress={handleSubmit} loading={loading} />
    </Screen>
  );
}
