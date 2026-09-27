import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { Pressable, Text, View } from "react-native";

interface ScreenHeaderProps {
  title: string;
  subtitle?: string;
  showProfileButton?: boolean;
  backButton?: boolean;
  rightAction?: React.ReactNode;
}

export function ScreenHeader({
  title,
  subtitle,
  showProfileButton = false,
  backButton = false,
  rightAction,
}: ScreenHeaderProps) {
  return (
    <View className="mb-6 flex-row items-center justify-between">
      <View className="flex-1 pr-3">
        {backButton && (
          <Pressable
            onPress={() => router.back()}
            className="mb-2 w-9 h-9 items-center justify-center rounded-full bg-slate-200 active:bg-slate-300"
            accessibilityLabel="Retour"
          >
            <Ionicons name="arrow-back" size={20} color="#0f172a" />
          </Pressable>
        )}
        <Text className="text-3xl font-bold text-slate-900">{title}</Text>
        {subtitle ? <Text className="mt-1 text-base text-slate-500">{subtitle}</Text> : null}
      </View>

      {rightAction ? (
        rightAction
      ) : showProfileButton ? (
        <Pressable
          onPress={() => router.push("/account")}
          className="relative h-11 w-11 items-center justify-center rounded-full bg-slate-100 border border-slate-200 active:bg-slate-200 shadow-sm"
          accessibilityLabel="Profil et Paramètres"
        >
          <Ionicons name="person" size={20} color="#059669" />
          <View className="absolute bottom-0 right-0 h-3 w-3 rounded-full bg-emerald-500 border-2 border-white" />
        </Pressable>
      ) : null}
    </View>
  );
}

