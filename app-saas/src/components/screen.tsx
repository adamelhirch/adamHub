import { ReactNode } from "react";
import { ScrollView, ScrollViewProps } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

interface ScreenProps extends ScrollViewProps {
  children: ReactNode;
}

export function Screen({ children, ...props }: ScreenProps) {
  return (
    <SafeAreaView className="flex-1 bg-slate-50">
      <ScrollView
        contentContainerClassName="p-6 pb-12"
        keyboardShouldPersistTaps="handled"
        {...props}
      >
        {children}
      </ScrollView>
    </SafeAreaView>
  );
}
