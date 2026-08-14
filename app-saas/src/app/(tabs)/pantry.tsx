import { Ionicons } from "@expo/vector-icons";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, Alert, Pressable, Text, View } from "react-native";

import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { listPantryItems, type PantryItemRead } from "@/lib/api";
import { consumePantryItem, deletePantryItem, updatePantryItem } from "@/lib/pantry";

const UNCATEGORIZED = "Sans catégorie";

function formatQuantity(quantity: number): string {
  return parseFloat(quantity.toFixed(2)).toString();
}

export default function PantryScreen() {
  const [items, setItems] = useState<PantryItemRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      let active = true;
      setLoading(true);
      setError(null);
      listPantryItems()
        .then((data) => {
          if (active) setItems(data);
        })
        .catch((err) => {
          if (active) setError(err instanceof Error ? err.message : "Une erreur est survenue");
        })
        .finally(() => {
          if (active) setLoading(false);
        });
      return () => {
        active = false;
      };
    }, []),
  );

  async function adjustQuantity(item: PantryItemRead, delta: number) {
    const previous = item.quantity;
    const next = Math.max(0, previous + delta);
    if (next === previous) return;

    setError(null);
    setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, quantity: next } : i)));
    try {
      const updated =
        delta > 0
          ? await updatePantryItem(item.id, { quantity: next })
          : await consumePantryItem(item.id, previous - next);
      setItems((prev) => prev.map((i) => (i.id === item.id ? updated : i)));
    } catch (err) {
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, quantity: previous } : i)));
      setError(err instanceof Error ? err.message : "Une erreur est survenue");
    }
  }

  function confirmDelete(item: PantryItemRead) {
    Alert.alert("Supprimer l'article", `Voulez-vous supprimer « ${item.name} » ?`, [
      { text: "Annuler", style: "cancel" },
      { text: "Supprimer", style: "destructive", onPress: () => handleDelete(item) },
    ]);
  }

  async function handleDelete(item: PantryItemRead) {
    setError(null);
    setItems((prev) => prev.filter((i) => i.id !== item.id));
    try {
      await deletePantryItem(item.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue");
      try {
        const data = await listPantryItems();
        setItems(data);
      } catch {
        // La liste locale reste déjà cohérente en cas d'échec du rechargement.
      }
    }
  }

  const categories = [...new Set(items.map((item) => item.category ?? UNCATEGORIZED))];

  return (
    <Screen>
      <View className="mb-6 flex-row items-center justify-between">
        <ScreenHeader title="Garde-manger" subtitle="Vos stocks actuels" />
        <View className="flex-row items-center gap-2">
          <Pressable
            onPress={() =>
              router.push({ pathname: "/supermarket-search", params: { returnTo: "pantry" } })
            }
            hitSlop={8}
            className="h-11 w-11 items-center justify-center rounded-full bg-slate-200 active:bg-slate-300"
          >
            <Ionicons name="storefront-outline" size={22} color="#0f172a" />
          </Pressable>
          <Pressable
            onPress={() => router.push("/new-pantry")}
            className="h-11 w-11 items-center justify-center rounded-full bg-emerald-600 active:bg-emerald-700"
          >
            <Ionicons name="add" size={24} color="#ffffff" />
          </Pressable>
        </View>
      </View>

      {error ? (
        <View className="mb-4 rounded-xl bg-red-50 px-4 py-3">
          <Text className="text-sm text-red-600">{error}</Text>
        </View>
      ) : null}

      {loading ? (
        <ActivityIndicator className="mt-8" />
      ) : categories.length === 0 ? (
        <Text className="text-base text-slate-500">Votre garde-manger est vide.</Text>
      ) : (
        categories.map((category) => (
          <View key={category} className="mb-5">
            <Text className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
              {category}
            </Text>
            <View className="overflow-hidden rounded-2xl border border-slate-100 bg-white">
              {items
                .filter((item) => (item.category ?? UNCATEGORIZED) === category)
                .map((item, index) => (
                  <View
                    key={item.id}
                    className={`px-4 py-3 ${index > 0 ? "border-t border-slate-100" : ""}`}
                  >
                    <View className="flex-row items-center justify-between">
                      <View className="flex-1 pr-2">
                        <Text className="text-base text-slate-900">{item.name}</Text>
                        {item.expires_at ? (
                          <Text className="text-xs text-slate-400">
                            Expire :{" "}
                            {new Intl.DateTimeFormat("fr-FR", {
                              day: "numeric",
                              month: "long",
                            }).format(new Date(`${item.expires_at}T00:00:00`))}
                          </Text>
                        ) : null}
                      </View>
                      <View className="flex-row items-center">
                        <Pressable
                          onPress={() => adjustQuantity(item, -1)}
                          hitSlop={6}
                          className="h-8 w-8 items-center justify-center rounded-full bg-slate-100 active:bg-slate-200"
                        >
                          <Ionicons name="remove" size={16} color="#334155" />
                        </Pressable>
                        <Text className="min-w-[70px] text-center text-sm font-medium text-slate-500">
                          {formatQuantity(item.quantity)} {item.unit}
                        </Text>
                        <Pressable
                          onPress={() => adjustQuantity(item, 1)}
                          hitSlop={6}
                          className="h-8 w-8 items-center justify-center rounded-full bg-emerald-100 active:bg-emerald-200"
                        >
                          <Ionicons name="add" size={16} color="#059669" />
                        </Pressable>
                        <Pressable
                          onPress={() => confirmDelete(item)}
                          hitSlop={6}
                          className="ml-2 h-8 w-8 items-center justify-center rounded-full"
                        >
                          <Ionicons name="trash-outline" size={18} color="#ef4444" />
                        </Pressable>
                      </View>
                    </View>
                  </View>
                ))}
            </View>
          </View>
        ))
      )}
    </Screen>
  );
}
