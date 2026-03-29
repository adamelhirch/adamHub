import { create } from 'zustand';
import api from '../lib/api';

export type AccountType = 'checking' | 'savings' | 'investment' | 'crypto' | 'other';

export interface Account {
  id: number;
  name: string;
  account_type: AccountType;
  balance: number;
  currency: string;
  institution: string | null;
  note: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SavingsGoal {
  id: number;
  title: string;
  target_amount: number;
  current_amount: number;
  currency: string;
  target_date: string | null;
  account_id: number | null;
  note: string | null;
  completed: boolean;
  created_at: string;
  updated_at: string;
}

export interface PatrimoineOverview {
  net_worth: number;
  currency: string;
  accounts: Account[];
  goals: SavingsGoal[];
}

interface PatrimonyStore {
  overview: PatrimoineOverview | null;
  isLoading: boolean;
  error: string | null;

  fetchOverview: () => Promise<void>;

  addAccount: (data: {
    name: string;
    account_type: AccountType;
    balance: number;
    currency?: string;
    institution?: string;
    note?: string;
  }) => Promise<void>;

  updateAccount: (id: number, data: Partial<Pick<Account, 'name' | 'balance' | 'institution' | 'note' | 'is_active' | 'account_type'>>) => Promise<void>;

  deleteAccount: (id: number) => Promise<void>;

  addGoal: (data: {
    title: string;
    target_amount: number;
    current_amount?: number;
    currency?: string;
    target_date?: string;
    account_id?: number;
    note?: string;
  }) => Promise<void>;

  updateGoal: (id: number, data: Partial<Pick<SavingsGoal, 'title' | 'target_amount' | 'current_amount' | 'target_date' | 'account_id' | 'note' | 'completed'>>) => Promise<void>;

  deleteGoal: (id: number) => Promise<void>;
}

export const usePatrimonyStore = create<PatrimonyStore>((set) => ({
  overview: null,
  isLoading: false,
  error: null,

  fetchOverview: async () => {
    set({ isLoading: true, error: null });
    try {
      const res = await api.get('/patrimony/overview');
      set({ overview: res.data, isLoading: false });
    } catch {
      set({ error: 'Failed to fetch overview', isLoading: false });
    }
  },

  addAccount: async (data) => {
    const res = await api.post('/patrimony/accounts', data);
    const newAccount: Account = res.data;
    set((state) => {
      if (!state.overview) return state;
      const accounts = [...state.overview.accounts, newAccount];
      const net_worth = accounts.reduce((s, a) => s + (a.is_active ? a.balance : 0), 0);
      return { overview: { ...state.overview, accounts, net_worth } };
    });
  },

  updateAccount: async (id, data) => {
    const res = await api.patch(`/patrimony/accounts/${id}`, data);
    const updated: Account = res.data;
    set((state) => {
      if (!state.overview) return state;
      const accounts = state.overview.accounts.map((a) => (a.id === id ? updated : a));
      const net_worth = accounts.reduce((s, a) => s + (a.is_active ? a.balance : 0), 0);
      return { overview: { ...state.overview, accounts, net_worth } };
    });
  },

  deleteAccount: async (id) => {
    await api.delete(`/patrimony/accounts/${id}`);
    set((state) => {
      if (!state.overview) return state;
      const accounts = state.overview.accounts.filter((a) => a.id !== id);
      const net_worth = accounts.reduce((s, a) => s + (a.is_active ? a.balance : 0), 0);
      return { overview: { ...state.overview, accounts, net_worth } };
    });
  },

  addGoal: async (data) => {
    const res = await api.post('/patrimony/goals', data);
    set((state) => {
      if (!state.overview) return state;
      return { overview: { ...state.overview, goals: [...state.overview.goals, res.data] } };
    });
  },

  updateGoal: async (id, data) => {
    const res = await api.patch(`/patrimony/goals/${id}`, data);
    set((state) => {
      if (!state.overview) return state;
      return { overview: { ...state.overview, goals: state.overview.goals.map((g) => (g.id === id ? res.data : g)) } };
    });
  },

  deleteGoal: async (id) => {
    await api.delete(`/patrimony/goals/${id}`);
    set((state) => {
      if (!state.overview) return state;
      return { overview: { ...state.overview, goals: state.overview.goals.filter((g) => g.id !== id) } };
    });
  },
}));
