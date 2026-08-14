import { Text, TextInput, TextInputProps, View } from "react-native";

interface FieldProps extends TextInputProps {
  label: string;
  error?: string;
}

export function Field({ label, error, ...props }: FieldProps) {
  return (
    <View className="mb-4">
      <Text className="mb-1.5 text-sm font-medium text-slate-700">{label}</Text>
      <TextInput
        {...props}
        placeholderTextColor="#94a3b8"
        className={`w-full rounded-xl border bg-white px-4 py-3 text-base text-slate-900 ${
          error ? "border-red-400" : "border-slate-200"
        }`}
      />
      {error ? <Text className="mt-1 text-sm text-red-500">{error}</Text> : null}
    </View>
  );
}
