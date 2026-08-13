import { Ionicons } from "@expo/vector-icons";
import { Link, router } from "expo-router";
import { useState } from "react";
import { KeyboardAvoidingView, Platform, Text, View } from "react-native";

import { Field } from "@/components/field";
import { PrimaryButton } from "@/components/primary-button";
import { Screen } from "@/components/screen";
import { register } from "@/lib/api";

export default function RegisterScreen() {
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit =
    displayName.trim().length > 0 && email.trim().length > 0 && password.length >= 6;

  async function handleRegister() {
    if (!canSubmit || loading) return;
    setLoading(true);
    setError(null);
    try {
      await register(email.trim(), password, displayName.trim());
      router.replace("/(tabs)/meal-plan");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue");
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      className="flex-1 bg-slate-50"
    >
      <Screen>
        <View className="mb-8 mt-8 items-center">
          <View className="mb-4 h-16 w-16 items-center justify-center rounded-2xl bg-emerald-600">
            <Ionicons name="nutrition" size={32} color="#ffffff" />
          </View>
          <Text className="text-3xl font-bold text-slate-900">AdamHUB SaaS</Text>
          <Text className="mt-1 text-base text-slate-500">(nom provisoire)</Text>
        </View>

        <Text className="mb-1 text-2xl font-bold text-slate-900">Créer un compte</Text>
        <Text className="mb-6 text-base text-slate-500">
          En quelques secondes pour démarrer.
        </Text>

        {error ? (
          <View className="mb-4 rounded-xl bg-red-50 px-4 py-3">
            <Text className="text-sm text-red-600">{error}</Text>
          </View>
        ) : null}

        <Field
          label="Nom d'affichage"
          value={displayName}
          onChangeText={setDisplayName}
          placeholder="Votre prénom ou pseudo"
          autoCapitalize="words"
          autoComplete="name"
        />
        <Field
          label="Email"
          value={email}
          onChangeText={setEmail}
          placeholder="vous@exemple.com"
          keyboardType="email-address"
          autoCapitalize="none"
          autoComplete="email"
        />
        <Field
          label="Mot de passe"
          value={password}
          onChangeText={setPassword}
          placeholder="6 caractères minimum"
          secureTextEntry
          autoCapitalize="none"
          autoComplete="new-password"
        />

        <PrimaryButton
          label="Créer le compte"
          onPress={handleRegister}
          loading={loading}
          disabled={!canSubmit}
        />

        <View className="mt-6 flex-row items-center justify-center">
          <Text className="text-slate-600">Déjà inscrit ? </Text>
          <Link href="/(auth)/login" className="font-semibold text-emerald-600">
            Se connecter
          </Link>
        </View>
      </Screen>
    </KeyboardAvoidingView>
  );
}
