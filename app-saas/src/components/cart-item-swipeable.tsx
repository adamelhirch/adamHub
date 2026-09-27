import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import Animated, {
  Easing,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";

import { MatchedCartItemRead } from "@/lib/supermarket-api";

export interface CartItemSwipeableProps {
  item: MatchedCartItemRead;
  onRemove: (item: MatchedCartItemRead) => void;
  onOpenEdit: (item: MatchedCartItemRead) => void;
  onRestore?: (item: MatchedCartItemRead) => void;
}

const SWIPE_THRESHOLD = 80;

export function CartItemSwipeable({
  item,
  onRemove,
  onOpenEdit,
  onRestore,
}: CartItemSwipeableProps) {
  const translateX = useSharedValue(0);

  const panGesture = Gesture.Pan()
    .activeOffsetX([-15, 15])
    .failOffsetY([-12, 12])
    .onUpdate((event) => {
      // Allow swiping left (remove) and right (modify)
      translateX.value = Math.max(-120, Math.min(120, event.translationX));
    })
    .onEnd((event) => {
      const tx = event.translationX;
      if (tx <= -SWIPE_THRESHOLD) {
        runOnJS(onRemove)(item);
      } else if (tx >= SWIPE_THRESHOLD) {
        runOnJS(onOpenEdit)(item);
      }
      translateX.value = withTiming(0, {
        duration: 180,
        easing: Easing.out(Easing.cubic),
      });
    });

  const cardAnimatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: translateX.value }],
  }));

  const removeBackgroundStyle = useAnimatedStyle(() => ({
    opacity: translateX.value < 0 ? Math.min(1, Math.abs(translateX.value) / SWIPE_THRESHOLD) : 0,
    zIndex: translateX.value < 0 ? 1 : 0,
  }));

  const editBackgroundStyle = useAnimatedStyle(() => ({
    opacity: translateX.value > 0 ? Math.min(1, translateX.value / SWIPE_THRESHOLD) : 0,
    zIndex: translateX.value > 0 ? 1 : 0,
  }));

  const isRemoved = item.status === "removed";
  const isToModify = item.status === "to_modify";

  return (
    <View style={styles.container}>
      {/* Background Revealed on Swipe Right: EDIT */}
      <Animated.View style={[styles.backgroundEdit, editBackgroundStyle]}>
        <Ionicons name="create-outline" size={24} color="#ffffff" />
        <Text style={styles.actionText}>Modifier</Text>
      </Animated.View>

      {/* Background Revealed on Swipe Left: REMOVE */}
      <Animated.View style={[styles.backgroundRemove, removeBackgroundStyle]}>
        <Text style={styles.actionText}>Supprimer</Text>
        <Ionicons name="trash-outline" size={24} color="#ffffff" />
      </Animated.View>

      {/* Main Foreground Card */}
      <GestureDetector gesture={panGesture}>
        <Animated.View
          style={[
            styles.card,
            isRemoved && styles.cardRemoved,
            cardAnimatedStyle,
          ]}
        >
          <View style={styles.contentRow}>
            {/* Image or icon */}
            {item.image_url ? (
              <Image source={{ uri: item.image_url }} style={styles.productImage} resizeMode="contain" />
            ) : (
              <View style={styles.placeholderImage}>
                <Ionicons name="basket-outline" size={20} color="#059669" />
              </View>
            )}

            {/* Product Details */}
            <View style={styles.detailsCol}>
              <View style={styles.titleRow}>
                <Text
                  style={[styles.productName, isRemoved && styles.textStrikethrough]}
                  numberOfLines={2}
                >
                  {item.name}
                </Text>
              </View>

              <View style={styles.metaRow}>
                {item.brand ? (
                  <Text style={styles.brandText}>{item.brand}</Text>
                ) : null}
                {item.packaging ? (
                  <Text style={styles.metaText}> • {item.packaging}</Text>
                ) : null}
              </View>

              {/* Badges */}
              <View style={styles.badgesRow}>
                {item.match_type === "substitute" && (
                  <View style={styles.substituteBadge}>
                    <Text style={styles.substituteBadgeText}>Substitut</Text>
                  </View>
                )}
                {isToModify && (
                  <View style={styles.modifyBadge}>
                    <Ionicons name="alert-circle-outline" size={12} color="#b45309" />
                    <Text style={styles.modifyBadgeText}>À modifier</Text>
                  </View>
                )}
                {isRemoved && (
                  <View style={styles.removedBadge}>
                    <Text style={styles.removedBadgeText}>Retiré</Text>
                  </View>
                )}
              </View>

              {/* Custom Note from User/LLM */}
              {isToModify && item.custom_note ? (
                <Text style={styles.customNoteText}>
                  « {item.custom_note} »
                </Text>
              ) : null}
            </View>

            {/* Price & Actions */}
            <View style={styles.priceCol}>
              <Text style={[styles.totalPrice, isRemoved && styles.textMuted]}>
                {(item.total_price_cents / 100).toFixed(2)} €
              </Text>
              <Text style={styles.unitPrice}>
                {item.quantity} × {(item.unit_price_cents / 100).toFixed(2)} €
              </Text>

              {/* Touch trigger buttons */}
              <View style={styles.actionsRow}>
                {isRemoved && onRestore ? (
                  <Pressable onPress={() => onRestore(item)} hitSlop={8} style={styles.miniBtn}>
                    <Ionicons name="arrow-undo" size={16} color="#059669" />
                  </Pressable>
                ) : (
                  <>
                    <Pressable onPress={() => onOpenEdit(item)} hitSlop={8} style={styles.miniBtn}>
                      <Ionicons name="ellipsis-horizontal" size={18} color="#64748b" />
                    </Pressable>
                  </>
                )}
              </View>
            </View>
          </View>
        </Animated.View>
      </GestureDetector>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginVertical: 4,
    position: "relative",
    overflow: "hidden",
    borderRadius: 16,
  },
  backgroundEdit: {
    ...StyleSheet.absoluteFill,
    backgroundColor: "#3b82f6",
    flexDirection: "row",
    alignItems: "center",
    paddingLeft: 20,
    gap: 8,
  },
  backgroundRemove: {
    ...StyleSheet.absoluteFill,
    backgroundColor: "#ef4444",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "flex-end",
    paddingRight: 20,
    gap: 8,
  },
  actionText: {
    color: "#ffffff",
    fontWeight: "600",
    fontSize: 13,
  },
  card: {
    backgroundColor: "#ffffff",
    padding: 12,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#f1f5f9",
    shadowColor: "#0f172a",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  cardRemoved: {
    backgroundColor: "#f8fafc",
    opacity: 0.65,
  },
  contentRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  productImage: {
    width: 48,
    height: 48,
    borderRadius: 8,
    backgroundColor: "#f8fafc",
    marginRight: 10,
  },
  placeholderImage: {
    width: 48,
    height: 48,
    borderRadius: 8,
    backgroundColor: "#ecfdf5",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 10,
  },
  detailsCol: {
    flex: 1,
    marginRight: 8,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  productName: {
    fontSize: 13,
    fontWeight: "600",
    color: "#0f172a",
    flex: 1,
  },
  textStrikethrough: {
    textDecorationLine: "line-through",
    color: "#94a3b8",
  },
  textMuted: {
    color: "#94a3b8",
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 2,
  },
  brandText: {
    fontSize: 11,
    fontWeight: "500",
    color: "#059669",
  },
  metaText: {
    fontSize: 11,
    color: "#64748b",
  },
  badgesRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 4,
  },
  substituteBadge: {
    backgroundColor: "#ede9fe",
    borderRadius: 6,
    paddingHorizontal: 6,
    paddingVertical: 1,
  },
  substituteBadgeText: {
    fontSize: 10,
    fontWeight: "600",
    color: "#6d28d9",
  },
  modifyBadge: {
    backgroundColor: "#fef3c7",
    borderRadius: 6,
    paddingHorizontal: 6,
    paddingVertical: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
  },
  modifyBadgeText: {
    fontSize: 10,
    fontWeight: "600",
    color: "#b45309",
  },
  removedBadge: {
    backgroundColor: "#fee2e2",
    borderRadius: 6,
    paddingHorizontal: 6,
    paddingVertical: 1,
  },
  removedBadgeText: {
    fontSize: 10,
    fontWeight: "600",
    color: "#b91c1c",
  },
  customNoteText: {
    fontSize: 11,
    fontStyle: "italic",
    color: "#b45309",
    marginTop: 3,
  },
  priceCol: {
    alignItems: "flex-end",
  },
  totalPrice: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0f172a",
  },
  unitPrice: {
    fontSize: 10,
    color: "#64748b",
    marginTop: 1,
  },
  actionsRow: {
    marginTop: 4,
  },
  miniBtn: {
    padding: 4,
  },
});
