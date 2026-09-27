import { Alert as RNAlert, Platform } from "react-native";

export interface AlertButton {
  text?: string;
  onPress?: () => void;
  style?: "default" | "cancel" | "destructive";
}

export const Alert = {
  alert(title: string, message?: string, buttons?: AlertButton[]) {
    if (Platform.OS === "web") {
      const fullText = [title, message].filter(Boolean).join("\n\n");

      if (!buttons || buttons.length === 0) {
        if (typeof window !== "undefined") {
          window.alert(fullText);
        }
        return;
      }

      if (buttons.length === 1) {
        if (typeof window !== "undefined") {
          window.alert(fullText);
        }
        buttons[0].onPress?.();
        return;
      }

      // Check for confirm/cancel
      const cancelBtn = buttons.find((b) => b.style === "cancel");
      const confirmBtn =
        buttons.find((b) => b.style === "destructive" || b.style === "default") ||
        buttons.find((b) => b !== cancelBtn) ||
        buttons[buttons.length - 1];

      const ok = typeof window !== "undefined" ? window.confirm(fullText) : true;

      if (ok) {
        confirmBtn?.onPress?.();
      } else {
        cancelBtn?.onPress?.();
      }
    } else {
      RNAlert.alert(title, message, buttons);
    }
  },
};
