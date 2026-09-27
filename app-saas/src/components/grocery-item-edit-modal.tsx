import { Ionicons } from "@expo/vector-icons";
import React, { useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { type GroceryItemRead } from "@/lib/api";

export interface GroceryItemEditModalProps {
  visible: boolean;
  item: GroceryItemRead | null;
  onClose: () => void;
  onSave: (
    id: number,
    payload: {
      name: string;
      quantity: number;
      unit: string;
      category?: string | null;
    },
  ) => Promise<void>;
}

interface GroceryItemEditFormProps {
  item: GroceryItemRead;
  onClose: () => void;
  onSave: (
    id: number,
    payload: {
      name: string;
      quantity: number;
      unit: string;
      category?: string | null;
    },
  ) => Promise<void>;
}

function GroceryItemEditForm({ item, onClose, onSave }: GroceryItemEditFormProps) {
  const [name, setName] = useState(item.name);
  const [quantity, setQuantity] = useState(item.quantity.toString());
  const [unit, setUnit] = useState(item.unit || "item");
  const [category, setCategory] = useState(item.category || "");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    const parsedQty = parseFloat(quantity.replace(",", "."));
    const validQty = !isNaN(parsedQty) && parsedQty > 0 ? parsedQty : 1;
    setSaving(true);
    try {
      await onSave(item.id, {
        name: name.trim() || item.name,
        quantity: validQty,
        unit: unit.trim() || "item",
        category: category.trim() || null,
      });
      onClose();
    } catch {
      // Handled by parent
    } finally {
      setSaving(false);
    }
  }

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.title}>Modifier {"l'article"}</Text>
        <Pressable onPress={onClose} hitSlop={8}>
          <Ionicons name="close" size={20} color="#94a3b8" />
        </Pressable>
      </View>

      <View style={styles.form}>
        <Text style={styles.label}>Nom de {"l'article"}</Text>
        <TextInput
          value={name}
          onChangeText={setName}
          style={styles.input}
          placeholder="Ex. Tomates, Riz..."
          placeholderTextColor="#94a3b8"
        />

        <View style={styles.row}>
          <View style={styles.flex1}>
            <Text style={styles.label}>Quantité</Text>
            <TextInput
              value={quantity}
              onChangeText={setQuantity}
              keyboardType="numeric"
              style={styles.input}
              placeholder="1"
              placeholderTextColor="#94a3b8"
            />
          </View>

          <View style={styles.flex1}>
            <Text style={styles.label}>Unité</Text>
            <TextInput
              value={unit}
              onChangeText={setUnit}
              style={styles.input}
              placeholder="item, g, L..."
              placeholderTextColor="#94a3b8"
            />
          </View>
        </View>

        <Text style={styles.label}>Rayon / Catégorie</Text>
        <TextInput
          value={category}
          onChangeText={setCategory}
          style={styles.input}
          placeholder="Ex. Légumes, Épicerie..."
          placeholderTextColor="#94a3b8"
        />
      </View>

      <View style={styles.actions}>
        <Pressable onPress={onClose} style={styles.cancelBtn}>
          <Text style={styles.cancelText}>Annuler</Text>
        </Pressable>

        <Pressable
          onPress={handleSave}
          disabled={saving || !name.trim()}
          style={[styles.saveBtn, (!name.trim() || saving) && styles.disabledBtn]}
        >
          {saving ? (
            <ActivityIndicator size="small" color="#ffffff" />
          ) : (
            <Text style={styles.saveText}>Enregistrer</Text>
          )}
        </Pressable>
      </View>
    </View>
  );
}

export function GroceryItemEditModal({
  visible,
  item,
  onClose,
  onSave,
}: GroceryItemEditModalProps) {
  if (!item) return null;

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <GroceryItemEditForm
          key={item.id}
          item={item}
          onClose={onClose}
          onSave={onSave}
        />
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.5)",
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  card: {
    backgroundColor: "#ffffff",
    borderRadius: 20,
    width: "100%",
    maxWidth: 400,
    padding: 20,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 5,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  title: {
    fontSize: 17,
    fontWeight: "700",
    color: "#0f172a",
  },
  form: {
    gap: 12,
  },
  row: {
    flexDirection: "row",
    gap: 12,
  },
  flex1: {
    flex: 1,
  },
  label: {
    fontSize: 12,
    fontWeight: "600",
    color: "#64748b",
    marginBottom: 4,
  },
  input: {
    backgroundColor: "#f8fafc",
    borderWidth: 1,
    borderColor: "#e2e8f0",
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    color: "#0f172a",
  },
  actions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 10,
    marginTop: 20,
  },
  cancelBtn: {
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 12,
    backgroundColor: "#f1f5f9",
  },
  cancelText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#64748b",
  },
  saveBtn: {
    paddingVertical: 10,
    paddingHorizontal: 18,
    borderRadius: 12,
    backgroundColor: "#059669",
  },
  disabledBtn: {
    opacity: 0.5,
  },
  saveText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#ffffff",
  },
});
