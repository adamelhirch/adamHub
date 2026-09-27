import React from "react";
import { View, Text } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { ActionCardData } from "@/lib/assistant-api";

interface ActionCardProps {
  action: ActionCardData;
}

export const ActionCard: React.FC<ActionCardProps> = ({ action }) => {
  const { action: actionName, success, data, error } = action;

  // Domain resolution
  let iconName: keyof typeof Ionicons.glyphMap = "flash-outline";
  let title = "Action exécutée";
  let subtitle = "";
  let borderColor = "border-slate-200";
  let bgBadge = "bg-slate-100";
  let iconColor = "#0f172a";

  if (actionName.startsWith("task.")) {
    iconName = "checkmark-done-circle";
    title = actionName === "task.create" ? "Tâche créée" : "Tâche mise à jour";
    const taskData = data?.task || data;
    subtitle = taskData?.title || "Tâche planifiée";
  } else if (actionName.startsWith("grocery.")) {
    iconName = "cart";
    title = "Liste de courses";
    const itemData = data?.item || data;
    const qty = itemData?.quantity ? `${itemData.quantity} ` : "";
    const unit = itemData?.unit ? `${itemData.unit} ` : "";
    subtitle = `${qty}${unit}${itemData?.name || "Article ajouté"}`.trim();
  } else if (actionName.startsWith("calendar.")) {
    iconName = "calendar";
    title = "Calendrier";
    const calData = data?.item || data;
    subtitle = calData?.title || "Événement ajouté";
  } else if (actionName.startsWith("fitness.")) {
    iconName = "barbell";
    title = "Séance de sport";
    const fitData = data?.session || data;
    subtitle = fitData?.title || "Entraînement enregistré";
  } else if (actionName.startsWith("pantry.")) {
    iconName = "file-tray-stacked";
    title = "Garde-manger";
    const pantryData = data?.item || data;
    subtitle = pantryData?.name || "Stock mis à jour";
  }

  if (!success) {
    borderColor = "border-rose-200";
    bgBadge = "bg-rose-50";
    iconColor = "#e11d48";
  }

  return (
    <View
      className={`my-2 p-3 rounded-xl border bg-white ${borderColor} flex-row items-center justify-between shadow-xs`}
    >
      <View className="flex-row items-center flex-1 mr-2">
        <View
          className={`w-9 h-9 rounded-lg items-center justify-center mr-3 ${bgBadge}`}
        >
          <Ionicons
            name={iconName}
            size={20}
            color={iconColor}
          />
        </View>
        <View className="flex-1">
          <View className="flex-row items-center">
            <Text className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              {title}
            </Text>
            {success ? (
              <View className="ml-2 flex-row items-center bg-slate-100 px-1.5 py-0.5 rounded-full">
                <Ionicons name="checkmark" size={10} color="#0f172a" />
                <Text className="text-[10px] text-slate-700 font-medium ml-0.5">
                  Validé
                </Text>
              </View>
            ) : (
              <View className="ml-2 flex-row items-center bg-rose-50 px-1.5 py-0.5 rounded-full">
                <Ionicons name="alert-circle" size={10} color="#e11d48" />
                <Text className="text-[10px] text-rose-600 font-medium ml-0.5">
                  Erreur
                </Text>
              </View>
            )}
          </View>
          <Text
            className="text-sm font-medium text-slate-900 mt-0.5"
            numberOfLines={2}
          >
            {success ? subtitle : error || "Une erreur est survenue"}
          </Text>
        </View>
      </View>
      <Ionicons name="chevron-forward" size={16} color="#94a3b8" />
    </View>
  );
};
