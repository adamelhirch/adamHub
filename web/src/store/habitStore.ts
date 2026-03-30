import { create } from "zustand";
import api from "../lib/api";

export type HabitFrequency = "daily" | "weekly";

export type HabitItem = {
  id: number;
  name: string;
  description?: string | null;
  frequency: HabitFrequency;
  targetPerPeriod: number;
  scheduleTime?: string | null;
  scheduleTimes: string[];
  scheduleWeekday?: number | null;
  scheduleWeekdays: number[];
  durationMinutes: number;
  streak: number;
  active: boolean;
  createdAt: string;
  updatedAt: string;
};

export type HabitLog = {
  id: number;
  habitId: number;
  loggedAt: string;
  value: number;
  note?: string | null;
};

type HabitCreateInput = {
  name: string;
  description?: string;
  frequency?: HabitFrequency;
  targetPerPeriod?: number;
  scheduleTime?: string | null;
  scheduleTimes?: string[];
  scheduleWeekday?: number | null;
  scheduleWeekdays?: number[];
  durationMinutes?: number;
};

type HabitUpdateInput = {
  name?: string;
  description?: string | null;
  frequency?: HabitFrequency;
  targetPerPeriod?: number;
  scheduleTime?: string | null;
  scheduleTimes?: string[];
  scheduleWeekday?: number | null;
  scheduleWeekdays?: number[];
  durationMinutes?: number;
  active?: boolean;
};

interface HabitStore {
  habits: HabitItem[];
  logsByHabitId: Record<number, HabitLog[]>;
  isLoading: boolean;
  error: string | null;
  fetchHabits: (activeOnly?: boolean) => Promise<void>;
  createHabit: (payload: HabitCreateInput) => Promise<void>;
  updateHabit: (habitId: number, payload: HabitUpdateInput) => Promise<void>;
  logHabit: (habitId: number, value?: number, note?: string) => Promise<void>;
  fetchHabitLogs: (habitId: number, limit?: number) => Promise<void>;
}

function mapHabit(b: any): HabitItem {
  return {
    id: b.id,
    name: b.name,
    description: b.description ?? null,
    frequency: b.frequency,
    targetPerPeriod: b.target_per_period,
    scheduleTime: b.schedule_time ?? null,
    scheduleTimes: b.schedule_times ?? (b.schedule_time ? [b.schedule_time] : []),
    scheduleWeekday: b.schedule_weekday ?? null,
    scheduleWeekdays:
      b.schedule_weekdays ?? (b.schedule_weekday !== null && b.schedule_weekday !== undefined ? [b.schedule_weekday] : []),
    durationMinutes: b.duration_minutes ?? 30,
    streak: b.streak ?? 0,
    active: Boolean(b.active),
    createdAt: b.created_at,
    updatedAt: b.updated_at,
  };
}

function mapLog(b: any): HabitLog {
  return {
    id: b.id,
    habitId: b.habit_id,
    loggedAt: b.logged_at,
    value: b.value,
    note: b.note ?? null,
  };
}

export const useHabitStore = create<HabitStore>((set, get) => ({
  habits: [],
  logsByHabitId: {},
  isLoading: false,
  error: null,

  fetchHabits: async (activeOnly = false) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.get("/habits", {
        params: { active_only: activeOnly },
      });
      set({
        habits: response.data.map(mapHabit),
        isLoading: false,
      });
    } catch (error: any) {
      set({ error: error.message ?? "Failed to fetch habits", isLoading: false });
      console.error("Failed to fetch habits", error);
    }
  },

  createHabit: async (payload) => {
    try {
      const response = await api.post("/habits", {
        name: payload.name,
        description: payload.description || undefined,
        frequency: payload.frequency ?? "daily",
        target_per_period: payload.targetPerPeriod ?? 1,
        schedule_time: payload.scheduleTime || undefined,
        schedule_times: payload.scheduleTimes ?? [],
        schedule_weekday: payload.scheduleWeekday ?? undefined,
        schedule_weekdays: payload.scheduleWeekdays ?? [],
        duration_minutes: payload.durationMinutes ?? 30,
      });
      const created = mapHabit(response.data);
      set((state) => ({ habits: [created, ...state.habits] }));
    } catch (error) {
      console.error("Failed to create habit", error);
      throw error;
    }
  },

  updateHabit: async (habitId, payload) => {
    const optimistic = get().habits.map((habit) =>
      habit.id === habitId
        ? {
            ...habit,
            ...(payload.name !== undefined ? { name: payload.name } : {}),
            ...(payload.description !== undefined
              ? { description: payload.description }
              : {}),
            ...(payload.frequency !== undefined
              ? { frequency: payload.frequency }
              : {}),
            ...(payload.targetPerPeriod !== undefined
              ? { targetPerPeriod: payload.targetPerPeriod }
              : {}),
            ...(payload.scheduleTime !== undefined
              ? { scheduleTime: payload.scheduleTime }
              : {}),
            ...(payload.scheduleTimes !== undefined
              ? { scheduleTimes: payload.scheduleTimes }
              : {}),
            ...(payload.scheduleWeekday !== undefined
              ? { scheduleWeekday: payload.scheduleWeekday }
              : {}),
            ...(payload.scheduleWeekdays !== undefined
              ? { scheduleWeekdays: payload.scheduleWeekdays }
              : {}),
            ...(payload.durationMinutes !== undefined
              ? { durationMinutes: payload.durationMinutes }
              : {}),
            ...(payload.active !== undefined ? { active: payload.active } : {}),
          }
        : habit,
    );

    set({ habits: optimistic });

    try {
      const response = await api.patch(`/habits/${habitId}`, {
        ...(payload.name !== undefined ? { name: payload.name } : {}),
        ...(payload.description !== undefined
          ? { description: payload.description }
          : {}),
        ...(payload.frequency !== undefined
          ? { frequency: payload.frequency }
          : {}),
        ...(payload.targetPerPeriod !== undefined
          ? { target_per_period: payload.targetPerPeriod }
          : {}),
        ...(payload.scheduleTime !== undefined
          ? { schedule_time: payload.scheduleTime }
          : {}),
        ...(payload.scheduleTimes !== undefined
          ? { schedule_times: payload.scheduleTimes }
          : {}),
        ...(payload.scheduleWeekday !== undefined
          ? { schedule_weekday: payload.scheduleWeekday }
          : {}),
        ...(payload.scheduleWeekdays !== undefined
          ? { schedule_weekdays: payload.scheduleWeekdays }
          : {}),
        ...(payload.durationMinutes !== undefined
          ? { duration_minutes: payload.durationMinutes }
          : {}),
        ...(payload.active !== undefined ? { active: payload.active } : {}),
      });
      const updated = mapHabit(response.data);
      set((state) => ({
        habits: state.habits.map((habit) =>
          habit.id === habitId ? updated : habit,
        ),
      }));
    } catch (error) {
      console.error("Failed to update habit", error);
      await get().fetchHabits(false);
      throw error;
    }
  },

  logHabit: async (habitId, value = 1, note) => {
    try {
      const response = await api.post(`/habits/${habitId}/logs`, {
        value,
        note: note || undefined,
      });
      const createdLog = mapLog(response.data);
      set((state) => ({
        logsByHabitId: {
          ...state.logsByHabitId,
          [habitId]: [createdLog, ...(state.logsByHabitId[habitId] ?? [])],
        },
      }));
      await get().fetchHabits(false);
    } catch (error) {
      console.error("Failed to log habit", error);
      throw error;
    }
  },

  fetchHabitLogs: async (habitId, limit = 20) => {
    try {
      const response = await api.get(`/habits/${habitId}/logs`, {
        params: { limit },
      });
      set((state) => ({
        logsByHabitId: {
          ...state.logsByHabitId,
          [habitId]: response.data.map(mapLog),
        },
      }));
    } catch (error) {
      console.error("Failed to fetch habit logs", error);
      throw error;
    }
  },
}));
