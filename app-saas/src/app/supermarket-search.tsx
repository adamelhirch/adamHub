import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Image, Pressable, Text, View } from "react-native";

import { Field } from "@/components/field";
import { PrimaryButton } from "@/components/primary-button";
import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { ApiError } from "@/lib/api";
import { createGroceryItem } from "@/lib/groceries";
import { createPantryItem } from "@/lib/pantry";
import { searchSupermarket, type SupermarketSearchResult } from "@/lib/supermarket";

const DEFAULT_STORE = "intermarche";
const MAX_RESULTS = 20;

type ReturnTarget = "grocery" | "pantry";

const SCRAPER_UNAVAILABLE_MESSAGE =
  "Le catalogue Intermarché est momentanément indisponible. Réessayez dans quelques instants.";

function isReturnTarget(value: string | undefined): value is ReturnTarget {
  return value === "grocery" || value === "pantry";
}

function errorMessage(err: unknown): string {
  if (err instanceof ApiError && err.status === 503) {
    return SCRAPER_UNAVAILABLE_MESSAGE;
  }
  return err instanceof Error ? err.message : "Une erreur est survenue";
}

function formatPrice(item: SupermarketSearchResult): string | null {
  if (item.price_text) return item.price_text;
  if (item.price_amount != null) return `${item.price_amount.toFixed(2)} €`;
  return null;
}

export default function SupermarketSearchScreen() {
  const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();
  const target: ReturnTarget = isReturnTarget(returnTo) ? returnTo : "grocery";

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SupermarketSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [addingIds, setAddingIds] = useState<Set<number>>(new Set());
  const [addedIds, setAddedIds] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const addLabel = target === "grocery" ? "Ajouter aux courses" : "Ajouter au garde-manger";

  function handleSearch() {
    const trimmed = query.trim();
    if (!trimmed) {
      setError("Veuillez renseigner le nom d'un produit.");
      return;
    }
    if (searching) return;

    setError(null);
    setSearching(true);
    setResults([]);
    searchSupermarket({
      store: DEFAULT_STORE,
      queries: [trimmed],
      max_results: MAX_RESULTS,
    })
      .then((data) => setResults(data))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setSearching(false));
  }

  async function handleAdd(item: SupermarketSearchResult) {
    if (addingIds.has(item.cache_id) || addedIds.has(item.cache_id)) return;
    setError(null);
    setAddingIds((prev) => new Set(prev).add(item.cache_id));
    try {
      if (target === "grocery") {
        await createGroceryItem({
          name: item.name,
          quantity: 1,
          unit: "item",
          cache_id: item.cache_id,
        });
      } else {
        await createPantryItem({
          name: item.name,
          quantity: 1,
          unit: "item",
          cache_id: item.cache_id,
        });
      }
      setAddedIds((prev) => new Set(prev).add(item.cache_id));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setAddingIds((prev) => {
        const next = new Set(prev);
        next.delete(item.cache_id);
        return next;
      });
    }
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

      <ScreenHeader
        title="Recherche supermarché"
        subtitle={`Trouvez un produit chez Intermarché pour l'ajouter à ${
          target === "grocery" ? "vos courses" : "votre garde-manger"
        }.`}
      />

      {error ? (
        <View className="mb-4 rounded-xl bg-red-50 px-4 py-3">
          <Text className="text-sm text-red-600">{error}</Text>
        </View>
      ) : null}

      <Field
        label="Produit"
        value={query}
        onChangeText={setQuery}
        placeholder="Ex. : Lait, pâtes…"
        returnKeyType="search"
        onSubmitEditing={handleSearch}
      />
      <PrimaryButton label="Rechercher" onPress={handleSearch} loading={searching} />

      {results.length > 0 ? (
        <View className="mt-6">
          <Text className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            {results.length} résultat{results.length > 1 ? "s" : ""}
          </Text>
          {results.map((item) => {
            const isAdding = addingIds.has(item.cache_id);
            const isAdded = addedIds.has(item.cache_id);
            const price = formatPrice(item);
            return (
              <View
                key={item.cache_id}
                className="mb-3 flex-row items-center rounded-2xl border border-slate-100 bg-white p-4"
              >
                {item.image_url ? (
                  <Image
                    source={{ uri: item.image_url }}
                    className="mr-3 h-14 w-14 rounded-xl bg-slate-100"
                    resizeMode="cover"
                  />
                ) : (
                  <View className="mr-3 h-14 w-14 items-center justify-center rounded-xl bg-slate-100">
                    <Ionicons name="storefront-outline" size={24} color="#94a3b8" />
                  </View>
                )}
                <View className="flex-1 pr-2">
                  <Text className="text-base text-slate-900" numberOfLines={2}>
                    {item.name}
                  </Text>
                  {item.brand ? (
                    <Text className="text-sm text-slate-500">{item.brand}</Text>
                  ) : null}
                  <Text className="text-sm font-semibold text-emerald-600">
                    {price ?? "Prix indisponible"}
                  </Text>
                </View>
                <Pressable
                  onPress={() => handleAdd(item)}
                  disabled={isAdding || isAdded}
                  className={`w-28 items-center justify-center rounded-full px-2 py-2 ${
                    isAdded
                      ? "bg-emerald-100"
                      : isAdding
                        ? "bg-emerald-100"
                        : "bg-emerald-600 active:bg-emerald-700"
                  }`}
                >
                  {isAdding ? (
                    <ActivityIndicator color="#059669" />
                  ) : (
                    <Text
                      className={`text-center text-sm font-medium ${
                        isAdded ? "text-emerald-600" : "text-white"
                      }`}
                    >
                      {isAdded ? "Ajouté ✓" : addLabel}
                    </Text>
                  )}
                </Pressable>
              </View>
            );
          })}
        </View>
      ) : null}

      {!searching && results.length === 0 && !error && query.trim() ? (
        <View className="mt-8 items-center">
          <Text className="text-base text-slate-500">
            Aucun résultat pour « {query.trim()} ».
          </Text>
        </View>
      ) : null}
    </Screen>
  );
}
