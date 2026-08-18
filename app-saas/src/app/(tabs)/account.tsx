import { Ionicons } from "@expo/vector-icons";
import * as Clipboard from "expo-clipboard";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, Alert, Pressable, Text, View } from "react-native";

import { Field } from "@/components/field";
import { PrimaryButton } from "@/components/primary-button";
import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import {
  API_URL,
  generateApiKey,
  getApiKey,
  getNtfyTopic,
  logout,
  revokeApiKey,
  setNtfyTopic,
  type AuthUser,
} from "@/lib/api";
import { me } from "@/lib/auth";

// API_URL is ".../api/v1"; the MCP endpoint is mounted on the bare API root.
const MCP_URL = `${API_URL.replace(/\/api\/v1$/, "")}/mcp`;

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

  const [apiKey, setApiKey] = useState<string | null>(null);
  const [keyLoading, setKeyLoading] = useState(true);
  const [keyActionLoading, setKeyActionLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const [ntfyTopic, setNtfyTopicValue] = useState("");
  const [ntfyLoading, setNtfyLoading] = useState(true);
  const [ntfySaving, setNtfySaving] = useState(false);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;

      async function load() {
        setLoading(true);
        setKeyLoading(true);
        setNtfyLoading(true);
        setError(null);
        try {
          const [userData, keyData, ntfyData] = await Promise.all([
            me(),
            getApiKey(),
            getNtfyTopic(),
          ]);
          if (!cancelled) {
            setUser(userData);
            setApiKey(keyData.api_key);
            setNtfyTopicValue(ntfyData.ntfy_topic ?? "");
          }
        } catch (err) {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "Une erreur est survenue");
          }
        } finally {
          if (!cancelled) {
            setLoading(false);
            setKeyLoading(false);
            setNtfyLoading(false);
          }
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

  async function handleCopyKey(key: string) {
    await Clipboard.setStringAsync(key);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }

  async function handleGenerateKey() {
    if (keyActionLoading) return;
    setKeyActionLoading(true);
    setError(null);
    try {
      const data = await generateApiKey();
      setApiKey(data.api_key);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue");
    } finally {
      setKeyActionLoading(false);
    }
  }

  function handleRegenerateKey() {
    Alert.alert(
      "Régénérer la clé ?",
      "L'ancienne clé cessera immédiatement de fonctionner — mets à jour tes clients MCP (Claude, ChatGPT, opencode, …) avec la nouvelle.",
      [
        { text: "Annuler", style: "cancel" },
        { text: "Régénérer", onPress: () => void handleGenerateKey() },
      ],
    );
  }

  function handleRevokeKey() {
    Alert.alert(
      "Révoquer la clé ?",
      "Tes clients MCP connectés avec cette clé cesseront de fonctionner immédiatement.",
      [
        { text: "Annuler", style: "cancel" },
        {
          text: "Révoquer",
          style: "destructive",
          onPress: () => {
            setKeyActionLoading(true);
            setError(null);
            revokeApiKey()
              .then(() => setApiKey(null))
              .catch((err) => {
                setError(err instanceof Error ? err.message : "Une erreur est survenue");
              })
              .finally(() => setKeyActionLoading(false));
          },
        },
      ],
    );
  }

  async function handleSaveNtfyTopic() {
    if (ntfySaving) return;
    setNtfySaving(true);
    setError(null);
    const next = ntfyTopic.trim();
    try {
      const data = await setNtfyTopic(next.length > 0 ? next : null);
      setNtfyTopicValue(data.ntfy_topic ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue");
    } finally {
      setNtfySaving(false);
    }
  }

  function confirmSaveNtfyTopic() {
    const hasValue = ntfyTopic.trim().length > 0;
    Alert.alert(
      hasValue ? "Enregistrer le topic ?" : "Effacer le topic ?",
      hasValue
        ? "Tes rappels calendrier seront envoyés sur ce topic ntfy à la place du topic global."
        : "Tes rappels calendrier repartiront sur le topic global configuré sur le serveur.",
      [
        { text: "Annuler", style: "cancel" },
        { text: "Enregistrer", onPress: () => void handleSaveNtfyTopic() },
      ],
    );
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

          <View className="mb-6 rounded-2xl border border-slate-100 bg-white p-4">
            <View className="mb-3 flex-row items-center justify-between">
              <Text className="text-sm font-semibold text-slate-900">Clé API / MCP</Text>
              {!keyLoading && !keyActionLoading ? (
                <Pressable onPress={apiKey ? handleRegenerateKey : () => void handleGenerateKey()}>
                  <Text className="text-sm font-medium text-emerald-600">
                    {apiKey ? "Régénérer" : "Générer"}
                  </Text>
                </Pressable>
              ) : null}
            </View>

            {keyLoading || keyActionLoading ? (
              <View className="items-center py-4">
                <ActivityIndicator color="#10b981" />
              </View>
            ) : apiKey ? (
              <>
                <Pressable
                  onPress={() => void handleCopyKey(apiKey)}
                  className="flex-row items-center justify-between rounded-xl bg-slate-50 px-3 py-2.5 active:bg-slate-100"
                >
                  <Text className="mr-2 flex-1 font-mono text-xs text-slate-700" numberOfLines={1}>
                    {apiKey}
                  </Text>
                  <Ionicons
                    name={copied ? "checkmark" : "copy-outline"}
                    size={18}
                    color={copied ? "#059669" : "#64748b"}
                  />
                </Pressable>
                <Text className="mt-3 text-xs text-slate-500">
                  Colle cette clé dans la config de ton client MCP (Claude, ChatGPT, opencode, …) — endpoint :
                </Text>
                <Text className="mt-1 font-mono text-xs text-slate-700" selectable>
                  {MCP_URL}
                </Text>
                <Pressable onPress={handleRevokeKey} className="mt-3 self-start">
                  <Text className="text-xs font-medium text-red-600">Révoquer</Text>
                </Pressable>
              </>
            ) : (
              <Text className="text-sm text-slate-500">
                Génère une clé pour connecter un assistant IA (via MCP) à tes courses, recettes, garde-manger et
                plannings repas.
              </Text>
            )}
          </View>

          <View className="mb-6 rounded-2xl border border-slate-100 bg-white p-4">
            <View className="mb-3 flex-row items-center justify-between">
              <Text className="text-sm font-semibold text-slate-900">Notifications push (ntfy)</Text>
            </View>

            {ntfyLoading ? (
              <View className="items-center py-4">
                <ActivityIndicator color="#10b981" />
              </View>
            ) : (
              <>
                <Field
                  label="Topic ntfy"
                  value={ntfyTopic}
                  onChangeText={setNtfyTopicValue}
                  placeholder="ex. : mon-topic-personnel"
                  autoCapitalize="none"
                  autoCorrect={false}
                />
                <Text className="mb-3 text-xs text-slate-500">
                  Tes rappels calendrier seront envoyés sur ce topic ntfy. Laisse vide pour revenir au topic
                  global configuré sur le serveur.
                </Text>
                <PrimaryButton
                  label="Enregistrer"
                  onPress={confirmSaveNtfyTopic}
                  loading={ntfySaving}
                />
              </>
            )}
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
