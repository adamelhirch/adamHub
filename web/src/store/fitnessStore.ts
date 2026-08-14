import { create } from 'zustand';
import api from '../lib/api';

export type FitnessSessionType = 'strength' | 'cardio' | 'mobility' | 'recovery' | 'mixed';
export type FitnessSessionStatus = 'planned' | 'completed' | 'skipped';
export type FitnessExerciseMode = 'reps' | 'duration';

export type FitnessExercise = {
  name: string;
  mode: FitnessExerciseMode;
  reps: number | null;
  duration_minutes: number | null;
  note: string | null;
};

export type FitnessSession = {
  id: number;
  title: string;
  session_type: FitnessSessionType;
  planned_at: string;
  duration_minutes: number;
  exercises: FitnessExercise[];
  note: string | null;
  status: FitnessSessionStatus;
  completed_at: string | null;
  actual_duration_minutes: number | null;
  effort_rating: number | null;
  calories_burned: number | null;
  created_at: string;
  updated_at: string;
};

export type FitnessMeasurement = {
  id: number;
  recorded_at: string;
  body_weight_kg: number | null;
  body_fat_pct: number | null;
  resting_hr: number | null;
  sleep_hours: number | null;
  steps: number | null;
  note: string | null;
  created_at: string;
  updated_at: string;
};

export type FitnessStats = {
  planned_sessions: number;
  upcoming_sessions: number;
  completed_sessions_30d: number;
  completion_rate_30d: number;
  avg_duration_minutes: number | null;
  latest_body_weight_kg: number | null;
  body_weight_delta_30d: number | null;
  latest_resting_hr: number | null;
  latest_sleep_hours: number | null;
};

export type FitnessOverview = {
  stats: FitnessStats;
  upcoming_sessions: FitnessSession[];
  recent_sessions: FitnessSession[];
  measurements: FitnessMeasurement[];
};

export type FitnessSessionInput = {
  title: string;
  session_type: FitnessSessionType;
  planned_at: string;
  duration_minutes: number;
  exercises: Array<{
    name: string;
    mode: FitnessExerciseMode;
    reps: number | null;
    duration_minutes: number | null;
    note: string | null;
  }>;
  note: string | null;
};

export type FitnessMeasurementInput = {
  recorded_at: string;
  body_weight_kg: number | null;
  body_fat_pct: number | null;
  resting_hr: number | null;
  sleep_hours: number | null;
  steps: number | null;
  note: string | null;
};

interface FitnessStore {
  overview: FitnessOverview | null;
  isLoading: boolean;
  error: string | null;

  fetchOverview: () => Promise<void>;

  createSession: (data: FitnessSessionInput) => Promise<void>;
  updateSession: (id: number, data: Partial<FitnessSessionInput> & { status?: FitnessSessionStatus }) => Promise<void>;
  completeSession: (id: number) => Promise<void>;
  undoSession: (id: number) => Promise<void>;
  deleteSession: (id: number) => Promise<void>;

  createMeasurement: (data: FitnessMeasurementInput) => Promise<void>;
  updateMeasurement: (id: number, data: Partial<FitnessMeasurementInput>) => Promise<void>;
  deleteMeasurement: (id: number) => Promise<void>;
}

export const useFitnessStore = create<FitnessStore>((set, get) => ({
  overview: null,
  isLoading: false,
  error: null,

  fetchOverview: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.get('/fitness');
      set({ overview: response.data, isLoading: false });
    } catch (error) {
      set({ error: (error as Error).message ?? 'Failed to fetch fitness overview', isLoading: false });
      console.error('Failed to fetch fitness overview', error);
      throw error;
    }
  },

  createSession: async (data) => {
    try {
      await api.post('/fitness/sessions', data);
      await get().fetchOverview();
    } catch (error) {
      console.error('Failed to create fitness session', error);
      throw error;
    }
  },

  updateSession: async (id, data) => {
    try {
      await api.patch(`/fitness/sessions/${id}`, data);
      await get().fetchOverview();
    } catch (error) {
      console.error('Failed to update fitness session', error);
      throw error;
    }
  },

  completeSession: async (id) => {
    try {
      await api.post(`/fitness/sessions/${id}/complete`, {});
      await get().fetchOverview();
    } catch (error) {
      console.error('Failed to complete fitness session', error);
      throw error;
    }
  },

  undoSession: async (id) => {
    try {
      await api.patch(`/fitness/sessions/${id}`, { status: 'planned' });
      await get().fetchOverview();
    } catch (error) {
      console.error('Failed to undo fitness session', error);
      throw error;
    }
  },

  deleteSession: async (id) => {
    try {
      await api.delete(`/fitness/sessions/${id}`);
      await get().fetchOverview();
    } catch (error) {
      console.error('Failed to delete fitness session', error);
      throw error;
    }
  },

  createMeasurement: async (data) => {
    try {
      await api.post('/fitness/measurements', data);
      await get().fetchOverview();
    } catch (error) {
      console.error('Failed to create fitness measurement', error);
      throw error;
    }
  },

  updateMeasurement: async (id, data) => {
    try {
      await api.patch(`/fitness/measurements/${id}`, data);
      await get().fetchOverview();
    } catch (error) {
      console.error('Failed to update fitness measurement', error);
      throw error;
    }
  },

  deleteMeasurement: async (id) => {
    try {
      await api.delete(`/fitness/measurements/${id}`);
      await get().fetchOverview();
    } catch (error) {
      console.error('Failed to delete fitness measurement', error);
      throw error;
    }
  },
}));
