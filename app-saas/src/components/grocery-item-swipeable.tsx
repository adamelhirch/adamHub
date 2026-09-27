import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import Animated, {
  Easing,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";

import { type GroceryItemRead } from "@/lib/api";

export interface GroceryItemSwipeableProps {
  item: GroceryItemRead;
  onToggleChecked: (id: number) => void;
  onRemove: (item: GroceryItemRead) => void;
  onOpenEdit: (item: GroceryItemRead) => void;
}

const SWIPE_THRESHOLD = 80;

export function GroceryItemSwipeable({
  item,
  onToggleChecked,
  onRemove,
  onOpenEdit,
}: GroceryItemSwipeableProps) {
  const translateX = useSharedValue(0);

  const panGesture = Gesture.Pan()
    .activeOffsetX([-15, 15])
    .failOffsetY([-12, 12])
    .onUpdate((event) => {
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

  return (
    <View style={styles.container}>
      {/* Background Revealed on Swipe Right: EDIT */}
      <Animated.View style={[styles.backgroundEdit, editBackgroundStyle]}>
        <Ionicons name="create-outline" size={22} color="#ffffff" />
        <Text style={styles.actionText}>Modifier</Text>
      </Animated.View>

      {/* Background Revealed on Swipe Left: REMOVE */}
      <Animated.View style={[styles.backgroundRemove, removeBackgroundStyle]}>
        <Text style={styles.actionText}>Supprimer</Text>
        <Ionicons name="trash-outline" size={22} color="#ffffff" />
      </Animated.View>

      {/* Main Foreground Row */}
      <GestureDetector gesture={panGesture}>
        <Animated.View style={[styles.card, cardAnimatedStyle]}>
          <Pressable
            onPress={() => onToggleChecked(item.id)}
            style={styles.contentRow}
            accessibilityRole="checkbox"
            accessibilityState={{ checked: item.checked }}
          >
            {/* Checkbox */}
            <View
              style={[
                styles.checkbox,
                item.checked && styles.checkboxChecked,
              ]}
            >
              {item.checked && <Ionicons name="checkmark" size={15} color="#ffffff" />}
            </View>

            {/* Item details */}
            <View style={styles.detailsCol}>
              <View style={styles.titleRow}>
                <Text
                  style={[
                    styles.itemName,
                    item.checked && styles.itemNameChecked,
                  ]}
                  numberOfLines={1}
                >
                  {item.name}
                </Text>

                {/* Drive Cart Badge */}
                {item.in_cart && (
                  <View style={styles.inCartBadge}>
                    <Ionicons name="car-outline" size={12} color="#2563eb" />
                    <Text style={styles.inCartBadgeText}>En panier drive</Text>
                  </View>
                )}
              </View>

              <Text style={styles.metaText}>
                {item.quantity} {item.unit}
                {item.category ? ` • ${item.category}` : ""}
              </Text>
            </View>

            {/* Quick action icons */}
            <Pressable
              onPress={() => onOpenEdit(item)}
              style={styles.quickActionBtn}
              hitSlop={8}
            >
              <Ionicons name="create-outline" size={17} color="#94a3b8" />
            </Pressable>

            <Pressable
              onPress={() => onRemove(item)}
              style={styles.quickActionBtn}
              hitSlop={8}
            >
              <Ionicons name="trash-outline" size={17} color="#94a3b8" />
            </Pressable>
          </Pressable>
        </Animated.View>
      </GestureDetector>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: "relative",
    overflow: "hidden",
    backgroundColor: "#ffffff",
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#f1f5f9",
  },
  backgroundEdit: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "#0284c7",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "flex-start",
    paddingLeft: 20,
    gap: 8,
  },
  backgroundRemove: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "#dc2626",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "flex-end",
    paddingRight: 20,
    gap: 8,
  },
  actionText: {
    color: "#ffffff",
    fontSize: 13,
    fontWeight: "700",
  },
  card: {
    backgroundColor: "#ffffff",
    paddingVertical: 12,
    paddingHorizontal: 14,
  },
  contentRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 7,
    borderWidth: 1.5,
    borderColor: "#cbd5e1",
    backgroundColor: "#ffffff",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  checkboxChecked: {
    backgroundColor: "#10b981",
    borderColor: "#10b981",
  },
  detailsCol: {
    flex: 1,
    marginRight: 8,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    flexWrap: "wrap",
  },
  itemName: {
    fontSize: 14,
    fontWeight: "600",
    color: "#0f172a",
  },
  itemNameChecked: {
    color: "#94a3b8",
    textDecorationLine: "line-through",
  },
  metaText: {
    fontSize: 12,
    color: "#64748b",
    marginTop: 2,
  },
  inCartBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#eff6ff",
    borderColor: "#bfdbfe",
    borderWidth: 1,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 6,
    gap: 3,
  },
  inCartBadgeText: {
    fontSize: 10,
    fontWeight: "600",
    color: "#1d4ed8",
  },
  quickActionBtn: {
    padding: 6,
    marginLeft: 2,
  },
});
