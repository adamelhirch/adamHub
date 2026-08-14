import { useEffect, useState } from "react";
import { ActivityIndicator, Text, View } from "react-native";

import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { listPantryItems, PantryItemRead } from "@/lib/api";

const UNCATEGORIZED = "Sans catégorie";

export default function PantryScreen() {
  const [items, setItems] = useState<PantryItemRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
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
  }, []);

  if (loading) {
    return (
      <Screen>
        <ScreenHeader title="Garde-manger" subtitle="Vos stocks actuels" />
        <ActivityIndicator className="mt-8" />
      </Screen>
    );
  }

  const categories = [...new Set(items.map((item) => item.category ?? UNCATEGORIZED))];

  return (
    <Screen>
      <ScreenHeader title="Garde-manger" subtitle="Vos stocks actuels" />
      {error ? (
        <View className="mb-4 rounded-xl bg-red-50 px-4 py-3">
          <Text className="text-sm text-red-600">{error}</Text>
        </View>
      ) : null}
      {categories.length === 0 ? (
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
                    className={`flex-row items-center justify-between px-4 py-3 ${
                      index > 0 ? "border-t border-slate-100" : ""
                    }`}
                  >
                    <View className="flex-1">
                      <Text className="text-base text-slate-900">{item.name}</Text>
                      {item.expires_at ? (
                        <Text className="text-xs text-slate-400">
                          Expire :{" "}
                          {new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long" }).format(
                            new Date(`${item.expires_at}T00:00:00`),
                          )}
                        </Text>
                      ) : null}
                    </View>
                    <Text className="text-sm font-medium text-slate-500">
                      {item.quantity} {item.unit}
                    </Text>
                  </View>
                ))}
            </View>
          </View>
        ))
      )}
    </Screen>
  );
}
