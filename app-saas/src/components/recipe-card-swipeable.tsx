import { Ionicons } from "@expo/vector-icons";
import React, { useEffect } from "react";
import { Pressable, StyleSheet, Text, Vibration, View } from "react-native";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import Animated, {
  Easing,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withSequence,
  withTiming,
} from "react-native-reanimated";

import { RecipeRead } from "@/lib/recipes";

export interface RecipeCardSwipeableProps {
  recipe: RecipeRead;
  onCookShort: (recipe: RecipeRead) => Promise<void> | void;
  onPlanLong: (recipe: RecipeRead) => void;
  onGroceriesSwipe: (recipe: RecipeRead) => void;
  onPressCard: (recipeId: number) => void;
  isShaking?: boolean;
}

const LONG_SWIPE_THRESHOLD = -180;
const SHORT_SWIPE_THRESHOLD = -90;
const RIGHT_SWIPE_THRESHOLD = 90;

function triggerLightHaptic(duration = 25) {
  try {
    Vibration.vibrate(duration);
  } catch {
    // Ignore if not supported
  }
}

export function RecipeCardSwipeable({
  recipe,
  onCookShort,
  onPlanLong,
  onGroceriesSwipe,
  onPressCard,
  isShaking = false,
}: RecipeCardSwipeableProps) {
  const translateX = useSharedValue(0);
  const shakeOffset = useSharedValue(0);
  const hasTriggeredLongHaptic = useSharedValue(false);

  useEffect(() => {
    if (isShaking) {
      // Gentle horizontal-only shake: 6px max amplitude, snappy
      shakeOffset.value = withSequence(
        withTiming(-6, { duration: 40 }),
        withTiming(6, { duration: 40 }),
        withTiming(-4, { duration: 40 }),
        withTiming(4, { duration: 40 }),
        withTiming(0, { duration: 40 })
      );
      try {
        Vibration.vibrate(30);
      } catch {
        // Platform not supporting vibration
      }
    }
  }, [isShaking, shakeOffset]);

  const panGesture = Gesture.Pan()
    .activeOffsetX([-15, 15])
    .failOffsetY([-12, 12])
    .onUpdate((event) => {
      if (event.translationX > 0) {
        // Dragging right -> Grocery action
        translateX.value = Math.min(event.translationX, 150);
      } else {
        // Dragging left -> Short cook or long plan
        translateX.value = Math.max(event.translationX, -230);

        // Haptic feedback notch when crossing into long-swipe threshold
        if (translateX.value <= LONG_SWIPE_THRESHOLD) {
          if (!hasTriggeredLongHaptic.value) {
            hasTriggeredLongHaptic.value = true;
            runOnJS(triggerLightHaptic)(25);
          }
        } else {
          hasTriggeredLongHaptic.value = false;
        }
      }
    })
    .onEnd((event) => {
      const tx = event.translationX;
      if (tx >= RIGHT_SWIPE_THRESHOLD) {
        runOnJS(onGroceriesSwipe)(recipe);
      } else if (tx <= LONG_SWIPE_THRESHOLD) {
        runOnJS(onPlanLong)(recipe);
      } else if (tx <= SHORT_SWIPE_THRESHOLD) {
        runOnJS(onCookShort)(recipe);
      }
      hasTriggeredLongHaptic.value = false;
      // CRITICAL: Always return cleanly with withTiming (no spring overshoot / no bounce left-right)
      translateX.value = withTiming(0, {
        duration: 180,
        easing: Easing.out(Easing.cubic),
      });
    });

  // Card slide + shake (strictly horizontal transform)
  const cardAnimatedStyle = useAnimatedStyle(() => {
    return {
      transform: [
        { translateX: translateX.value + shakeOffset.value },
      ],
    };
  });

  // SWIPE RIGHT action background (revealed on the left)
  const groceriesBackgroundStyle = useAnimatedStyle(() => {
    const isVisible = translateX.value > 0;
    return {
      opacity: isVisible ? 1 : 0,
      zIndex: isVisible ? 1 : 0,
    };
  });

  const groceriesContentStyle = useAnimatedStyle(() => {
    const isReady = translateX.value >= RIGHT_SWIPE_THRESHOLD;
    return {
      transform: [
        { scale: isReady ? withTiming(1.06, { duration: 100 }) : withTiming(1, { duration: 100 }) },
      ],
    };
  });

  // SWIPE LEFT action background (revealed on the right)
  const leftSwipeBackgroundStyle = useAnimatedStyle(() => {
    const isVisible = translateX.value < 0;
    const isPlan = translateX.value <= LONG_SWIPE_THRESHOLD;
    return {
      opacity: isVisible ? 1 : 0,
      zIndex: isVisible ? 1 : 0,
      backgroundColor: isPlan ? "#4f46e5" : "#059669",
    };
  });

  const cookActionContentStyle = useAnimatedStyle(() => {
    const isPlan = translateX.value <= LONG_SWIPE_THRESHOLD;
    const isReady = translateX.value <= SHORT_SWIPE_THRESHOLD && !isPlan;
    return {
      opacity: isPlan ? withTiming(0, { duration: 100 }) : withTiming(1, { duration: 100 }),
      transform: [
        { scale: isReady ? withTiming(1.06, { duration: 100 }) : withTiming(1, { duration: 100 }) },
      ],
    };
  });

  const planActionContentStyle = useAnimatedStyle(() => {
    const isPlan = translateX.value <= LONG_SWIPE_THRESHOLD;
    return {
      opacity: isPlan ? withTiming(1, { duration: 100 }) : withTiming(0, { duration: 100 }),
      transform: [
        { scale: isPlan ? withTiming(1.06, { duration: 100 }) : withTiming(0.9, { duration: 100 }) },
      ],
    };
  });

  const totalMinutes = (recipe.prep_minutes || 0) + (recipe.cook_minutes || 0);

  return (
    <View style={styles.container}>
      {/* Background action for SWIPE RIGHT -> Courses (revealed on the left) */}
      <Animated.View
        style={[
          styles.actionBackground,
          styles.groceriesBackground,
          groceriesBackgroundStyle,
        ]}
      >
        <Animated.View style={[styles.actionContentRow, groceriesContentStyle]}>
          <View style={styles.iconCircle}>
            <Ionicons name="cart" size={20} color="#ffffff" />
          </View>
          <Text style={styles.actionTextRight}>
            Ajouter aux courses
          </Text>
        </Animated.View>
      </Animated.View>

      {/* Background action for SWIPE LEFT -> Cuisiner or Planifier (revealed on the right) */}
      <Animated.View
        style={[
          styles.actionBackground,
          styles.leftSwipeBackground,
          leftSwipeBackgroundStyle,
        ]}
      >
        {/* Short swipe target: Cuisiner */}
        <Animated.View
          style={[styles.actionContentRow, cookActionContentStyle]}
        >
          <Text style={styles.actionTextLeft}>Cuisiner</Text>
          <View style={styles.iconCircle}>
            <Ionicons name="restaurant" size={18} color="#ffffff" />
          </View>
        </Animated.View>

        {/* Long swipe target: Planifier */}
        <Animated.View
          style={[styles.actionContentRow, styles.planActionAbsolute, planActionContentStyle]}
        >
          <Text style={styles.actionTextLeft}>Planifier</Text>
          <View style={styles.iconCircle}>
            <Ionicons name="calendar" size={18} color="#ffffff" />
          </View>
        </Animated.View>
      </Animated.View>

      {/* Foreground Card */}
      <GestureDetector gesture={panGesture}>
        <Animated.View style={[styles.cardWrapper, cardAnimatedStyle]}>
          <Pressable
            onPress={() => onPressCard(recipe.id)}
            className="rounded-2xl border border-slate-100 bg-white p-4 shadow-sm active:bg-slate-50"
          >
            <View className="flex-row items-center justify-between">
              <Text className="mr-2 flex-1 text-base font-bold text-slate-900" numberOfLines={1}>
                {recipe.name}
              </Text>
              <Ionicons name="chevron-forward" size={18} color="#94a3b8" />
            </View>

            {recipe.description ? (
              <Text className="mt-1 text-xs text-slate-500" numberOfLines={2}>
                {recipe.description}
              </Text>
            ) : null}

            <View className="mt-3 flex-row items-center justify-between">
              <View className="flex-row items-center gap-4">
                <View className="flex-row items-center">
                  <Ionicons name="time-outline" size={14} color="#64748b" />
                  <Text className="ml-1 text-xs text-slate-500">
                    {totalMinutes > 0 ? `${totalMinutes} min` : "Rapide"}
                  </Text>
                </View>

                <View className="flex-row items-center">
                  <Ionicons name="people-outline" size={14} color="#64748b" />
                  <Text className="ml-1 text-xs text-slate-500">
                    {recipe.servings} {recipe.servings > 1 ? "pers." : "pers."}
                  </Text>
                </View>

                <View className="flex-row items-center">
                  <Ionicons name="list-outline" size={14} color="#64748b" />
                  <Text className="ml-1 text-xs text-slate-500">
                    {recipe.ingredients?.length ?? 0} ingr.
                  </Text>
                </View>
              </View>

              {/* Swipe Hints */}
              <View className="flex-row items-center gap-1.5">
                <View className="rounded bg-slate-100 px-1.5 py-0.5">
                  <Text className="text-[10px] font-medium text-slate-400">← Glisser →</Text>
                </View>
              </View>
            </View>
          </Pressable>
        </Animated.View>
      </GestureDetector>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: "relative",
    marginBottom: 12,
    overflow: "hidden",
    borderRadius: 16,
    backgroundColor: "#ffffff",
  },
  actionBackground: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    borderRadius: 16,
    flexDirection: "row",
    alignItems: "center",
  },
  groceriesBackground: {
    justifyContent: "flex-start",
    paddingLeft: 20,
    backgroundColor: "#059669",
  },
  leftSwipeBackground: {
    justifyContent: "flex-end",
    paddingRight: 20,
  },
  actionContentRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  planActionAbsolute: {
    position: "absolute",
    right: 20,
  },
  iconCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255, 255, 255, 0.22)",
  },
  actionTextRight: {
    marginLeft: 10,
    fontSize: 14,
    fontWeight: "700",
    color: "#ffffff",
  },
  actionTextLeft: {
    marginRight: 10,
    fontSize: 14,
    fontWeight: "700",
    color: "#ffffff",
  },
  cardWrapper: {
    zIndex: 2,
    backgroundColor: "#ffffff",
    borderRadius: 16,
  },
});
