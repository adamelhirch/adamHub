import { Text, View } from "react-native";

import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { mockPantry } from "@/data/mock";

export default function PantryScreen() {
  const categories = [...new Set(mockPantry.map((item) => item.category))];

  return (
    <Screen>
      <ScreenHeader title="Garde-manger" subtitle="Vos stocks actuels" />
      {categories.map((category) => (
        <View key={category} className="mb-5">
          <Text className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
            {category}
          </Text>
          <View className="overflow-hidden rounded-2xl border border-slate-100 bg-white">
            {mockPantry
              .filter((item) => item.category === category)
              .map((item, index) => (
                <View
                  key={item.id}
                  className={`flex-row items-center justify-between px-4 py-3 ${
                    index > 0 ? "border-t border-slate-100" : ""
                  }`}
                >
                  <View className="flex-1">
                    <Text className="text-base text-slate-900">{item.name}</Text>
                    {item.expiry ? (
                      <Text className="text-xs text-slate-400">Expire : {item.expiry}</Text>
                    ) : null}
                  </View>
                  <Text className="text-sm font-medium text-slate-500">{item.quantity}</Text>
                </View>
              ))}
          </View>
        </View>
      ))}
    </Screen>
  );
}
