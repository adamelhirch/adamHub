import { Ionicons } from "@expo/vector-icons";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";

import { Screen } from "@/components/screen";
import { ScreenHeader } from "@/components/screen-header";
import {
  CalendarItemRead,
  createTask,
  deleteTask,
  listCalendarAgenda,
  listTasks,
  TaskRead,
  updateTask,
} from "@/lib/api";
import { me } from "@/lib/auth";

function formatTodayDate(): string {
  const date = new Date();
  return new Intl.DateTimeFormat("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(date);
}

function formatTime(iso: string): string {
  const match = iso.match(/T(\d{2}):(\d{2})/);
  if (match) {
    return `${match[1]}:${match[2]}`;
  }
  const d = new Date(iso);
  return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

export default function HomeScreen() {
  const [userName, setUserName] = useState<string>("Adam");
  const [calendarItems, setCalendarItems] = useState<CalendarItemRead[]>([]);
  const [tasks, setTasks] = useState<TaskRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New task quick add
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [addingTask, setAddingTask] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const [userData, agendaData, tasksData] = await Promise.all([
        me().catch(() => null),
        listCalendarAgenda(),
        listTasks({ limit: 100 }),
      ]);
      if (userData?.display_name) {
        setUserName(userData.display_name.split(" ")[0]);
      }
      setCalendarItems(agendaData);
      setTasks(tasksData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur lors du chargement des données");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [loadData]),
  );

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadData();
  }, [loadData]);

  async function handleToggleTask(task: TaskRead) {
    const nextStatus = task.status === "done" ? "todo" : "done";
    setTasks((prev) =>
      prev.map((t) => (t.id === task.id ? { ...t, status: nextStatus } : t)),
    );
    try {
      await updateTask(task.id, { status: nextStatus });
    } catch {
      setTasks((prev) =>
        prev.map((t) => (t.id === task.id ? { ...t, status: task.status } : t)),
      );
      Alert.alert("Erreur", "Impossible de mettre à jour la tâche.");
    }
  }

  async function handleAddTask() {
    const title = newTaskTitle.trim();
    if (!title) return;
    setAddingTask(true);
    try {
      const created = await createTask({ title, priority: "medium" });
      setTasks((prev) => [created, ...prev]);
      setNewTaskTitle("");
    } catch {
      Alert.alert("Erreur", "Impossible de créer la tâche.");
    } finally {
      setAddingTask(false);
    }
  }

  async function handleDeleteTask(taskId: number) {
    try {
      await deleteTask(taskId);
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
    } catch {
      Alert.alert("Erreur", "Impossible de supprimer la tâche.");
    }
  }

  const openTasks = tasks.filter((t) => t.status !== "done");

  return (
    <Screen>
      <ScrollView
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        <ScreenHeader
          title={`Bonjour, ${userName} 👋`}
          subtitle={formatTodayDate().replace(/^\w/, (c) => c.toUpperCase())}
          showProfileButton={true}
        />

        {error ? (
          <View className="mb-4 rounded-xl bg-red-50 p-3">
            <Text className="text-sm text-red-600">{error}</Text>
          </View>
        ) : null}

        {/* AI Quick Banner */}
        <Pressable
          onPress={() => router.push("/assistant")}
          className="mb-6 overflow-hidden rounded-2xl bg-slate-900 p-5 shadow-md active:opacity-95"
        >
          <View className="flex-row items-center justify-between">
            <View className="flex-1 pr-3">
              <View className="flex-row items-center mb-1">
                <View className="h-2 w-2 rounded-full bg-slate-400 mr-2" />
                <Text className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Assistant Personnel
                </Text>
              </View>
              <Text className="text-lg font-bold text-white">
                {"Que faisons-nous aujourd'hui ?"}
              </Text>
              <Text className="text-xs text-slate-300 mt-1">
                Planifier des repas, ajouter des séances de sport ou organiser ton agenda.
              </Text>
            </View>
            <View className="h-12 w-12 items-center justify-center rounded-2xl bg-slate-800 border border-slate-700 shadow-sm">
              <Ionicons name="sparkles" size={24} color="#ffffff" />
            </View>
          </View>
        </Pressable>

        {/* SECTION 1: Calendrier du Jour */}
        <View className="mb-6">
          <View className="mb-3 flex-row items-center justify-between">
            <View className="flex-row items-center">
              <Ionicons name="calendar-outline" size={20} color="#0f172a" />
              <Text className="ml-2 text-lg font-bold text-slate-900">Agenda du jour</Text>
            </View>
            <Text className="text-xs font-medium text-slate-500">
              {calendarItems.length} événement{calendarItems.length > 1 ? "s" : ""}
            </Text>
          </View>

          {loading ? (
            <View className="py-6 items-center">
              <ActivityIndicator color="#10b981" />
            </View>
          ) : calendarItems.length === 0 ? (
            <View className="rounded-2xl border border-slate-100 bg-white p-5 items-center justify-center shadow-sm">
              <Ionicons name="sunny-outline" size={32} color="#94a3b8" />
              <Text className="mt-2 text-sm font-semibold text-slate-700">
                {"Aucun événement prévu aujourd'hui"}
              </Text>
              <Text className="mt-1 text-center text-xs text-slate-400">
                {"Demande à l'assistant IA pour planifier un entraînement ou un créneau."}
              </Text>
            </View>
          ) : (
            <View className="rounded-2xl border border-slate-100 bg-white p-2 shadow-sm">
              {calendarItems.map((item, index) => {
                const isLast = index === calendarItems.length - 1;
                return (
                  <View
                    key={item.id}
                    className={`flex-row items-center p-3 ${!isLast ? "border-b border-slate-50" : ""}`}
                  >
                    <View className="mr-3 w-14 items-center">
                      <Text className="text-xs font-bold text-slate-900">
                        {item.all_day ? "Journée" : formatTime(item.start_at)}
                      </Text>
                      {!item.all_day && (
                        <Text className="text-[10px] text-slate-400">
                          {formatTime(item.end_at)}
                        </Text>
                      )}
                    </View>
                    <View className="h-8 w-1 rounded-full bg-emerald-500 mr-3" />
                    <View className="flex-1">
                      <Text className="text-sm font-semibold text-slate-900" numberOfLines={1}>
                        {item.title}
                      </Text>
                      {item.description ? (
                        <Text className="text-xs text-slate-500" numberOfLines={1}>
                          {item.description}
                        </Text>
                      ) : null}
                    </View>
                    <View className="rounded-full bg-slate-100 px-2 py-0.5">
                      <Text className="text-[10px] font-medium text-slate-600 capitalize">
                        {item.category}
                      </Text>
                    </View>
                  </View>
                );
              })}
            </View>
          )}
        </View>

        {/* SECTION 2: Tâches */}
        <View className="mb-8">
          <View className="mb-3 flex-row items-center justify-between">
            <View className="flex-row items-center">
              <Ionicons name="checkbox-outline" size={20} color="#0f172a" />
              <Text className="ml-2 text-lg font-bold text-slate-900">Tâches à faire</Text>
            </View>
            <Text className="text-xs font-medium text-slate-500">
              {openTasks.length} ouverte{openTasks.length > 1 ? "s" : ""}
            </Text>
          </View>

          {/* Quick Add Task Input */}
          <View className="mb-3 flex-row items-center rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-sm">
            <TextInput
              placeholder="Ajouter une tâche rapide..."
              placeholderTextColor="#94a3b8"
              value={newTaskTitle}
              onChangeText={setNewTaskTitle}
              onSubmitEditing={handleAddTask}
              className="flex-1 text-sm text-slate-900 py-1"
            />
            <Pressable
              onPress={handleAddTask}
              disabled={addingTask || !newTaskTitle.trim()}
              className={`ml-2 h-8 w-8 items-center justify-center rounded-xl ${
                newTaskTitle.trim() ? "bg-emerald-600" : "bg-slate-200"
              }`}
            >
              {addingTask ? (
                <ActivityIndicator size="small" color="#ffffff" />
              ) : (
                <Ionicons name="arrow-up" size={18} color="#ffffff" />
              )}
            </Pressable>
          </View>

          {loading ? (
            <View className="py-6 items-center">
              <ActivityIndicator color="#10b981" />
            </View>
          ) : tasks.length === 0 ? (
            <View className="rounded-2xl border border-slate-100 bg-white p-5 items-center justify-center shadow-sm">
              <Ionicons name="checkmark-done-circle-outline" size={32} color="#10b981" />
              <Text className="mt-2 text-sm font-semibold text-slate-700">Aucune tâche</Text>
              <Text className="mt-1 text-center text-xs text-slate-400">
                {"Tu es à jour ! Ajoute une tâche ci-dessus ou via l'assistant vocal/chat."}
              </Text>
            </View>
          ) : (
            <View className="rounded-2xl border border-slate-100 bg-white p-2 shadow-sm">
              {tasks.map((task, index) => {
                const isDone = task.status === "done";
                const isLast = index === tasks.length - 1;
                const priorityColors: Record<string, { bg: string; text: string }> = {
                  urgent: { bg: "bg-red-100", text: "text-red-700" },
                  high: { bg: "bg-amber-100", text: "text-amber-700" },
                  medium: { bg: "bg-blue-100", text: "text-blue-700" },
                  low: { bg: "bg-slate-100", text: "text-slate-600" },
                };
                const badge = priorityColors[task.priority] ?? priorityColors.medium;

                return (
                  <View
                    key={task.id}
                    className={`flex-row items-center justify-between p-3 ${
                      !isLast ? "border-b border-slate-50" : ""
                    }`}
                  >
                    <Pressable
                      onPress={() => handleToggleTask(task)}
                      className="flex-row items-center flex-1 mr-2"
                    >
                      <View
                        className={`mr-3 h-6 w-6 items-center justify-center rounded-lg border ${
                          isDone
                            ? "bg-emerald-500 border-emerald-500"
                            : "border-slate-300 bg-white"
                        }`}
                      >
                        {isDone && <Ionicons name="checkmark" size={16} color="#ffffff" />}
                      </View>
                      <View className="flex-1">
                        <Text
                          className={`text-sm font-medium ${
                            isDone ? "text-slate-400 line-through" : "text-slate-900"
                          }`}
                        >
                          {task.title}
                        </Text>
                        {task.description && (
                          <Text className="text-xs text-slate-400" numberOfLines={1}>
                            {task.description}
                          </Text>
                        )}
                      </View>
                    </Pressable>

                    <View className="flex-row items-center">
                      <View className={`mr-2 rounded-md px-2 py-0.5 ${badge.bg}`}>
                        <Text className={`text-[10px] font-semibold uppercase ${badge.text}`}>
                          {task.priority}
                        </Text>
                      </View>
                      <Pressable
                        onPress={() => handleDeleteTask(task.id)}
                        className="p-1"
                        hitSlop={8}
                      >
                        <Ionicons name="trash-outline" size={16} color="#94a3b8" />
                      </Pressable>
                    </View>
                  </View>
                );
              })}
            </View>
          )}
        </View>
      </ScrollView>
    </Screen>
  );
}
