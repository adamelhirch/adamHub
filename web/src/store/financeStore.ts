import { create } from 'zustand';
import api from '../lib/api';

export type TransactionKind = 'expense' | 'income';
export type SubscriptionInterval = 'weekly' | 'monthly' | 'yearly';

export interface FinanceTransaction {
  id: number;
  kind: TransactionKind;
  amount: number;
  currency: string;
  category: string;
  note: string | null;
  occurred_at: string;
  is_recurring: boolean;
  created_at: string;
}

export interface Budget {
  id: number;
  month: string; // YYYY-MM
  category: string;
  monthly_limit: number;
  currency: string;
  alert_threshold: number;
  created_at: string;
}

export interface CategoryBudgetAnalytics {
  category: string;
  spent: number;
  limit: number;
  remaining: number;
  percentage_used: number;
  status: string; // "ok" | "warning" | "over"
}

export interface FinanceMonthSummary {
  year: number;
  month: number;
  income: number;
  expense: number;
  net: number;
  expense_by_category: Record<string, number>;
  budgets: CategoryBudgetAnalytics[];
}

export interface Subscription {
  id: number;
  name: string;
  category: string;
  amount: number;
  currency: string;
  interval: SubscriptionInterval;
  next_due_date: string;
  autopay: boolean;
  active: boolean;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubscriptionProjection {
  monthly_total: number;
  yearly_total: number;
  currency: string;
}

interface FinanceStore {
  transactions: FinanceTransaction[];
  budgets: Budget[];
  summary: FinanceMonthSummary | null;
  subscriptions: Subscription[];
  projection: SubscriptionProjection | null;
  isLoading: boolean;
  error: string | null;

  fetchTransactions: (year?: number, month?: number) => Promise<void>;
  addTransaction: (data: {
    kind: TransactionKind;
    amount: number;
    currency?: string;
    category: string;
    note?: string;
    occurred_at?: string;
    is_recurring?: boolean;
  }) => Promise<void>;

  fetchBudgets: (month?: string) => Promise<void>;
  addBudget: (data: { month: string; category: string; monthly_limit: number; currency?: string }) => Promise<void>;

  fetchSummary: (year: number, month: number) => Promise<void>;

  fetchSubscriptions: () => Promise<void>;
  addSubscription: (data: {
    name: string;
    category?: string;
    amount: number;
    currency?: string;
    interval?: SubscriptionInterval;
    next_due_date: string;
    autopay?: boolean;
    active?: boolean;
    note?: string;
  }) => Promise<Subscription>;
  fetchProjection: () => Promise<void>;
}

export const useFinanceStore = create<FinanceStore>((set, get) => ({
  transactions: [],
  budgets: [],
  summary: null,
  subscriptions: [],
  projection: null,
  isLoading: false,
  error: null,

  fetchTransactions: async (year, month) => {
    try {
      const params: Record<string, string | number> = { limit: 200 };
      if (year) params.year = year;
      if (month) params.month = month;
      const res = await api.get('/finances/transactions', { params });
      set({ transactions: res.data });
    } catch (e) {
      set({ error: 'Failed to fetch transactions' });
    }
  },

  addTransaction: async (data) => {
    try {
      const res = await api.post('/finances/transactions', data);
      set((state) => ({ transactions: [res.data, ...state.transactions] }));
    } catch (e) {
      set({ error: 'Failed to add transaction' });
    }
  },

  fetchBudgets: async (month) => {
    try {
      const params = month ? { month } : {};
      const res = await api.get('/finances/budgets', { params });
      set({ budgets: res.data });
    } catch (e) {
      set({ error: 'Failed to fetch budgets' });
    }
  },

  addBudget: async (data) => {
    try {
      const res = await api.post('/finances/budgets', data);
      set((state) => ({ budgets: [...state.budgets, res.data] }));
    } catch (e) {
      set({ error: 'Failed to add budget' });
    }
  },

  fetchSummary: async (year, month) => {
    try {
      const res = await api.get('/finances/summary', { params: { year, month } });
      set({ summary: res.data });
    } catch (e) {
      set({ error: 'Failed to fetch summary' });
    }
  },

  fetchSubscriptions: async () => {
    try {
      const res = await api.get('/subscriptions', { params: { active_only: false } });
      set({ subscriptions: res.data });
    } catch (e) {
      set({ error: 'Failed to fetch subscriptions' });
    }
  },

  addSubscription: async (data) => {
    try {
      const res = await api.post('/subscriptions', data);
      set((state) => ({
        subscriptions: [...state.subscriptions, res.data].sort((a, b) =>
          String(a.next_due_date).localeCompare(String(b.next_due_date)),
        ),
        error: null,
      }));
      await get().fetchProjection();
      return res.data;
    } catch (e) {
      set({ error: 'Failed to add subscription' });
      throw e;
    }
  },

  fetchProjection: async () => {
    try {
      const res = await api.get('/subscriptions/projection');
      set({ projection: res.data });
    } catch (e) {
      set({ error: 'Failed to fetch projection' });
    }
  },
}));
