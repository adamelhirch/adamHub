import React, { useState, useRef, useEffect } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  Platform,
  Alert,
  ActivityIndicator,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { transcribeAudio } from "@/lib/assistant-api";

// Web SpeechRecognition types
interface IWindowWithSpeech extends Window {
  SpeechRecognition?: any;
  webkitSpeechRecognition?: any;
}

interface VoiceRecorderProps {
  onTranscriptReady: (transcript: string) => void;
  disabled?: boolean;
}

export function VoiceRecorder({ onTranscriptReady, disabled }: VoiceRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [duration, setDuration] = useState(0);
  const [liveTranscript, setLiveTranscript] = useState("");

  const recognitionRef = useRef<any>(null);
  const mediaRecorderRef = useRef<any>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<any>(null);

  const stopAll = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      try {
        mediaRecorderRef.current.stop();
      } catch {}
      mediaRecorderRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      stopAll();
    };
  }, []);

  const startRecording = async () => {
    if (disabled || isRecording || isTranscribing) return;

    setDuration(0);
    setLiveTranscript("");
    audioChunksRef.current = [];

    if (Platform.OS === "web" && typeof window !== "undefined") {
      const win = window as unknown as IWindowWithSpeech;
      const SpeechRecognitionClass = win.SpeechRecognition || win.webkitSpeechRecognition;

      let speechStarted = false;

      if (SpeechRecognitionClass) {
        try {
          const recognition = new SpeechRecognitionClass();
          recognition.lang = "fr-FR";
          recognition.continuous = true;
          recognition.interimResults = true;

          let accumulated = "";

          recognition.onresult = (event: any) => {
            let interim = "";
            for (let i = event.resultIndex; i < event.results.length; ++i) {
              if (event.results[i].isFinal) {
                accumulated += event.results[i][0].transcript + " ";
              } else {
                interim += event.results[i][0].transcript;
              }
            }
            const current = (accumulated + interim).trim();
            setLiveTranscript(current);
          };

          recognition.onerror = (err: any) => {
            console.warn("Speech recognition error:", err);
          };

          recognition.onend = () => {
            // Recognition finished
          };

          recognition.start();
          recognitionRef.current = recognition;
          speechStarted = true;
        } catch (e) {
          console.warn("Could not start SpeechRecognition, falling back to MediaRecorder:", e);
        }
      }

      // Also record audio stream via MediaRecorder as backup or for Whisper transcription
      try {
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          const mediaRecorder = new MediaRecorder(stream);
          audioChunksRef.current = [];

          mediaRecorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) {
              audioChunksRef.current.push(event.data);
            }
          };

          mediaRecorder.start(250);
          mediaRecorderRef.current = mediaRecorder;
        }
      } catch (err) {
        console.warn("MediaDevices getUserMedia failed:", err);
        if (!speechStarted) {
          Alert.alert(
            "Microphone inaccessible",
            "Impossible d'accéder au micro. Vérifie que les autorisations sont accordées."
          );
          return;
        }
      }
    } else {
      Alert.alert(
        "Vocal non supporté",
        "L'enregistrement vocal est actuellement disponible sur l'application Web Chrome/Safari."
      );
      return;
    }

    setIsRecording(true);
    timerRef.current = setInterval(() => {
      setDuration((prev) => prev + 1);
    }, 1000);
  };

  const handleCancel = () => {
    stopAll();
    setIsRecording(false);
    setLiveTranscript("");
    setDuration(0);
  };

  const handleConfirm = async () => {
    const finalSpeechText = liveTranscript.trim();
    stopAll();
    setIsRecording(false);

    if (finalSpeechText) {
      onTranscriptReady(finalSpeechText);
      setLiveTranscript("");
      setDuration(0);
      return;
    }

    // If Web Speech API didn't produce text, fallback to backend transcription via audio chunks
    if (audioChunksRef.current.length > 0) {
      setIsTranscribing(true);
      try {
        const mimeType = audioChunksRef.current[0].type || "audio/webm";
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });

        const base64 = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onloadend = () => {
            const res = reader.result as string;
            // Remove data URI prefix if present
            const cleanBase64 = res.includes(",") ? res.split(",")[1] : res;
            resolve(cleanBase64);
          };
          reader.onerror = reject;
          reader.readAsDataURL(audioBlob);
        });

        const transcribedText = await transcribeAudio(base64, mimeType);
        if (transcribedText && transcribedText.trim()) {
          onTranscriptReady(transcribedText.trim());
        } else {
          Alert.alert("Transcription", "Aucune voix détectée dans l'enregistrement.");
        }
      } catch (e) {
        console.error("Transcription error:", e);
        Alert.alert("Erreur", "La transcription du message vocal a échoué.");
      } finally {
        setIsTranscribing(false);
      }
    }

    setLiveTranscript("");
    setDuration(0);
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  if (isTranscribing) {
    return (
      <View className="flex-row items-center px-3 py-1.5 bg-slate-100 rounded-full border border-slate-200">
        <ActivityIndicator size="small" color="#0f172a" />
        <Text className="text-xs font-medium text-slate-700 ml-2">Transcription...</Text>
      </View>
    );
  }

  if (isRecording) {
    return (
      <View className="flex-row items-center bg-white border border-slate-300 rounded-full px-3 py-1 shadow-sm">
        {/* Pulsing indicator */}
        <View className="w-2.5 h-2.5 rounded-full bg-red-500 mr-2 animate-pulse" />
        <Text className="text-xs font-semibold text-red-600 mr-2">{formatTime(duration)}</Text>

        {/* Live speech preview if text is coming in */}
        {liveTranscript ? (
          <Text className="text-xs text-slate-700 max-w-[140px] truncate mr-2" numberOfLines={1}>
            {`"${liveTranscript}"`}
          </Text>
        ) : (
          <Text className="text-xs text-slate-400 mr-2">Parle...</Text>
        )}

        {/* Cancel button */}
        <TouchableOpacity
          onPress={handleCancel}
          className="w-7 h-7 rounded-full bg-slate-100 items-center justify-center mr-1.5"
          hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
        >
          <Ionicons name="close" size={14} color="#64748b" />
        </TouchableOpacity>

        {/* Confirm / Send transcript button */}
        <TouchableOpacity
          onPress={handleConfirm}
          className="w-7 h-7 rounded-full bg-slate-900 items-center justify-center shadow-xs"
          hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
        >
          <Ionicons name="checkmark" size={16} color="#ffffff" />
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <TouchableOpacity
      onPress={startRecording}
      disabled={disabled}
      className="w-9 h-9 rounded-full items-center justify-center bg-slate-100 hover:bg-slate-200 active:bg-slate-200"
      hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
      accessibilityLabel="Enregistrer un message vocal"
    >
      <Ionicons name="mic-outline" size={19} color="#475569" />
    </TouchableOpacity>
  );
}
