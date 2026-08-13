import { Text, View } from "react-native";

import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { mockMealPlan } from "@/data/mock";

export default function MealPlanScreen() {
  return (
    <Screen>
      <ScreenHeader title="Repas" subtitle="Votre plan de la semaine" />
      {mockMealPlan.map((day) => (
        <View key={day.day} className="mb-4 rounded-2xl border border-slate-100 bg-white p-4">
          <View className="mb-3 flex-row items-center justify-between">
            <Text className="text-lg font-bold text-slate-900">{day.day}</Text>
            <Text className="text-sm text-slate-400">{day.date}</Text>
          </View>
          {day.meals.map((meal) => (
            <View key={meal.label} className="flex-row items-start py-1.5">
              <View className="mr-3 mt-1 h-2 w-2 rounded-full bg-emerald-500" />
              <View className="flex-1">
                <Text className="text-sm font-medium text-slate-500">{meal.label}</Text>
                <Text className="text-base text-slate-900">{meal.recipe}</Text>
              </View>
            </View>
          ))}
        </View>
      ))}
    </Screen>
  );
}
