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

import { MatchedCartItemRead } from "@/lib/supermarket-api";

export interface CartItemEditModalProps {
  visible: boolean;
  item: MatchedCartItemRead | null;
  onClose: () => void;
  onAcceptSubstitute?: (item: MatchedCartItemRead, substituteId: number) => Promise<void> | void;
  onSaveCustomNote: (item: MatchedCartItemRead, note: string) => Promise<void> | void;
  onRemoveItem: (item: MatchedCartItemRead) => Promise<void> | void;
}

const QUICK_NOTES = [
  "Préférer en Bio",
  "Prendre le moins cher",
  "Marque distributeur",
  "Grand format",
  "Sans lactose / végétal",
];

function CartItemEditContent({
  item,
  onClose,
  onAcceptSubstitute,
  onSaveCustomNote,
  onRemoveItem,
}: {
  item: MatchedCartItemRead;
  onClose: () => void;
  onAcceptSubstitute?: (item: MatchedCartItemRead, substituteId: number) => Promise<void> | void;
  onSaveCustomNote: (item: MatchedCartItemRead, note: string) => Promise<void> | void;
  onRemoveItem: (item: MatchedCartItemRead) => Promise<void> | void;
}) {
  const [note, setNote] = useState(item.custom_note || "");
  const [loading, setLoading] = useState(false);

  const sub = item.substitute_proposal;

  async function handleSaveNote() {
    setLoading(true);
    try {
      await onSaveCustomNote(item, note.trim());
      onClose();
    } finally {
      setLoading(false);
    }
  }

  async function handleAcceptSub() {
    if (!sub || !onAcceptSubstitute) return;
    setLoading(true);
    try {
      await onAcceptSubstitute(item, sub.id);
      onClose();
    } finally {
      setLoading(false);
    }
  }

  async function handleRemove() {
    setLoading(true);
    try {
      await onRemoveItem(item);
      onClose();
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.sheetContainer}>
      {/* Header */}
      <View style={styles.headerRow}>
        <View style={styles.headerTitles}>
          <Text style={styles.title}>{"Modifier l'article"}</Text>
          <Text style={styles.subtitle} numberOfLines={1}>
            {item.name}
          </Text>
        </View>
        <Pressable onPress={onClose} hitSlop={12} style={styles.closeBtn}>
          <Ionicons name="close" size={20} color="#64748b" />
        </Pressable>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        {/* Current Item Overview */}
        <View style={styles.currentCard}>
          <View style={styles.currentDetails}>
            <Text style={styles.currentName}>{item.name}</Text>
            <Text style={styles.currentMeta}>
              {item.brand ? `${item.brand} • ` : ""}
              {item.packaging || ""}
            </Text>
          </View>
          <Text style={styles.currentPrice}>
            {(item.unit_price_cents / 100).toFixed(2)} €
          </Text>
        </View>

        {/* Substitute proposal card if available */}
        {sub && sub.status === "pending" && (
          <View style={styles.substituteCard}>
            <View style={styles.subHeader}>
              <Ionicons name="swap-horizontal" size={16} color="#7c3aed" />
              <Text style={styles.subTitle}>Alternative suggérée</Text>
            </View>
            <Text style={styles.subName}>{sub.alternative_name}</Text>
            <Text style={styles.subReason}>Raison : {sub.reason}</Text>

            <View style={styles.subPriceRow}>
              <Text style={styles.subPrice}>
                {(sub.alternative_unit_price_cents / 100).toFixed(2)} €
              </Text>
              <Text style={styles.priceDiff}>
                {sub.price_difference_cents > 0 ? "+" : ""}
                {(sub.price_difference_cents / 100).toFixed(2)} €
              </Text>
            </View>

            <Pressable
              onPress={handleAcceptSub}
              disabled={loading}
              style={styles.acceptSubBtn}
            >
              <Ionicons name="checkmark-circle-outline" size={18} color="#ffffff" />
              <Text style={styles.acceptSubText}>Choisir cette alternative</Text>
            </Pressable>
          </View>
        )}

        {/* Custom note section */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>
            {"Consigne pour l'IA (mise à jour du panier)"}
          </Text>
          <TextInput
            value={note}
            onChangeText={setNote}
            placeholder="Ex : Préférer une marque locale, sans sucre ajouté…"
            placeholderTextColor="#94a3b8"
            style={styles.textInput}
            multiline
            numberOfLines={3}
          />

          {/* Quick suggestions */}
          <View style={styles.chipsContainer}>
            {QUICK_NOTES.map((q) => (
              <Pressable
                key={q}
                onPress={() => setNote(q)}
                style={styles.chip}
              >
                <Text style={styles.chipText}>{q}</Text>
              </Pressable>
            ))}
          </View>

          <Pressable
            onPress={handleSaveNote}
            disabled={loading}
            style={styles.saveNoteBtn}
          >
            {loading ? (
              <ActivityIndicator size="small" color="#ffffff" />
            ) : (
              <>
                <Ionicons name="sparkles" size={16} color="#ffffff" />
                <Text style={styles.saveNoteText}>Enregistrer la consigne</Text>
              </>
            )}
          </Pressable>
        </View>

        {/* Danger actions */}
        <View style={styles.dangerSection}>
          <Pressable
            onPress={handleRemove}
            disabled={loading}
            style={styles.removeBtn}
          >
            <Ionicons name="trash-outline" size={16} color="#ef4444" />
            <Text style={styles.removeBtnText}>Retirer cet article du panier</Text>
          </Pressable>
        </View>
      </ScrollView>
    </View>
  );
}

export function CartItemEditModal({
  visible,
  item,
  onClose,
  onAcceptSubstitute,
  onSaveCustomNote,
  onRemoveItem,
}: CartItemEditModalProps) {
  if (!item) return null;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <CartItemEditContent
          key={item.id}
          item={item}
          onClose={onClose}
          onAcceptSubstitute={onAcceptSubstitute}
          onSaveCustomNote={onSaveCustomNote}
          onRemoveItem={onRemoveItem}
        />
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.4)",
    justifyContent: "flex-end",
  },
  sheetContainer: {
    backgroundColor: "#ffffff",
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: "85%",
    paddingBottom: 24,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#f1f5f9",
  },
  headerTitles: {
    flex: 1,
    marginRight: 12,
  },
  title: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0f172a",
  },
  subtitle: {
    fontSize: 12,
    color: "#64748b",
    marginTop: 2,
  },
  closeBtn: {
    padding: 6,
    borderRadius: 20,
    backgroundColor: "#f1f5f9",
  },
  scrollContent: {
    padding: 16,
    gap: 16,
  },
  currentCard: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "#f8fafc",
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  currentDetails: {
    flex: 1,
    marginRight: 12,
  },
  currentName: {
    fontSize: 13,
    fontWeight: "600",
    color: "#0f172a",
  },
  currentMeta: {
    fontSize: 11,
    color: "#64748b",
    marginTop: 2,
  },
  currentPrice: {
    fontSize: 14,
    fontWeight: "700",
    color: "#059669",
  },
  substituteCard: {
    backgroundColor: "#faf5ff",
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: "#e9d5ff",
  },
  subHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 6,
  },
  subTitle: {
    fontSize: 12,
    fontWeight: "700",
    color: "#7c3aed",
    textTransform: "uppercase",
  },
  subName: {
    fontSize: 13,
    fontWeight: "600",
    color: "#1e1b4b",
  },
  subReason: {
    fontSize: 11,
    color: "#6b7280",
    marginTop: 2,
  },
  subPriceRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 6,
    marginBottom: 10,
  },
  subPrice: {
    fontSize: 14,
    fontWeight: "700",
    color: "#0f172a",
  },
  priceDiff: {
    fontSize: 11,
    fontWeight: "600",
    color: "#6b7280",
  },
  acceptSubBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#7c3aed",
    paddingVertical: 10,
    borderRadius: 10,
    gap: 6,
  },
  acceptSubText: {
    color: "#ffffff",
    fontSize: 12,
    fontWeight: "600",
  },
  section: {
    gap: 8,
  },
  sectionLabel: {
    fontSize: 13,
    fontWeight: "600",
    color: "#334155",
  },
  textInput: {
    backgroundColor: "#f8fafc",
    borderWidth: 1,
    borderColor: "#e2e8f0",
    borderRadius: 12,
    padding: 12,
    fontSize: 13,
    color: "#0f172a",
    textAlignVertical: "top",
    minHeight: 70,
  },
  chipsContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 4,
  },
  chip: {
    backgroundColor: "#f1f5f9",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  chipText: {
    fontSize: 11,
    color: "#475569",
    fontWeight: "500",
  },
  saveNoteBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#059669",
    paddingVertical: 12,
    borderRadius: 12,
    gap: 8,
    marginTop: 6,
  },
  saveNoteText: {
    color: "#ffffff",
    fontSize: 13,
    fontWeight: "600",
  },
  dangerSection: {
    marginTop: 8,
    borderTopWidth: 1,
    borderTopColor: "#f1f5f9",
    paddingTop: 12,
  },
  removeBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
    borderRadius: 12,
    backgroundColor: "#fef2f2",
    gap: 6,
  },
  removeBtnText: {
    color: "#ef4444",
    fontSize: 12,
    fontWeight: "600",
  },
});
