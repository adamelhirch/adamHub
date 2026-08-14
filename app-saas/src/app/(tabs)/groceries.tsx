import { Ionicons } from "@expo/vector-icons";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, Alert, Pressable, Text, View } from "react-native";

import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { GroceryItemRead, listGroceryItems, updateGroceryItem } from "@/lib/api";
import { deleteGroceryItem } from "@/lib/groceries";

export default function GroceriesScreen() {
  const [items, setItems] = useState<GroceryItemRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const remaining = items.filter((item) => !item.checked).length;

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;

      async function load() {
        setLoading(true);
        setError(null);
        try {
          const data = await listGroceryItems();
          if (!cancelled) setItems(data);
        } catch (err) {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "Une erreur est survenue");
          }
        } finally {
          if (!cancelled) setLoading(false);
        }
      }

      load();
      return () => {
        cancelled = true;
      };
    }, []),
  );

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

  function handleDelete(id: number) {
    Alert.alert("Supprimer l'article ?", "Cette action est irréversible.", [
      { text: "Annuler", style: "cancel" },
      {
        text: "Supprimer",
        style: "destructive",
        onPress: () => {
          deleteGroceryItem(id)
            .then(() => {
              setItems((prev) => prev.filter((item) => item.id !== id));
            })
            .catch((err) => {
              setError(err instanceof Error ? err.message : "Une erreur est survenue");
            });
        },
      },
    ]);
  }

  return (
    <Screen>
      <View className="mb-6 flex-row items-center justify-between">
        <ScreenHeader
          title="Courses"
          subtitle={`${remaining} article${remaining > 1 ? "s" : ""} à acheter`}
        />
        <View className="flex-row items-center gap-2">
          <Pressable
            onPress={() =>
              router.push({ pathname: "/supermarket-search", params: { returnTo: "grocery" } })
            }
            hitSlop={8}
            className="h-11 w-11 items-center justify-center rounded-full bg-slate-200 active:bg-slate-300"
          >
            <Ionicons name="storefront-outline" size={22} color="#0f172a" />
          </Pressable>
          <Pressable
            onPress={() => router.push("/new-grocery")}
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
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#059669" />
        </View>
      ) : items.length === 0 ? (
        <View className="flex-1 items-center justify-center">
          <Text className="text-base text-slate-500">Aucun article pour l&apos;instant.</Text>
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
            <Pressable onPress={() => handleDelete(item.id)} hitSlop={8} className="ml-3">
              <Ionicons name="trash-outline" size={20} color="#94a3b8" />
            </Pressable>
          </Pressable>
        ))
      )}
    </Screen>
  );
}
