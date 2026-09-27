import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Alert,
  RefreshControl,
} from "react-native";
import { useRouter, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  getUserProfile,
  updateUserProfile,
  listUserMemories,
  deleteUserMemory,
  UserMemory,
} from "@/lib/assistant-api";
import { MemoryTag } from "@/components/assistant/memory-tag";

const TONE_OPTIONS = [
  { id: "direct", label: "Direct & Précis" },
  { id: "motivant", label: "Motivant" },
  { id: "concise", label: "Concis / Puces" },
  { id: "chaleureux", label: "Chaleureux" },
];

export default function SettingsMemoriesScreen() {
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // Profile Form State
  const [fitnessGoals, setFitnessGoals] = useState("");
  const [dietaryPrefs, setDietaryPrefs] = useState("");
  const [lifestyleNotes, setLifestyleNotes] = useState("");
  const [aiTone, setAiTone] = useState("direct");

  // Memories State
  const [memories, setMemories] = useState<UserMemory[]>([]);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;

      async function load() {
        setLoading(true);
        try {
          const [userProf, mems] = await Promise.all([
            getUserProfile(),
            listUserMemories(),
          ]);
          if (!cancelled) {
            setFitnessGoals(userProf.fitness_goals || "");
            setDietaryPrefs((userProf.dietary_preferences || []).join(", "));
            setLifestyleNotes(userProf.lifestyle_notes || "");
            setAiTone(userProf.ai_tone || "direct");
            setMemories(mems);
          }
        } catch {
          if (!cancelled) {
            Alert.alert("Erreur", "Impossible de charger les paramètres de l'assistant.");
          }
        } finally {
          if (!cancelled) {
            setLoading(false);
            setRefreshing(false);
          }
        }
      }

      load();
      return () => {
        cancelled = true;
      };
    }, []),
  );

  const refreshData = async () => {
    setRefreshing(true);
    try {
      const [userProf, mems] = await Promise.all([
        getUserProfile(),
        listUserMemories(),
      ]);
      setFitnessGoals(userProf.fitness_goals || "");
      setDietaryPrefs((userProf.dietary_preferences || []).join(", "));
      setLifestyleNotes(userProf.lifestyle_notes || "");
      setAiTone(userProf.ai_tone || "direct");
      setMemories(mems);
    } catch {
      Alert.alert("Erreur", "Impossible de rafraîchir les données.");
    } finally {
      setRefreshing(false);
    }
  };

  const handleSaveProfile = async () => {
    setSavingProfile(true);
    try {
      const dietList = dietaryPrefs
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      await updateUserProfile({
        fitness_goals: fitnessGoals,
        dietary_preferences: dietList,
        lifestyle_notes: lifestyleNotes,
        ai_tone: aiTone,
        onboarding_completed: true,
      });
      Alert.alert("Succès", "Ton profil IA a été mis à jour !");
    } catch {
      Alert.alert("Erreur", "Échec de la sauvegarde du profil.");
    } finally {
      setSavingProfile(false);
    }
  };

  const handleDeleteMemory = async (id: number) => {
    setDeletingId(id);
    try {
      await deleteUserMemory(id);
      setMemories((prev) => prev.filter((m) => m.id !== id));
    } catch {
      Alert.alert("Erreur", "Impossible d'effacer ce souvenir.");
    } finally {
      setDeletingId(null);
    }
  };

  if (loading) {
    return (
      <SafeAreaView className="flex-1 bg-slate-950 items-center justify-center">
        <ActivityIndicator size="large" color="#10b981" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView className="flex-1 bg-slate-950">
      {/* Header */}
      <View className="flex-row items-center px-4 py-3 border-b border-slate-800 bg-slate-900/80">
        <TouchableOpacity
          onPress={() => router.back()}
          className="w-10 h-10 rounded-full items-center justify-center bg-slate-800 mr-3"
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <Ionicons name="arrow-back" size={22} color="#f8fafc" />
        </TouchableOpacity>
        <View>
          <Text className="text-base font-bold text-white">Mémoire & Copilote</Text>
          <Text className="text-xs text-slate-400">Transparence et personnalisation IA</Text>
        </View>
      </View>

      <ScrollView
        className="flex-1 px-4 py-4"
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={refreshData}
            tintColor="#10b981"
          />
        }
      >
        {/* Section 1: AI Tone */}
        <View className="mb-6 p-4 rounded-2xl bg-slate-900 border border-slate-800">
          <Text className="text-sm font-bold text-white mb-1">
            Ton de communication préféré
          </Text>
          <Text className="text-xs text-slate-400 mb-3">
            Choisis la façon dont ton assistant s&apos;adresse à toi.
          </Text>

          <View className="flex-row flex-wrap gap-2">
            {TONE_OPTIONS.map((opt) => (
              <TouchableOpacity
                key={opt.id}
                onPress={() => setAiTone(opt.id)}
                className={`px-3 py-2 rounded-xl border ${
                  aiTone === opt.id
                    ? "bg-emerald-500/20 border-emerald-500"
                    : "bg-slate-800 border-slate-700"
                }`}
              >
                <Text
                  className={`text-xs font-semibold ${
                    aiTone === opt.id ? "text-emerald-400" : "text-slate-300"
                  }`}
                >
                  {opt.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Section 2: Profile inputs */}
        <View className="mb-6 p-4 rounded-2xl bg-slate-900 border border-slate-800">
          <Text className="text-sm font-bold text-white mb-3">
            Profil & Préférences durables
          </Text>

          <View className="mb-3">
            <Text className="text-xs font-medium text-slate-400 mb-1">
              Objectifs physiques / sportifs
            </Text>
            <TextInput
              className="bg-slate-800 text-white rounded-xl px-3 py-2.5 text-sm"
              placeholder="Ex: Prise de masse, 4 séances par semaine..."
              placeholderTextColor="#64748b"
              value={fitnessGoals}
              onChangeText={setFitnessGoals}
            />
          </View>

          <View className="mb-3">
            <Text className="text-xs font-medium text-slate-400 mb-1">
              Régimes & Restrictions alimentaires (séparés par des virgules)
            </Text>
            <TextInput
              className="bg-slate-800 text-white rounded-xl px-3 py-2.5 text-sm"
              placeholder="Ex: sans gluten, végétarien, pas d'arachides..."
              placeholderTextColor="#64748b"
              value={dietaryPrefs}
              onChangeText={setDietaryPrefs}
            />
          </View>

          <View className="mb-4">
            <Text className="text-xs font-medium text-slate-400 mb-1">
              Style de vie & Habitudes
            </Text>
            <TextInput
              className="bg-slate-800 text-white rounded-xl px-3 py-2.5 text-sm min-h-16"
              placeholder="Ex: Télétravail les mardis, écoute de la drill..."
              placeholderTextColor="#64748b"
              value={lifestyleNotes}
              onChangeText={setLifestyleNotes}
              multiline
            />
          </View>

          <TouchableOpacity
            onPress={handleSaveProfile}
            disabled={savingProfile}
            className="w-full py-3 rounded-xl bg-emerald-600 items-center justify-center flex-row"
          >
            {savingProfile ? (
              <ActivityIndicator size="small" color="#ffffff" />
            ) : (
              <>
                <Ionicons name="save-outline" size={18} color="#ffffff" className="mr-2" />
                <Text className="text-sm font-bold text-white ml-2">Enregistrer mon profil</Text>
              </>
            )}
          </TouchableOpacity>
        </View>

        {/* Section 3: Extracted Memories */}
        <View className="mb-8">
          <View className="flex-row items-center justify-between mb-2">
            <Text className="text-sm font-bold text-white">
              Faits mémorisés automatiquement ({memories.length})
            </Text>
          </View>
          <Text className="text-xs text-slate-400 mb-3">
            L&apos;assistant retient les faits utiles mentionnés dans vos conversations. Tu peux révoquer un fait à tout moment pour qu&apos;il soit oublié.
          </Text>

          {memories.length === 0 ? (
            <View className="p-6 rounded-2xl bg-slate-900 border border-slate-800 items-center">
              <Ionicons name="sparkles-outline" size={32} color="#64748b" />
              <Text className="text-sm font-medium text-slate-300 mt-2">
                Aucun souvenir autonome pour l&apos;instant
              </Text>
              <Text className="text-xs text-slate-500 text-center mt-1">
                Au fil de tes discussions (blessures, goûts, contraintes), ton copilote mémorisera les faits durables ici.
              </Text>
            </View>
          ) : (
            memories.map((mem) => (
              <MemoryTag
                key={mem.id}
                memory={mem}
                onDelete={handleDeleteMemory}
                isDeleting={deletingId === mem.id}
              />
            ))
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
