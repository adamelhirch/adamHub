import { Ionicons } from "@expo/vector-icons";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  View,
} from "react-native";

import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import {
  FitnessOverviewRead,
  getFitnessOverview,
} from "@/lib/api";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return new Intl.DateTimeFormat("fr-FR", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

export default function FitnessScreen() {
  const [overview, setOverview] = useState<FitnessOverviewRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const data = await getFitnessOverview();
      setOverview(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur de chargement fitness");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [loadData]),
  );

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadData();
  }, [loadData]);

  const stats = overview?.stats;
  const upcoming = overview?.upcoming_sessions ?? [];
  const recent = overview?.recent_sessions ?? [];

  return (
    <Screen>
      <ScrollView
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        <ScreenHeader
          title="Sport & Forme"
          subtitle="Suivi de tes entraînements et métriques"
          showProfileButton={true}
        />

        {error ? (
          <View className="mb-4 rounded-xl bg-red-50 p-3">
            <Text className="text-sm text-red-600">{error}</Text>
          </View>
        ) : null}

        {/* AI Workout Assistant CTA */}
        <Pressable
          onPress={() => router.push("/assistant")}
          className="mb-6 rounded-2xl bg-gradient-to-r bg-emerald-700 p-4 shadow-sm active:opacity-95 flex-row items-center justify-between"
        >
          <View className="flex-1 mr-2">
            <View className="flex-row items-center mb-1">
              <Ionicons name="flash" size={16} color="#fbbf24" />
              <Text className="ml-1 text-xs font-bold text-amber-300 uppercase tracking-wide">
                Coach Sport IA
              </Text>
            </View>
            <Text className="text-base font-bold text-white">Générer une séance sur-mesure</Text>
            <Text className="text-xs text-emerald-100 mt-0.5">
              Demande un entraînement push/pull/legs selon tes objectifs
            </Text>
          </View>
          <View className="h-10 w-10 items-center justify-center rounded-xl bg-white/20">
            <Ionicons name="sparkles" size={20} color="#ffffff" />
          </View>
        </Pressable>

        {loading ? (
          <View className="py-12 items-center">
            <ActivityIndicator color="#10b981" />
          </View>
        ) : (
          <>
            {/* Stat Cards */}
            <View className="mb-6 flex-row gap-3">
              <View className="flex-1 rounded-2xl border border-slate-100 bg-white p-3.5 shadow-sm items-center">
                <Text className="text-2xl font-black text-slate-900">
                  {stats?.planned_sessions ?? 0}
                </Text>
                <Text className="mt-1 text-[11px] font-medium text-slate-500 text-center">
                  Prévues
                </Text>
              </View>

              <View className="flex-1 rounded-2xl border border-slate-100 bg-white p-3.5 shadow-sm items-center">
                <Text className="text-2xl font-black text-emerald-600">
                  {stats?.completed_sessions_30d ?? 0}
                </Text>
                <Text className="mt-1 text-[11px] font-medium text-slate-500 text-center">
                  Faites (30j)
                </Text>
              </View>

              <View className="flex-1 rounded-2xl border border-slate-100 bg-white p-3.5 shadow-sm items-center">
                <Text className="text-2xl font-black text-blue-600">
                  {stats?.completion_rate_30d ? `${Math.round(stats.completion_rate_30d * 100)}%` : "0%"}
                </Text>
                <Text className="mt-1 text-[11px] font-medium text-slate-500 text-center">
                  Assiduité
                </Text>
              </View>
            </View>

            {/* SECTION: Prochaines Séances */}
            <View className="mb-6">
              <View className="mb-3 flex-row items-center justify-between">
                <View className="flex-row items-center">
                  <Ionicons name="barbell-outline" size={20} color="#0f172a" />
                  <Text className="ml-2 text-lg font-bold text-slate-900">
                    Prochaines séances
                  </Text>
                </View>
                <Text className="text-xs font-medium text-slate-500">
                  {upcoming.length} planifiée{upcoming.length > 1 ? "s" : ""}
                </Text>
              </View>

              {upcoming.length === 0 ? (
                <View className="rounded-2xl border border-slate-100 bg-white p-6 items-center justify-center shadow-sm">
                  <Ionicons name="barbell-outline" size={36} color="#94a3b8" />
                  <Text className="mt-2 text-sm font-semibold text-slate-700">
                    Aucune séance à venir
                  </Text>
                  <Text className="mt-1 text-center text-xs text-slate-400">
                    {"Dis à l'assistant IA de te planifier une séance dans ton calendrier."}
                  </Text>
                </View>
              ) : (
                <View className="gap-3">
                  {upcoming.map((sess) => (
                    <View
                      key={sess.id}
                      className="rounded-2xl border border-slate-100 bg-white p-4 shadow-sm"
                    >
                      <View className="flex-row items-center justify-between">
                        <Text className="text-base font-bold text-slate-900">{sess.title}</Text>
                        <View className="rounded-full bg-emerald-100 px-2.5 py-0.5">
                          <Text className="text-[10px] font-bold text-emerald-800 uppercase">
                            {sess.session_type}
                          </Text>
                        </View>
                      </View>

                      <View className="mt-2 flex-row items-center gap-4">
                        <View className="flex-row items-center">
                          <Ionicons name="time-outline" size={14} color="#64748b" />
                          <Text className="ml-1 text-xs text-slate-500">
                            {formatDate(sess.planned_at)}
                          </Text>
                        </View>
                        <View className="flex-row items-center">
                          <Ionicons name="hourglass-outline" size={14} color="#64748b" />
                          <Text className="ml-1 text-xs text-slate-500">
                            {sess.duration_minutes} min
                          </Text>
                        </View>
                      </View>

                      {sess.exercises && sess.exercises.length > 0 && (
                        <View className="mt-3 border-t border-slate-100 pt-2">
                          <Text className="text-xs font-semibold text-slate-700 mb-1">
                            Exercices ({sess.exercises.length}) :
                          </Text>
                          <Text className="text-xs text-slate-500" numberOfLines={2}>
                            {sess.exercises.map((e) => e.name).join(" • ")}
                          </Text>
                        </View>
                      )}
                    </View>
                  ))}
                </View>
              )}
            </View>

            {/* SECTION: Historique Récent */}
            <View className="mb-8">
              <View className="mb-3 flex-row items-center justify-between">
                <View className="flex-row items-center">
                  <Ionicons name="checkmark-circle-outline" size={20} color="#0f172a" />
                  <Text className="ml-2 text-lg font-bold text-slate-900">
                    Historique récent
                  </Text>
                </View>
              </View>

              {recent.length === 0 ? (
                <View className="rounded-2xl border border-slate-100 bg-white p-5 items-center justify-center shadow-sm">
                  <Text className="text-xs text-slate-400">
                    Pas encore de séances terminées enregistrées.
                  </Text>
                </View>
              ) : (
                <View className="rounded-2xl border border-slate-100 bg-white p-2 shadow-sm">
                  {recent.map((sess, index) => {
                    const isLast = index === recent.length - 1;
                    return (
                      <View
                        key={sess.id}
                        className={`flex-row items-center justify-between p-3 ${
                          !isLast ? "border-b border-slate-50" : ""
                        }`}
                      >
                        <View className="flex-1 mr-2">
                          <Text className="text-sm font-semibold text-slate-900">
                            {sess.title}
                          </Text>
                          <Text className="text-xs text-slate-400">
                            {formatDate(sess.planned_at)} • {sess.duration_minutes} min
                          </Text>
                        </View>
                        <Ionicons name="checkmark-done" size={18} color="#10b981" />
                      </View>
                    );
                  })}
                </View>
              )}
            </View>
          </>
        )}
      </ScrollView>
    </Screen>
  );
}
