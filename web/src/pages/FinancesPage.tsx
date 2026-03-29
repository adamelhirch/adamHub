import { useState, useEffect } from 'react';
import { format, differenceInDays } from 'date-fns';
import {
  TrendingUp, TrendingDown, CreditCard, Plus, X, Calendar, RefreshCw, Zap, AlertTriangle, CheckCircle, Landmark, Target, Pencil, Check, Trash2
} from 'lucide-react';
import { useFinanceStore } from '../store/financeStore';
import type { TransactionKind } from '../store/financeStore';
import { usePatrimonyStore } from '../store/patrimonyStore';
import type { AccountType } from '../store/patrimonyStore';

// ─── Helpers ────────────────────────────────────────────────────────────────
const fmtEur = (n: number) =>
  new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', minimumFractionDigits: 2 }).format(n);

const CATEGORY_COLORS: Record<string, string> = {
  Housing: '#6366f1', Food: '#f59e0b', Transport: '#10b981', Health: '#ef4444',
  Entertainment: '#8b5cf6', Shopping: '#ec4899', Utilities: '#06b6d4',
  Education: '#84cc16', Salary: '#22c55e', Freelance: '#14b8a6', Other: '#94a3b8',
};

function getColor(cat: string) {
  return CATEGORY_COLORS[cat] ?? '#94a3b8';
}

const TAB_LIST = ['Overview', 'Transactions', 'Subscriptions', 'Patrimoine'] as const;
type Tab = (typeof TAB_LIST)[number];

const ACCOUNT_TYPE_LABELS: Record<AccountType, string> = {
  checking: 'Compte courant', savings: 'Épargne', investment: 'Investissement', crypto: 'Crypto', other: 'Autre',
};
const ACCOUNT_TYPE_COLORS: Record<AccountType, string> = {
  checking: '#6366f1', savings: '#10b981', investment: '#f59e0b', crypto: '#8b5cf6', other: '#94a3b8',
};

// ─── Sub-components ──────────────────────────────────────────────────────────
function SummaryCard({ label, value, sub, icon, green }: { label: string; value: string; sub?: string; icon: React.ReactNode; green?: boolean }) {
  return (
    <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm p-5 flex items-center gap-4">
      <div className={`p-3 rounded-xl ${green ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-500'}`}>
        {icon}
      </div>
      <div>
        <p className="text-xs font-semibold text-apple-gray-500 uppercase tracking-wider">{label}</p>
        <p className={`text-2xl font-bold mt-0.5 ${green ? 'text-emerald-600' : 'text-red-500'}`}>{value}</p>
        {sub && <p className="text-xs text-apple-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function BudgetBar({ category, spent, limit, percentage_used, status }: {
  category: string; spent: number; limit: number; percentage_used: number; status: string;
}) {
  const pct = Math.min(percentage_used, 100);
  const barColor = status === 'over' ? 'bg-red-500' : status === 'warning' ? 'bg-amber-400' : 'bg-emerald-500';
  const StatusIcon = status === 'over' ? AlertTriangle : status === 'warning' ? AlertTriangle : CheckCircle;
  const statusColor = status === 'over' ? 'text-red-500' : status === 'warning' ? 'text-amber-500' : 'text-emerald-500';
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2 font-medium text-black">
          <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: getColor(category) }} />
          {category}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-apple-gray-500">{fmtEur(spent)} / {fmtEur(limit)}</span>
          <StatusIcon className={`w-3.5 h-3.5 ${statusColor}`} />
        </div>
      </div>
      <div className="w-full h-2 rounded-full bg-apple-gray-100">
        <div className={`h-2 rounded-full transition-all ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function FinancesPage() {
  const {
    transactions, summary, subscriptions, projection,
    fetchTransactions, addTransaction, fetchBudgets, addBudget,
    fetchSummary, fetchSubscriptions, fetchProjection,
  } = useFinanceStore();
  const { overview, fetchOverview, addAccount, updateAccount, deleteAccount, addGoal, updateGoal, deleteGoal } = usePatrimonyStore();


  const now = new Date();
  const [activeTab, setActiveTab] = useState<Tab>('Overview');
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(now.getMonth() + 1);

  // Add-Transaction form state
  const [showTxForm, setShowTxForm] = useState(false);
  const [txKind, setTxKind] = useState<TransactionKind>('expense');
  const [txAmount, setTxAmount] = useState('');
  const [txCategory, setTxCategory] = useState('');
  const [txNote, setTxNote] = useState('');
  const [txDate, setTxDate] = useState(format(new Date(), 'yyyy-MM-dd'));

  // Add-Budget form state
  const [showBudgetForm, setShowBudgetForm] = useState(false);
  const [budgetCategory, setBudgetCategory] = useState('');
  const [budgetLimit, setBudgetLimit] = useState('');

  const monthStr = `${selectedYear}-${String(selectedMonth).padStart(2, '0')}`;

  useEffect(() => {
    fetchTransactions(selectedYear, selectedMonth);
    fetchSummary(selectedYear, selectedMonth);
    fetchBudgets(monthStr);
  }, [selectedYear, selectedMonth]);

  useEffect(() => {
    fetchSubscriptions();
    fetchProjection();
    fetchOverview();
  }, []);

  // Patrimoine state
  const [showAccForm, setShowAccForm] = useState(false);
  const [accName, setAccName] = useState('');
  const [accType, setAccType] = useState<AccountType>('savings');
  const [accBalance, setAccBalance] = useState('');
  const [accInstitution, setAccInstitution] = useState('');
  const [editingAccId, setEditingAccId] = useState<number | null>(null);
  const [editingAccBalance, setEditingAccBalance] = useState('');

  const [showGoalForm, setShowGoalForm] = useState(false);
  const [goalTitle, setGoalTitle] = useState('');
  const [goalTarget, setGoalTarget] = useState('');
  const [goalCurrent, setGoalCurrent] = useState('');
  const [goalDate, setGoalDate] = useState('');

  const handleAddAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!accName || !accBalance) return;
    await addAccount({ name: accName, account_type: accType, balance: parseFloat(accBalance), institution: accInstitution || undefined });
    setAccName(''); setAccBalance(''); setAccInstitution(''); setShowAccForm(false);
  };

  const handleSaveBalance = async (id: number) => {
    const val = parseFloat(editingAccBalance);
    if (isNaN(val)) return;
    await updateAccount(id, { balance: val });
    setEditingAccId(null);
  };

  const handleAddGoal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!goalTitle || !goalTarget) return;
    await addGoal({
      title: goalTitle,
      target_amount: parseFloat(goalTarget),
      current_amount: goalCurrent ? parseFloat(goalCurrent) : 0,
      target_date: goalDate || undefined,
    });
    setGoalTitle(''); setGoalTarget(''); setGoalCurrent(''); setGoalDate(''); setShowGoalForm(false);
  };

  const handleAddTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!txAmount || !txCategory) return;
    await addTransaction({
      kind: txKind,
      amount: parseFloat(txAmount),
      category: txCategory,
      note: txNote || undefined,
      occurred_at: new Date(txDate).toISOString(),
    });
    setTxAmount(''); setTxCategory(''); setTxNote(''); setShowTxForm(false);
  };

  const handleAddBudget = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!budgetCategory || !budgetLimit) return;
    await addBudget({ month: monthStr, category: budgetCategory, monthly_limit: parseFloat(budgetLimit) });
    setBudgetCategory(''); setBudgetLimit(''); setShowBudgetForm(false);
  };

  const intervalLabel: Record<string, string> = { weekly: '/sem', monthly: '/mois', yearly: '/an' };

  return (
    <div className="flex-1 flex flex-col h-full bg-apple-gray-50 overflow-hidden">
      {/* Header */}
      <div className="px-8 py-5 border-b border-apple-gray-200 bg-white shadow-sm z-10 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-black">Finances</h1>
          <p className="text-apple-gray-500 mt-0.5 text-sm">Suivez vos dépenses et revenus</p>
        </div>
        {/* Month picker */}
        <div className="flex items-center gap-2">
          <input
            type="month"
            value={monthStr}
            onChange={(e) => {
              const [y, m] = e.target.value.split('-').map(Number);
              setSelectedYear(y); setSelectedMonth(m);
            }}
            className="px-4 py-2 rounded-xl border border-apple-gray-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
          />
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-apple-gray-200 bg-white px-8">
        <div className="flex gap-1">
          {TAB_LIST.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-5 py-3 text-sm font-semibold border-b-2 transition-colors ${
                activeTab === tab
                  ? 'border-apple-blue text-apple-blue'
                  : 'border-transparent text-apple-gray-500 hover:text-black'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-6">

          {/* ── OVERVIEW TAB ─────────────────────────────────────── */}
          {activeTab === 'Overview' && (
            <>
              {/* Summary cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <SummaryCard
                  label="Revenus"
                  value={fmtEur(summary?.income ?? 0)}
                  icon={<TrendingUp className="w-5 h-5" />}
                  green
                />
                <SummaryCard
                  label="Dépenses"
                  value={fmtEur(summary?.expense ?? 0)}
                  icon={<TrendingDown className="w-5 h-5" />}
                  green={false}
                />
                <SummaryCard
                  label="Solde Net"
                  value={fmtEur(summary?.net ?? 0)}
                  icon={<CreditCard className="w-5 h-5" />}
                  green={(summary?.net ?? 0) >= 0}
                />
              </div>

              {/* Budgets */}
              <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm p-6">
                <div className="flex items-center justify-between mb-5">
                  <h2 className="text-base font-semibold text-black">Budgets — {monthStr}</h2>
                  <button
                    onClick={() => setShowBudgetForm(!showBudgetForm)}
                    className="flex items-center gap-1.5 text-sm font-medium text-apple-blue hover:text-blue-700 transition-colors"
                  >
                    <Plus className="w-4 h-4" />
                    Ajouter
                  </button>
                </div>

                {showBudgetForm && (
                  <form onSubmit={handleAddBudget} className="mb-5 flex flex-wrap gap-3 p-4 bg-apple-gray-50 rounded-xl border border-apple-gray-200">
                    <input
                      type="text" placeholder="Catégorie (ex: Food)" value={budgetCategory}
                      onChange={(e) => setBudgetCategory(e.target.value)}
                      className="flex-1 min-w-[120px] px-3 py-2 rounded-lg border border-apple-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                    />
                    <div className="relative w-28">
                      <input
                        type="number" placeholder="Limite" value={budgetLimit}
                        onChange={(e) => setBudgetLimit(e.target.value)} min="0" step="0.01"
                        className="w-full pl-3 pr-7 py-2 rounded-lg border border-apple-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                      />
                      <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-apple-gray-400">€</span>
                    </div>
                    <button type="submit" className="px-4 py-2 bg-apple-blue text-white text-sm font-medium rounded-lg hover:bg-blue-600 transition-colors">
                      Ajouter
                    </button>
                    <button type="button" onClick={() => setShowBudgetForm(false)} className="p-2 text-apple-gray-400 hover:text-black rounded-lg transition-colors">
                      <X className="w-4 h-4" />
                    </button>
                  </form>
                )}

                {summary?.budgets && summary.budgets.length > 0 ? (
                  <div className="space-y-4">
                    {summary.budgets.map((b) => <BudgetBar key={b.category} {...b} />)}
                  </div>
                ) : (
                  <p className="text-center text-apple-gray-400 py-8 text-sm">Aucun budget défini pour ce mois.</p>
                )}
              </div>

              {/* Expenses by category */}
              {summary?.expense_by_category && Object.keys(summary.expense_by_category).length > 0 && (
                <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm p-6">
                  <h2 className="text-base font-semibold text-black mb-4">Dépenses par catégorie</h2>
                  <div className="space-y-3">
                    {Object.entries(summary.expense_by_category)
                      .sort(([, a], [, b]) => b - a)
                      .map(([cat, amount]) => {
                        const pct = summary.expense > 0 ? (amount / summary.expense) * 100 : 0;
                        return (
                          <div key={cat} className="flex items-center gap-3">
                            <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: getColor(cat) }} />
                            <span className="text-sm font-medium text-black flex-1">{cat}</span>
                            <span className="text-sm text-apple-gray-500 w-24 text-right">{fmtEur(amount)}</span>
                            <div className="w-24 h-2 bg-apple-gray-100 rounded-full">
                              <div className="h-2 rounded-full" style={{ width: `${pct}%`, background: getColor(cat) }} />
                            </div>
                          </div>
                        );
                      })}
                  </div>
                </div>
              )}
            </>
          )}

          {/* ── TRANSACTIONS TAB ──────────────────────────────────── */}
          {activeTab === 'Transactions' && (
            <>
              {/* Add transaction button */}
              <div className="flex justify-end">
                <button
                  onClick={() => setShowTxForm(!showTxForm)}
                  className="flex items-center gap-2 px-5 py-2.5 bg-apple-blue text-white text-sm font-semibold rounded-xl hover:bg-blue-600 transition-colors shadow-sm"
                >
                  <Plus className="w-4 h-4" />
                  Nouvelle transaction
                </button>
              </div>

              {/* Add transaction form */}
              {showTxForm && (
                <form onSubmit={handleAddTransaction} className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm p-5 space-y-4">
                  <h3 className="text-sm font-semibold text-black">Ajouter une transaction</h3>
                  {/* Kind toggle */}
                  <div className="flex rounded-xl overflow-hidden border border-apple-gray-200 w-fit">
                    {(['expense', 'income'] as TransactionKind[]).map((k) => (
                      <button
                        key={k} type="button" onClick={() => setTxKind(k)}
                        className={`px-5 py-2 text-sm font-semibold transition-colors ${
                          txKind === k
                            ? k === 'expense' ? 'bg-red-500 text-white' : 'bg-emerald-500 text-white'
                            : 'text-apple-gray-500 hover:bg-apple-gray-50'
                        }`}
                      >
                        {k === 'expense' ? '− Dépense' : '+ Revenu'}
                      </button>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <div className="relative w-36">
                      <input
                        type="number" placeholder="Montant" value={txAmount}
                        onChange={(e) => setTxAmount(e.target.value)} min="0" step="0.01" required
                        className="w-full pl-3 pr-7 py-2.5 rounded-xl border border-apple-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-apple-gray-400">€</span>
                    </div>
                    <input
                      type="text" placeholder="Catégorie (ex: Food)" value={txCategory}
                      onChange={(e) => setTxCategory(e.target.value)} required
                      className="flex-1 min-w-[140px] px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                    />
                    <input
                      type="text" placeholder="Note (optionnel)" value={txNote}
                      onChange={(e) => setTxNote(e.target.value)}
                      className="flex-1 min-w-[140px] px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                    />
                    <input
                      type="date" value={txDate}
                      onChange={(e) => setTxDate(e.target.value)}
                      className="px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                    />
                  </div>
                  <div className="flex gap-3">
                    <button type="submit" className="px-5 py-2.5 bg-apple-blue text-white text-sm font-semibold rounded-xl hover:bg-blue-600 transition-colors">
                      Ajouter
                    </button>
                    <button type="button" onClick={() => setShowTxForm(false)} className="px-5 py-2.5 text-sm font-medium text-apple-gray-500 hover:bg-apple-gray-100 rounded-xl transition-colors">
                      Annuler
                    </button>
                  </div>
                </form>
              )}

              {/* Transactions list */}
              <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm overflow-hidden divide-y divide-apple-gray-100">
                {transactions.length === 0 ? (
                  <p className="text-center text-apple-gray-400 py-12 text-sm">Aucune transaction pour ce mois.</p>
                ) : (
                  transactions.map((tx) => (
                    <div key={tx.id} className="flex items-center px-5 py-4 hover:bg-apple-gray-50 transition-colors gap-3">
                      <div className={`text-xs font-bold px-2.5 py-1 rounded-lg shrink-0 ${
                        tx.kind === 'expense' ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-600'
                      }`}>
                        {tx.kind === 'expense' ? 'OUT' : 'IN'}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-black truncate">{tx.category}</p>
                        {tx.note && <p className="text-xs text-apple-gray-400 mt-0.5 truncate">{tx.note}</p>}
                      </div>
                      <div className="shrink-0 text-right">
                        <p className={`text-base font-bold ${tx.kind === 'expense' ? 'text-red-500' : 'text-emerald-600'}`}>
                          {tx.kind === 'expense' ? '−' : '+'}{fmtEur(tx.amount)}
                        </p>
                        <p className="text-[10px] text-apple-gray-400 mt-0.5">
                          {format(new Date(tx.occurred_at), 'dd/MM/yyyy')}
                        </p>
                      </div>
                      {tx.is_recurring && (
                        <div title="Récurrent" className="shrink-0 text-apple-gray-400"><RefreshCw className="w-3.5 h-3.5" /></div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </>
          )}

          {/* ── SUBSCRIPTIONS TAB ─────────────────────────────────── */}
          {activeTab === 'Subscriptions' && (
            <>
              {/* Projection summary */}
              {projection && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm p-5">
                    <p className="text-xs font-semibold text-apple-gray-500 uppercase tracking-wider">Total mensuel</p>
                    <p className="text-2xl font-bold text-black mt-1">{fmtEur(projection.monthly_total)}</p>
                  </div>
                  <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm p-5">
                    <p className="text-xs font-semibold text-apple-gray-500 uppercase tracking-wider">Total annuel</p>
                    <p className="text-2xl font-bold text-black mt-1">{fmtEur(projection.yearly_total)}</p>
                  </div>
                </div>
              )}

              {/* Subscriptions list */}
              <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm overflow-hidden divide-y divide-apple-gray-100">
                {subscriptions.length === 0 ? (
                  <p className="text-center text-apple-gray-400 py-12 text-sm">Aucun abonnement enregistré.</p>
                ) : (
                  subscriptions.map((sub) => {
                    const daysUntil = Math.ceil(
                      (new Date(sub.next_due_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
                    );
                    const isUrgent = daysUntil <= 7;
                    return (
                      <div key={sub.id} className={`flex items-center px-5 py-4 hover:bg-apple-gray-50 transition-colors gap-3 ${!sub.active ? 'opacity-50' : ''}`}>
                        <div className={`p-2.5 rounded-xl shrink-0 ${isUrgent ? 'bg-amber-50 text-amber-500' : 'bg-apple-gray-100 text-apple-gray-400'}`}>
                          <Zap className="w-4 h-4" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-semibold text-black truncate">{sub.name}</p>
                            {!sub.active && <span className="text-[10px] font-bold text-apple-gray-400 bg-apple-gray-100 px-1.5 py-0.5 rounded uppercase">Inactif</span>}
                            {sub.autopay && <span className="text-[10px] font-bold text-apple-blue bg-apple-blue/10 px-1.5 py-0.5 rounded uppercase">Auto</span>}
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-xs text-apple-gray-400">{sub.category}</span>
                            <span className="w-1 h-1 rounded-full bg-apple-gray-300" />
                            <span className={`text-xs font-medium ${isUrgent ? 'text-amber-600' : 'text-apple-gray-500'}`}>
                              <Calendar className="w-3 h-3 inline mr-0.5" />
                              {format(new Date(sub.next_due_date), 'dd/MM/yyyy')}
                              {isUrgent && ` · J-${daysUntil}`}
                            </span>
                          </div>
                        </div>
                        <div className="shrink-0 text-right">
                          <p className="text-base font-bold text-black">{fmtEur(sub.amount)}</p>
                          <p className="text-xs text-apple-gray-400">{intervalLabel[sub.interval] ?? sub.interval}</p>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </>
          )}

          {/* ── PATRIMOINE TAB ─────────────────────────────────── */}
          {activeTab === 'Patrimoine' && (
            <>
              {/* Net worth banner */}
              <div className="bg-gradient-to-br from-indigo-600 to-violet-600 rounded-2xl p-6 text-white shadow-lg">
                <p className="text-xs font-semibold uppercase tracking-widest text-indigo-200 mb-1">Patrimoine net</p>
                <p className="text-4xl font-black tracking-tight">{new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(overview?.net_worth ?? 0)}</p>
                <p className="text-indigo-200 text-xs mt-2">{overview?.accounts.filter(a => a.is_active).length ?? 0} compte(s) actif(s)</p>
              </div>

              {/* Accounts */}
              <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm p-6">
                <div className="flex items-center justify-between mb-5">
                  <h2 className="text-base font-semibold text-black flex items-center gap-2"><Landmark className="w-4 h-4" />Comptes</h2>
                  <button onClick={() => setShowAccForm(!showAccForm)} className="flex items-center gap-1.5 text-sm font-medium text-apple-blue hover:text-blue-700">
                    <Plus className="w-4 h-4" />Ajouter
                  </button>
                </div>

                {showAccForm && (
                  <form onSubmit={handleAddAccount} className="mb-5 grid grid-cols-2 gap-3 p-4 bg-apple-gray-50 rounded-xl border border-apple-gray-200">
                    <input type="text" placeholder="Nom (ex: Livret A)" value={accName} onChange={e => setAccName(e.target.value)} required
                      className="col-span-2 px-3 py-2 rounded-lg border border-apple-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50" />
                    <select value={accType} onChange={e => setAccType(e.target.value as AccountType)}
                      className="px-3 py-2 rounded-lg border border-apple-gray-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-apple-blue/50">
                      {(Object.keys(ACCOUNT_TYPE_LABELS) as AccountType[]).map(t => (
                        <option key={t} value={t}>{ACCOUNT_TYPE_LABELS[t]}</option>
                      ))}
                    </select>
                    <div className="relative">
                      <input type="number" placeholder="Solde" value={accBalance} onChange={e => setAccBalance(e.target.value)} min="0" step="0.01" required
                        className="w-full pl-3 pr-7 py-2 rounded-lg border border-apple-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50" />
                      <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-apple-gray-400">€</span>
                    </div>
                    <input type="text" placeholder="Banque (optionnel)" value={accInstitution} onChange={e => setAccInstitution(e.target.value)}
                      className="col-span-2 px-3 py-2 rounded-lg border border-apple-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50" />
                    <div className="col-span-2 flex gap-2">
                      <button type="submit" className="px-4 py-2 bg-apple-blue text-white text-sm font-semibold rounded-lg hover:bg-blue-600 transition-colors">Ajouter</button>
                      <button type="button" onClick={() => setShowAccForm(false)} className="p-2 text-apple-gray-400 hover:text-black rounded-lg"><X className="w-4 h-4" /></button>
                    </div>
                  </form>
                )}

                {!overview?.accounts.length ? (
                  <p className="text-center text-apple-gray-400 py-8 text-sm">Aucun compte enregistré.</p>
                ) : (
                  <div className="space-y-3">
                    {overview.accounts.map(acc => (
                      <div key={acc.id} className="flex items-center gap-3 p-3 rounded-xl hover:bg-apple-gray-50 transition-colors group">
                        <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0" style={{ background: ACCOUNT_TYPE_COLORS[acc.account_type] + '20', color: ACCOUNT_TYPE_COLORS[acc.account_type] }}>
                          <Landmark className="w-4 h-4" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-black truncate">{acc.name}</p>
                          <p className="text-xs text-apple-gray-400">{ACCOUNT_TYPE_LABELS[acc.account_type]}{acc.institution ? ` · ${acc.institution}` : ''}</p>
                        </div>
                        {editingAccId === acc.id ? (
                          <div className="flex items-center gap-1.5">
                            <div className="relative">
                              <input type="number" value={editingAccBalance} onChange={e => setEditingAccBalance(e.target.value)} step="0.01"
                                autoFocus className="w-28 pl-3 pr-6 py-1.5 rounded-lg border border-apple-blue text-sm focus:outline-none" />
                              <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-apple-gray-400">€</span>
                            </div>
                            <button onClick={() => handleSaveBalance(acc.id)} className="p-1.5 text-emerald-600 hover:bg-emerald-50 rounded-lg"><Check className="w-4 h-4" /></button>
                            <button onClick={() => setEditingAccId(null)} className="p-1.5 text-apple-gray-400 hover:bg-apple-gray-100 rounded-lg"><X className="w-4 h-4" /></button>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            <p className="text-base font-bold text-black">{fmtEur(acc.balance)}</p>
                            <button onClick={() => { setEditingAccId(acc.id); setEditingAccBalance(String(acc.balance)); }} className="opacity-0 group-hover:opacity-100 p-1.5 text-apple-gray-400 hover:text-apple-blue hover:bg-apple-blue/10 rounded-lg transition-all">
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={() => deleteAccount(acc.id)} className="opacity-0 group-hover:opacity-100 p-1.5 text-apple-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all">
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Savings Goals */}
              <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm p-6">
                <div className="flex items-center justify-between mb-5">
                  <h2 className="text-base font-semibold text-black flex items-center gap-2"><Target className="w-4 h-4" />Objectifs d'épargne</h2>
                  <button onClick={() => setShowGoalForm(!showGoalForm)} className="flex items-center gap-1.5 text-sm font-medium text-apple-blue hover:text-blue-700">
                    <Plus className="w-4 h-4" />Ajouter
                  </button>
                </div>

                {showGoalForm && (
                  <form onSubmit={handleAddGoal} className="mb-5 grid grid-cols-2 gap-3 p-4 bg-apple-gray-50 rounded-xl border border-apple-gray-200">
                    <input type="text" placeholder="Objectif (ex: Vacances été)" value={goalTitle} onChange={e => setGoalTitle(e.target.value)} required
                      className="col-span-2 px-3 py-2 rounded-lg border border-apple-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50" />
                    <div className="relative">
                      <input type="number" placeholder="Montant cible" value={goalTarget} onChange={e => setGoalTarget(e.target.value)} min="0" step="1" required
                        className="w-full pl-3 pr-7 py-2 rounded-lg border border-apple-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50" />
                      <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-apple-gray-400">€</span>
                    </div>
                    <div className="relative">
                      <input type="number" placeholder="Déjà épargné" value={goalCurrent} onChange={e => setGoalCurrent(e.target.value)} min="0" step="1"
                        className="w-full pl-3 pr-7 py-2 rounded-lg border border-apple-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50" />
                      <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-apple-gray-400">€</span>
                    </div>
                    <input type="date" placeholder="Date cible" value={goalDate} onChange={e => setGoalDate(e.target.value)}
                      className="col-span-2 px-3 py-2 rounded-lg border border-apple-gray-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-apple-blue/50" />
                    <div className="col-span-2 flex gap-2">
                      <button type="submit" className="px-4 py-2 bg-apple-blue text-white text-sm font-semibold rounded-lg hover:bg-blue-600 transition-colors">Ajouter</button>
                      <button type="button" onClick={() => setShowGoalForm(false)} className="p-2 text-apple-gray-400 hover:text-black rounded-lg"><X className="w-4 h-4" /></button>
                    </div>
                  </form>
                )}

                {!overview?.goals.length ? (
                  <p className="text-center text-apple-gray-400 py-8 text-sm">Aucun objectif défini.</p>
                ) : (
                  <div className="space-y-4">
                    {overview.goals.map(goal => {
                      const pct = Math.min((goal.current_amount / goal.target_amount) * 100, 100);
                      const daysLeft = goal.target_date ? differenceInDays(new Date(goal.target_date), new Date()) : null;
                      const isLate = daysLeft !== null && daysLeft < 0;
                      return (
                        <div key={goal.id} className={`p-4 rounded-xl border transition-colors group ${goal.completed ? 'border-emerald-200 bg-emerald-50' : 'border-apple-gray-200 hover:bg-apple-gray-50'}`}>
                          <div className="flex items-start justify-between gap-2 mb-3">
                            <div className="flex-1 min-w-0">
                              <p className={`text-sm font-semibold truncate ${goal.completed ? 'line-through text-apple-gray-400' : 'text-black'}`}>{goal.title}</p>
                              {goal.target_date && (
                                <p className={`text-xs mt-0.5 ${isLate ? 'text-red-500' : 'text-apple-gray-400'}`}>
                                  <Calendar className="w-3 h-3 inline mr-0.5" />
                                  {format(new Date(goal.target_date), 'dd/MM/yyyy')}
                                  {daysLeft !== null && !goal.completed && (
                                    <span className="ml-1">{isLate ? `· ${Math.abs(daysLeft)}j de retard` : `· J-${daysLeft}`}</span>
                                  )}
                                </p>
                              )}
                            </div>
                            <div className="flex items-center gap-1 shrink-0">
                              {!goal.completed && (
                                <button onClick={() => updateGoal(goal.id, { completed: true })} className="opacity-0 group-hover:opacity-100 p-1.5 text-emerald-500 hover:bg-emerald-50 rounded-lg transition-all" title="Marquer comme atteint">
                                  <Check className="w-3.5 h-3.5" />
                                </button>
                              )}
                              <button onClick={() => deleteGoal(goal.id)} className="opacity-0 group-hover:opacity-100 p-1.5 text-apple-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all">
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>
                          <div className="flex items-center justify-between text-xs text-apple-gray-500 mb-1.5">
                            <span className="font-semibold text-black">{fmtEur(goal.current_amount)}</span>
                            <span>{Math.round(pct)}% — objectif : {fmtEur(goal.target_amount)}</span>
                          </div>
                          <div className="w-full h-2.5 rounded-full bg-apple-gray-100">
                            <div className={`h-2.5 rounded-full transition-all ${goal.completed ? 'bg-emerald-500' : pct >= 100 ? 'bg-emerald-500' : pct >= 60 ? 'bg-amber-400' : 'bg-apple-blue'}`}
                              style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          )}

        </div>
      </div>
    </div>
  );
}
