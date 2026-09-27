import React, { useEffect, useState } from "react";
import {
  Building2,
  CheckCircle2,
  Circle,
  Loader2,
  MapPin,
  Search,
  Star,
  X,
} from "lucide-react";
import axios from "axios";
import { api } from "../lib/api";
import type {
  OptimizationStrategy,
  PickupType,
  SupermarketStore,
  SupermarketStoreLocation,
  UserStorePreference,
} from "../types/supermarket";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSelectStore?: (
    store: SupermarketStore,
    externalStoreId: string,
    storeLabel: string,
    strategy: OptimizationStrategy
  ) => void;
  initialStore?: SupermarketStore;
}

const RETAILERS: { key: SupermarketStore; label: string }[] = [
  { key: "leclerc", label: "E.Leclerc" },
  { key: "auchan", label: "Auchan" },
  { key: "carrefour", label: "Carrefour" },
  { key: "intermarche", label: "Intermarché" },
];

const STRATEGIES: { key: OptimizationStrategy; label: string; desc: string }[] = [
  { key: "mdd", label: "MDD (Qualité/Prix)", desc: "Marque distributeur par défaut" },
  { key: "budget", label: "Budget strict", desc: "Prix au kg/L le plus bas" },
  { key: "bio", label: "Bio / Label", desc: "Priorité aux produits biologiques" },
];

export const SupermarketStoreSelector: React.FC<Props> = ({
  isOpen,
  onClose,
  onSelectStore,
  initialStore = "leclerc",
}) => {
  const [selectedRetailer, setSelectedRetailer] = useState<SupermarketStore>(initialStore);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [stores, setStores] = useState<SupermarketStoreLocation[]>([]);
  const [preferences, setPreferences] = useState<UserStorePreference[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<OptimizationStrategy>("mdd");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadPreferences();
    }
  }, [isOpen]);

  useEffect(() => {
    const current = preferences.find((p) => p.store === selectedRetailer);
    if (current) {
      setSelectedStrategy(current.optimization_strategy);
    }
  }, [selectedRetailer, preferences]);

  const loadPreferences = async () => {
    try {
      const res = await api.get<UserStorePreference[]>("/supermarket/stores/preferences");
      setPreferences(res.data);
    } catch {
      // ignore
    }
  };

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const isZip = /^\d{5}$/.test(searchQuery.trim());
      const res = await api.get<SupermarketStoreLocation[]>("/supermarket/stores/search", {
        params: {
          store: selectedRetailer,
          zipcode: isZip ? searchQuery.trim() : undefined,
          city: !isZip ? searchQuery.trim() : undefined,
        },
      });
      setStores(res.data);
      if (res.data.length === 0) {
        setError("Aucun magasin trouvé pour cette recherche.");
      }
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err) && err.response?.data?.detail
        ? String(err.response.data.detail)
        : "Erreur lors de la recherche.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectStore = async (storeLoc: SupermarketStoreLocation) => {
    setSaving(true);
    try {
      const res = await api.put<UserStorePreference>(
        `/supermarket/stores/preferences/${storeLoc.store}`,
        {
          external_store_id: storeLoc.external_store_id,
          store_label: storeLoc.name,
          location_label: [storeLoc.address, storeLoc.zipcode, storeLoc.city]
            .filter(Boolean)
            .join(", "),
          pickup_type: storeLoc.pickup_type,
          optimization_strategy: selectedStrategy,
          channel: storeLoc.channel,
        }
      );
      setPreferences((prev) => [
        ...prev.filter((p) => p.store !== res.data.store),
        res.data,
      ]);
      if (onSelectStore) {
        onSelectStore(
          storeLoc.store,
          storeLoc.external_store_id,
          storeLoc.name,
          selectedStrategy
        );
      }
      onClose();
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err) && err.response?.data?.detail
        ? String(err.response.data.detail)
        : "Impossible de sauvegarder ce magasin favori.";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  const activePref = preferences.find((p) => p.store === selectedRetailer);

  const renderBadge = (type: PickupType) => {
    switch (type) {
      case "tape":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-900/50 text-purple-300 border border-purple-700">
            Borne TAPE 24/7
          </span>
        );
      case "spot":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-900/50 text-amber-300 border border-amber-700">
            Spot déporté
          </span>
        );
      case "pieton":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-900/50 text-emerald-300 border border-emerald-700">
            Drive Piéton
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-900/50 text-blue-300 border border-blue-700">
            Quai standard
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 overflow-y-auto">
      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl w-full max-w-xl p-6 shadow-2xl relative">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-neutral-800">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Building2 className="w-5 h-5 text-amber-500" />
              Sélection du Magasin Drive
            </h2>
            <p className="text-xs text-neutral-400 mt-0.5">
              Choisissez votre enseigne, point de retrait et stratégie de panier
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-white p-1 rounded-lg hover:bg-neutral-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Retailer Tabs */}
        <div className="grid grid-cols-4 gap-2 my-4">
          {RETAILERS.map((r) => {
            const isSelected = selectedRetailer === r.key;
            return (
              <button
                key={r.key}
                type="button"
                onClick={() => {
                  setSelectedRetailer(r.key);
                  setStores([]);
                  setError(null);
                }}
                className={`py-2 px-3 rounded-xl text-sm font-semibold border transition ${
                  isSelected
                    ? "bg-amber-500/20 border-amber-500 text-amber-400"
                    : "bg-neutral-800/60 border-neutral-700/60 text-neutral-400 hover:bg-neutral-800 hover:text-white"
                }`}
              >
                {r.label}
              </button>
            );
          })}
        </div>

        {/* Current Active Preference */}
        {activePref && (
          <div className="mb-4 p-3.5 bg-neutral-800/80 border border-neutral-700/80 rounded-xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-amber-400 text-xs font-semibold">
                <Star className="w-3.5 h-3.5 fill-amber-400" />
                Magasin favori configuré
              </div>
              {renderBadge(activePref.pickup_type)}
            </div>
            <div className="text-white font-medium text-sm mt-1">{activePref.store_label}</div>
            {activePref.location_label && (
              <div className="text-neutral-400 text-xs mt-0.5">{activePref.location_label}</div>
            )}
          </div>
        )}

        {/* Strategy Selection */}
        <div className="mb-4">
          <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">
            Stratégie d'optimisation
          </label>
          <div className="space-y-2">
            {STRATEGIES.map((strat) => {
              const isSelected = selectedStrategy === strat.key;
              return (
                <div
                  key={strat.key}
                  onClick={() => setSelectedStrategy(strat.key)}
                  className={`p-3 rounded-xl border flex items-center justify-between cursor-pointer transition ${
                    isSelected
                      ? "bg-amber-500/10 border-amber-500/80 text-amber-400"
                      : "bg-neutral-800/50 border-neutral-800 text-neutral-300 hover:bg-neutral-800"
                  }`}
                >
                  <div>
                    <div className="text-sm font-medium">{strat.label}</div>
                    <div className="text-xs text-neutral-400">{strat.desc}</div>
                  </div>
                  {isSelected ? (
                    <CheckCircle2 className="w-5 h-5 text-amber-500" />
                  ) : (
                    <Circle className="w-5 h-5 text-neutral-600" />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Search Input */}
        <form onSubmit={handleSearch} className="mb-4">
          <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">
            Rechercher par code postal ou commune
          </label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <MapPin className="w-4 h-4 text-neutral-500 absolute left-3 top-3" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Ex. 31700 ou Blagnac"
                className="w-full bg-neutral-800 border border-neutral-700 rounded-xl pl-9 pr-4 py-2 text-sm text-white placeholder-neutral-500 focus:outline-none focus:border-amber-500"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !searchQuery.trim()}
              className="px-4 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-neutral-950 font-semibold rounded-xl text-sm transition flex items-center gap-1.5"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              Rechercher
            </button>
          </div>
        </form>

        {error && (
          <div className="mb-4 p-3 bg-red-950/40 border border-red-800/60 rounded-xl text-xs text-red-300">
            {error}
          </div>
        )}

        {/* Results */}
        {stores.length > 0 && (
          <div className="max-h-60 overflow-y-auto space-y-2 pr-1">
            {stores.map((s) => (
              <div
                key={s.external_store_id}
                onClick={() => handleSelectStore(s)}
                className="p-3 bg-neutral-800/70 hover:bg-neutral-800 border border-neutral-700/60 rounded-xl cursor-pointer transition flex items-start justify-between"
              >
                <div>
                  <div className="text-white font-medium text-sm">{s.name}</div>
                  <div className="text-xs text-neutral-400 mt-0.5">
                    {[s.address, s.zipcode, s.city].filter(Boolean).join(", ")}
                  </div>
                  {s.distance_km !== null && s.distance_km !== undefined && (
                    <div className="text-xs text-amber-500 mt-0.5 font-medium">
                      À {s.distance_km.toFixed(1)} km
                    </div>
                  )}
                </div>
                <div className="flex flex-col items-end gap-1">
                  {renderBadge(s.pickup_type)}
                  {saving && <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-500" />}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
