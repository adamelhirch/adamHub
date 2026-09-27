import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect } from "expo-router";
import { useCallback, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  Text,
  View,
} from "react-native";
import { WebView, WebViewMessageEvent } from "react-native-webview";

import { Alert } from "@/lib/alert";
import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import {
  deleteSupermarketConnection,
  importSupermarketConnection,
  listSupermarketConnections,
  SupermarketConnectionRead,
  SupermarketStore,
} from "@/lib/supermarket-api";

interface StoreMeta {
  key: SupermarketStore;
  name: string;
  url: string;
  color: string;
  domain: string;
}

const STORES: StoreMeta[] = [
  {
    key: "leclerc",
    name: "E.Leclerc Drive",
    url: "https://www.leclercdrive.fr",
    color: "#0066b2",
    domain: "leclercdrive.fr",
  },
  {
    key: "carrefour",
    name: "Carrefour Drive",
    url: "https://www.carrefour.fr/mon-compte",
    color: "#004e9a",
    domain: "carrefour.fr",
  },
  {
    key: "intermarche",
    name: "Intermarché",
    url: "https://www.intermarche.com/connexion",
    color: "#e2001a",
    domain: "intermarche.com",
  },
  {
    key: "auchan",
    name: "Auchan Drive",
    url: "https://www.auchan.fr/identification",
    color: "#e2001a",
    domain: "auchan.fr",
  },
];

const COOKIE_INJECT_JS = `
(function() {
  function sendCookies() {
    try {
      window.ReactNativeWebView.postMessage(JSON.stringify({
        type: 'COOKIES_EXTRACTED',
        cookieString: document.cookie,
        url: window.location.href,
        title: document.title
      }));
    } catch(e) {}
  }
  sendCookies();
  // Also hook into pushState/replaceState
  var oldPush = history.pushState;
  history.pushState = function() {
    oldPush.apply(this, arguments);
    setTimeout(sendCookies, 1000);
  };
})();
true;
`;

export default function SupermarketConnectScreen() {
  const [selectedStore, setSelectedStore] = useState<StoreMeta>(STORES[0]);
  const [connections, setConnections] = useState<SupermarketConnectionRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [showWeb, setShowWeb] = useState(false);
  const webViewRef = useRef<WebView>(null);

  const activeConnection = connections.find(
    (c) => c.store === selectedStore.key && c.is_active,
  );

  const fetchConnections = useCallback(async () => {
    try {
      const data = await listSupermarketConnections();
      setConnections(data);
    } catch (err) {
      console.warn("Could not load supermarket connections", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      fetchConnections();
    }, [fetchConnections]),
  );

  function handleMessage(event: WebViewMessageEvent) {
    try {
      const data = JSON.parse(event.nativeEvent.data);
      if (data.type === "COOKIES_EXTRACTED" && data.cookieString) {
        processCookieString(data.cookieString, data.url);
      }
    } catch {
      // not JSON or not our event
    }
  }

  async function processCookieString(rawCookies: string, currentUrl?: string) {
    if (!rawCookies || rawCookies.trim().length === 0) return;

    const cookieList = rawCookies.split(";").map((pair) => {
      const idx = pair.indexOf("=");
      const name = idx > -1 ? pair.substring(0, idx).trim() : pair.trim();
      const value = idx > -1 ? pair.substring(idx + 1).trim() : "";
      return {
        name,
        value,
        domain: selectedStore.domain,
        path: "/",
      };
    }).filter((c) => c.name.length > 0);

    if (cookieList.length === 0) return;

    // Check for customer UUID if Intermarché
    let customerUuid: string | undefined;
    if (selectedStore.key === "intermarche" && currentUrl) {
      const match = currentUrl.match(/userId=([a-zA-Z0-9_-]+)/);
      if (match) customerUuid = match[1];
    }

    try {
      setSyncing(true);
      await importSupermarketConnection({
        store: selectedStore.key,
        label: `${selectedStore.name} (Mobile App)`,
        cookies: cookieList,
        activate: true,
        customer_uuid: customerUuid,
      });
      await fetchConnections();
      Alert.alert(
        "Connexion réussie",
        `Votre session ${selectedStore.name} (${cookieList.length} cookies) a été synchronisée avec succès !`,
      );
      setShowWeb(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erreur de synchronisation";
      Alert.alert("Erreur", msg);
    } finally {
      setSyncing(false);
    }
  }

  function handleTriggerCapture() {
    if (webViewRef.current) {
      webViewRef.current.injectJavaScript(`
        window.ReactNativeWebView.postMessage(JSON.stringify({
          type: 'COOKIES_EXTRACTED',
          cookieString: document.cookie,
          url: window.location.href
        }));
        true;
      `);
    }
  }

  async function handleDeleteConnection(connId: number) {
    Alert.alert(
      "Déconnexion",
      `Êtes-vous sûr de vouloir supprimer la connexion à ${selectedStore.name} ?`,
      [
        { text: "Annuler", style: "cancel" },
        {
          text: "Déconnecter",
          style: "destructive",
          onPress: async () => {
            try {
              await deleteSupermarketConnection(connId);
              await fetchConnections();
            } catch (err) {
              const msg = err instanceof Error ? err.message : "Erreur de déconnexion";
              Alert.alert("Erreur", msg);
            }
          },
        },
      ],
    );
  }

  return (
    <Screen>
      <ScreenHeader
        title="Connexion Enseignes"
        subtitle="Connectez vos comptes Drive pour synchroniser vos paniers"
        backButton={true}
      />

      {/* Store Selector Tabs */}
      <View className="flex-row px-4 py-2 border-b border-slate-800 bg-slate-900/60">
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
          {STORES.map((s) => {
            const isSelected = s.key === selectedStore.key;
            const isConnected = connections.some((c) => c.store === s.key && c.is_active);
            return (
              <Pressable
                key={s.key}
                onPress={() => {
                  setSelectedStore(s);
                  setShowWeb(false);
                }}
                className={`px-3 py-2 rounded-xl border flex-row items-center gap-1.5 ${
                  isSelected
                    ? "bg-emerald-500/20 border-emerald-500"
                    : "bg-slate-800/80 border-slate-700"
                }`}
              >
                <View
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: isConnected ? "#10b981" : "#64748b" }}
                />
                <Text
                  className={`text-xs font-semibold ${
                    isSelected ? "text-emerald-400" : "text-slate-300"
                  }`}
                >
                  {s.name}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>
      </View>

      {/* Main Content */}
      <View className="flex-1">
        {loading ? (
          <View className="flex-1 items-center justify-center">
            <ActivityIndicator size="large" color="#10b981" />
          </View>
        ) : showWeb ? (
          <View className="flex-1 bg-white">
            {/* WebView Controls Bar */}
            <View className="flex-row items-center justify-between px-4 py-2.5 bg-slate-900 border-b border-slate-800">
              <Pressable
                onPress={() => setShowWeb(false)}
                className="flex-row items-center gap-1 py-1"
              >
                <Ionicons name="close" size={20} color="#94a3b8" />
                <Text className="text-xs text-slate-300">Fermer</Text>
              </Pressable>

              <Pressable
                onPress={handleTriggerCapture}
                disabled={syncing}
                className="flex-row items-center gap-1.5 bg-emerald-600 px-3 py-1.5 rounded-lg active:opacity-80"
              >
                {syncing ? (
                  <ActivityIndicator size="small" color="#ffffff" />
                ) : (
                  <>
                    <Ionicons name="checkmark-done" size={16} color="#ffffff" />
                    <Text className="text-xs font-bold text-white">Capturer & Enregistrer</Text>
                  </>
                )}
              </Pressable>
            </View>

            <WebView
              ref={webViewRef}
              source={{ uri: selectedStore.url }}
              injectedJavaScript={COOKIE_INJECT_JS}
              onMessage={handleMessage}
              sharedCookiesEnabled={true}
              thirdPartyCookiesEnabled={true}
              domStorageEnabled={true}
              javaScriptEnabled={true}
              className="flex-1"
            />
          </View>
        ) : (
          <ScrollView className="flex-1 p-4" contentContainerStyle={{ gap: 16 }}>
            {/* Status Card */}
            <View className="bg-slate-900 border border-slate-800 rounded-2xl p-4 gap-3">
              <View className="flex-row items-center justify-between">
                <View className="flex-row items-center gap-2.5">
                  <View
                    className="w-10 h-10 rounded-xl items-center justify-center"
                    style={{ backgroundColor: `${selectedStore.color}25` }}
                  >
                    <Ionicons name="cart" size={20} color={selectedStore.color} />
                  </View>
                  <View>
                    <Text className="text-base font-bold text-slate-100">{selectedStore.name}</Text>
                    <Text className="text-xs text-slate-400">
                      {activeConnection
                        ? `Connecté • ${activeConnection.cookies_count} cookies`
                        : "Non connecté"}
                    </Text>
                  </View>
                </View>

                <View
                  className={`px-2.5 py-1 rounded-full ${
                    activeConnection ? "bg-emerald-500/20" : "bg-slate-800"
                  }`}
                >
                  <Text
                    className={`text-xs font-medium ${
                      activeConnection ? "text-emerald-400" : "text-slate-400"
                    }`}
                  >
                    {activeConnection ? "Actif" : "Inactif"}
                  </Text>
                </View>
              </View>

              {activeConnection && (
                <View className="bg-slate-950/60 rounded-xl p-3 gap-1">
                  <Text className="text-xs text-slate-400">
                    Dernière synchronisation :{" "}
                    <Text className="text-slate-200">
                      {new Date(activeConnection.updated_at).toLocaleString("fr-FR")}
                    </Text>
                  </Text>
                  {activeConnection.last_used_at && (
                    <Text className="text-xs text-slate-400">
                      Dernière utilisation du panier :{" "}
                      <Text className="text-slate-200">
                        {new Date(activeConnection.last_used_at).toLocaleString("fr-FR")}
                      </Text>
                    </Text>
                  )}
                </View>
              )}

              {/* Action Buttons */}
              <View className="flex-row gap-2 pt-1">
                <Pressable
                  onPress={() => setShowWeb(true)}
                  className="flex-1 bg-emerald-600 active:bg-emerald-700 py-3 rounded-xl flex-row items-center justify-center gap-2"
                >
                  <Ionicons name="globe-outline" size={18} color="#ffffff" />
                  <Text className="text-sm font-semibold text-white">
                    {activeConnection ? "Mettre à jour la session" : "Se connecter via le Web"}
                  </Text>
                </Pressable>

                {activeConnection && (
                  <Pressable
                    onPress={() => handleDeleteConnection(activeConnection.id)}
                    className="bg-rose-500/20 border border-rose-500/30 px-3.5 py-3 rounded-xl items-center justify-center"
                    accessibilityLabel="Déconnecter"
                  >
                    <Ionicons name="trash-outline" size={18} color="#f43f5e" />
                  </Pressable>
                )}
              </View>
            </View>

            {/* How it works info card */}
            <View className="bg-slate-900/50 border border-slate-800/80 rounded-2xl p-4 gap-2.5">
              <View className="flex-row items-center gap-2">
                <Ionicons name="information-circle-outline" size={18} color="#38bdf8" />
                <Text className="text-sm font-semibold text-sky-400">Comment ça marche ?</Text>
              </View>
              <Text className="text-xs text-slate-400 leading-relaxed">
                1. Cliquez sur <Text className="font-semibold text-slate-200">&quot;Se connecter via le Web&quot;</Text> pour ouvrir le portail officiel de votre supermarché.
              </Text>
              <Text className="text-xs text-slate-400 leading-relaxed">
                2. Connectez-vous avec vos identifiants habituels et acceptez les cookies.
              </Text>
              <Text className="text-xs text-slate-400 leading-relaxed">
                3. Cliquez sur <Text className="font-semibold text-slate-200">&quot;Capturer &amp; Enregistrer&quot;</Text> pour synchroniser vos cookies chiffrés de session.
              </Text>
              <Text className="text-xs text-slate-400 leading-relaxed">
                4. AdamHUB pourra alors transférer vos articles de courses directement dans votre panier Drive !
              </Text>
            </View>
          </ScrollView>
        )}
      </View>
    </Screen>
  );
}
