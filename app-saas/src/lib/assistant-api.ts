import { API_URL } from "@/lib/api";
import { getStoredToken } from "@/lib/token-storage";

export interface UserProfile {
  id: number;
  user_id: number;
  dietary_preferences: string[];
  fitness_goals: string;
  lifestyle_notes: string;
  ai_tone: string;
  onboarding_completed: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserMemory {
  id: number;
  user_id: number;
  category: string;
  fact: string;
  confidence: number;
  source: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ActionCardData {
  action: string;
  success: boolean;
  data?: any;
  error?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  toolCalls?: any[];
  actions?: ActionCardData[];
  images?: string[];
  audioUrl?: string;
  timestamp: string;
}

export async function getUserProfile(): Promise<UserProfile> {
  const token = await getStoredToken();
  const res = await fetch(`${API_URL}/assistant/profile`, {
    headers: {
      Authorization: `Bearer ${token ?? ""}`,
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) throw new Error("Failed to load profile");
  return res.json();
}

export async function updateUserProfile(data: Partial<UserProfile>): Promise<UserProfile> {
  const token = await getStoredToken();
  const res = await fetch(`${API_URL}/assistant/profile`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token ?? ""}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to update profile");
  return res.json();
}

export async function listUserMemories(): Promise<UserMemory[]> {
  const token = await getStoredToken();
  const res = await fetch(`${API_URL}/assistant/memories`, {
    headers: {
      Authorization: `Bearer ${token ?? ""}`,
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) throw new Error("Failed to list memories");
  return res.json();
}

export async function deleteUserMemory(memoryId: number): Promise<void> {
  const token = await getStoredToken();
  const res = await fetch(`${API_URL}/assistant/memories/${memoryId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token ?? ""}`,
    },
  });
  if (!res.ok) throw new Error("Failed to delete memory");
}

export async function resetAssistantSession(): Promise<void> {
  const token = await getStoredToken();
  await fetch(`${API_URL}/assistant/session/reset`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token ?? ""}`,
      "Content-Type": "application/json",
    },
  });
}

/**
 * Stream conversational response from the backend assistant endpoint using XMLHttpRequest
 * which handles progressive streaming chunks reliably in React Native/Expo.
 */
export async function streamAssistantChat({
  message,
  images,
  sessionId,
  history,
  onDelta,
  onToolCall,
  onToolResult,
  onDone,
  onError,
}: {
  message: string;
  images?: string[];
  sessionId?: string;
  history?: { role: "user" | "assistant"; content: string }[];
  onDelta: (text: string) => void;
  onToolCall?: (toolCall: any) => void;
  onToolResult?: (toolResult: ActionCardData) => void;
  onDone?: (fullText: string) => void;
  onError?: (err: Error) => void;
}): Promise<void> {
  const token = await getStoredToken();

  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/assistant/chat`, true);
    xhr.setRequestHeader("Content-Type", "application/json");
    if (token) {
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    }

    let seenBytes = 0;

    xhr.onprogress = () => {
      const newText = xhr.responseText.substring(seenBytes);
      seenBytes = xhr.responseText.length;

      const lines = newText.split("\n\n");
      for (const block of lines) {
        if (!block.trim()) continue;
        const lineParts = block.split("\n");
        let event = "message";
        let dataStr = "";

        for (const part of lineParts) {
          if (part.startsWith("event: ")) {
            event = part.substring(7).trim();
          } else if (part.startsWith("data: ")) {
            dataStr = part.substring(6).trim();
          }
        }

        if (dataStr) {
          try {
            const parsed = JSON.parse(dataStr);
            if (event === "delta" && parsed.content) {
              onDelta(parsed.content);
            } else if (event === "tool_call" && onToolCall) {
              onToolCall(parsed);
            } else if (event === "tool_result" && onToolResult) {
              onToolResult(parsed);
            } else if (event === "done" && onDone) {
              onDone(parsed.full_text ?? "");
            }
          } catch {
            // Ignore partial or non-json chunks
          }
        }
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        const error = new Error(`Request failed with status ${xhr.status}`);
        if (onError) onError(error);
        resolve();
      }
    };

    xhr.onerror = () => {
      const error = new Error("Network request failed");
      if (onError) onError(error);
      resolve();
    };

    xhr.send(
      JSON.stringify({
        message,
        images: images || [],
        session_id: sessionId,
        history: history || [],
      }),
    );
  });
}

export async function transcribeAudio(
  audioBase64: string,
  mimeType: string = "audio/webm",
): Promise<string> {
  const token = await getStoredToken();
  const res = await fetch(`${API_URL}/assistant/transcribe`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token ?? ""}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ audio_base64: audioBase64, mime_type: mimeType }),
  });
  if (!res.ok) throw new Error("Échec de transcription audio");
  const data = await res.json();
  return data.text || "";
}

