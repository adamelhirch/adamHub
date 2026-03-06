import { useEffect, useState } from 'react';
import { API } from '../api';
import { CreditCard, TrendingUp, AlertCircle, CheckCircle2 } from 'lucide-react';
import { format } from 'date-fns';
import { fr } from 'date-fns/locale';

interface AnalyticsType {
    year: number;
    month: number;
    total_spent: number;
    total_income: number;
    total_savings: number;
    budgets: Array<{
        category_name: string;
        spent: number;
        limit: number;
        remaining: number;
        percentage_used: number;
        status: 'ok' | 'warning' | 'exceeded';
    }>;
}

export default function Dashboard() {
    const [data, setData] = useState<AnalyticsType | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const today = new Date();
        API.finances.getAnalytics(today.getFullYear(), today.getMonth() + 1)
            .then((res) => {
                setData(res);
                setLoading(false);
            })
            .catch((err) => {
                console.error(err);
                setError('Impossible de se connecter au backend Life API.');
                setLoading(false);
            });
    }, []);

    if (loading) {
        return (
            <div className="p-8 flex items-center justify-center h-full">
                <div className="animate-pulse flex flex-col items-center">
                    <div className="w-12 h-12 border-4 border-[--color-primary] border-t-transparent rounded-full animate-spin"></div>
                    <p className="mt-4 text-foreground/50 font-medium">Chargement des données...</p>
                </div>
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="p-8">
                <div className="bg-red-500/10 border border-red-500/20 rounded-2xl p-6 flex items-start gap-4">
                    <AlertCircle className="w-6 h-6 text-red-500 shrink-0" />
                    <div>
                        <h3 className="text-red-500 font-semibold text-lg">Erreur de connexion</h3>
                        <p className="text-red-500/80 mt-1">{error}</p>
                        <p className="text-sm mt-4 text-foreground/50">Vérifie que le backend FastAPI tourne sur le port 8000 et que la clé API est bonne.</p>
                    </div>
                </div>
            </div>
        );
    }

    const currentMonthName = format(new Date(), 'MMMM yyyy', { locale: fr });

    // Calcul global
    const totalBudgetLimit = data.budgets.reduce((acc, b) => acc + b.limit, 0);
    const globalPercentage = totalBudgetLimit > 0 ? (data.total_spent / totalBudgetLimit) * 100 : 0;

    return (
        <div className="p-8 max-w-6xl mx-auto space-y-8 animate-in fade-in duration-500">
            <header className="flex items-end justify-between">
                <div>
                    <h1 className="text-4xl font-bold tracking-tight">Bonjour Adam.</h1>
                    <p className="text-foreground/60 text-lg mt-1 capitalize">{currentMonthName}</p>
                </div>
            </header>

            {/* Hero Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-[--color-card] dark:bg-[--color-dark-card] rounded-3xl p-6 shadow-sm border border-[--color-border] dark:border-[--color-dark-border]">
                    <div className="flex items-center gap-3 text-foreground/60 mb-2">
                        <CreditCard className="w-5 h-5" />
                        <h2 className="font-medium">Dépenses du mois</h2>
                    </div>
                    <p className="text-4xl font-bold">{data.total_spent.toFixed(2)} €</p>
                    <div className="mt-4 h-2 w-full bg-black/5 dark:bg-white/10 rounded-full overflow-hidden">
                        <div
                            className={`h-full rounded-full ${globalPercentage > 90 ? 'bg-red-500' : globalPercentage > 75 ? 'bg-orange-500' : 'bg-[--color-primary]'}`}
                            style={{ width: `${Math.min(globalPercentage, 100)}%` }}
                        />
                    </div>
                    <p className="text-sm text-foreground/50 mt-2 text-right">{globalPercentage.toFixed(0)}% du budget total</p>
                </div>

                <div className="bg-[--color-card] dark:bg-[--color-dark-card] rounded-3xl p-6 shadow-sm border border-[--color-border] dark:border-[--color-dark-border]">
                    <div className="flex items-center gap-3 text-foreground/60 mb-2">
                        <TrendingUp className="w-5 h-5" />
                        <h2 className="font-medium">Revenus (Mois)</h2>
                    </div>
                    <p className="text-4xl font-bold text-emerald-500">{data.total_income.toFixed(2)} €</p>
                </div>

                <div className="bg-gradient-to-br from-[--color-primary] to-purple-600 rounded-3xl p-6 shadow-lg shadow-[--color-primary]/20 text-white flex flex-col justify-center">
                    <h2 className="font-medium opacity-80 mb-1">Épargne Théorique</h2>
                    <p className="text-4xl font-bold">{data.total_savings.toFixed(2)} €</p>
                    <p className="text-sm opacity-80 mt-2">Restant si aucune dépense supp.</p>
                </div>
            </div>

            {/* Budgets Section */}
            <div>
                <h2 className="text-2xl font-semibold mb-6">Suivi des Budgets</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {data.budgets.map((budget) => (
                        <div key={budget.category_name} className="bg-[--color-card] dark:bg-[--color-dark-card] rounded-2xl p-5 shadow-sm border border-[--color-border] dark:border-[--color-dark-border] flex flex-col">
                            <div className="flex justify-between items-start mb-4">
                                <h3 className="font-semibold text-lg">{budget.category_name}</h3>
                                {budget.status === 'ok' && <CheckCircle2 className="w-5 h-5 text-emerald-500" />}
                                {budget.status === 'warning' && <AlertCircle className="w-5 h-5 text-orange-500" />}
                                {budget.status === 'exceeded' && <AlertCircle className="w-5 h-5 text-red-500" />}
                            </div>

                            <p className="text-2xl font-bold mb-1">{budget.spent.toFixed(2)} €</p>
                            <p className="text-sm text-foreground/60 mb-4">sur {budget.limit.toFixed(2)} €</p>

                            <div className="mt-auto">
                                <div className="h-1.5 w-full bg-black/5 dark:bg-white/10 rounded-full overflow-hidden">
                                    <div
                                        className={`h-full rounded-full transition-all duration-1000 ${budget.status === 'exceeded' ? 'bg-red-500' : budget.status === 'warning' ? 'bg-orange-500' : 'bg-emerald-500'}`}
                                        style={{ width: `${Math.min(budget.percentage_used, 100)}%` }}
                                    />
                                </div>
                                <p className="text-xs text-right mt-2 font-medium text-foreground/50">{budget.percentage_used.toFixed(0)}% utilisé</p>
                            </div>
                        </div>
                    ))}
                    {data.budgets.length === 0 && (
                        <div className="col-span-full py-12 text-center border-2 border-dashed border-[--color-border] dark:border-[--color-dark-border] rounded-3xl">
                            <p className="text-foreground/50 font-medium">Aucun budget défini pour ce mois.</p>
                        </div>
                    )}
                </div>
            </div>

        </div>
    );
}
