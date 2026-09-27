import React from "react";
import { View, Text, TouchableOpacity, ActivityIndicator } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { UserMemory } from "@/lib/assistant-api";

interface MemoryTagProps {
  memory: UserMemory;
  onDelete: (id: number) => void;
  isDeleting?: boolean;
}

const CATEGORY_LABELS: Record<string, { label: string; icon: keyof typeof Ionicons.glyphMap; color: string }> = {
  health_fitness: {
    label: "Santé & Sport",
    icon: "fitness",
    color: "text-rose-400 bg-rose-500/10 border-rose-800/40",
  },
  nutrition: {
    label: "Nutrition",
    icon: "restaurant",
    color: "text-amber-400 bg-amber-500/10 border-amber-800/40",
  },
  lifestyle: {
    label: "Style de vie",
    icon: "musical-notes",
    color: "text-sky-400 bg-sky-500/10 border-sky-800/40",
  },
  preferences: {
    label: "Préférences",
    icon: "options",
    color: "text-purple-400 bg-purple-500/10 border-purple-800/40",
  },
};

export const MemoryTag: React.FC<MemoryTagProps> = ({
  memory,
  onDelete,
  isDeleting = false,
}) => {
  const catInfo = CATEGORY_LABELS[memory.category] || {
    label: memory.category,
    icon: "bookmark",
    color: "text-slate-400 bg-slate-500/10 border-slate-700/40",
  };

  return (
    <View className="my-1.5 p-3.5 rounded-xl bg-slate-900 border border-slate-800 flex-row items-center justify-between">
      <View className="flex-1 mr-3">
        <View className="flex-row items-center mb-1.5">
          <View className={`px-2 py-0.5 rounded-md border flex-row items-center ${catInfo.color}`}>
            <Ionicons name={catInfo.icon} size={12} color="currentColor" className="mr-1" />
            <Text className="text-[10px] font-semibold uppercase tracking-wider text-slate-300 ml-1">
              {catInfo.label}
            </Text>
          </View>
          <Text className="text-[10px] text-slate-500 ml-2">
            {new Date(memory.created_at).toLocaleDateString([], {
              day: "numeric",
              month: "short",
            })}
          </Text>
        </View>

        <Text className="text-sm font-medium text-slate-200 leading-snug">
          {memory.fact}
        </Text>
      </View>

      <TouchableOpacity
        onPress={() => onDelete(memory.id)}
        disabled={isDeleting}
        className="w-8 h-8 rounded-lg items-center justify-center bg-slate-800/80 active:bg-rose-500/20"
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        {isDeleting ? (
          <ActivityIndicator size="small" color="#f87171" />
        ) : (
          <Ionicons name="trash-outline" size={16} color="#94a3b8" />
        )}
      </TouchableOpacity>
    </View>
  );
};
