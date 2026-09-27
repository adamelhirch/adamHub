import React, { useState, useRef, useEffect } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  ChatMessage,
  streamAssistantChat,
  resetAssistantSession,
} from "@/lib/assistant-api";
import { ChatMessageItem } from "@/components/assistant/chat-message";
import {
  pickImages,
  AttachmentPreviewBar,
} from "@/components/assistant/image-attachment";
import { VoiceRecorder } from "@/components/assistant/voice-recorder";

const SUGGESTIONS = [
  { icon: "restaurant-outline", text: "Repas conseillé pour ce midi ?" },
  { icon: "cart-outline", text: "Ajoute 6 œufs, du lait et du riz aux courses" },
  { icon: "calendar-outline", text: "Génère un menu équilibré pour 3 jours" },
  { icon: "flash-outline", text: "Quelles sont mes priorités culinaires aujourd'hui ?" },
];

export default function AssistantScreen() {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome-msg",
      role: "assistant",
      content:
        "Bonjour ! Je suis ton copilote AdamHUB. J'ai accès à ton profil, tes recettes, tes stocks et tes courses. En quoi puis-je t'aider aujourd'hui ?",
      timestamp: new Date().toISOString(),
    },
  ]);
  const [inputText, setInputText] = useState("");
  const [attachedImages, setAttachedImages] = useState<string[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const scrollViewRef = useRef<ScrollView>(null);
  const nextIdRef = useRef(1);

  useEffect(() => {
    scrollViewRef.current?.scrollToEnd({ animated: true });
  }, [messages, attachedImages]);

  const handlePickImages = async () => {
    if (isStreaming) return;
    const uris = await pickImages();
    if (uris.length > 0) {
      setAttachedImages((prev) => [...prev, ...uris].slice(0, 4));
    }
  };

  const handleRemoveImage = (index: number) => {
    setAttachedImages((prev) => prev.filter((_, i) => i !== index));
  };

  const handleVoiceTranscript = (transcript: string) => {
    if (!transcript) return;
    setInputText((prev) => (prev.trim() ? `${prev.trim()} ${transcript}` : transcript));
  };

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend !== undefined ? textToSend : inputText).trim();
    const imagesToSend = [...attachedImages];

    // Must have either text or an image
    if ((!text && imagesToSend.length === 0) || isStreaming) return;

    // Reset input fields
    setInputText("");
    setAttachedImages([]);

    const uId = `user-${nextIdRef.current++}`;
    const userMessage: ChatMessage = {
      id: uId,
      role: "user",
      content: text,
      images: imagesToSend.length > 0 ? imagesToSend : undefined,
      timestamp: new Date().toISOString(),
    };

    const aId = `assistant-${nextIdRef.current++}`;
    const assistantMessage: ChatMessage = {
      id: aId,
      role: "assistant",
      content: "",
      isStreaming: true,
      timestamp: new Date().toISOString(),
    };

    const history = messages
      .filter((m) => (m.role === "user" || m.role === "assistant") && m.content.trim().length > 0)
      .slice(-10)
      .map((m) => ({ role: m.role, content: m.content }));

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsStreaming(true);

    try {
      await streamAssistantChat({
        message: text || (imagesToSend.length > 0 ? "Analyse cette image s'il te plaît." : ""),
        images: imagesToSend,
        history,
        onDelta: (delta) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === aId
                ? { ...msg, content: msg.content + delta }
                : msg
            )
          );
        },
        onToolResult: (toolResult) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === aId
                ? {
                    ...msg,
                    actions: [...(msg.actions || []), toolResult],
                  }
                : msg
            )
          );
        },
        onDone: (fullText) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === aId
                ? { ...msg, content: fullText || msg.content, isStreaming: false }
                : msg
            )
          );
          setIsStreaming(false);
        },
        onError: () => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === aId
                ? {
                    ...msg,
                    content:
                      msg.content +
                      "\n\n[Impossible de contacter le copilote. Vérifie ta connexion.]",
                    isStreaming: false,
                  }
                : msg
            )
          );
          setIsStreaming(false);
        },
      });
    } catch {
      setIsStreaming(false);
    }
  };

  const handleReset = async () => {
    try {
      await resetAssistantSession();
    } catch {
      // Ignore network failure on reset
    }
    setAttachedImages([]);
    setMessages([
      {
        id: `welcome-${nextIdRef.current++}`,
        role: "assistant",
        content:
          "Nouvelle session démarrée ! Tes préférences et ta mémoire restent actives. Que souhaites-tu faire ?",
        timestamp: new Date().toISOString(),
      },
    ]);
  };

  const canSend = (inputText.trim().length > 0 || attachedImages.length > 0) && !isStreaming;

  return (
    <SafeAreaView className="flex-1 bg-slate-50">
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        className="flex-1"
      >
        {/* Header */}
        <View className="flex-row items-center justify-between px-4 py-3 border-b border-slate-200 bg-white">
          <TouchableOpacity
            onPress={() => router.back()}
            className="w-9 h-9 rounded-full items-center justify-center bg-slate-100 border border-slate-200 hover:bg-slate-200 active:bg-slate-200"
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          >
            <Ionicons name="chevron-down" size={22} color="#0f172a" />
          </TouchableOpacity>

          <View className="items-center">
            <View className="flex-row items-center">
              <View className="w-2 h-2 rounded-full bg-slate-900 mr-1.5" />
              <Text className="text-base font-bold text-slate-900">AdamHUB Copilot</Text>
            </View>
            <Text className="text-[11px] text-slate-500">Assistant IA contextuel</Text>
          </View>

          <TouchableOpacity
            onPress={handleReset}
            className="flex-row items-center px-2.5 py-1.5 rounded-full bg-slate-100 border border-slate-200 hover:bg-slate-200 active:bg-slate-200"
          >
            <Ionicons name="refresh" size={13} color="#475569" />
            <Text className="text-xs text-slate-700 ml-1 font-medium">Nouveau</Text>
          </TouchableOpacity>
        </View>

        {/* Message Thread */}
        <ScrollView
          ref={scrollViewRef}
          className="flex-1 px-3.5 py-2"
          contentContainerStyle={{ paddingBottom: 24 }}
          keyboardShouldPersistTaps="handled"
        >
          {messages.map((msg) => (
            <ChatMessageItem key={msg.id} message={msg} />
          ))}

          {/* Quick Suggestions if thread only has welcome message */}
          {messages.length === 1 ? (
            <View className="mt-6 px-1">
              <Text className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                Suggestions rapides
              </Text>
              <View className="gap-2.5">
                {SUGGESTIONS.map((s, idx) => (
                  <TouchableOpacity
                    key={idx}
                    onPress={() => handleSend(s.text)}
                    className="flex-row items-center bg-white border border-slate-200 hover:border-slate-300 rounded-2xl p-3.5 shadow-xs"
                  >
                    <View className="w-9 h-9 rounded-xl bg-slate-100 items-center justify-center mr-3">
                      <Ionicons name={s.icon as any} size={18} color="#0f172a" />
                    </View>
                    <Text className="text-sm text-slate-800 flex-1 font-medium">
                      {s.text}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          ) : null}
        </ScrollView>

        {/* Composer Bar (assistant-ui inspired, cohesive light theme) */}
        <View className="p-3 border-t border-slate-200 bg-white/95">
          <View className="bg-slate-100/90 border border-slate-200/90 rounded-3xl overflow-hidden shadow-xs focus-within:border-slate-300">
            {/* Attachment preview bar (if images attached) */}
            <AttachmentPreviewBar
              images={attachedImages}
              onRemove={handleRemoveImage}
            />

            {/* Main composer input and actions row */}
            <View className="flex-row items-end px-3 py-2">
              {/* Left action buttons */}
              <View className="flex-row items-center pb-1 mr-2 gap-1.5">
                {/* Image Picker */}
                <TouchableOpacity
                  onPress={handlePickImages}
                  disabled={isStreaming}
                  className="w-9 h-9 rounded-full items-center justify-center bg-slate-200/80 hover:bg-slate-300 active:bg-slate-300"
                  hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
                  accessibilityLabel="Joindre une image"
                >
                  <Ionicons name="image-outline" size={19} color="#475569" />
                </TouchableOpacity>

                {/* Voice Recorder */}
                <VoiceRecorder
                  onTranscriptReady={handleVoiceTranscript}
                  disabled={isStreaming}
                />
              </View>

              {/* Text Input */}
              <TextInput
                className="flex-1 text-slate-900 text-sm py-2 px-1 max-h-32 min-h-[40px]"
                placeholder={
                  attachedImages.length > 0
                    ? "Ajoute une question sur l'image..."
                    : "Demande une recette, un planning, gère tes courses..."
                }
                placeholderTextColor="#94a3b8"
                value={inputText}
                onChangeText={setInputText}
                multiline
                editable={!isStreaming}
              />

              {/* Send Button */}
              <View className="pb-1 ml-2">
                <TouchableOpacity
                  onPress={() => handleSend()}
                  disabled={!canSend}
                  className={`w-9 h-9 rounded-full items-center justify-center transition-all ${
                    canSend
                      ? "bg-slate-900 shadow-sm active:bg-slate-800"
                      : "bg-slate-200/80"
                  }`}
                  accessibilityLabel="Envoyer le message"
                >
                  {isStreaming ? (
                    <ActivityIndicator size="small" color="#ffffff" />
                  ) : (
                    <Ionicons
                      name="arrow-up"
                      size={18}
                      color={canSend ? "#ffffff" : "#94a3b8"}
                    />
                  )}
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
