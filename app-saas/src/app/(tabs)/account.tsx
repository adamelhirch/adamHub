import { Ionicons } from "@expo/vector-icons";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { logout, type AuthUser } from "@/lib/api";
import { me } from "@/lib/auth";

function formatCreatedAt(iso: string): string {
  return new Intl.DateTimeFormat("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(iso));
}

export default function AccountScreen() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;

      async function load() {
        setLoading(true);
        setError(null);
        try {
          const data = await me();
          if (!cancelled) setUser(data);
        } catch (err) {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "Une erreur est survenue");
          }
        } finally {
          if (!cancelled) setLoading(false);
        }
      }

      load();
      return () => {
        cancelled = true;
      };
    }, []),
  );

  async function handleLogout() {
    if (loggingOut) return;
    setLoggingOut(true);
    setError(null);
    try {
      await logout();
      router.replace("/(auth)/login");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue");
      setLoggingOut(false);
    }
  }

  return (
    <Screen>
      <View className="mb-6 flex-row items-center justify-between">
        <ScreenHeader title="Compte" subtitle="Vos informations personnelles" />
      </View>

      {error ? (
        <View className="mb-4 rounded-xl bg-red-50 px-4 py-3">
          <Text className="text-sm text-red-600">{error}</Text>
        </View>
      ) : null}

      {loading ? (
        <View className="py-12 items-center">
          <ActivityIndicator color="#10b981" />
        </View>
      ) : user ? (
        <>
          <View className="mb-4 items-center rounded-2xl border border-slate-100 bg-white p-6">
            <View className="mb-3 h-16 w-16 items-center justify-center rounded-full bg-emerald-100">
              <Ionicons name="person" size={32} color="#059669" />
            </View>
            <Text className="text-xl font-bold text-slate-900">{user.display_name}</Text>
            <Text className="mt-1 text-base text-slate-500">{user.email}</Text>
          </View>

          <View className="mb-6 rounded-2xl border border-slate-100 bg-white p-4">
            <View className="flex-row items-center justify-between py-2">
              <Text className="text-sm text-slate-500">Membre depuis</Text>
              <Text className="text-sm font-medium text-slate-900">
                {formatCreatedAt(user.created_at)}
              </Text>
            </View>
            <View className="flex-row items-center justify-between border-t border-slate-100 py-2">
              <Text className="text-sm text-slate-500">Statut</Text>
              <Text className="text-sm font-medium text-emerald-600">
                {user.is_active ? "Actif" : "Inactif"}
              </Text>
            </View>
          </View>

          <Pressable
            onPress={handleLogout}
            disabled={loggingOut}
            className="w-full items-center justify-center rounded-xl border border-red-200 bg-red-50 py-3.5 active:bg-red-100"
          >
            {loggingOut ? (
              <ActivityIndicator color="#ef4444" />
            ) : (
              <View className="flex-row items-center">
                <Ionicons name="log-out-outline" size={20} color="#ef4444" />
                <Text className="ml-2 text-base font-semibold text-red-600">
                  Se déconnecter
                </Text>
              </View>
            )}
          </Pressable>
        </>
      ) : null}
    </Screen>
  );
}
