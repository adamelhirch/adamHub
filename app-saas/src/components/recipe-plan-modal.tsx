import { Ionicons } from "@expo/vector-icons";
import React, { useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  Switch,
  Text,
  View,
} from "react-native";

import { ApiError } from "@/lib/api";
import { AlternativeSlot, CalendarConflictDetail, RecipeRead } from "@/lib/recipes";

export interface RecipePlanModalProps {
  visible: boolean;
  recipe: RecipeRead | null;
  onClose: () => void;
  onSchedule: (plannedAt: string, autoAddMissing: boolean) => Promise<void>;
}

export function RecipePlanModal(props: RecipePlanModalProps) {
  if (!props.visible || !props.recipe) return null;

  return (
    <RecipePlanModalContent
      {...props}
      recipe={props.recipe}
    />
  );
}

function RecipePlanModalContent({
  visible,
  recipe,
  onClose,
  onSchedule,
}: RecipePlanModalProps & { recipe: RecipeRead }) {
  const [targetDate, setTargetDate] = useState<"today" | "tomorrow" | "dayAfter">("today");
  const [selectedHour, setSelectedHour] = useState(() => (new Date().getHours() < 13 ? 12 : 19));
  const [selectedMinute, setSelectedMinute] = useState(30);
  const [autoAddMissing, setAutoAddMissing] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Conflict state when HTTP 409 occurs
  const [conflictError, setConflictError] = useState<{
    detail: string;
    colliding: CalendarConflictDetail[];
    suggested: AlternativeSlot[];
  } | null>(null);

  const durationMin =
    ((recipe.prep_minutes || 0) + (recipe.cook_minutes || 0)) > 0
      ? (recipe.prep_minutes || 0) + (recipe.cook_minutes || 0)
      : 45;

  function formatPlannedAtISO(
    dateChoice: "today" | "tomorrow" | "dayAfter",
    hour: number,
    minute: number
  ): string {
    const d = new Date();
    if (dateChoice === "tomorrow") {
      d.setDate(d.getDate() + 1);
    } else if (dateChoice === "dayAfter") {
      d.setDate(d.getDate() + 2);
    }
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    const h = String(hour).padStart(2, "0");
    const m = String(minute).padStart(2, "0");
    return `${year}-${month}-${day}T${h}:${m}:00Z`;
  }

  function formatSlotTime(iso: string): string {
    const match = iso.match(/T(\d{2}):(\d{2})/);
    if (match) return `${match[1]}:${match[2]}`;
    const d = new Date(iso);
    return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  }

  async function handleConfirmSchedule() {
    setSubmitting(true);
    setConflictError(null);

    const isoString = formatPlannedAtISO(targetDate, selectedHour, selectedMinute);

    try {
      await onSchedule(isoString, autoAddMissing);
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const data = err.data;
        const colliding: CalendarConflictDetail[] = data?.colliding_items || [];
        const suggested: AlternativeSlot[] = data?.suggested_slots || [];
        setConflictError({
          detail: err.message || "Conflit d'agenda détecté",
          colliding,
          suggested,
        });
      } else {
        setConflictError({
          detail: err instanceof Error ? err.message : "Impossible de planifier le repas",
          colliding: [],
          suggested: [],
        });
      }
    } finally {
      setSubmitting(false);
    }
  }

  function applySuggestedSlot(slot: AlternativeSlot) {
    const match = slot.start_at.match(/(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
    if (match) {
      const [, y, m, d, h, min] = match;
      const slotDateStr = `${y}-${m}-${d}`;
      const now = new Date();
      const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
      const tomorrow = new Date(now);
      tomorrow.setDate(now.getDate() + 1);
      const tomorrowStr = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, "0")}-${String(tomorrow.getDate()).padStart(2, "0")}`;

      if (slotDateStr === todayStr) setTargetDate("today");
      else if (slotDateStr === tomorrowStr) setTargetDate("tomorrow");
      else setTargetDate("dayAfter");

      setSelectedHour(parseInt(h, 10));
      setSelectedMinute(parseInt(min, 10));
    }
    setConflictError(null);
  }

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View className="flex-1 justify-end bg-black/50">
        <Pressable className="flex-1" onPress={onClose} />
        <View className="max-h-[90%] rounded-t-3xl bg-white px-5 pb-8 pt-4 shadow-xl">
          {/* Handle bar */}
          <View className="mb-3 h-1 w-12 self-center rounded-full bg-slate-300" />

          {/* Header */}
          <View className="mb-4 flex-row items-center justify-between">
            <View className="flex-1 pr-2">
              <Text className="text-xl font-bold text-slate-900" numberOfLines={1}>
                Planifier la recette
              </Text>
              <Text className="text-xs text-slate-500" numberOfLines={1}>
                {recipe.name} • {durationMin} min estimées
              </Text>
            </View>
            <Pressable
              onPress={onClose}
              hitSlop={8}
              className="h-8 w-8 items-center justify-center rounded-full bg-slate-100"
            >
              <Ionicons name="close" size={18} color="#64748b" />
            </Pressable>
          </View>

          <ScrollView showsVerticalScrollIndicator={false} className="max-h-[500px]">
            {/* Conflict Alert Banner */}
            {conflictError ? (
              <View className="mb-4 rounded-2xl border border-amber-300 bg-amber-50 p-4">
                <View className="flex-row items-start">
                  <Ionicons name="alert-circle" size={22} color="#d97706" />
                  <View className="ml-2.5 flex-1">
                    <Text className="text-sm font-bold text-amber-900">
                      Créneau occupé sur le calendrier
                    </Text>
                    <Text className="mt-0.5 text-xs text-amber-800 leading-relaxed">
                      {conflictError.detail}
                    </Text>

                    {conflictError.colliding.length > 0 && (
                      <View className="mt-2 rounded-xl bg-amber-100/60 p-2">
                        {conflictError.colliding.map((c, i) => (
                          <Text key={i} className="text-xs font-semibold text-amber-900">
                            • {c.title} ({formatSlotTime(c.start_at)} - {formatSlotTime(c.end_at)})
                          </Text>
                        ))}
                      </View>
                    )}

                    {conflictError.suggested.length > 0 && (
                      <View className="mt-3">
                        <Text className="text-xs font-bold uppercase tracking-wider text-amber-900 mb-1.5">
                          Créneaux suggérés (sans conflit) :
                        </Text>
                        <View className="gap-2">
                          {conflictError.suggested.map((slot, idx) => (
                            <Pressable
                              key={idx}
                              onPress={() => applySuggestedSlot(slot)}
                              className="flex-row items-center justify-between rounded-xl bg-white border border-amber-300 px-3 py-2 active:bg-amber-100"
                            >
                              <View className="flex-row items-center">
                                <Ionicons name="time" size={14} color="#059669" />
                                <Text className="ml-2 text-xs font-semibold text-slate-800">
                                  {slot.label}
                                </Text>
                              </View>
                              <Text className="text-xs font-bold text-emerald-700">Choisir →</Text>
                            </Pressable>
                          ))}
                        </View>
                      </View>
                    )}
                  </View>
                </View>
              </View>
            ) : null}

            {/* Day Selector */}
            <Text className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-400">
              Jour
            </Text>
            <View className="mb-4 flex-row gap-2">
              <Pressable
                onPress={() => setTargetDate("today")}
                className={`flex-1 items-center justify-center rounded-xl py-2.5 border ${
                  targetDate === "today"
                    ? "border-emerald-600 bg-emerald-50"
                    : "border-slate-200 bg-white"
                }`}
              >
                <Text
                  className={`text-xs font-bold ${
                    targetDate === "today" ? "text-emerald-700" : "text-slate-700"
                  }`}
                >
                  Aujourd&apos;hui
                </Text>
              </Pressable>

              <Pressable
                onPress={() => setTargetDate("tomorrow")}
                className={`flex-1 items-center justify-center rounded-xl py-2.5 border ${
                  targetDate === "tomorrow"
                    ? "border-emerald-600 bg-emerald-50"
                    : "border-slate-200 bg-white"
                }`}
              >
                <Text
                  className={`text-xs font-bold ${
                    targetDate === "tomorrow" ? "text-emerald-700" : "text-slate-700"
                  }`}
                >
                  Demain
                </Text>
              </Pressable>

              <Pressable
                onPress={() => setTargetDate("dayAfter")}
                className={`flex-1 items-center justify-center rounded-xl py-2.5 border ${
                  targetDate === "dayAfter"
                    ? "border-emerald-600 bg-emerald-50"
                    : "border-slate-200 bg-white"
                }`}
              >
                <Text
                  className={`text-xs font-bold ${
                    targetDate === "dayAfter" ? "text-emerald-700" : "text-slate-700"
                  }`}
                >
                  Après-demain
                </Text>
              </Pressable>
            </View>

            {/* Meal Preset Buttons */}
            <Text className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-400">
              Moment du repas
            </Text>
            <View className="mb-4 flex-row gap-2">
              <Pressable
                onPress={() => {
                  setSelectedHour(12);
                  setSelectedMinute(30);
                }}
                className={`flex-1 items-center justify-center rounded-xl py-2 border ${
                  selectedHour === 12 && selectedMinute === 30
                    ? "border-emerald-600 bg-emerald-50"
                    : "border-slate-200 bg-white"
                }`}
              >
                <Text className="text-xs font-semibold text-slate-800">Déjeuner</Text>
                <Text className="text-[10px] text-slate-400">12:30</Text>
              </Pressable>

              <Pressable
                onPress={() => {
                  setSelectedHour(19);
                  setSelectedMinute(30);
                }}
                className={`flex-1 items-center justify-center rounded-xl py-2 border ${
                  selectedHour === 19 && selectedMinute === 30
                    ? "border-emerald-600 bg-emerald-50"
                    : "border-slate-200 bg-white"
                }`}
              >
                <Text className="text-xs font-semibold text-slate-800">Dîner</Text>
                <Text className="text-[10px] text-slate-400">19:30</Text>
              </Pressable>

              <Pressable
                onPress={() => {
                  setSelectedHour(20);
                  setSelectedMinute(0);
                }}
                className={`flex-1 items-center justify-center rounded-xl py-2 border ${
                  selectedHour === 20 && selectedMinute === 0
                    ? "border-emerald-600 bg-emerald-50"
                    : "border-slate-200 bg-white"
                }`}
              >
                <Text className="text-xs font-semibold text-slate-800">Tardif</Text>
                <Text className="text-[10px] text-slate-400">20:00</Text>
              </Pressable>
            </View>

            {/* Time Adjuster */}
            <View className="mb-4 flex-row items-center justify-between rounded-2xl bg-slate-50 p-3">
              <View>
                <Text className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Heure début
                </Text>
                <Text className="text-lg font-bold text-slate-900">
                  {String(selectedHour).padStart(2, "0")}:{String(selectedMinute).padStart(2, "0")}
                </Text>
              </View>

              <View className="flex-row items-center gap-2">
                <Pressable
                  onPress={() => {
                    if (selectedMinute === 0) {
                      setSelectedMinute(45);
                      setSelectedHour((h) => Math.max(0, h - 1));
                    } else {
                      setSelectedMinute((m) => m - 15);
                    }
                  }}
                  className="h-8 w-8 items-center justify-center rounded-full bg-white border border-slate-200 shadow-sm active:bg-slate-100"
                >
                  <Ionicons name="remove" size={16} color="#0f172a" />
                </Pressable>

                <Pressable
                  onPress={() => {
                    if (selectedMinute === 45) {
                      setSelectedMinute(0);
                      setSelectedHour((h) => Math.min(23, h + 1));
                    } else {
                      setSelectedMinute((m) => m + 15);
                    }
                  }}
                  className="h-8 w-8 items-center justify-center rounded-full bg-white border border-slate-200 shadow-sm active:bg-slate-100"
                >
                  <Ionicons name="add" size={16} color="#0f172a" />
                </Pressable>
              </View>
            </View>

            {/* Auto add missing ingredients toggle */}
            <View className="mb-6 flex-row items-center justify-between rounded-2xl bg-slate-50 p-3.5">
              <View className="flex-1 pr-3">
                <Text className="text-sm font-semibold text-slate-900">
                  Ajout auto aux courses
                </Text>
                <Text className="text-xs text-slate-500">
                  Ajoute automatiquement les ingrédients manquants à ta liste de courses
                </Text>
              </View>
              <Switch
                value={autoAddMissing}
                onValueChange={setAutoAddMissing}
                trackColor={{ false: "#cbd5e1", true: "#10b981" }}
              />
            </View>
          </ScrollView>

          {/* Action button */}
          <Pressable
            onPress={handleConfirmSchedule}
            disabled={submitting}
            className="flex-row items-center justify-center rounded-2xl bg-indigo-600 py-3.5 shadow-sm active:bg-indigo-700"
          >
            {submitting ? (
              <ActivityIndicator color="#ffffff" />
            ) : (
              <>
                <Ionicons name="calendar-outline" size={18} color="#ffffff" />
                <Text className="ml-2 text-base font-bold text-white">
                  Confirmer la planification
                </Text>
              </>
            )}
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}
