import { useEffect, useState, type ReactNode } from 'react';
import {
  CalendarClock,
  CheckCircle2,
  Clock3,
  HeartPulse,
  Loader2,
  PencilLine,
  Plus,
  Scale,
  Timer,
  Trash2,
  X,
} from 'lucide-react';
import api from '../lib/api';

type FitnessSessionType = 'strength' | 'cardio' | 'mobility' | 'recovery' | 'mixed';
type FitnessSessionStatus = 'planned' | 'completed' | 'skipped';
type FitnessExerciseMode = 'reps' | 'duration';

type FitnessSession = {
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

type FitnessExercise = {
  name: string;
  mode: FitnessExerciseMode;
  reps: number | null;
  duration_minutes: number | null;
  note: string | null;
};

type FitnessMeasurement = {
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

type FitnessStats = {
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

type FitnessOverview = {
  stats: FitnessStats;
  upcoming_sessions: FitnessSession[];
  recent_sessions: FitnessSession[];
  measurements: FitnessMeasurement[];
};

const TAB_LIST = ['Stats', 'Séances', 'Mesures'] as const;
type Tab = (typeof TAB_LIST)[number];

type DraftItem = {
  id: string;
  name: string;
  mode: FitnessExerciseMode;
  reps: string;
  duration_minutes: string;
  note: string;
};

type SessionFormState = {
  title: string;
  session_type: FitnessSessionType;
  planned_at: string;
  duration_minutes: string;
  note: string;
};

type MeasurementFormState = {
  recorded_at: string;
  body_weight_kg: string;
  body_fat_pct: string;
  resting_hr: string;
  sleep_hours: string;
  steps: string;
  note: string;
};

const EMPTY_SESSION_FORM: SessionFormState = {
  title: '',
  session_type: 'mixed',
  planned_at: '',
  duration_minutes: '45',
  note: '',
};

const EMPTY_MEASUREMENT_FORM: MeasurementFormState = {
  recorded_at: '',
  body_weight_kg: '',
  body_fat_pct: '',
  resting_hr: '',
  sleep_hours: '',
  steps: '',
  note: '',
};
const SURFACE = 'rounded-[28px] border border-white/70 bg-white/82 shadow-[0_18px_60px_rgba(15,23,42,0.08)] backdrop-blur-xl';

function createDraftItem(value = ''): DraftItem {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name: value,
    mode: 'reps',
    reps: '',
    duration_minutes: '',
    note: '',
  };
}

function normalizeDrafts(values: FitnessExercise[]): DraftItem[] {
  if (values.length === 0) return [createDraftItem()];
  return values.map((value) => ({
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name: value.name,
    mode: value.mode,
    reps: value.reps !== null ? String(value.reps) : '',
    duration_minutes: value.duration_minutes !== null ? String(value.duration_minutes) : '',
    note: value.note || '',
  }));
}

function exerciseLabel(exercise: FitnessExercise): string {
  if (exercise.mode === 'duration') {
    return exercise.duration_minutes !== null ? `${exercise.name} · ${exercise.duration_minutes} min` : exercise.name;
  }
  return exercise.reps !== null ? `${exercise.name} · ${exercise.reps} reps` : exercise.name;
}

function toDateTimeLocalValue(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function fromDateTimeLocalValue(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const date = new Date(trimmed);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
}

function formatDateOnly(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('fr-FR', { dateStyle: 'medium' });
}

function formatKg(value: number | null): string {
  if (value === null || Number.isNaN(value)) return '--';
  return `${value.toFixed(1)} kg`;
}

function formatMinutes(value: number | null): string {
  if (value === null || Number.isNaN(value)) return '--';
  return `${Math.round(value)} min`;
}

function sessionTypeLabel(value: FitnessSessionType): string {
  const labels: Record<FitnessSessionType, string> = {
    strength: 'Muscu',
    cardio: 'Cardio',
    mobility: 'Mobilité',
    recovery: 'Récup',
    mixed: 'Mixte',
  };
  return labels[value];
}

function sessionTypeClasses(value: FitnessSessionType): string {
  const classes: Record<FitnessSessionType, string> = {
    strength: 'bg-red-50 text-red-700 border-red-200',
    cardio: 'bg-blue-50 text-blue-700 border-blue-200',
    mobility: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    recovery: 'bg-amber-50 text-amber-700 border-amber-200',
    mixed: 'bg-apple-gray-100 text-apple-gray-600 border-apple-gray-200',
  };
  return classes[value];
}

function statusLabel(value: FitnessSessionStatus): string {
  const labels: Record<FitnessSessionStatus, string> = {
    planned: 'Planifiée',
    completed: 'Terminée',
    skipped: 'Passée',
  };
  return labels[value];
}

function statusClasses(value: FitnessSessionStatus): string {
  const classes: Record<FitnessSessionStatus, string> = {
    planned: 'bg-amber-50 text-amber-700 border-amber-200',
    completed: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    skipped: 'bg-apple-gray-100 text-apple-gray-600 border-apple-gray-200',
  };
  return classes[value];
}

function StatCard({
  label,
  value,
  sub,
  icon,
}: {
  label: string;
  value: string;
  sub?: string;
  icon: ReactNode;
}) {
  return (
    <div className={`${SURFACE} p-4 flex items-start gap-3`}>
      <div className="rounded-2xl bg-apple-gray-100 p-2.5 text-black">{icon}</div>
      <div className="min-w-0">
        <p className="text-[11px] font-bold uppercase tracking-wider text-apple-gray-500">{label}</p>
        <p className="mt-1 text-2xl font-bold tracking-tight text-black">{value}</p>
        {sub && <p className="mt-1 text-xs text-apple-gray-500">{sub}</p>}
      </div>
    </div>
  );
}

export default function FitnessPage() {
  const [overview, setOverview] = useState<FitnessOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('Stats');
  const [sessionForm, setSessionForm] = useState<SessionFormState>(EMPTY_SESSION_FORM);
  const [exerciseDrafts, setExerciseDrafts] = useState<DraftItem[]>([createDraftItem()]);
  const [measurementForm, setMeasurementForm] = useState<MeasurementFormState>(EMPTY_MEASUREMENT_FORM);
  const [editingSessionId, setEditingSessionId] = useState<number | null>(null);
  const [editingMeasurementId, setEditingMeasurementId] = useState<number | null>(null);
  const [showSessionComposer, setShowSessionComposer] = useState(false);
  const [showMeasurementComposer, setShowMeasurementComposer] = useState(false);
  const [sessionSaving, setSessionSaving] = useState(false);
  const [measurementSaving, setMeasurementSaving] = useState(false);
  const [sessionActionId, setSessionActionId] = useState<number | null>(null);
  const [measurementActionId, setMeasurementActionId] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadOverview = async () => {
    setLoading(true);
    try {
      const res = await api.get('/fitness');
      setOverview(res.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadOverview();
  }, []);

  const resetSessionEditor = () => {
    setEditingSessionId(null);
    setSessionForm(EMPTY_SESSION_FORM);
    setExerciseDrafts([createDraftItem()]);
    setShowSessionComposer(false);
  };

  const resetMeasurementEditor = () => {
    setEditingMeasurementId(null);
    setMeasurementForm(EMPTY_MEASUREMENT_FORM);
    setShowMeasurementComposer(false);
  };

  const startCreateSession = () => {
    setError(null);
    setFeedback(null);
    setEditingSessionId(null);
    setShowSessionComposer(true);
    setSessionForm({
      ...EMPTY_SESSION_FORM,
      planned_at: toDateTimeLocalValue(new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString()),
    });
    setExerciseDrafts([createDraftItem()]);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const startEditSession = (session: FitnessSession) => {
    setError(null);
    setFeedback(null);
    setEditingSessionId(session.id);
    setShowSessionComposer(true);
    setSessionForm({
      title: session.title,
      session_type: session.session_type,
      planned_at: toDateTimeLocalValue(session.planned_at),
      duration_minutes: String(session.duration_minutes ?? 45),
      note: session.note || '',
    });
    setExerciseDrafts(normalizeDrafts(session.exercises || []));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const startCreateMeasurement = () => {
    setError(null);
    setFeedback(null);
    setEditingMeasurementId(null);
    setShowMeasurementComposer(true);
    setMeasurementForm({
      ...EMPTY_MEASUREMENT_FORM,
      recorded_at: toDateTimeLocalValue(new Date().toISOString()),
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const startEditMeasurement = (measurement: FitnessMeasurement) => {
    setError(null);
    setFeedback(null);
    setEditingMeasurementId(measurement.id);
    setShowMeasurementComposer(true);
    setMeasurementForm({
      recorded_at: toDateTimeLocalValue(measurement.recorded_at),
      body_weight_kg: measurement.body_weight_kg !== null ? String(measurement.body_weight_kg) : '',
      body_fat_pct: measurement.body_fat_pct !== null ? String(measurement.body_fat_pct) : '',
      resting_hr: measurement.resting_hr !== null ? String(measurement.resting_hr) : '',
      sleep_hours: measurement.sleep_hours !== null ? String(measurement.sleep_hours) : '',
      steps: measurement.steps !== null ? String(measurement.steps) : '',
      note: measurement.note || '',
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const updateExerciseDraft = (index: number, patch: Partial<DraftItem>) => {
    setExerciseDrafts((current) => current.map((draft, draftIndex) => (draftIndex === index ? { ...draft, ...patch } : draft)));
  };

  const addExerciseDraft = () => {
    setExerciseDrafts((current) => [...current, createDraftItem()]);
  };

  const removeExerciseDraft = (index: number) => {
    setExerciseDrafts((current) => {
      const next = current.filter((_, draftIndex) => draftIndex !== index);
      return next.length > 0 ? next : [createDraftItem()];
    });
  };

  const saveSession = async () => {
    setError(null);
    setFeedback(null);
    try {
      const title = sessionForm.title.trim();
      const plannedAt = fromDateTimeLocalValue(sessionForm.planned_at);
      if (!title || !plannedAt) {
        setError('Le titre et la date de séance sont obligatoires.');
        return;
      }

      const exercises = exerciseDrafts
        .map((draft, index) => {
          const name = draft.name.trim();
          if (!name) {
            return null;
          }

          if (draft.mode === 'duration') {
            const durationMinutes = draft.duration_minutes.trim();
            if (!durationMinutes) {
              throw new Error(`Renseigne une durée pour l’exercice ${index + 1}.`);
            }
            const parsedDuration = Number(durationMinutes);
            if (!Number.isFinite(parsedDuration) || parsedDuration < 1) {
              throw new Error(`La durée de l’exercice ${index + 1} est invalide.`);
            }
            return {
              name,
              mode: 'duration' as const,
              duration_minutes: Math.round(parsedDuration),
              reps: null,
              note: draft.note.trim() || null,
            };
          }

          const reps = draft.reps.trim();
          if (!reps) {
            throw new Error(`Renseigne un nombre de reps pour l’exercice ${index + 1}.`);
          }
          const parsedReps = Number(reps);
          if (!Number.isFinite(parsedReps) || parsedReps < 1) {
            throw new Error(`Le nombre de reps de l’exercice ${index + 1} est invalide.`);
          }
          return {
            name,
            mode: 'reps' as const,
            reps: Math.round(parsedReps),
            duration_minutes: null,
            note: draft.note.trim() || null,
          };
        })
        .filter(Boolean) as Array<{
        name: string;
        mode: FitnessExerciseMode;
        reps: number | null;
        duration_minutes: number | null;
        note: string | null;
      }>;

      const payload = {
        title,
        session_type: sessionForm.session_type,
        planned_at: plannedAt,
        duration_minutes: sessionForm.duration_minutes ? Number(sessionForm.duration_minutes) : 45,
        exercises,
        note: sessionForm.note.trim() || null,
      };

      setSessionSaving(true);
      if (editingSessionId !== null) {
        await api.patch(`/fitness/sessions/${editingSessionId}`, payload);
        setFeedback('Séance modifiée.');
      } else {
        await api.post('/fitness/sessions', payload);
        setFeedback('Séance planifiée.');
      }
      resetSessionEditor();
      await loadOverview();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible d’enregistrer la séance.');
    } finally {
      setSessionSaving(false);
    }
  };

  const completeSession = async (session: FitnessSession) => {
    setSessionActionId(session.id);
    setError(null);
    setFeedback(null);
    try {
      await api.post(`/fitness/sessions/${session.id}/complete`, {});
      setFeedback(`Séance "${session.title}" marquée comme terminée.`);
      await loadOverview();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible de terminer la séance.');
    } finally {
      setSessionActionId(null);
    }
  };

  const undoSession = async (session: FitnessSession) => {
    setSessionActionId(session.id);
    setError(null);
    setFeedback(null);
    try {
      await api.patch(`/fitness/sessions/${session.id}`, { status: 'planned' });
      setFeedback(`Séance "${session.title}" remise en planification.`);
      await loadOverview();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible d’annuler la séance.');
    } finally {
      setSessionActionId(null);
    }
  };

  const deleteSession = async (session: FitnessSession) => {
    const ok = window.confirm(`Supprimer la séance "${session.title}" ?`);
    if (!ok) return;

    setSessionActionId(session.id);
    setError(null);
    setFeedback(null);
    try {
      await api.delete(`/fitness/sessions/${session.id}`);
      if (editingSessionId === session.id) {
        resetSessionEditor();
      }
      setFeedback('Séance supprimée.');
      await loadOverview();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible de supprimer la séance.');
    } finally {
      setSessionActionId(null);
    }
  };

  const saveMeasurement = async () => {
    setError(null);
    setFeedback(null);

    const recordedAt = fromDateTimeLocalValue(measurementForm.recorded_at);
    if (!recordedAt) {
      setError('La date de mesure est obligatoire.');
      return;
    }

    const payload = {
      recorded_at: recordedAt,
      body_weight_kg: measurementForm.body_weight_kg ? Number(measurementForm.body_weight_kg) : null,
      body_fat_pct: measurementForm.body_fat_pct ? Number(measurementForm.body_fat_pct) : null,
      resting_hr: measurementForm.resting_hr ? Number(measurementForm.resting_hr) : null,
      sleep_hours: measurementForm.sleep_hours ? Number(measurementForm.sleep_hours) : null,
      steps: measurementForm.steps ? Number(measurementForm.steps) : null,
      note: measurementForm.note.trim() || null,
    };

    setMeasurementSaving(true);
    try {
      if (editingMeasurementId !== null) {
        await api.patch(`/fitness/measurements/${editingMeasurementId}`, payload);
        setFeedback('Mesure modifiée.');
      } else {
        await api.post('/fitness/measurements', payload);
        setFeedback('Mesure enregistrée.');
      }
      resetMeasurementEditor();
      await loadOverview();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible d’enregistrer la mesure.');
    } finally {
      setMeasurementSaving(false);
    }
  };

  const deleteMeasurement = async (measurement: FitnessMeasurement) => {
    const ok = window.confirm('Supprimer cette mesure ?');
    if (!ok) return;

    setMeasurementActionId(measurement.id);
    setError(null);
    setFeedback(null);
    try {
      await api.delete(`/fitness/measurements/${measurement.id}`);
      if (editingMeasurementId === measurement.id) {
        resetMeasurementEditor();
      }
      setFeedback('Mesure supprimée.');
      await loadOverview();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible de supprimer la mesure.');
    } finally {
      setMeasurementActionId(null);
    }
  };

  const stats = overview?.stats;

  return (
    <div className="flex-1 flex flex-col h-full bg-transparent overflow-y-auto pb-[calc(env(safe-area-inset-bottom)+5.75rem)]">
      <div className="sticky top-0 z-20 border-b border-white/70 bg-white/76 px-4 py-4 shadow-[0_10px_40px_rgba(15,23,42,0.06)] backdrop-blur-2xl md:px-8 md:py-5">
        <div className="max-w-6xl mx-auto flex items-end justify-between gap-4">
          <div>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-black md:text-3xl">Séances et stats</h1>
            <p className="mt-1 text-sm text-apple-gray-500">Planifie tes séances, enregistre tes mesures et suis tes tendances.</p>
          </div>
        </div>
      </div>

      <div className="border-b border-white/60 bg-white/60 px-4 backdrop-blur-xl md:px-8">
        <div className="mx-auto flex max-w-6xl gap-1 overflow-x-auto py-2">
          {TAB_LIST.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`rounded-full px-4 py-2.5 text-sm font-semibold transition-all ${
                activeTab === tab
                  ? 'bg-white text-black shadow-[0_8px_24px_rgba(15,23,42,0.06)] ring-1 ring-black/5'
                  : 'text-apple-gray-500 hover:bg-white/70 hover:text-black'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      <div className="px-4 py-4 space-y-4 md:px-8 md:py-6">
        {(feedback || error) && (
          <div className={`max-w-6xl mx-auto rounded-2xl px-4 py-3 text-sm ${error ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'}`}>
            {error || feedback}
          </div>
        )}

        {activeTab === 'Stats' ? (
          <div className="max-w-6xl mx-auto space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard
                label="Séances prévues"
                value={stats ? String(stats.planned_sessions) : '--'}
                sub={stats ? `${stats.upcoming_sessions} à venir` : 'Chargement...'}
                icon={<CalendarClock className="w-4 h-4" />}
              />
              <StatCard
                label="Complétées 30j"
                value={stats ? String(stats.completed_sessions_30d) : '--'}
                sub={stats ? `${stats.completion_rate_30d}% de complétion` : 'Chargement...'}
                icon={<CheckCircle2 className="w-4 h-4" />}
              />
              <StatCard
                label="Poids"
                value={stats ? formatKg(stats.latest_body_weight_kg) : '--'}
                sub={stats && stats.body_weight_delta_30d !== null ? `${stats.body_weight_delta_30d > 0 ? '+' : ''}${stats.body_weight_delta_30d.toFixed(1)} kg / 30j` : 'Dernière mesure'}
                icon={<Scale className="w-4 h-4" />}
              />
              <StatCard
                label="Sommeil"
                value={stats?.latest_sleep_hours !== null && stats?.latest_sleep_hours !== undefined ? `${stats.latest_sleep_hours.toFixed(1)} h` : '--'}
                sub={stats?.latest_resting_hr !== null && stats?.latest_resting_hr !== undefined ? `Repos ${stats.latest_resting_hr} bpm` : 'Dernière mesure'}
                icon={<HeartPulse className="w-4 h-4" />}
              />
            </div>
            <div className={`${SURFACE} p-5`}>
              <p className="text-xs font-bold uppercase tracking-wider text-apple-gray-500">Vue générale</p>
              <p className="mt-2 text-sm text-apple-gray-500">
                Utilise l’onglet Séances pour le planning et la liste, et l’onglet Mesures pour les points de contrôle.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setActiveTab('Séances')}
                  className="inline-flex items-center gap-2 rounded-xl bg-apple-blue px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-600"
                >
                  <CalendarClock className="w-4 h-4" />
                  Voir les séances
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('Mesures')}
                  className="inline-flex items-center gap-2 rounded-xl border border-apple-gray-200 bg-white px-4 py-2.5 text-sm font-semibold text-black transition-colors hover:bg-apple-gray-50"
                >
                  <Scale className="w-4 h-4" />
                  Voir les mesures
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {activeTab !== 'Stats' ? (
          <div className="max-w-6xl mx-auto grid gap-4 lg:grid-cols-[1.35fr_0.95fr]">
          <div className={`space-y-4 ${activeTab === 'Séances' ? 'lg:col-span-2' : 'hidden'}`}>
            {!showSessionComposer && (
              <div className="rounded-2xl border border-dashed border-apple-gray-200 bg-white/80 p-5 shadow-sm">
                <p className="text-xs font-bold uppercase tracking-wider text-red-600">
                  {editingSessionId !== null ? 'Modifier la séance' : 'Planifier une séance'}
                </p>
                <h2 className="mt-2 text-lg font-semibold text-black">
                  {editingSessionId !== null ? 'Séance existante' : 'Nouvelle séance'}
                </h2>
                <p className="mt-1 text-sm text-apple-gray-500">
                  Les séances restent en lecture seule ici. Ouvre le composeur pour saisir le titre, les exercices et le créneau.
                </p>
                <button
                  type="button"
                  onClick={startCreateSession}
                  className="mt-4 inline-flex items-center gap-2 rounded-xl bg-apple-blue px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-600"
                >
                  <Plus className="w-4 h-4" />
                  Ouvrir le composeur
                </button>
              </div>
            )}

            <div className={`rounded-2xl border border-apple-gray-200 bg-white shadow-sm p-5 space-y-4 ${showSessionComposer ? '' : 'hidden'}`}>
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-red-600">{editingSessionId !== null ? 'Modifier la séance' : 'Planifier une séance'}</p>
                  <h2 className="text-lg font-semibold text-black mt-2">{editingSessionId !== null ? 'Séance existante' : 'Nouvelle séance'}</h2>
                  <p className="text-sm text-apple-gray-500 mt-1">Ajoute une séance à l’avance avec ses exercices, leurs reps ou leur durée, et une note.</p>
                </div>
                {editingSessionId !== null && (
                  <button
                    type="button"
                    onClick={resetSessionEditor}
                    className="inline-flex items-center gap-2 rounded-xl border border-apple-gray-200 px-3 py-2 text-sm font-semibold text-apple-gray-600 hover:bg-apple-gray-50"
                  >
                    <X className="w-4 h-4" />
                    Annuler
                  </button>
                )}
                <button
                  type="button"
                  onClick={resetSessionEditor}
                  className="inline-flex items-center gap-2 rounded-xl border border-apple-gray-200 px-3 py-2 text-sm font-semibold text-black hover:bg-apple-gray-50"
                >
                  <X className="w-4 h-4" />
                  Fermer
                </button>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                <input
                  value={sessionForm.title}
                  onChange={(e) => setSessionForm((current) => ({ ...current, title: e.target.value }))}
                  className="w-full rounded-xl border border-apple-gray-200 px-3 py-2.5 text-sm bg-white"
                  placeholder="Titre de la séance"
                />
                <select
                  value={sessionForm.session_type}
                  onChange={(e) => setSessionForm((current) => ({ ...current, session_type: e.target.value as FitnessSessionType }))}
                  className="w-full rounded-xl border border-apple-gray-200 px-3 py-2.5 text-sm bg-white"
                >
                  <option value="mixed">Mixte</option>
                  <option value="strength">Musculation</option>
                  <option value="cardio">Cardio</option>
                  <option value="mobility">Mobilité</option>
                  <option value="recovery">Récupération</option>
                </select>
                <input
                  type="datetime-local"
                  value={sessionForm.planned_at}
                  onChange={(e) => setSessionForm((current) => ({ ...current, planned_at: e.target.value }))}
                  className="w-full rounded-xl border border-apple-gray-200 px-3 py-2.5 text-sm bg-white"
                />
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={sessionForm.duration_minutes}
                  onChange={(e) => setSessionForm((current) => ({ ...current, duration_minutes: e.target.value }))}
                  className="w-full rounded-xl border border-apple-gray-200 px-3 py-2.5 text-sm bg-white"
                  placeholder="Durée (min)"
                />
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-apple-gray-500">Exercices</p>
                    <p className="text-sm text-apple-gray-500 mt-1">Ajoute les exercices un par un.</p>
                  </div>
                  <button
                    type="button"
                    onClick={addExerciseDraft}
                    className="inline-flex items-center gap-2 rounded-xl border border-apple-gray-200 px-3 py-2 text-sm font-semibold text-black hover:bg-apple-gray-50"
                  >
                    <Plus className="w-4 h-4" />
                    Ajouter
                  </button>
                </div>

                <div className="space-y-2">
                  {exerciseDrafts.map((draft, index) => (
                    <div key={draft.id} className="rounded-2xl border border-apple-gray-200 bg-apple-gray-50/60 p-4 space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-apple-blue/10 text-xs font-bold text-apple-blue">
                            {index + 1}
                          </span>
                          <p className="text-sm font-semibold text-black truncate">
                            {draft.name.trim() || `Exercice ${index + 1}`}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => removeExerciseDraft(index)}
                          className="inline-flex items-center gap-2 rounded-xl border border-apple-gray-200 bg-white px-3 py-2 text-sm font-semibold text-apple-gray-600 hover:bg-apple-gray-50"
                        >
                          <X className="w-4 h-4" />
                          Supprimer
                        </button>
                      </div>
                      <div className="grid gap-3 md:grid-cols-[1.4fr_0.9fr]">
                        <input
                          value={draft.name}
                          onChange={(e) => updateExerciseDraft(index, { name: e.target.value })}
                          className="w-full rounded-xl border border-apple-gray-200 bg-white px-3 py-2.5 text-sm"
                          placeholder={`Exercice ${index + 1}`}
                        />
                        <select
                          value={draft.mode}
                          onChange={(e) => {
                            const mode = e.target.value as FitnessExerciseMode;
                            updateExerciseDraft(index, {
                              mode,
                              reps: mode === 'reps' ? draft.reps : '',
                              duration_minutes: mode === 'duration' ? draft.duration_minutes : '',
                            });
                          }}
                          className="w-full rounded-xl border border-apple-gray-200 bg-white px-3 py-2.5 text-sm"
                        >
                          <option value="reps">Reps</option>
                          <option value="duration">Durée</option>
                        </select>
                      </div>
                      <div className="grid gap-3 md:grid-cols-[1fr_1fr]">
                        {draft.mode === 'reps' ? (
                          <input
                            type="number"
                            min="1"
                            step="1"
                            value={draft.reps}
                            onChange={(e) => updateExerciseDraft(index, { reps: e.target.value })}
                            className="w-full rounded-xl border border-apple-gray-200 bg-white px-3 py-2.5 text-sm"
                            placeholder="Nombre de reps"
                          />
                        ) : (
                          <input
                            type="number"
                            min="1"
                            step="1"
                            value={draft.duration_minutes}
                            onChange={(e) => updateExerciseDraft(index, { duration_minutes: e.target.value })}
                            className="w-full rounded-xl border border-apple-gray-200 bg-white px-3 py-2.5 text-sm"
                            placeholder="Durée (min)"
                          />
                        )}
                        <input
                          value={draft.note}
                          onChange={(e) => updateExerciseDraft(index, { note: e.target.value })}
                          className="w-full rounded-xl border border-apple-gray-200 bg-white px-3 py-2.5 text-sm"
                          placeholder="Note optionnelle"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <textarea
                value={sessionForm.note}
                onChange={(e) => setSessionForm((current) => ({ ...current, note: e.target.value }))}
                className="w-full min-h-24 rounded-xl border border-apple-gray-200 px-3 py-2.5 text-sm bg-white resize-y"
                placeholder="Note optionnelle"
              />

              <div className="flex flex-col sm:flex-row gap-2">
                <button
                  type="button"
                  onClick={() => void saveSession()}
                  disabled={sessionSaving}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-apple-blue px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-600 disabled:opacity-50"
                >
                  {sessionSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CalendarClock className="w-4 h-4" />}
                  {editingSessionId !== null ? 'Enregistrer' : 'Planifier'}
                </button>
                {editingSessionId !== null && (
                  <button
                    type="button"
                    onClick={resetSessionEditor}
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-apple-gray-200 px-4 py-2.5 text-sm font-semibold text-apple-gray-600 hover:bg-apple-gray-50"
                  >
                    <X className="w-4 h-4" />
                    Annuler
                  </button>
                )}
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-apple-gray-500">Séances</p>
                  <p className="text-sm text-apple-gray-500 mt-1">Aperçu des prochaines séances et de l’historique récent.</p>
                </div>
                <button
                  type="button"
                  onClick={startCreateSession}
                  className="inline-flex items-center gap-2 rounded-xl border border-apple-gray-200 px-3 py-2 text-sm font-semibold text-black hover:bg-apple-gray-50"
                >
                  <Plus className="w-4 h-4" />
                  Ajouter
                </button>
              </div>

              {loading ? (
                <div className="rounded-2xl border border-apple-gray-200 bg-white py-14 flex items-center justify-center shadow-sm">
                  <Loader2 className="w-8 h-8 animate-spin text-apple-blue" />
                </div>
              ) : (
                <div className="space-y-3">
                  {(overview?.recent_sessions ?? []).length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-apple-gray-200 bg-white p-6 text-sm text-apple-gray-400 shadow-sm">
                      Aucune séance pour l’instant.
                    </div>
                  ) : (
                    (overview?.recent_sessions ?? []).map((session) => (
                      <div key={session.id} className="rounded-2xl border border-apple-gray-200 bg-white p-4 shadow-sm space-y-3">
                        <div className="flex items-start justify-between gap-3 flex-wrap">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-base font-semibold text-black truncate">{session.title}</p>
                              <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${sessionTypeClasses(session.session_type)}`}>
                                {sessionTypeLabel(session.session_type)}
                              </span>
                              <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusClasses(session.status)}`}>
                                {statusLabel(session.status)}
                              </span>
                            </div>
                            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-apple-gray-500">
                              <span className="inline-flex items-center gap-1">
                                <Clock3 className="w-3.5 h-3.5" />
                                {formatDateTime(session.planned_at)}
                              </span>
                              <span className="inline-flex items-center gap-1">
                                <Timer className="w-3.5 h-3.5" />
                                {session.actual_duration_minutes ? formatMinutes(session.actual_duration_minutes) : formatMinutes(session.duration_minutes)}
                              </span>
                            </div>
                            {session.note && <p className="mt-2 text-sm text-apple-gray-500">{session.note}</p>}
                          </div>
                          <div className="flex flex-wrap gap-2 justify-end">
                            <button
                              type="button"
                              onClick={() => startEditSession(session)}
                              className="inline-flex items-center gap-2 rounded-xl border border-apple-gray-200 px-3 py-2 text-sm font-semibold text-black hover:bg-apple-gray-50"
                            >
                              <PencilLine className="w-4 h-4" />
                              Modifier
                            </button>
                            {session.status === 'completed' ? (
                              <button
                                type="button"
                                onClick={() => void undoSession(session)}
                                disabled={sessionActionId === session.id}
                                className="inline-flex items-center gap-2 rounded-xl border border-amber-200 px-3 py-2 text-sm font-semibold text-amber-700 hover:bg-amber-50 disabled:opacity-50"
                              >
                                {sessionActionId === session.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <X className="w-4 h-4" />}
                                Annuler
                              </button>
                            ) : (
                              <button
                                type="button"
                                onClick={() => void completeSession(session)}
                                disabled={sessionActionId === session.id}
                                className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
                              >
                                {sessionActionId === session.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                                Terminer
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => void deleteSession(session)}
                              disabled={sessionActionId === session.id}
                              className="inline-flex items-center gap-2 rounded-xl border border-red-200 px-3 py-2 text-sm font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50"
                            >
                              {sessionActionId === session.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                              Supprimer
                            </button>
                          </div>
                        </div>
                        {session.exercises.length > 0 && (
                          <div className="flex flex-wrap gap-2">
                            {session.exercises.map((exercise, index) => (
                              <span
                                key={`${session.id}-${index}-${exercise.name}`}
                                className="rounded-full border border-apple-gray-200 bg-apple-gray-50 px-3 py-1.5 text-xs font-semibold text-apple-gray-600"
                              >
                                {exerciseLabel(exercise)}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>

          <div className={`space-y-4 lg:sticky lg:top-6 lg:self-start ${activeTab === 'Mesures' ? 'lg:col-span-2' : 'hidden'}`}>
            {!showMeasurementComposer && (
              <div className="rounded-2xl border border-dashed border-apple-gray-200 bg-white/80 p-5 shadow-sm">
                <p className="text-xs font-bold uppercase tracking-wider text-red-600">
                  {editingMeasurementId !== null ? 'Modifier la mesure' : 'Suivi des stats'}
                </p>
                <h2 className="mt-2 text-lg font-semibold text-black">Mesures du corps</h2>
                <p className="mt-1 text-sm text-apple-gray-500">
                  Le suivi reste en lecture seule ici. Ouvre le composeur pour enregistrer un point de contrôle.
                </p>
                <button
                  type="button"
                  onClick={startCreateMeasurement}
                  className="mt-4 inline-flex items-center gap-2 rounded-xl bg-apple-blue px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-600"
                >
                  <Plus className="w-4 h-4" />
                  Ouvrir le composeur
                </button>
              </div>
            )}

            <div className={`rounded-2xl border border-apple-gray-200 bg-white shadow-sm p-5 space-y-4 ${showMeasurementComposer ? '' : 'hidden'}`}>
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-red-600">
                    {editingMeasurementId !== null ? 'Modifier la mesure' : 'Suivi des stats'}
                  </p>
                  <h2 className="text-lg font-semibold text-black mt-2">Mesures du corps</h2>
                  <p className="text-sm text-apple-gray-500 mt-1">Enregistre un point de contrôle rapide pour suivre la tendance.</p>
                </div>
                {editingMeasurementId !== null && (
                  <button
                    type="button"
                    onClick={resetMeasurementEditor}
                    className="inline-flex items-center gap-2 rounded-xl border border-apple-gray-200 px-3 py-2 text-sm font-semibold text-apple-gray-600 hover:bg-apple-gray-50"
                  >
                    <X className="w-4 h-4" />
                    Annuler
                  </button>
                )}
                <button
                  type="button"
                  onClick={resetMeasurementEditor}
                  className="inline-flex items-center gap-2 rounded-xl border border-apple-gray-200 px-3 py-2 text-sm font-semibold text-black hover:bg-apple-gray-50"
                >
                  <X className="w-4 h-4" />
                  Fermer
                </button>
              </div>

              <button
                type="button"
                onClick={startCreateMeasurement}
                className="inline-flex items-center gap-2 rounded-xl border border-apple-gray-200 px-3 py-2 text-sm font-semibold text-black hover:bg-apple-gray-50"
              >
                <Plus className="w-4 h-4" />
                Nouvelle mesure
              </button>

              <div className="grid gap-3 sm:grid-cols-2">
                <input
                  type="datetime-local"
                  value={measurementForm.recorded_at}
                  onChange={(e) => setMeasurementForm((current) => ({ ...current, recorded_at: e.target.value }))}
                  className="w-full rounded-xl border border-apple-gray-200 px-3 py-2.5 text-sm bg-white"
                />
                <input
                  type="number"
                  step="0.1"
                  value={measurementForm.body_weight_kg}
                  onChange={(e) => setMeasurementForm((current) => ({ ...current, body_weight_kg: e.target.value }))}
                  className="w-full rounded-xl border border-apple-gray-200 px-3 py-2.5 text-sm bg-white"
                  placeholder="Poids (kg)"
                />
                <input
                  type="number"
                  step="0.1"
                  value={measurementForm.body_fat_pct}
                  onChange={(e) => setMeasurementForm((current) => ({ ...current, body_fat_pct: e.target.value }))}
                  className="w-full rounded-xl border border-apple-gray-200 px-3 py-2.5 text-sm bg-white"
                  placeholder="% masse grasse"
                />
                <input
                  type="number"
                  value={measurementForm.resting_hr}
                  onChange={(e) => setMeasurementForm((current) => ({ ...current, resting_hr: e.target.value }))}
                  className="w-full rounded-xl border border-apple-gray-200 px-3 py-2.5 text-sm bg-white"
                  placeholder="FC repos"
                />
                <input
                  type="number"
                  step="0.1"
                  value={measurementForm.sleep_hours}
                  onChange={(e) => setMeasurementForm((current) => ({ ...current, sleep_hours: e.target.value }))}
                  className="w-full rounded-xl border border-apple-gray-200 px-3 py-2.5 text-sm bg-white"
                  placeholder="Sommeil (h)"
                />
                <input
                  type="number"
                  value={measurementForm.steps}
                  onChange={(e) => setMeasurementForm((current) => ({ ...current, steps: e.target.value }))}
                  className="w-full rounded-xl border border-apple-gray-200 px-3 py-2.5 text-sm bg-white"
                  placeholder="Pas"
                />
              </div>

              <textarea
                value={measurementForm.note}
                onChange={(e) => setMeasurementForm((current) => ({ ...current, note: e.target.value }))}
                className="w-full min-h-24 rounded-xl border border-apple-gray-200 px-3 py-2.5 text-sm bg-white resize-y"
                placeholder="Note optionnelle"
              />

              <div className="flex flex-col sm:flex-row gap-2">
                <button
                  type="button"
                  onClick={() => void saveMeasurement()}
                  disabled={measurementSaving}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-apple-blue px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-600 disabled:opacity-50"
                >
                  {measurementSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Scale className="w-4 h-4" />}
                  {editingMeasurementId !== null ? 'Enregistrer' : 'Ajouter'}
                </button>
                {editingMeasurementId !== null && (
                  <button
                    type="button"
                    onClick={resetMeasurementEditor}
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-apple-gray-200 px-4 py-2.5 text-sm font-semibold text-apple-gray-600 hover:bg-apple-gray-50"
                  >
                    <X className="w-4 h-4" />
                    Annuler
                  </button>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-apple-gray-200 bg-white shadow-sm p-5 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-apple-gray-500">Mesures récentes</p>
                  <p className="text-sm text-apple-gray-500 mt-1">Historique des derniers points de contrôle.</p>
                </div>
                {loading && <Loader2 className="w-4 h-4 animate-spin text-apple-gray-400" />}
              </div>

              <div className="space-y-2">
                {(overview?.measurements ?? []).length === 0 ? (
                  <div className="rounded-xl border border-dashed border-apple-gray-200 p-4 text-sm text-apple-gray-400">
                    Aucune mesure enregistrée.
                  </div>
                ) : (
                  (overview?.measurements ?? []).map((measurement) => (
                    <div key={measurement.id} className="rounded-xl border border-apple-gray-200 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-black">{formatDateOnly(measurement.recorded_at)}</p>
                          <div className="mt-2 flex flex-wrap gap-2 text-xs text-apple-gray-500">
                            {measurement.body_weight_kg !== null && <span className="rounded-full bg-apple-gray-100 px-2 py-0.5">{formatKg(measurement.body_weight_kg)}</span>}
                            {measurement.body_fat_pct !== null && <span className="rounded-full bg-apple-gray-100 px-2 py-0.5">{measurement.body_fat_pct.toFixed(1)} %</span>}
                            {measurement.resting_hr !== null && <span className="rounded-full bg-apple-gray-100 px-2 py-0.5">{measurement.resting_hr} bpm</span>}
                            {measurement.sleep_hours !== null && <span className="rounded-full bg-apple-gray-100 px-2 py-0.5">{measurement.sleep_hours.toFixed(1)} h</span>}
                            {measurement.steps !== null && <span className="rounded-full bg-apple-gray-100 px-2 py-0.5">{measurement.steps} pas</span>}
                          </div>
                          {measurement.note && <p className="mt-2 text-sm text-apple-gray-500">{measurement.note}</p>}
                        </div>
                        <div className="flex flex-wrap gap-2 justify-end">
                          <button
                            type="button"
                            onClick={() => startEditMeasurement(measurement)}
                            className="inline-flex items-center gap-2 rounded-xl border border-apple-gray-200 px-3 py-2 text-sm font-semibold text-black hover:bg-apple-gray-50"
                          >
                            <PencilLine className="w-4 h-4" />
                            Modifier
                          </button>
                          <button
                            type="button"
                            onClick={() => void deleteMeasurement(measurement)}
                            disabled={measurementActionId === measurement.id}
                            className="inline-flex items-center gap-2 rounded-xl border border-red-200 px-3 py-2 text-sm font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50"
                          >
                            {measurementActionId === measurement.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                            Supprimer
                          </button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
