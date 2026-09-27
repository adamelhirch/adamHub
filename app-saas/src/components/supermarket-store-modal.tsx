import { Ionicons } from "@expo/vector-icons";
import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  OptimizationStrategy,
  PickupType,
  SupermarketStore,
  SupermarketStoreLocation,
  UserStorePreference,
  getUserStorePreferences,
  searchSupermarketStores,
  setUserStorePreference,
} from "@/lib/supermarket-api";

export interface SupermarketStoreModalProps {
  visible: boolean;
  onClose: () => void;
  onSelect?: (
    store: SupermarketStore,
    externalId: string,
    label: string,
    strategy: OptimizationStrategy,
  ) => void;
  defaultStore?: SupermarketStore;
}

const RETAILERS: { key: SupermarketStore; label: string; icon: string }[] = [
  { key: "leclerc", label: "Leclerc", icon: "cart" },
  { key: "auchan", label: "Auchan", icon: "basket" },
  { key: "carrefour", label: "Carrefour", icon: "storefront" },
  { key: "intermarche", label: "Intermarché", icon: "pricetag" },
];

const STRATEGIES: { key: OptimizationStrategy; label: string; desc: string }[] = [
  { key: "mdd", label: "MDD (Qualité/Prix)", desc: "Marques distributeurs par défaut" },
  { key: "budget", label: "Budget strict", desc: "Prix au kg/L le plus bas" },
  { key: "bio", label: "Bio / Label", desc: "Priorité aux produits biologiques" },
];

export function SupermarketStoreModal({
  visible,
  onClose,
  onSelect,
  defaultStore = "leclerc",
}: SupermarketStoreModalProps) {
  const [selectedRetailer, setSelectedRetailer] = useState<SupermarketStore>(defaultStore);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [stores, setStores] = useState<SupermarketStoreLocation[]>([]);
  const [preferences, setPreferences] = useState<UserStorePreference[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<OptimizationStrategy>("mdd");
  const [selectedStoreLoc, setSelectedStoreLoc] = useState<SupermarketStoreLocation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (visible) {
      getUserStorePreferences()
        .then((prefs) => {
          if (!cancelled) {
            setPreferences(prefs);
            const cur = prefs.find((p) => p.store === selectedRetailer);
            if (cur) {
              setSelectedStrategy(cur.optimization_strategy);
            }
          }
        })
        .catch(() => {});
    }
    return () => {
      cancelled = true;
    };
  }, [visible, selectedRetailer]);

  async function handleSearch() {
    if (!searchQuery.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const isZip = /^\d{5}$/.test(searchQuery.trim());
      const results = await searchSupermarketStores({
        store: selectedRetailer,
        zipcode: isZip ? searchQuery.trim() : undefined,
        city: !isZip ? searchQuery.trim() : undefined,
      });
      setStores(results);
      if (results.length === 0) {
        setError("Aucun point de retrait trouvé pour cette recherche.");
      }
    } catch (e: any) {
      setError(e.message || "Erreur lors de la recherche des magasins.");
    } finally {
      setLoading(false);
    }
  }

  function handleSelectSearchResult(storeLoc: SupermarketStoreLocation) {
    setSelectedStoreLoc(storeLoc);
    setError(null);
  }

  async function handleConfirmAndPrepare() {
    const activePref = preferences.find((p) => p.store === selectedRetailer);
    const target = selectedStoreLoc || activePref;
    if (!target) {
      setError("Veuillez d'abord sélectionner ou rechercher un point de retrait.");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const externalId = target.external_store_id;
      const storeLabel = "store_label" in target ? target.store_label : target.name;
      const locationLabel =
        "location_label" in target && target.location_label
          ? target.location_label
          : "address" in target
            ? [target.address, target.zipcode, target.city].filter(Boolean).join(", ")
            : "";
      const pickupType = target.pickup_type;
      const channel = target.channel;

      // Persist chosen store and strategy to user preferences
      await setUserStorePreference(selectedRetailer, {
        external_store_id: externalId,
        store_label: storeLabel,
        location_label: locationLabel,
        pickup_type: pickupType,
        optimization_strategy: selectedStrategy,
        channel: channel,
      });

      if (onSelect) {
        onSelect(selectedRetailer, externalId, storeLabel, selectedStrategy);
      }
      onClose();
    } catch (e: any) {
      setError(e.message || "Impossible de préparer le panier pour ce magasin.");
    } finally {
      setSaving(false);
    }
  }

  function renderPickupBadge(type: PickupType) {
    switch (type) {
      case "tape":
        return (
          <View className="bg-purple-900/60 border border-purple-600 px-2 py-0.5 rounded-md">
            <Text className="text-[11px] font-medium text-purple-200">Borne TAPE 24/7</Text>
          </View>
        );
      case "spot":
        return (
          <View className="bg-amber-900/60 border border-amber-600 px-2 py-0.5 rounded-md">
            <Text className="text-[11px] font-medium text-amber-200">Spot déporté</Text>
          </View>
        );
      case "pieton":
        return (
          <View className="bg-emerald-900/60 border border-emerald-600 px-2 py-0.5 rounded-md">
            <Text className="text-[11px] font-medium text-emerald-200">Drive Piéton</Text>
          </View>
        );
      default:
        return (
          <View className="bg-blue-900/60 border border-blue-600 px-2 py-0.5 rounded-md">
            <Text className="text-[11px] font-medium text-blue-200">Quai Drive</Text>
          </View>
        );
    }
  }

  const activePref = preferences.find((p) => p.store === selectedRetailer);
  const activeTarget = selectedStoreLoc || activePref;
  const activeStoreName = activeTarget
    ? "store_label" in activeTarget
      ? activeTarget.store_label
      : activeTarget.name
    : null;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View className="flex-1 bg-black/70 justify-end">
        <View className="bg-neutral-900 border-t border-neutral-800 rounded-t-3xl max-h-[92%] p-5 pb-7">
          {/* Header */}
          <View className="flex-row items-center justify-between pb-4 border-b border-neutral-800">
            <View>
              <Text className="text-xl font-bold text-white">Sélection du Magasin Drive</Text>
              <Text className="text-xs text-neutral-400">
                Point de retrait et stratégie de panier
              </Text>
            </View>
            <Pressable
              onPress={onClose}
              className="w-9 h-9 rounded-full bg-neutral-800 items-center justify-center active:bg-neutral-700"
            >
              <Ionicons name="close" size={20} color="#a3a3a3" />
            </Pressable>
          </View>

          <ScrollView showsVerticalScrollIndicator={false} className="mt-4">
            {/* Retailer Tabs */}
            <Text className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">
              Enseigne
            </Text>
            <View className="flex-row space-x-2 mb-4">
              {RETAILERS.map((r) => {
                const isSelected = selectedRetailer === r.key;
                const retailerPref = preferences.find((p) => p.store === r.key);
                return (
                  <Pressable
                    key={r.key}
                    onPress={() => {
                      setSelectedRetailer(r.key);
                      setSelectedStoreLoc(null);
                      const cur = preferences.find((p) => p.store === r.key);
                      if (cur) {
                        setSelectedStrategy(cur.optimization_strategy);
                      }
                      setStores([]);
                      setError(null);
                    }}
                    className={`flex-1 py-2.5 px-2 rounded-xl items-center border ${
                      isSelected
                        ? "bg-amber-500/20 border-amber-500"
                        : "bg-neutral-800 border-neutral-700 active:bg-neutral-750"
                    }`}
                  >
                    <Ionicons
                      name={r.icon as any}
                      size={18}
                      color={isSelected ? "#f59e0b" : "#a3a3a3"}
                    />
                    <Text
                      className={`text-xs font-semibold mt-1 ${
                        isSelected ? "text-amber-400" : "text-neutral-400"
                      }`}
                    >
                      {r.label}
                    </Text>
                    {retailerPref ? (
                      <View className="mt-1 flex-row items-center">
                        <Ionicons name="star" size={10} color="#f59e0b" />
                      </View>
                    ) : null}
                  </Pressable>
                );
              })}
            </View>

            {/* Selected Store / Favorite Card */}
            <Text className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">
              Point de retrait sélectionné
            </Text>
            {activeTarget ? (
              <Pressable
                onPress={() => {
                  if (selectedStoreLoc && activePref) {
                    // Toggle back to default favorite if user was viewing search result
                    setSelectedStoreLoc(null);
                  }
                }}
                className="bg-neutral-800/90 border-2 border-amber-500 rounded-2xl p-4 mb-4 shadow-sm"
              >
                <View className="flex-row items-center justify-between">
                  <View className="flex-row items-center space-x-2">
                    <Ionicons
                      name={selectedStoreLoc ? "checkmark-circle" : "star"}
                      size={16}
                      color="#f59e0b"
                    />
                    <Text className="text-xs font-semibold text-amber-400">
                      {selectedStoreLoc ? "Point de retrait choisi" : "Magasin favori actuel"}
                    </Text>
                  </View>
                  {renderPickupBadge(activeTarget.pickup_type)}
                </View>
                <Text className="text-base font-bold text-white mt-1.5">
                  {"store_label" in activeTarget ? activeTarget.store_label : activeTarget.name}
                </Text>
                <Text className="text-xs text-neutral-400 mt-0.5">
                  {"location_label" in activeTarget && activeTarget.location_label
                    ? activeTarget.location_label
                    : "address" in activeTarget
                      ? [activeTarget.address, activeTarget.zipcode, activeTarget.city]
                          .filter(Boolean)
                          .join(", ")
                      : ""}
                </Text>
                {selectedStoreLoc && activePref ? (
                  <Text className="mt-2 text-[11px] text-amber-400/80 underline">
                    Revenir à mon magasin favori ({activePref.store_label})
                  </Text>
                ) : null}
              </Pressable>
            ) : (
              <View className="bg-neutral-800/40 border border-neutral-700/60 rounded-2xl p-4 mb-4">
                <Text className="text-xs text-neutral-400">
                  Aucun point de retrait configuré pour cette enseigne. Utilisez la recherche
                  ci-dessous pour choisir votre magasin.
                </Text>
              </View>
            )}

            {/* Optimization Strategy Picker */}
            <Text className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">
              {"Stratégie d'optimisation"}
            </Text>
            <View className="space-y-2 mb-4">
              {STRATEGIES.map((strat) => {
                const isSelected = selectedStrategy === strat.key;
                return (
                  <Pressable
                    key={strat.key}
                    onPress={() => setSelectedStrategy(strat.key)}
                    className={`p-3 rounded-xl border flex-row items-center justify-between ${
                      isSelected
                        ? "bg-amber-500/10 border-amber-500"
                        : "bg-neutral-800/60 border-neutral-750"
                    }`}
                  >
                    <View className="flex-1 mr-2">
                      <Text
                        className={`text-sm font-semibold ${
                          isSelected ? "text-amber-400" : "text-white"
                        }`}
                      >
                        {strat.label}
                      </Text>
                      <Text className="text-xs text-neutral-400 mt-0.5">{strat.desc}</Text>
                    </View>
                    <Ionicons
                      name={isSelected ? "checkmark-circle" : "ellipse-outline"}
                      size={20}
                      color={isSelected ? "#f59e0b" : "#525252"}
                    />
                  </Pressable>
                );
              })}
            </View>

            {/* Search Box */}
            <Text className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">
              Changer ou rechercher un magasin
            </Text>
            <View className="flex-row space-x-2 mb-3">
              <View className="flex-1 flex-row items-center bg-neutral-800 border border-neutral-700 rounded-xl px-3 py-2">
                <Ionicons name="search" size={18} color="#737373" className="mr-2" />
                <TextInput
                  placeholder="Code postal (ex. 31700) ou ville"
                  placeholderTextColor="#737373"
                  value={searchQuery}
                  onChangeText={setSearchQuery}
                  onSubmitEditing={handleSearch}
                  returnKeyType="search"
                  className="flex-1 text-white text-sm"
                />
              </View>
              <Pressable
                onPress={handleSearch}
                disabled={loading || !searchQuery.trim()}
                className={`px-4 rounded-xl items-center justify-center ${
                  loading || !searchQuery.trim()
                    ? "bg-amber-500/40"
                    : "bg-amber-500 active:bg-amber-600"
                }`}
              >
                {loading ? (
                  <ActivityIndicator size="small" color="#171717" />
                ) : (
                  <Text className="text-neutral-950 font-bold text-sm">Chercher</Text>
                )}
              </Pressable>
            </View>

            {/* Error Message */}
            {error && (
              <View className="bg-red-950/50 border border-red-800 rounded-xl p-3 mb-3">
                <Text className="text-xs text-red-300">{error}</Text>
              </View>
            )}

            {/* Store Search Results */}
            {stores.length > 0 && (
              <View className="space-y-2 mb-6">
                <Text className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
                  Points de retrait trouvés ({stores.length})
                </Text>
                {stores.map((s) => {
                  const isCurrentChosen =
                    selectedStoreLoc?.external_store_id === s.external_store_id;
                  return (
                    <Pressable
                      key={s.external_store_id}
                      onPress={() => handleSelectSearchResult(s)}
                      className={`p-3.5 rounded-xl border ${
                        isCurrentChosen
                          ? "bg-amber-500/20 border-amber-500"
                          : "bg-neutral-800 border-neutral-700 active:bg-neutral-750"
                      }`}
                    >
                      <View className="flex-row items-start justify-between">
                        <View className="flex-1 pr-2">
                          <Text className="text-sm font-bold text-white">{s.name}</Text>
                          <Text className="text-xs text-neutral-400 mt-1">
                            {[s.address, s.zipcode, s.city].filter(Boolean).join(", ")}
                          </Text>
                          {s.distance_km !== null && s.distance_km !== undefined ? (
                            <Text className="text-[11px] text-amber-500 mt-1">
                              À {s.distance_km.toFixed(1)} km
                            </Text>
                          ) : null}
                        </View>
                        <View className="items-end">
                          {renderPickupBadge(s.pickup_type)}
                          {isCurrentChosen ? (
                            <Ionicons
                              name="checkmark-circle"
                              size={18}
                              color="#f59e0b"
                              className="mt-2"
                            />
                          ) : null}
                        </View>
                      </View>
                    </Pressable>
                  );
                })}
              </View>
            )}
          </ScrollView>

          {/* Sticky Bottom Action CTA Button */}
          <View className="pt-3 border-t border-neutral-800">
            <Pressable
              onPress={handleConfirmAndPrepare}
              disabled={!activeTarget || saving}
              className={`py-3.5 px-4 rounded-2xl items-center justify-center flex-row shadow-sm ${
                activeTarget && !saving
                  ? "bg-amber-500 active:bg-amber-600"
                  : "bg-neutral-800 opacity-50"
              }`}
            >
              {saving ? (
                <ActivityIndicator size="small" color="#171717" />
              ) : (
                <>
                  <Ionicons name="cart" size={18} color="#171717" />
                  <Text className="ml-2 font-bold text-base text-neutral-950">
                    {activeStoreName
                      ? `Concevoir mon panier (${activeStoreName})`
                      : "Sélectionnez un point de retrait"}
                  </Text>
                </>
              )}
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}
