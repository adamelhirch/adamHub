import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Image, Pressable, Text, View } from "react-native";

import { Field } from "@/components/field";
import { PrimaryButton } from "@/components/primary-button";
import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { SupermarketStoreModal } from "@/components/supermarket-store-modal";
import { ApiError } from "@/lib/api";
import { createGroceryItem } from "@/lib/groceries";
import { createPantryItem } from "@/lib/pantry";
import { searchSupermarket, type SupermarketSearchResult } from "@/lib/supermarket";
import {
  getUserStorePreferences,
  type SupermarketStore,
  type UserStorePreference,
} from "@/lib/supermarket-api";

const AVAILABLE_STORES: { id: SupermarketStore; label: string }[] = [
  { id: "intermarche", label: "Intermarché" },
  { id: "leclerc", label: "E.Leclerc" },
  { id: "carrefour", label: "Carrefour" },
  { id: "auchan", label: "Auchan" },
];

const MAX_RESULTS = 20;

type ReturnTarget = "grocery" | "pantry";

function isReturnTarget(value: string | undefined): value is ReturnTarget {
  return value === "grocery" || value === "pantry";
}

function parseErrorMessage(
  err: unknown,
  storeLabel: string,
): { message: string; isAuthRequired: boolean } {
  const raw =
    err instanceof ApiError
      ? err.message
      : err instanceof Error
        ? err.message
        : "Une erreur est survenue";
  if (
    raw.includes("cookies") ||
    raw.includes("cookies_") ||
    raw.includes("No Leclerc Drive cookies") ||
    raw.includes("No Carrefour cookies") ||
    raw.includes("403") ||
    raw.includes("Challenge")
  ) {
    return {
      message: `La recherche en direct chez ${storeLabel} nécessite une session connectée (cookies). Vous pouvez basculer sur Intermarché pour une recherche immédiate.`,
      isAuthRequired: true,
    };
  }
  return { message: raw, isAuthRequired: false };
}

function formatPrice(item: SupermarketSearchResult): string | null {
  if (item.price_text) return item.price_text;
  if (item.price_amount != null) return `${item.price_amount.toFixed(2)} €`;
  return null;
}

export default function SupermarketSearchScreen() {
  const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();
  const target: ReturnTarget = isReturnTarget(returnTo) ? returnTo : "grocery";

  const [selectedStore, setSelectedStore] = useState<SupermarketStore>("intermarche");
  const [preferences, setPreferences] = useState<UserStorePreference[]>([]);
  const [showStoreModal, setShowStoreModal] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SupermarketSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [addingIds, setAddingIds] = useState<Set<number>>(new Set());
  const [addedIds, setAddedIds] = useState<Set<number>>(new Set());
  const [errorInfo, setErrorInfo] = useState<{ message: string; isAuthRequired: boolean } | null>(
    null,
  );

  const addLabel = target === "grocery" ? "Ajouter aux courses" : "Ajouter au garde-manger";

  useEffect(() => {
    getUserStorePreferences()
      .then((prefs) => {
        setPreferences(prefs);
        if (prefs.length > 0) {
          // If the user has a preference, select it by default
          setSelectedStore(prefs[0].store);
        }
      })
      .catch(() => {});
  }, []);

  const activeStoreDef = AVAILABLE_STORES.find((s) => s.id === selectedStore);
  const activeStoreLabel = activeStoreDef?.label ?? selectedStore;
  const currentPref = preferences.find((p) => p.store === selectedStore);

  function executeSearch(storeToUse: SupermarketStore, q: string) {
    const trimmed = q.trim();
    if (!trimmed) {
      setErrorInfo({ message: "Veuillez renseigner le nom d'un produit.", isAuthRequired: false });
      return;
    }
    if (searching) return;

    setErrorInfo(null);
    setSearching(true);
    setResults([]);

    const storeDef = AVAILABLE_STORES.find((s) => s.id === storeToUse);
    const storeLabel = storeDef?.label ?? storeToUse;

    searchSupermarket({
      store: storeToUse,
      queries: [trimmed],
      max_results: MAX_RESULTS,
    })
      .then((data) => setResults(data))
      .catch((err) => setErrorInfo(parseErrorMessage(err, storeLabel)))
      .finally(() => setSearching(false));
  }

  function handleSearch() {
    executeSearch(selectedStore, query);
  }

  function handleSwitchToIntermarche() {
    setSelectedStore("intermarche");
    executeSearch("intermarche", query);
  }

  async function handleAdd(item: SupermarketSearchResult) {
    if (addingIds.has(item.cache_id) || addedIds.has(item.cache_id)) return;
    setErrorInfo(null);
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
      setErrorInfo(parseErrorMessage(err, activeStoreLabel));
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
        subtitle={
          currentPref
            ? `Recherche chez ${activeStoreLabel} (${currentPref.store_label}) pour ${
                target === "grocery" ? "vos courses" : "votre garde-manger"
              }.`
            : `Trouvez un produit chez ${activeStoreLabel} pour ${
                target === "grocery" ? "vos courses" : "votre garde-manger"
              }.`
        }
      />

      {/* Retailer Selector Pills */}
      <View className="mb-4 flex-row flex-wrap gap-2">
        {AVAILABLE_STORES.map((s) => {
          const isSelected = selectedStore === s.id;
          const pref = preferences.find((p) => p.store === s.id);
          return (
            <Pressable
              key={s.id}
              onPress={() => {
                setSelectedStore(s.id);
                setResults([]);
                setErrorInfo(null);
              }}
              className={`rounded-xl px-3 py-2 border ${
                isSelected
                  ? "border-emerald-600 bg-emerald-50 shadow-xs"
                  : "border-slate-200 bg-white"
              }`}
            >
              <View className="flex-row items-center gap-1.5">
                <Text
                  className={`text-xs font-semibold ${
                    isSelected ? "text-emerald-800" : "text-slate-700"
                  }`}
                >
                  {s.label}
                </Text>
                {pref ? (
                  <Ionicons name="star" size={11} color={isSelected ? "#059669" : "#10b981"} />
                ) : null}
              </View>
              {pref ? (
                <Text
                  className="mt-0.5 text-[10px] text-slate-500 max-w-[120px]"
                  numberOfLines={1}
                >
                  {pref.location_label || pref.store_label}
                </Text>
              ) : null}
            </Pressable>
          );
        })}
      </View>

      {/* Current store summary & Changer button */}
      <View className="mb-4 flex-row items-center justify-between rounded-xl bg-slate-50 p-2.5 border border-slate-200">
        <View className="flex-1 mr-2">
          <Text className="text-xs font-semibold text-slate-800">
            {activeStoreLabel}
            {currentPref
              ? ` • ${currentPref.location_label || currentPref.store_label}`
              : " • Aucun magasin configuré"}
          </Text>
          <Text className="text-[11px] text-slate-500">
            {currentPref
              ? "Magasin favori utilisé pour les prix & stocks"
              : "Sélectionnez votre magasin pour voir les disponibilités réelles"}
          </Text>
        </View>
        <Pressable
          onPress={() => setShowStoreModal(true)}
          className="rounded-lg bg-white px-2.5 py-1.5 border border-slate-300 shadow-xs active:bg-slate-100"
        >
          <Text className="text-xs font-medium text-slate-700">Changer</Text>
        </Pressable>
      </View>

      {errorInfo ? (
        <View className="mb-4 rounded-xl bg-amber-50 p-4 border border-amber-200">
          <View className="flex-row items-start gap-2">
            <Ionicons name="information-circle-outline" size={20} color="#d97706" />
            <View className="flex-1">
              <Text className="text-xs text-amber-900 leading-relaxed">{errorInfo.message}</Text>
              {errorInfo.isAuthRequired && selectedStore !== "intermarche" ? (
                <Pressable
                  onPress={handleSwitchToIntermarche}
                  className="mt-2.5 self-start rounded-lg bg-emerald-600 px-3 py-1.5 active:bg-emerald-700"
                >
                  <Text className="text-xs font-semibold text-white">
                    Rechercher plutôt sur Intermarché
                  </Text>
                </Pressable>
              ) : null}
            </View>
          </View>
        </View>
      ) : null}

      <Field
        label="Produit"
        value={query}
        onChangeText={setQuery}
        placeholder="Ex. : Lait, pâtes, saumon…"
        returnKeyType="search"
        onSubmitEditing={handleSearch}
      />
      <PrimaryButton label="Rechercher" onPress={handleSearch} loading={searching} />

      {results.length > 0 ? (
        <View className="mt-6">
          <Text className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            {results.length} résultat{results.length > 1 ? "s" : ""} chez {activeStoreLabel}
          </Text>
          {results.map((item) => {
            const isAdding = addingIds.has(item.cache_id);
            const isAdded = addedIds.has(item.cache_id);
            const price = formatPrice(item);
            return (
              <View
                key={item.cache_id}
                className="mb-3 flex-row items-center rounded-2xl border border-slate-100 bg-white p-4 shadow-xs"
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
                  <Text className="text-base font-medium text-slate-900" numberOfLines={2}>
                    {item.name}
                  </Text>
                  {item.brand ? (
                    <Text className="text-xs text-slate-500 mt-0.5">{item.brand}</Text>
                  ) : null}
                  <Text className="text-sm font-semibold text-emerald-600 mt-1">
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
                      className={`text-center text-xs font-medium ${
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

      {!searching && results.length === 0 && !errorInfo && query.trim() ? (
        <View className="mt-8 items-center">
          <Text className="text-base text-slate-500">
            Aucun résultat pour « {query.trim()} » chez {activeStoreLabel}.
          </Text>
        </View>
      ) : null}

      <SupermarketStoreModal
        visible={showStoreModal}
        defaultStore={selectedStore}
        onClose={() => setShowStoreModal(false)}
        onSelect={(store) => {
          setSelectedStore(store);
          setShowStoreModal(false);
          getUserStorePreferences()
            .then((prefs) => setPreferences(prefs))
            .catch(() => {});
        }}
      />
    </Screen>
  );
}
