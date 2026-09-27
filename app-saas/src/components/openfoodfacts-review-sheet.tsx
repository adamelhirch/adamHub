import { Ionicons } from "@expo/vector-icons";
import React, { useState } from "react";
import {
  ActivityIndicator,
  Image,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { type OpenFoodFactsProductDraft, type PantryItemCreateInput } from "@/lib/pantry";

export interface OpenFoodFactsReviewSheetProps {
  visible: boolean;
  draft: OpenFoodFactsProductDraft | null;
  onClose: () => void;
  onConfirm: (payload: PantryItemCreateInput) => Promise<void>;
}

const COMMON_UNITS = ["g", "kg", "ml", "cl", "l", "item", "c. à soupe", "c. à café"];
const COMMON_CATEGORIES = [
  "Poisson",
  "Viande",
  "Légumes",
  "Fruits",
  "Produits_laitiers",
  "Épicerie",
  "Boissons",
  "Surgelés",
];
const COMMON_LOCATIONS = ["Placard", "Réfrigérateur", "Congélateur"];

const NUTRISCORE_COLORS: Record<string, { bg: string; text: string }> = {
  a: { bg: "#15803d", text: "#ffffff" },
  b: { bg: "#84cc16", text: "#ffffff" },
  c: { bg: "#eab308", text: "#ffffff" },
  d: { bg: "#f97316", text: "#ffffff" },
  e: { bg: "#ef4444", text: "#ffffff" },
};

interface ReviewFormProps {
  draft: OpenFoodFactsProductDraft;
  onClose: () => void;
  onConfirm: (payload: PantryItemCreateInput) => Promise<void>;
}

function ReviewForm({ draft, onClose, onConfirm }: ReviewFormProps) {
  const [name, setName] = useState(draft.suggested_name || draft.raw_name || "");
  const [quantity, setQuantity] = useState(draft.quantity.toString());
  const [unit, setUnit] = useState(draft.unit || "item");
  const [category, setCategory] = useState(draft.category || "Épicerie");
  const [location, setLocation] = useState(draft.location || "Placard");
  const [expiresAt, setExpiresAt] = useState("");
  const [note, setNote] = useState(draft.brand ? `Marque: ${draft.brand}` : "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError("Veuillez renseigner un nom d'article.");
      return;
    }

    const parsedQty = parseFloat(quantity.replace(",", "."));
    if (isNaN(parsedQty) || parsedQty < 0) {
      setError("Veuillez saisir une quantité positive ou nulle.");
      return;
    }

    const trimmedExpires = expiresAt.trim();
    if (trimmedExpires && !/^\d{4}-\d{2}-\d{2}$/.test(trimmedExpires)) {
      setError("Date d'expiration invalide (format AAAA-MM-JJ).");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await onConfirm({
        name: trimmedName,
        quantity: parsedQty,
        unit: unit.trim() || "item",
        category: category.trim() || null,
        location: location.trim() || null,
        expires_at: trimmedExpires || null,
        note: note.trim() || null,
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur lors de l'enregistrement");
    } finally {
      setLoading(false);
    }
  }

  const nutri = draft.nutriscore?.toLowerCase();
  const nutriStyle = nutri ? NUTRISCORE_COLORS[nutri] : null;

  return (
    <View style={styles.sheetContainer}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.headerTitle}>{"Vérifier l'article"}</Text>
          <Text style={styles.headerSubtitle}>
            {draft.found
              ? "Produit reconnu par Open Food Facts"
              : "Produit non trouvé — création manuelle"}
          </Text>
        </View>
        <Pressable onPress={onClose} hitSlop={8} style={styles.closeButton}>
          <Ionicons name="close" size={22} color="#64748b" />
        </Pressable>
      </View>

      {error ? (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <ScrollView showsVerticalScrollIndicator={false} style={styles.body}>
        {/* Product preview card */}
        <View style={styles.previewCard}>
          {draft.image_url ? (
            <Image
              source={{ uri: draft.image_url }}
              style={styles.thumbnail}
              resizeMode="contain"
            />
          ) : (
            <View style={styles.thumbnailPlaceholder}>
              <Ionicons name="barcode-outline" size={28} color="#94a3b8" />
            </View>
          )}
          <View style={styles.previewInfo}>
            <View style={styles.badgeRow}>
              <View style={styles.barcodeBadge}>
                <Ionicons name="barcode-outline" size={14} color="#475569" />
                <Text style={styles.barcodeText}>{draft.barcode}</Text>
              </View>
              {nutri && nutriStyle ? (
                <View style={[styles.nutriBadge, { backgroundColor: nutriStyle.bg }]}>
                  <Text style={[styles.nutriText, { color: nutriStyle.text }]}>
                    Nutri-Score {nutri.toUpperCase()}
                  </Text>
                </View>
              ) : null}
            </View>
            {draft.raw_name ? (
              <Text style={styles.rawNameText} numberOfLines={2}>
                Origine: {draft.raw_name}
              </Text>
            ) : null}
            {draft.brand ? (
              <Text style={styles.brandText}>Marque: {draft.brand}</Text>
            ) : null}
          </View>
        </View>

        {/* Suggested / Cleaned Name */}
        <View style={styles.fieldGroup}>
          <Text style={styles.label}>Nom culinaire nettoyé</Text>
          <TextInput
            style={styles.input}
            value={name}
            onChangeText={setName}
            placeholder="Ex: Pâtes penne"
            placeholderTextColor="#94a3b8"
          />
        </View>

        {/* Quantity & Unit */}
        <View style={styles.row}>
          <View style={[styles.fieldGroup, { flex: 1 }]}>
            <Text style={styles.label}>Quantité nette</Text>
            <TextInput
              style={styles.input}
              value={quantity}
              onChangeText={setQuantity}
              keyboardType="decimal-pad"
              placeholder="Ex: 500"
              placeholderTextColor="#94a3b8"
            />
          </View>
          <View style={[styles.fieldGroup, { flex: 1, marginLeft: 12 }]}>
            <Text style={styles.label}>Unité</Text>
            <TextInput
              style={styles.input}
              value={unit}
              onChangeText={setUnit}
              placeholder="g, kg, item..."
              placeholderTextColor="#94a3b8"
            />
          </View>
        </View>

        {/* Unit chips */}
        <View style={styles.chipsContainer}>
          {COMMON_UNITS.map((u) => (
            <Pressable
              key={u}
              onPress={() => setUnit(u)}
              style={[styles.chip, unit === u && styles.chipActive]}
            >
              <Text style={[styles.chipText, unit === u && styles.chipTextActive]}>{u}</Text>
            </Pressable>
          ))}
        </View>

        {/* Location Chips */}
        <View style={styles.fieldGroup}>
          <Text style={styles.label}>Emplacement</Text>
          <View style={styles.chipsContainer}>
            {COMMON_LOCATIONS.map((loc) => (
              <Pressable
                key={loc}
                onPress={() => setLocation(loc)}
                style={[styles.chip, location === loc && styles.chipActive]}
              >
                <Text style={[styles.chipText, location === loc && styles.chipTextActive]}>
                  {loc}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        {/* Category Chips */}
        <View style={styles.fieldGroup}>
          <Text style={styles.label}>Catégorie</Text>
          <View style={styles.chipsContainer}>
            {COMMON_CATEGORIES.map((cat) => (
              <Pressable
                key={cat}
                onPress={() => setCategory(cat)}
                style={[styles.chip, category === cat && styles.chipActive]}
              >
                <Text style={[styles.chipText, category === cat && styles.chipTextActive]}>
                  {cat}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        {/* Expiration Date & Note */}
        <View style={styles.row}>
          <View style={[styles.fieldGroup, { flex: 1 }]}>
            <View style={styles.labelWithHint}>
              <Text style={styles.label}>Date de péremption</Text>
              {!expiresAt ? <Text style={styles.hintBadge}>À renseigner</Text> : null}
            </View>
            <TextInput
              style={[styles.input, !expiresAt && styles.inputHighlighted]}
              value={expiresAt}
              onChangeText={setExpiresAt}
              placeholder="AAAA-MM-JJ"
              placeholderTextColor="#94a3b8"
            />
          </View>
          <View style={[styles.fieldGroup, { flex: 1, marginLeft: 12 }]}>
            <Text style={styles.label}>Note / Détails</Text>
            <TextInput
              style={styles.input}
              value={note}
              onChangeText={setNote}
              placeholder="Ex: Marque, lot..."
              placeholderTextColor="#94a3b8"
            />
          </View>
        </View>
      </ScrollView>

      {/* Footer */}
      <View style={styles.footer}>
        <Pressable onPress={onClose} style={styles.cancelButton} disabled={loading}>
          <Text style={styles.cancelButtonText}>Annuler</Text>
        </Pressable>
        <Pressable onPress={handleConfirm} style={styles.confirmButton} disabled={loading}>
          {loading ? (
            <ActivityIndicator size="small" color="#ffffff" />
          ) : (
            <Text style={styles.confirmButtonText}>Ajouter au stock</Text>
          )}
        </Pressable>
      </View>
    </View>
  );
}

export function OpenFoodFactsReviewSheet({
  visible,
  draft,
  onClose,
  onConfirm,
}: OpenFoodFactsReviewSheetProps) {
  if (!visible || !draft) return null;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <Pressable style={styles.backdropPressable} onPress={onClose} />
        <ReviewForm draft={draft} onClose={onClose} onConfirm={onConfirm} />
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.45)",
    justifyContent: "flex-end",
  },
  backdropPressable: {
    flex: 1,
  },
  sheetContainer: {
    backgroundColor: "#ffffff",
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 32,
    maxHeight: "92%",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 14,
  },
  headerLeft: {
    flex: 1,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#0f172a",
  },
  headerSubtitle: {
    fontSize: 13,
    color: "#64748b",
    marginTop: 2,
  },
  closeButton: {
    padding: 6,
    borderRadius: 20,
    backgroundColor: "#f1f5f9",
  },
  previewCard: {
    flexDirection: "row",
    backgroundColor: "#f8fafc",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    padding: 12,
    marginBottom: 16,
    alignItems: "center",
    gap: 12,
  },
  thumbnail: {
    width: 64,
    height: 64,
    borderRadius: 10,
    backgroundColor: "#ffffff",
  },
  thumbnailPlaceholder: {
    width: 64,
    height: 64,
    borderRadius: 10,
    backgroundColor: "#f1f5f9",
    justifyContent: "center",
    alignItems: "center",
  },
  previewInfo: {
    flex: 1,
  },
  badgeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 4,
  },
  barcodeBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "#e2e8f0",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
  },
  barcodeText: {
    fontSize: 11,
    fontWeight: "600",
    color: "#334155",
  },
  nutriBadge: {
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 6,
  },
  nutriText: {
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0.5,
  },
  rawNameText: {
    fontSize: 12,
    color: "#64748b",
    marginTop: 2,
  },
  brandText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#0f172a",
    marginTop: 1,
  },
  body: {
    marginBottom: 16,
  },
  fieldGroup: {
    marginBottom: 14,
  },
  label: {
    fontSize: 12,
    fontWeight: "600",
    color: "#475569",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  labelWithHint: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 6,
  },
  hintBadge: {
    fontSize: 10,
    fontWeight: "600",
    color: "#f59e0b",
    backgroundColor: "#fef3c7",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  input: {
    borderWidth: 1,
    borderColor: "#e2e8f0",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 15,
    color: "#0f172a",
    backgroundColor: "#f8fafc",
  },
  inputHighlighted: {
    borderColor: "#f59e0b",
    backgroundColor: "#fffbeb",
  },
  row: {
    flexDirection: "row",
  },
  chipsContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 12,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: "#f1f5f9",
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  chipActive: {
    backgroundColor: "#ecfdf5",
    borderColor: "#10b981",
  },
  chipText: {
    fontSize: 12,
    color: "#475569",
    fontWeight: "500",
  },
  chipTextActive: {
    color: "#059669",
    fontWeight: "600",
  },
  footer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginTop: 8,
  },
  cancelButton: {
    flex: 1,
    paddingVertical: 13,
    borderRadius: 14,
    backgroundColor: "#f1f5f9",
    alignItems: "center",
  },
  cancelButtonText: {
    fontSize: 15,
    fontWeight: "600",
    color: "#475569",
  },
  confirmButton: {
    flex: 2,
    paddingVertical: 13,
    borderRadius: 14,
    backgroundColor: "#059669",
    alignItems: "center",
  },
  confirmButtonText: {
    fontSize: 15,
    fontWeight: "600",
    color: "#ffffff",
  },
  errorBox: {
    backgroundColor: "#fef2f2",
    padding: 10,
    borderRadius: 10,
    marginBottom: 12,
  },
  errorText: {
    color: "#dc2626",
    fontSize: 13,
  },
});
