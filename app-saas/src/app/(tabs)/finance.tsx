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
  FinanceMonthSummary,
  FinanceTransactionRead,
  getFinanceSummary,
  listFinanceTransactions,
  listSubscriptions,
  SubscriptionRead,
} from "@/lib/api";

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 2,
  }).format(amount);
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return new Intl.DateTimeFormat("fr-FR", {
    day: "numeric",
    month: "short",
  }).format(d);
}

export default function FinanceScreen() {
  const [summary, setSummary] = useState<FinanceMonthSummary | null>(null);
  const [transactions, setTransactions] = useState<FinanceTransactionRead[]>([]);
  const [subscriptions, setSubscriptions] = useState<SubscriptionRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const [sumData, txData, subData] = await Promise.all([
        getFinanceSummary(year, month).catch(() => null),
        listFinanceTransactions(20).catch(() => []),
        listSubscriptions().catch(() => []),
      ]);
      setSummary(sumData);
      setTransactions(txData);
      setSubscriptions(subData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur chargement finances");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [year, month]);

  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [loadData]),
  );

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadData();
  }, [loadData]);

  const totalMonthlySubs = subscriptions
    .filter((s) => s.active)
    .reduce((acc, curr) => acc + (curr.frequency === "yearly" ? curr.amount / 12 : curr.amount), 0);

  return (
    <Screen>
      <ScrollView
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        <ScreenHeader
          title="Finances"
          subtitle="Budget du mois et abonnements"
          showProfileButton={true}
        />

        {error ? (
          <View className="mb-4 rounded-xl bg-red-50 p-3">
            <Text className="text-sm text-red-600">{error}</Text>
          </View>
        ) : null}

        {loading ? (
          <View className="py-12 items-center">
            <ActivityIndicator color="#10b981" />
          </View>
        ) : (
          <>
            {/* Monthly Budget Card */}
            <View className="mb-6 rounded-3xl bg-slate-900 p-5 shadow-lg">
              <Text className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Solde Net du mois
              </Text>
              <Text className="mt-1 text-3xl font-extrabold text-white">
                {formatCurrency(summary?.net ?? 0)}
              </Text>

              <View className="mt-5 flex-row items-center justify-between border-t border-slate-800 pt-4">
                <View className="flex-1">
                  <View className="flex-row items-center">
                    <Ionicons name="arrow-down-circle" size={16} color="#10b981" />
                    <Text className="ml-1 text-xs text-slate-400">Revenus</Text>
                  </View>
                  <Text className="mt-0.5 text-base font-bold text-emerald-400">
                    {formatCurrency(summary?.income ?? 0)}
                  </Text>
                </View>

                <View className="h-8 w-[1px] bg-slate-800" />

                <View className="flex-1 items-end">
                  <View className="flex-row items-center">
                    <Ionicons name="arrow-up-circle" size={16} color="#f87171" />
                    <Text className="ml-1 text-xs text-slate-400">Dépenses</Text>
                  </View>
                  <Text className="mt-0.5 text-base font-bold text-red-400">
                    {formatCurrency(summary?.expense ?? 0)}
                  </Text>
                </View>
              </View>
            </View>

            {/* AI Finance Assistant CTA */}
            <Pressable
              onPress={() => router.push("/assistant")}
              className="mb-6 rounded-2xl border border-emerald-100 bg-emerald-50/60 p-4 shadow-sm active:bg-emerald-100/60 flex-row items-center justify-between"
            >
              <View className="flex-1 mr-2">
                <View className="flex-row items-center mb-1">
                  <Ionicons name="sparkles" size={16} color="#059669" />
                  <Text className="ml-1 text-xs font-bold text-emerald-800 uppercase tracking-wide">
                    Analyse Budget IA
                  </Text>
                </View>
                <Text className="text-sm font-semibold text-slate-900">
                  Optimiser mes dépenses du mois
                </Text>
                <Text className="text-xs text-slate-500 mt-0.5">
                  Vérifier les récurrences et identifier des économies potentielles
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color="#059669" />
            </Pressable>

            {/* SECTION: Abonnements */}
            <View className="mb-6">
              <View className="mb-3 flex-row items-center justify-between">
                <View className="flex-row items-center">
                  <Ionicons name="repeat-outline" size={20} color="#0f172a" />
                  <Text className="ml-2 text-lg font-bold text-slate-900">Abonnements</Text>
                </View>
                <Text className="text-xs font-medium text-slate-500">
                  {formatCurrency(totalMonthlySubs)} / mois
                </Text>
              </View>

              {subscriptions.length === 0 ? (
                <View className="rounded-2xl border border-slate-100 bg-white p-5 items-center justify-center shadow-sm">
                  <Ionicons name="card-outline" size={32} color="#94a3b8" />
                  <Text className="mt-2 text-sm font-semibold text-slate-700">
                    Aucun abonnement actif
                  </Text>
                  <Text className="mt-1 text-center text-xs text-slate-400">
                    Ajoute tes abonnements (Netflix, Spotify, etc.) pour suivre les échéances.
                  </Text>
                </View>
              ) : (
                <View className="rounded-2xl border border-slate-100 bg-white p-2 shadow-sm">
                  {subscriptions.map((sub, index) => {
                    const isLast = index === subscriptions.length - 1;
                    return (
                      <View
                        key={sub.id}
                        className={`flex-row items-center justify-between p-3 ${
                          !isLast ? "border-b border-slate-50" : ""
                        }`}
                      >
                        <View className="flex-1 mr-2">
                          <Text className="text-sm font-semibold text-slate-900">{sub.name}</Text>
                          <Text className="text-xs text-slate-400">
                            Prochain prélèvement : {formatDate(sub.next_due_date)} • {sub.category}
                          </Text>
                        </View>
                        <Text className="text-sm font-bold text-slate-900">
                          {formatCurrency(sub.amount)}
                        </Text>
                      </View>
                    );
                  })}
                </View>
              )}
            </View>

            {/* SECTION: Dernières Transactions */}
            <View className="mb-8">
              <View className="mb-3 flex-row items-center justify-between">
                <View className="flex-row items-center">
                  <Ionicons name="receipt-outline" size={20} color="#0f172a" />
                  <Text className="ml-2 text-lg font-bold text-slate-900">
                    Dernières transactions
                  </Text>
                </View>
              </View>

              {transactions.length === 0 ? (
                <View className="rounded-2xl border border-slate-100 bg-white p-5 items-center justify-center shadow-sm">
                  <Text className="text-xs text-slate-400">
                    Aucune transaction récente enregistrée.
                  </Text>
                </View>
              ) : (
                <View className="rounded-2xl border border-slate-100 bg-white p-2 shadow-sm">
                  {transactions.map((tx, index) => {
                    const isLast = index === transactions.length - 1;
                    const isIncome = tx.kind === "income";
                    return (
                      <View
                        key={tx.id}
                        className={`flex-row items-center justify-between p-3 ${
                          !isLast ? "border-b border-slate-50" : ""
                        }`}
                      >
                        <View className="flex-1 mr-2">
                          <Text className="text-sm font-semibold text-slate-900">{tx.label}</Text>
                          <Text className="text-xs text-slate-400">
                            {formatDate(tx.occurred_at)} • {tx.category}
                          </Text>
                        </View>
                        <Text
                          className={`text-sm font-bold ${
                            isIncome ? "text-emerald-600" : "text-slate-900"
                          }`}
                        >
                          {isIncome ? "+" : "-"}
                          {formatCurrency(tx.amount)}
                        </Text>
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
