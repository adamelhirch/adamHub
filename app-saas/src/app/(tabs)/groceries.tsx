import { Ionicons } from "@expo/vector-icons";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { GroceryItemRead, listGroceryItems, updateGroceryItem } from "@/lib/api";

export default function GroceriesScreen() {
  const [items, setItems] = useState<GroceryItemRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const remaining = items.filter((item) => !item.checked).length;

  useEffect(() => {
    let active = true;
    listGroceryItems()
      .then((data) => {
        if (active) setItems(data);
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
  }, []);

  async function toggle(id: number) {
    const current = items.find((item) => item.id === id);
    if (!current) return;
    const next = !current.checked;
    setItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, checked: next } : item)),
    );
    setError(null);
    try {
      await updateGroceryItem(id, { checked: next });
    } catch (err) {
      setItems((prev) =>
        prev.map((item) => (item.id === id ? { ...item, checked: current.checked } : item)),
      );
      setError(err instanceof Error ? err.message : "Une erreur est survenue");
    }
  }

  return (
    <Screen>
      <ScreenHeader
        title="Courses"
        subtitle={`${remaining} article${remaining > 1 ? "s" : ""} à acheter`}
      />
      {error ? (
        <View className="mb-4 rounded-xl bg-red-50 px-4 py-3">
          <Text className="text-sm text-red-600">{error}</Text>
        </View>
      ) : null}
      {loading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#059669" />
        </View>
      ) : items.length === 0 ? (
        <View className="flex-1 items-center justify-center">
          <Text className="text-base text-slate-500">Aucun article pour l'instant.</Text>
        </View>
      ) : (
        items.map((item) => (
          <Pressable
            key={item.id}
            onPress={() => toggle(item.id)}
            className="mb-3 flex-row items-center rounded-2xl border border-slate-100 bg-white p-4"
          >
            <View
              className={`mr-3 h-6 w-6 items-center justify-center rounded-full border-2 ${
                item.checked ? "border-emerald-500 bg-emerald-500" : "border-slate-300 bg-white"
              }`}
            >
              {item.checked ? <Ionicons name="checkmark" size={14} color="#ffffff" /> : null}
            </View>
            <View className="flex-1">
              <Text
                className={`text-base ${item.checked ? "text-slate-400 line-through" : "text-slate-900"}`}
              >
                {item.name}
              </Text>
              <Text className="text-sm text-slate-400">{item.category ?? "Sans catégorie"}</Text>
            </View>
            <Text className="text-sm font-medium text-slate-500">
              {item.quantity} {item.unit}
            </Text>
          </Pressable>
        ))
      )}
    </Screen>
  );
}
