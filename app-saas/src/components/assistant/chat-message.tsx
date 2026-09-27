import React, { useState } from "react";
import { View, Text, TouchableOpacity } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import * as Clipboard from "expo-clipboard";
import { ChatMessage as ChatMessageType } from "@/lib/assistant-api";
import { ActionCard } from "@/components/assistant/action-card";
import { MarkdownRenderer } from "@/components/assistant/markdown-renderer";
import { MessageImageGallery } from "@/components/assistant/image-attachment";

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessageItem({ message }: ChatMessageProps) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!message.content) return;
    try {
      await Clipboard.setStringAsync(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.warn("Failed to copy:", err);
    }
  };

  if (isUser) {
    return (
      <View className="my-2 max-w-[88%] self-end">
        <View className="bg-slate-900 rounded-2xl rounded-tr-xs p-3.5 shadow-sm">
          {/* Attached images gallery */}
          {message.images && message.images.length > 0 ? (
            <MessageImageGallery images={message.images} />
          ) : null}

          {/* Voice note indicator */}
          {message.audioUrl ? (
            <View className="flex-row items-center bg-slate-800 rounded-full px-2.5 py-1 mb-1.5 self-start">
              <Ionicons name="mic" size={12} color="#e2e8f0" />
              <Text className="text-[11px] font-semibold text-slate-200 ml-1">
                Note vocale
              </Text>
            </View>
          ) : null}

          {/* User message text */}
          {message.content ? (
            <Text className="text-sm leading-5 text-white font-medium">
              {message.content}
            </Text>
          ) : null}
        </View>

        <Text className="text-[10px] text-slate-400 mt-1 mr-1 text-right">
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </Text>
      </View>
    );
  }

  // Assistant Message
  return (
    <View className="my-2 w-full max-w-full self-start">
      <View className="rounded-2xl rounded-tl-xs p-4 bg-white border border-slate-200 shadow-xs">
        {/* Assistant Header Badge */}
        <View className="flex-row items-center justify-between mb-2.5 pb-2 border-b border-slate-100">
          <View className="flex-row items-center">
            <View className="w-6 h-6 rounded-full bg-slate-100 border border-slate-200 items-center justify-center mr-2">
              <Ionicons name="sparkles" size={12} color="#0f172a" />
            </View>
            <Text className="text-xs font-semibold text-slate-900">AdamHUB Copilot</Text>
          </View>

          {/* Action buttons (Copy) */}
          {Boolean(message.content) && !message.isStreaming ? (
            <TouchableOpacity
              onPress={handleCopy}
              className="flex-row items-center px-2 py-1 rounded-md bg-slate-100 hover:bg-slate-200 active:bg-slate-200 border border-slate-200/60"
              hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
            >
              <Ionicons
                name={copied ? "checkmark" : "copy-outline"}
                size={13}
                color={copied ? "#0f172a" : "#64748b"}
              />
              <Text className={`text-[11px] ml-1 ${copied ? "text-slate-900 font-semibold" : "text-slate-600"}`}>
                {copied ? "Copié" : "Copier"}
              </Text>
            </TouchableOpacity>
          ) : null}
        </View>

        {/* Attached images if any */}
        {message.images && message.images.length > 0 ? (
          <MessageImageGallery images={message.images} />
        ) : null}

        {/* Assistant Content rendered with rich markdown */}
        {message.content ? (
          <MarkdownRenderer
            content={message.content}
            isStreaming={message.isStreaming}
          />
        ) : message.isStreaming ? (
          <View className="flex-row items-center py-1">
            <View className="w-2 h-2 rounded-full bg-slate-400 mr-1.5 animate-pulse" />
            <Text className="text-xs text-slate-500 font-medium italic">
              Réflexion en cours...
            </Text>
          </View>
        ) : null}

        {/* Action Cards */}
        {message.actions && message.actions.length > 0 ? (
          <View className="mt-3 w-full">
            {message.actions.map((act, index) => (
              <ActionCard key={index} action={act} />
            ))}
          </View>
        ) : null}
      </View>

      <Text className="text-[10px] text-slate-400 mt-1 ml-1 text-left">
        {new Date(message.timestamp).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })}
      </Text>
    </View>
  );
}
