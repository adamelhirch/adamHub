import React, { useState } from "react";
import {
  View,
  Text,
  Image,
  TouchableOpacity,
  ScrollView,
  Modal,
  Platform,
  Alert,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import * as ImagePicker from "expo-image-picker";

/**
 * Opens image library and returns array of base64 data URLs: "data:image/jpeg;base64,..."
 */
export async function pickImages(): Promise<string[]> {
  try {
    if (Platform.OS !== "web") {
      const permissionResult = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permissionResult.granted) {
        Alert.alert(
          "Permission requise",
          "L'accès à tes photos est nécessaire pour envoyer des images à l'assistant."
        );
        return [];
      }
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      allowsMultipleSelection: true,
      selectionLimit: 4,
      quality: 0.7,
      base64: true,
    });

    if (result.canceled || !result.assets || result.assets.length === 0) {
      return [];
    }

    const dataUris: string[] = [];

    for (const asset of result.assets) {
      if (asset.base64) {
        const mime = asset.mimeType || "image/jpeg";
        dataUris.push(`data:${mime};base64,${asset.base64}`);
      } else if (asset.uri) {
        // Fallback for web or assets without base64
        try {
          const res = await fetch(asset.uri);
          const blob = await res.blob();
          const base64 = await new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result as string);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
          });
          dataUris.push(base64);
        } catch {
          dataUris.push(asset.uri);
        }
      }
    }

    return dataUris;
  } catch (err) {
    console.error("Failed to pick images:", err);
    return [];
  }
}

/**
 * Preview bar shown in the composer above the text input before sending
 */
export function AttachmentPreviewBar({
  images,
  onRemove,
}: {
  images: string[];
  onRemove: (index: number) => void;
}) {
  if (!images || images.length === 0) return null;

  return (
    <View className="px-3 pt-2 pb-1 border-b border-slate-200 bg-slate-50">
      <View className="flex-row items-center justify-between mb-1.5">
        <Text className="text-[11px] font-medium text-slate-500">
          {images.length > 1
            ? `${images.length} images prêtes à l'envoi`
            : "1 image prête à l'envoi"}
        </Text>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} className="flex-row">
        {images.map((imgUri, index) => (
          <View key={index} className="relative mr-2 mb-1">
            <Image
              source={{ uri: imgUri }}
              className="w-16 h-16 rounded-xl border border-slate-200 bg-slate-100"
              resizeMode="cover"
            />
            <TouchableOpacity
              onPress={() => onRemove(index)}
              className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-slate-900 border border-slate-700 items-center justify-center shadow"
              hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
            >
              <Ionicons name="close" size={12} color="#f8fafc" />
            </TouchableOpacity>
          </View>
        ))}
      </ScrollView>
    </View>
  );
}

/**
 * Gallery displayed inside a user or assistant chat message bubble
 */
export function MessageImageGallery({ images }: { images?: string[] }) {
  const [selectedImage, setSelectedImage] = useState<string | null>(null);

  if (!images || images.length === 0) return null;

  return (
    <>
      <View className="flex-row flex-wrap gap-2 mb-2 mt-1">
        {images.map((imgUri, index) => (
          <TouchableOpacity
            key={index}
            activeOpacity={0.85}
            onPress={() => setSelectedImage(imgUri)}
            className="overflow-hidden rounded-xl border border-slate-200 shadow-xs"
          >
            <Image
              source={{ uri: imgUri }}
              className={`${
                images.length === 1 ? "w-52 h-44" : "w-28 h-28"
              } bg-slate-100`}
              resizeMode="cover"
            />
          </TouchableOpacity>
        ))}
      </View>

      {/* Lightbox Modal */}
      <Modal
        visible={!!selectedImage}
        transparent={true}
        animationType="fade"
        onRequestClose={() => setSelectedImage(null)}
      >
        <View className="flex-1 bg-black/90 items-center justify-center p-4">
          <TouchableOpacity
            onPress={() => setSelectedImage(null)}
            className="absolute top-12 right-6 z-10 w-10 h-10 rounded-full bg-slate-800/80 items-center justify-center border border-slate-600"
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          >
            <Ionicons name="close" size={24} color="#ffffff" />
          </TouchableOpacity>

          {selectedImage && (
            <Image
              source={{ uri: selectedImage }}
              className="w-full h-[75%] rounded-2xl"
              resizeMode="contain"
            />
          )}
        </View>
      </Modal>
    </>
  );
}
