import { Redirect } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";

import { getStoredToken } from "@/lib/token-storage";

export default function RootIndex() {
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    let active = true;
    getStoredToken()
      .then((token) => {
        if (active) setAuthenticated(Boolean(token));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <View className="flex-1 items-center justify-center bg-slate-50">
        <ActivityIndicator size="large" color="#059669" />
      </View>
    );
  }

  return <Redirect href={authenticated ? "/(tabs)/meal-plan" : "/(auth)/login"} />;
}
