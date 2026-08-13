import { Ionicons } from "@expo/vector-icons";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";

import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import { mockGroceryList } from "@/data/mock";

export default function GroceriesScreen() {
  const [items, setItems] = useState(mockGroceryList);
  const remaining = items.filter((item) => !item.checked).length;

  function toggle(id: string) {
    setItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, checked: !item.checked } : item)),
    );
  }

  return (
    <Screen>
      <ScreenHeader
        title="Courses"
        subtitle={`${remaining} article${remaining > 1 ? "s" : ""} à acheter`}
      />
      {items.map((item) => (
        <Pressable
          key={item.id}
          onPress={() => toggle(item.id)}
          className="mb-3 flex-row items-center rounded-2xl border border-slate-100 bg-white p-4"
        >
          <View
            className={`mr-3 h-6 w-6 items-center justify-center rounded-full border-2 ${
              item.checked ? "border-emerald-500 bg-emerald-500" : "border-slate-300 bg-white"
            }`}
          >
            {item.checked ? <Ionicons name="checkmark" size={14} color="#ffffff" /> : null}
          </View>
          <View className="flex-1">
            <Text
              className={`text-base ${item.checked ? "text-slate-400 line-through" : "text-slate-900"}`}
            >
              {item.name}
            </Text>
            <Text className="text-sm text-slate-400">{item.category}</Text>
          </View>
          <Text className="text-sm font-medium text-slate-500">{item.quantity}</Text>
        </Pressable>
      ))}
    </Screen>
  );
}
