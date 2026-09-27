import React from "react";
import { TouchableOpacity, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Tabs, useRouter } from "expo-router";

export default function TabsLayout() {
  const router = useRouter();

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: "#10b981",
        tabBarInactiveTintColor: "#94a3b8",
        tabBarStyle: {
          backgroundColor: "#0f172a",
          borderTopColor: "#1e293b",
          height: 64,
          paddingBottom: 8,
          paddingTop: 6,
        },
      }}
    >
      {/* 1. Accueil (Hub Food & Supermarchés) */}
      <Tabs.Screen
        name="index"
        options={{
          title: "Accueil",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="home-outline" size={size} color={color} />
          ),
        }}
      />

      {/* 2. Courses (Liste + Drive) */}
      <Tabs.Screen
        name="groceries"
        options={{
          title: "Courses",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="cart-outline" size={size} color={color} />
          ),
        }}
      />

      {/* 3. Bouton Central IA Flottant */}
      <Tabs.Screen
        name="ai"
        options={{
          title: "",
          tabBarButton: () => (
            <TouchableOpacity
              onPress={() => router.push("/assistant")}
              activeOpacity={0.85}
              style={{
                top: -20,
                justifyContent: "center",
                alignItems: "center",
              }}
            >
              <View
                style={{
                  width: 60,
                  height: 60,
                  borderRadius: 30,
                  backgroundColor: "#1e293b",
                  justifyContent: "center",
                  alignItems: "center",
                  shadowColor: "#000000",
                  shadowOffset: { width: 0, height: 4 },
                  shadowOpacity: 0.3,
                  shadowRadius: 8,
                  elevation: 6,
                  borderWidth: 3,
                  borderColor: "#334155",
                }}
              >
                <Ionicons name="sparkles" size={26} color="#f8fafc" />
              </View>
            </TouchableOpacity>
          ),
        }}
      />

      {/* 4. Recettes & Menus */}
      <Tabs.Screen
        name="recipes"
        options={{
          title: "Recettes",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="restaurant-outline" size={size} color={color} />
          ),
        }}
      />

      {/* 5. Garde-manger / Frigo */}
      <Tabs.Screen
        name="pantry"
        options={{
          title: "Frigo",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="cube-outline" size={size} color={color} />
          ),
        }}
      />

      {/* Hidden sub-flows */}
      <Tabs.Screen name="kitchen" options={{ href: null }} />
      <Tabs.Screen name="meal-plan" options={{ href: null }} />
    </Tabs>
  );
}
