import { Ionicons } from "@expo/vector-icons";
import React, { useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { type PantryItemRead } from "@/lib/api";
import { type PantryItemUpdateInput } from "@/lib/pantry";

export interface PantryEditSheetProps {
  visible: boolean;
  item: PantryItemRead | null;
  onClose: () => void;
  onSave: (id: number, payload: PantryItemUpdateInput) => Promise<void>;
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
const COMMON_LOCATIONS = ["Réfrigérateur", "Placard", "Congélateur"];

interface PantryEditFormProps {
  item: PantryItemRead;
  onClose: () => void;
  onSave: (id: number, payload: PantryItemUpdateInput) => Promise<void>;
}

function PantryEditForm({ item, onClose, onSave }: PantryEditFormProps) {
  const [name, setName] = useState(item.name);
  const [quantity, setQuantity] = useState(item.quantity.toString());
  const [unit, setUnit] = useState(item.unit || "item");
  const [category, setCategory] = useState(item.category || "Épicerie");
  const [location, setLocation] = useState(item.location || "Placard");
  const [expiresAt, setExpiresAt] = useState(item.expires_at || "");
  const [note, setNote] = useState(item.note || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    const parsedQty = parseFloat(quantity.replace(",", "."));
    if (isNaN(parsedQty) || parsedQty < 0) {
      setError("Veuillez saisir une quantité positive ou nulle.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await onSave(item.id, {
        name: name.trim() || item.name,
        quantity: parsedQty,
        unit: unit.trim() || "item",
        category: category.trim() || null,
        location: location.trim() || null,
        expires_at: expiresAt.trim() || null,
        note: note.trim() || null,
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur lors de l'enregistrement");
    } finally {
      setSaving(false);
    }
  }

  return (
    <View style={styles.sheetContainer}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.headerTitle}>{"Modifier l'article"}</Text>
          <Text style={styles.headerSubtitle}>Mettez à jour le stock et les détails</Text>
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
        {/* Name */}
        <View style={styles.fieldGroup}>
          <Text style={styles.label}>{"Nom de l'ingrédient"}</Text>
          <TextInput
            style={styles.input}
            value={name}
            onChangeText={setName}
            placeholder="Ex: Saumon frais"
            placeholderTextColor="#94a3b8"
          />
        </View>

        {/* Quantity & Unit */}
        <View style={styles.row}>
          <View style={[styles.fieldGroup, { flex: 1 }]}>
            <Text style={styles.label}>Quantité en stock</Text>
            <TextInput
              style={styles.input}
              value={quantity}
              onChangeText={setQuantity}
              keyboardType="decimal-pad"
              placeholder="Ex: 250"
              placeholderTextColor="#94a3b8"
            />
          </View>
          <View style={[styles.fieldGroup, { flex: 1, marginLeft: 12 }]}>
            <Text style={styles.label}>Unité</Text>
            <TextInput
              style={styles.input}
              value={unit}
              onChangeText={setUnit}
              placeholder="g, item, ml..."
              placeholderTextColor="#94a3b8"
            />
          </View>
        </View>

        {/* Unit Chips */}
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
            <Text style={styles.label}>Date de péremption</Text>
            <TextInput
              style={styles.input}
              value={expiresAt}
              onChangeText={setExpiresAt}
              placeholder="AAAA-MM-JJ"
              placeholderTextColor="#94a3b8"
            />
          </View>
          <View style={[styles.fieldGroup, { flex: 1, marginLeft: 12 }]}>
            <Text style={styles.label}>Note / Pièces</Text>
            <TextInput
              style={styles.input}
              value={note}
              onChangeText={setNote}
              placeholder="Ex: 2 pavés"
              placeholderTextColor="#94a3b8"
            />
          </View>
        </View>
      </ScrollView>

      {/* Footer */}
      <View style={styles.footer}>
        <Pressable onPress={onClose} style={styles.cancelButton} disabled={saving}>
          <Text style={styles.cancelButtonText}>Annuler</Text>
        </Pressable>
        <Pressable onPress={handleSave} style={styles.saveButton} disabled={saving}>
          {saving ? (
            <ActivityIndicator size="small" color="#ffffff" />
          ) : (
            <Text style={styles.saveButtonText}>Enregistrer</Text>
          )}
        </Pressable>
      </View>
    </View>
  );
}

export function PantryEditSheet({ visible, item, onClose, onSave }: PantryEditSheetProps) {
  if (!visible || !item) return null;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <Pressable style={styles.backdropPressable} onPress={onClose} />
        <PantryEditForm item={item} onClose={onClose} onSave={onSave} />
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
    maxHeight: "88%",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 16,
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
  saveButton: {
    flex: 2,
    paddingVertical: 13,
    borderRadius: 14,
    backgroundColor: "#059669",
    alignItems: "center",
  },
  saveButtonText: {
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
