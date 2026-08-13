import { ActivityIndicator, Pressable, Text } from "react-native";

interface PrimaryButtonProps {
  label: string;
  loading?: boolean;
  disabled?: boolean;
  onPress: () => void;
}

export function PrimaryButton({ label, loading, disabled, onPress }: PrimaryButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      className={`w-full items-center justify-center rounded-xl py-3.5 ${
        isDisabled ? "bg-emerald-300" : "bg-emerald-600 active:bg-emerald-700"
      }`}
    >
      {loading ? (
        <ActivityIndicator color="#ffffff" />
      ) : (
        <Text className="text-base font-semibold text-white">{label}</Text>
      )}
    </Pressable>
  );
}
