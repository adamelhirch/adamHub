import { Ionicons } from "@expo/vector-icons";
import React, { useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { Alert } from "@/lib/alert";

import { CartItemEditModal } from "./cart-item-edit-modal";
import { CartItemSwipeable } from "./cart-item-swipeable";
import {
  confirmPickup,
  deleteCartJob,
  GroceryToCartJobRead,
  MatchedCartItemRead,
  refineCartJob,
  syncCartJob,
  updateCartJobItem,
} from "@/lib/supermarket-api";

export interface CartReviewModalProps {
  visible: boolean;
  job: GroceryToCartJobRead | null;
  onClose: () => void;
  onRefreshJob?: () => Promise<void>;
  onPickupConfirmed?: () => void;
  onDeleteJob?: () => void;
}

function CartReviewContent({
  job,
  onClose,
  onRefreshJob,
  onPickupConfirmed,
  onDeleteJob,
}: {
  job: GroceryToCartJobRead;
  onClose: () => void;
  onRefreshJob?: () => Promise<void>;
  onPickupConfirmed?: () => void;
  onDeleteJob?: () => void;
}) {
  const [currentJob, setCurrentJob] = useState<GroceryToCartJobRead>(job);
  const [editingItem, setEditingItem] = useState<MatchedCartItemRead | null>(null);
  const [refining, setRefining] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const activeItems = currentJob.items.filter((i) => i.status !== "removed");
  const removedItems = currentJob.items.filter((i) => i.status === "removed");
  const itemsToModify = currentJob.items.filter((i) => i.status === "to_modify");
  const isSynced = currentJob.status === "synced";
  const isCompleted = currentJob.status === "completed";

  async function handleRemove(item: MatchedCartItemRead) {
    try {
      const updated = await updateCartJobItem(currentJob.id, item.id, { status: "removed" });
      setCurrentJob((prev) => {
        const newItems = prev.items.map((it) => (it.id === item.id ? updated : it));
        const newTotal = newItems
          .filter((it) => it.status !== "removed")
          .reduce((sum, it) => sum + it.total_price_cents, 0);
        return { ...prev, items: newItems, estimated_total_cents: newTotal };
      });
    } catch {
      Alert.alert("Erreur", "Impossible de supprimer l'article.");
    }
  }

  async function handleRestore(item: MatchedCartItemRead) {
    try {
      const updated = await updateCartJobItem(currentJob.id, item.id, { status: "staged" });
      setCurrentJob((prev) => {
        const newItems = prev.items.map((it) => (it.id === item.id ? updated : it));
        const newTotal = newItems
          .filter((it) => it.status !== "removed")
          .reduce((sum, it) => sum + it.total_price_cents, 0);
        return { ...prev, items: newItems, estimated_total_cents: newTotal };
      });
    } catch {
      Alert.alert("Erreur", "Impossible de restaurer l'article.");
    }
  }

  async function handleSaveNote(item: MatchedCartItemRead, note: string) {
    try {
      const updated = await updateCartJobItem(currentJob.id, item.id, {
        status: "to_modify",
        custom_note: note,
      });
      setCurrentJob((prev) => ({
        ...prev,
        items: prev.items.map((it) => (it.id === item.id ? updated : it)),
      }));
    } catch {
      Alert.alert("Erreur", "Impossible d'enregistrer la consigne.");
    }
  }

  async function handleAcceptSubstitute(item: MatchedCartItemRead, substituteId: number) {
    try {
      const updatedJob = await refineCartJob(currentJob.id, {
        adjustments: [
          {
            matched_item_id: item.id,
            action: "accept_substitute",
            substitute_id: substituteId,
          },
        ],
      });
      setCurrentJob(updatedJob);
    } catch {
      Alert.alert("Erreur", "Impossible d'accepter l'alternative.");
    }
  }

  async function handleRefineBatch() {
    setRefining(true);
    try {
      const updatedJob = await refineCartJob(currentJob.id, { adjustments: [] });
      setCurrentJob(updatedJob);
      Alert.alert("Panier mis à jour", "Les articles à modifier ont été réajustés par l'IA.");
    } catch {
      Alert.alert("Erreur", "La mise à jour du panier a échoué.");
    } finally {
      setRefining(false);
    }
  }

  async function handleSyncDrive() {
    setSyncing(true);
    try {
      const res = await syncCartJob(currentJob.id);
      setCurrentJob((prev) => ({ ...prev, status: "synced", synced_at: res.synced_at }));
      if (onRefreshJob) await onRefreshJob();
      Alert.alert(
        "Panier synchronisé !",
        `${res.items_synced_count} articles ont été envoyés vers votre compte drive. Statut : En attente de retrait.`,
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erreur lors de la synchronisation.";
      Alert.alert("Erreur de synchronisation", msg);
    } finally {
      setSyncing(false);
    }
  }

  async function handleConfirmPickup() {
    setConfirming(true);
    try {
      const res = await confirmPickup(currentJob.id);
      setCurrentJob((prev) => ({ ...prev, status: "completed", completed_at: res.completed_at }));
      Alert.alert("Retrait confirmé", res.message);
      if (onPickupConfirmed) onPickupConfirmed();
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erreur lors de la confirmation.";
      Alert.alert("Erreur", msg);
    } finally {
      setConfirming(false);
    }
  }

  async function handleDeleteJob() {
    Alert.alert(
      "Abandonner le panier",
      "Voulez-vous supprimer ce panier drive ? Vos articles resteront dans votre liste de courses.",
      [
        { text: "Annuler", style: "cancel" },
        {
          text: "Supprimer",
          style: "destructive",
          onPress: async () => {
            try {
              await deleteCartJob(currentJob.id);
              if (onDeleteJob) await onDeleteJob();
              onClose();
            } catch (err: unknown) {
              const msg = err instanceof Error ? err.message : "Impossible de supprimer le panier.";
              Alert.alert("Erreur", msg);
            }
          },
        },
      ],
    );
  }

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <View style={styles.storeRow}>
            <Text style={styles.storeName}>Drive {currentJob.store.toUpperCase()}</Text>
            <View style={styles.statusBadge}>
              <Text style={styles.statusBadgeText}>{currentJob.status}</Text>
            </View>
          </View>
          <Text style={styles.storeId}>Point de retrait : {currentJob.external_store_id}</Text>
        </View>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <Pressable onPress={handleDeleteJob} hitSlop={10} style={styles.deleteHeaderBtn}>
            <Ionicons name="trash-outline" size={18} color="#dc2626" />
          </Pressable>
          <Pressable onPress={onClose} hitSlop={12} style={styles.closeBtn}>
            <Ionicons name="close" size={20} color="#64748b" />
          </Pressable>
        </View>
      </View>

      {/* Metrics Bar */}
      <View style={styles.metricsBar}>
        <View style={styles.metricItem}>
          <Text style={styles.metricLabel}>Total estimé</Text>
          <Text style={styles.metricValue}>
            {(currentJob.estimated_total_cents / 100).toFixed(2)} €
          </Text>
        </View>
        <View style={styles.metricDivider} />
        <View style={styles.metricItem}>
          <Text style={styles.metricLabel}>Articles</Text>
          <Text style={styles.metricValue}>
            {activeItems.length} / {currentJob.items_count}
          </Text>
        </View>
        <View style={styles.metricDivider} />
        <View style={styles.metricItem}>
          <Text style={styles.metricLabel}>Stratégie</Text>
          <Text style={styles.metricValue}>
            {currentJob.optimization_strategy.toUpperCase()}
          </Text>
        </View>
      </View>

      {/* Batch refinement alert banner */}
      {itemsToModify.length > 0 && (
        <View style={styles.refineBanner}>
          <Ionicons name="sparkles" size={18} color="#b45309" />
          <Text style={styles.refineBannerText}>
            {itemsToModify.length} article(s) avec consigne(s) en attente.
          </Text>
          <Pressable
            onPress={handleRefineBatch}
            disabled={refining}
            style={styles.refineBtn}
          >
            {refining ? (
              <ActivityIndicator size="small" color="#ffffff" />
            ) : (
              <Text style={styles.refineBtnText}>Mettre à jour</Text>
            )}
          </Pressable>
        </View>
      )}

      {/* List of items */}
      <ScrollView contentContainerStyle={styles.scrollList} showsVerticalScrollIndicator={false}>
        {activeItems.length === 0 && removedItems.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="cart-outline" size={40} color="#94a3b8" />
            <Text style={styles.emptyText}>Aucun article dans ce panier.</Text>
          </View>
        ) : (
          <>
            {activeItems.map((item) => (
              <CartItemSwipeable
                key={item.id}
                item={item}
                onRemove={handleRemove}
                onOpenEdit={(it) => setEditingItem(it)}
              />
            ))}

            {removedItems.length > 0 && (
              <View style={styles.removedSection}>
                <Text style={styles.removedSectionTitle}>
                  Articles retirés ({removedItems.length})
                </Text>
                {removedItems.map((item) => (
                  <CartItemSwipeable
                    key={item.id}
                    item={item}
                    onRemove={handleRemove}
                    onOpenEdit={(it) => setEditingItem(it)}
                    onRestore={handleRestore}
                  />
                ))}
              </View>
            )}
          </>
        )}
      </ScrollView>

      {/* Footer actions */}
      <View style={styles.footer}>
        {isSynced ? (
          <View style={{ gap: 8 }}>
            <View style={{ paddingBottom: 4 }}>
              <Text style={{ fontSize: 11, color: "#64748b", textAlign: "center" }}>
                Panier synchronisé • Vous pouvez confirmer la réception physique maintenant ou plus tard depuis vos Courses.
              </Text>
            </View>
            <View style={{ flexDirection: "row", gap: 8 }}>
              <Pressable
                onPress={onClose}
                style={[styles.primaryActionBtn, { flex: 1, backgroundColor: "#f1f5f9" }]}
              >
                <Text style={[styles.primaryActionText, { color: "#475569" }]}>
                  Confirmer plus tard
                </Text>
              </Pressable>

              <Pressable
                onPress={handleConfirmPickup}
                disabled={confirming || isCompleted}
                style={[styles.primaryActionBtn, styles.pickupBtn, { flex: 1 }]}
              >
                {confirming ? (
                  <ActivityIndicator size="small" color="#ffffff" />
                ) : (
                  <>
                    <Ionicons name="checkmark-done" size={16} color="#ffffff" />
                    <Text style={styles.primaryActionText}>
                      {isCompleted ? "Déjà confirmé" : "Confirmer le retrait"}
                    </Text>
                  </>
                )}
              </Pressable>
            </View>
          </View>
        ) : (
          <Pressable
            onPress={handleSyncDrive}
            disabled={syncing || activeItems.length === 0}
            style={[
              styles.primaryActionBtn,
              activeItems.length === 0 && styles.disabledBtn,
            ]}
          >
            {syncing ? (
              <ActivityIndicator size="small" color="#ffffff" />
            ) : (
              <>
                <Ionicons name="cart" size={18} color="#ffffff" />
                <Text style={styles.primaryActionText}>
                  Synchroniser vers mon Drive
                </Text>
              </>
            )}
          </Pressable>
        )}
      </View>

      {/* Edit Modal */}
      <CartItemEditModal
        visible={editingItem !== null}
        item={editingItem}
        onClose={() => setEditingItem(null)}
        onSaveCustomNote={handleSaveNote}
        onAcceptSubstitute={handleAcceptSubstitute}
        onRemoveItem={handleRemove}
      />
    </View>
  );
}

export function CartReviewModal({
  visible,
  job,
  onClose,
  onRefreshJob,
  onPickupConfirmed,
  onDeleteJob,
}: CartReviewModalProps) {
  if (!job) return null;

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <CartReviewContent
        key={`${job.id}-${job.updated_at}`}
        job={job}
        onClose={onClose}
        onRefreshJob={onRefreshJob}
        onPickupConfirmed={onPickupConfirmed}
        onDeleteJob={onDeleteJob}
      />
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#f8fafc",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: 16,
    backgroundColor: "#ffffff",
    borderBottomWidth: 1,
    borderBottomColor: "#f1f5f9",
  },
  storeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  storeName: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0f172a",
  },
  statusBadge: {
    backgroundColor: "#ecfdf5",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  statusBadgeText: {
    fontSize: 10,
    fontWeight: "600",
    color: "#059669",
    textTransform: "uppercase",
  },
  storeId: {
    fontSize: 11,
    color: "#64748b",
    marginTop: 2,
  },
  deleteHeaderBtn: {
    padding: 8,
    borderRadius: 20,
    backgroundColor: "#fef2f2",
  },
  closeBtn: {
    padding: 8,
    borderRadius: 20,
    backgroundColor: "#f1f5f9",
  },
  metricsBar: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#ffffff",
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  metricItem: {
    flex: 1,
    alignItems: "center",
  },
  metricLabel: {
    fontSize: 11,
    color: "#64748b",
  },
  metricValue: {
    fontSize: 14,
    fontWeight: "700",
    color: "#0f172a",
    marginTop: 2,
  },
  metricDivider: {
    width: 1,
    height: 24,
    backgroundColor: "#f1f5f9",
  },
  refineBanner: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fef3c7",
    paddingHorizontal: 14,
    paddingVertical: 10,
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 12,
    gap: 8,
  },
  refineBannerText: {
    flex: 1,
    fontSize: 12,
    color: "#92400e",
    fontWeight: "500",
  },
  refineBtn: {
    backgroundColor: "#b45309",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  refineBtnText: {
    color: "#ffffff",
    fontSize: 11,
    fontWeight: "600",
  },
  scrollList: {
    padding: 16,
    paddingBottom: 90,
  },
  emptyState: {
    paddingVertical: 48,
    alignItems: "center",
    justifyContent: "center",
  },
  emptyText: {
    fontSize: 13,
    color: "#94a3b8",
    marginTop: 8,
  },
  removedSection: {
    marginTop: 16,
    borderTopWidth: 1,
    borderTopColor: "#e2e8f0",
    paddingTop: 12,
  },
  removedSectionTitle: {
    fontSize: 12,
    fontWeight: "600",
    color: "#94a3b8",
    marginBottom: 8,
    textTransform: "uppercase",
  },
  footer: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: "#ffffff",
    padding: 16,
    borderTopWidth: 1,
    borderTopColor: "#e2e8f0",
  },
  primaryActionBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#059669",
    paddingVertical: 14,
    borderRadius: 14,
    gap: 8,
    shadowColor: "#059669",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 2,
  },
  pickupBtn: {
    backgroundColor: "#2563eb",
    shadowColor: "#2563eb",
  },
  disabledBtn: {
    opacity: 0.5,
  },
  primaryActionText: {
    color: "#ffffff",
    fontSize: 14,
    fontWeight: "700",
  },
});
