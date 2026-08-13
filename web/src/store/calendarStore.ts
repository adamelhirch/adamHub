import { create } from 'zustand';
import api from '../lib/api';

export type CalendarCategory = string;

export type CalendarSource =
  | 'manual'
  | 'task'
  | 'habit'
  | 'event'
  | 'subscription'
  | 'meal_plan'
  | 'fitness_session';

export interface CalendarItem {
  id: number;
  title: string;
  description: string | null;
  start_at: string;
  end_at: string;
  all_day: boolean;
  category: string;
  source: CalendarSource;
  source_ref_id: number | null;
  generated: boolean;
  completed: boolean;
  notification_enabled: boolean;
  reminder_offsets_min: number[];
  extra_data: Record<string, unknown>;
  last_notified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CalendarItemsQuery {
  from_at?: string;
  to_at?: string;
  category?: string;
  source?: CalendarSource;
  include_completed?: boolean;
  generated_only?: boolean;
  limit?: number;
}

export interface CalendarItemCreateInput {
  title: string;
  description?: string | null;
  start_at: string;
  end_at: string;
  all_day?: boolean;
  category?: string;
  notification_enabled?: boolean;
  reminder_offsets_min?: number[];
  extra_data?: Record<string, unknown>;
}

interface CalendarStore {
  items: CalendarItem[];
  isLoading: boolean;
  error: string | null;

  fetchItems: (query?: CalendarItemsQuery) => Promise<void>;
  createItem: (data: CalendarItemCreateInput) => Promise<void>;
  updateItem: (id: number, data: Partial<CalendarItemCreateInput>) => Promise<void>;
  deleteItem: (id: number) => Promise<void>;
}

export const useCalendarStore = create<CalendarStore>((set, get) => ({
  items: [],
  isLoading: false,
  error: null,

  fetchItems: async (query = {}) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.get('/calendar/items', {
        params: {
          include_completed: true,
          limit: 1000,
          ...query,
        },
      });
      set({ items: response.data, isLoading: false });
    } catch (error: any) {
      set({ error: error.message ?? 'Failed to fetch calendar items', isLoading: false });
      console.error('Failed to fetch calendar items', error);
    }
  },

  createItem: async (data) => {
    try {
      const response = await api.post('/calendar/items', data);
      set((state) => ({ items: [...state.items, response.data] }));
    } catch (error) {
      console.error('Failed to create calendar item', error);
      throw error;
    }
  },

  updateItem: async (id, data) => {
    set((state) => ({
      items: state.items.map((item) =>
        item.id === id ? { ...item, ...data } as CalendarItem : item,
      ),
    }));

    try {
      const response = await api.patch(`/calendar/items/${id}`, data);
      set((state) => ({
        items: state.items.map((item) => (item.id === id ? response.data : item)),
      }));
    } catch (error) {
      console.error('Failed to update calendar item', error);
      await get().fetchItems();
      throw error;
    }
  },

  deleteItem: async (id) => {
    const previousItems = get().items;
    set((state) => ({ items: state.items.filter((item) => item.id !== id) }));

    try {
      await api.delete(`/calendar/items/${id}`);
    } catch (error) {
      console.error('Failed to delete calendar item', error);
      set({ items: previousItems });
      throw error;
    }
  },
}));
