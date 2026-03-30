import { useEffect, useState, type FormEvent } from "react";
import {
  Check,
  Copy,
  ExternalLink,
  Link2,
  Loader2,
  RadioTower,
  Trash2,
  X,
} from "lucide-react";
import api from "../lib/api";

type CalendarFeedSource =
  | "manual"
  | "task"
  | "habit"
  | "event"
  | "subscription"
  | "meal_plan"
  | "fitness_session";

type CalendarFeedRead = {
  id: number;
  name: string;
  token: string;
  sources: CalendarFeedSource[];
  include_completed: boolean;
  active: boolean;
  ics_url: string;
  webcal_url: string;
  last_accessed_at: string | null;
  created_at: string;
  updated_at: string;
};

const SOURCE_OPTIONS: Array<{ value: CalendarFeedSource; label: string }> = [
  { value: "task", label: "Tâches" },
  { value: "habit", label: "Routine" },
  { value: "meal_plan", label: "Repas" },
  { value: "fitness_session", label: "Fitness" },
  { value: "event", label: "Événements" },
  { value: "subscription", label: "Abonnements" },
  { value: "manual", label: "Manuel" },
];

function formatTimestamp(value: string | null) {
  if (!value) return "Jamais";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Jamais";
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function describeSources(sources: CalendarFeedSource[]) {
  if (sources.length === 0) return "Toutes les sources";
  return SOURCE_OPTIONS.filter((option) => sources.includes(option.value))
    .map((option) => option.label)
    .join(" • ");
}

async function copyToClipboard(value: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  window.prompt("Copiez ce lien :", value);
}

type CalendarFeedPanelProps = {
  open: boolean;
  onClose: () => void;
};

export default function CalendarFeedPanel({
  open,
  onClose,
}: CalendarFeedPanelProps) {
  const [feeds, setFeeds] = useState<CalendarFeedRead[]>([]);
  const [name, setName] = useState("AdamHUB Calendar");
  const [selectedSources, setSelectedSources] = useState<CalendarFeedSource[]>(
    [],
  );
  const [includeCompleted, setIncludeCompleted] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const loadFeeds = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.get<CalendarFeedRead[]>("/calendar/feeds");
      setFeeds(response.data);
    } catch (err) {
      console.error("Failed to load calendar feeds", err);
      setError("Impossible de charger les abonnements calendrier.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    void loadFeeds();
  }, [open]);

  useEffect(() => {
    if (!copiedKey) return;
    const timeout = window.setTimeout(() => setCopiedKey(null), 1800);
    return () => window.clearTimeout(timeout);
  }, [copiedKey]);

  const toggleSource = (source: CalendarFeedSource) => {
    setSelectedSources((current) =>
      current.includes(source)
        ? current.filter((value) => value !== source)
        : [...current, source],
    );
  };

  const handleCreateFeed = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!name.trim()) {
      setError("Le nom du flux est requis.");
      return;
    }

    setIsSaving(true);
    setError(null);
    try {
      await api.post<CalendarFeedRead>("/calendar/feeds", {
        name: name.trim(),
        sources: selectedSources,
        include_completed: includeCompleted,
      });
      setName("AdamHUB Calendar");
      setSelectedSources([]);
      setIncludeCompleted(true);
      await loadFeeds();
    } catch (err) {
      console.error("Failed to create calendar feed", err);
      setError("Impossible de créer le flux calendrier.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteFeed = async (feed: CalendarFeedRead) => {
    const confirmed = window.confirm(
      `Révoquer le flux "${feed.name}" ? Les apps abonnées ne pourront plus le synchroniser.`,
    );
    if (!confirmed) return;

    try {
      await api.delete(`/calendar/feeds/${feed.id}`);
      setFeeds((current) => current.filter((entry) => entry.id !== feed.id));
    } catch (err) {
      console.error("Failed to delete calendar feed", err);
      setError("Impossible de révoquer ce flux.");
    }
  };

  const handleCopy = async (value: string, key: string) => {
    try {
      await copyToClipboard(value);
      setCopiedKey(key);
    } catch (err) {
      console.error("Failed to copy calendar feed URL", err);
      setError("Impossible de copier ce lien.");
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[80] flex items-end justify-center bg-black/40 p-0 backdrop-blur-sm md:items-center md:p-4">
      <div className="flex h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-t-[32px] border border-white/60 bg-[linear-gradient(180deg,rgba(255,255,255,0.97)_0%,rgba(244,247,252,0.98)_100%)] shadow-[0_32px_80px_rgba(15,23,42,0.22)] md:h-[min(780px,92vh)] md:rounded-[32px]">
        <div className="flex items-start justify-between gap-4 border-b border-white/60 bg-white/70 px-4 py-4 backdrop-blur-xl md:px-6">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-[0.32em] text-apple-gray-500">
              Calendar Feeds
            </p>
            <h2 className="mt-2 flex items-center gap-2 text-xl font-semibold tracking-tight text-black md:text-2xl">
              <RadioTower className="h-5 w-5 text-apple-blue" />
              ICS et webcal
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-apple-gray-500">
              Générez un lien signé pour Apple Calendar, Outlook ou toute app
              compatible. Aucun OAuth Google n’est nécessaire.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-10 w-10 items-center justify-center rounded-2xl border border-white/70 bg-white/85 text-apple-gray-500 shadow-sm transition-colors hover:text-black"
            aria-label="Fermer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4 pb-[calc(env(safe-area-inset-bottom)+6.5rem)] md:px-6 md:py-6 md:pb-6">
          <div className="grid gap-5 xl:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
            <form
              onSubmit={handleCreateFeed}
              className="rounded-[28px] border border-white/60 bg-white/80 p-5 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl"
            >
              <div className="flex items-center gap-2">
                <Link2 className="h-4 w-4 text-apple-blue" />
                <span className="text-xs font-bold uppercase tracking-[0.28em] text-apple-gray-500">
                  Nouveau flux
                </span>
              </div>

              <label className="mt-5 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                Nom
              </label>
              <input
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="AdamHUB Calendar"
                className="mt-2 w-full rounded-2xl border border-apple-gray-200 bg-white px-4 py-3 text-sm text-black outline-none transition focus:border-apple-blue/40 focus:ring-2 focus:ring-apple-blue/20"
              />

              <div className="mt-5 flex items-center justify-between gap-4 rounded-2xl border border-apple-gray-100 bg-apple-gray-50 px-4 py-3">
                <div>
                  <p className="text-sm font-semibold text-black">
                    Inclure les éléments terminés
                  </p>
                  <p className="mt-1 text-xs text-apple-gray-500">
                    Pratique si tu veux un historique complet dans l’agenda
                    externe.
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={includeCompleted}
                  onClick={() => setIncludeCompleted((current) => !current)}
                  className={`relative h-7 w-12 rounded-full transition ${
                    includeCompleted ? "bg-apple-blue" : "bg-apple-gray-300"
                  }`}
                >
                  <span
                    className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow-sm transition ${
                      includeCompleted ? "left-6" : "left-1"
                    }`}
                  />
                </button>
              </div>

              <div className="mt-5">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                    Sources filtrées
                  </p>
                  <button
                    type="button"
                    onClick={() => setSelectedSources([])}
                    className="text-xs font-semibold text-apple-blue transition hover:text-blue-700"
                  >
                    Tout inclure
                  </button>
                </div>
                <p className="mt-2 text-xs text-apple-gray-500">
                  Si rien n’est sélectionné, le flux exporte tout le calendrier.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {SOURCE_OPTIONS.map((option) => {
                    const active = selectedSources.includes(option.value);
                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => toggleSource(option.value)}
                        className={`rounded-full px-3 py-2 text-sm font-medium transition ${
                          active
                            ? "bg-[linear-gradient(135deg,rgba(10,132,255,0.16),rgba(99,102,241,0.14))] text-apple-blue ring-1 ring-apple-blue/15"
                            : "bg-apple-gray-50 text-apple-gray-600 ring-1 ring-apple-gray-200 hover:bg-white hover:text-black"
                        }`}
                      >
                        {option.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {error && (
                <div className="mt-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={isSaving}
                className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-apple-blue px-5 py-3 text-sm font-semibold text-white shadow-[0_12px_30px_rgba(10,132,255,0.24)] transition hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSaving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RadioTower className="h-4 w-4" />
                )}
                Créer le flux
              </button>
            </form>

            <div className="rounded-[28px] border border-white/60 bg-white/82 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl">
              <div className="flex items-center justify-between gap-4 border-b border-apple-gray-100 px-5 py-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.28em] text-apple-gray-500">
                    Flux actifs
                  </p>
                  <p className="mt-1 text-sm text-apple-gray-500">
                    Chaque lien est signé et peut être révoqué individuellement.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void loadFeeds()}
                  className="rounded-xl border border-apple-gray-200 bg-white px-3 py-2 text-xs font-semibold text-apple-gray-600 transition hover:text-black"
                >
                  Recharger
                </button>
              </div>

              <div className="max-h-[56vh] overflow-y-auto p-4 md:p-5">
                {isLoading ? (
                  <div className="flex min-h-40 items-center justify-center text-sm text-apple-gray-500">
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Chargement des flux...
                  </div>
                ) : feeds.length === 0 ? (
                  <div className="flex min-h-40 flex-col items-center justify-center rounded-[24px] border border-dashed border-apple-gray-200 bg-apple-gray-50 px-6 text-center">
                    <RadioTower className="h-8 w-8 text-apple-gray-300" />
                    <p className="mt-3 text-sm font-semibold text-black">
                      Aucun flux pour l’instant
                    </p>
                    <p className="mt-1 max-w-sm text-sm text-apple-gray-500">
                      Crée un flux à droite, puis colle le lien `webcal://` dans
                      ton application calendrier.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {feeds.map((feed) => (
                      <div
                        key={feed.id}
                        className="rounded-[24px] border border-apple-gray-100 bg-[linear-gradient(180deg,#ffffff_0%,#f8fafc_100%)] p-4 shadow-[0_12px_36px_rgba(15,23,42,0.06)]"
                      >
                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                          <div className="min-w-0">
                            <h3 className="text-base font-semibold text-black">
                              {feed.name}
                            </h3>
                            <p className="mt-1 text-sm text-apple-gray-500">
                              {describeSources(feed.sources)}
                            </p>
                            <div className="mt-3 flex flex-wrap gap-2">
                              <span className="rounded-full bg-apple-gray-100 px-2.5 py-1 text-[11px] font-semibold text-apple-gray-600">
                                {feed.include_completed
                                  ? "Avec terminés"
                                  : "Sans terminés"}
                              </span>
                              <span className="rounded-full bg-apple-gray-100 px-2.5 py-1 text-[11px] font-semibold text-apple-gray-600">
                                Dernier accès:{" "}
                                {formatTimestamp(feed.last_accessed_at)}
                              </span>
                            </div>
                          </div>

                          <button
                            type="button"
                            onClick={() => void handleDeleteFeed(feed)}
                            className="inline-flex items-center justify-center gap-2 self-start rounded-2xl border border-red-200 bg-white px-3 py-2 text-sm font-semibold text-red-500 transition hover:bg-red-50"
                          >
                            <Trash2 className="h-4 w-4" />
                            Révoquer
                          </button>
                        </div>

                        <div className="mt-4 grid gap-3 lg:grid-cols-2">
                          <div className="rounded-2xl border border-apple-gray-100 bg-white p-3">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-xs font-bold uppercase tracking-[0.24em] text-apple-gray-500">
                                Webcal
                              </span>
                              <button
                                type="button"
                                onClick={() =>
                                  void handleCopy(
                                    feed.webcal_url,
                                    `webcal-${feed.id}`,
                                  )
                                }
                                className="inline-flex items-center gap-1 text-xs font-semibold text-apple-blue transition hover:text-blue-700"
                              >
                                {copiedKey === `webcal-${feed.id}` ? (
                                  <>
                                    <Check className="h-3.5 w-3.5" />
                                    Copié
                                  </>
                                ) : (
                                  <>
                                    <Copy className="h-3.5 w-3.5" />
                                    Copier
                                  </>
                                )}
                              </button>
                            </div>
                            <p className="mt-2 break-all text-xs text-apple-gray-500">
                              {feed.webcal_url}
                            </p>
                          </div>

                          <div className="rounded-2xl border border-apple-gray-100 bg-white p-3">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-xs font-bold uppercase tracking-[0.24em] text-apple-gray-500">
                                ICS
                              </span>
                              <div className="flex items-center gap-3">
                                <button
                                  type="button"
                                  onClick={() =>
                                    void handleCopy(feed.ics_url, `ics-${feed.id}`)
                                  }
                                  className="inline-flex items-center gap-1 text-xs font-semibold text-apple-blue transition hover:text-blue-700"
                                >
                                  {copiedKey === `ics-${feed.id}` ? (
                                    <>
                                      <Check className="h-3.5 w-3.5" />
                                      Copié
                                    </>
                                  ) : (
                                    <>
                                      <Copy className="h-3.5 w-3.5" />
                                      Copier
                                    </>
                                  )}
                                </button>
                                <a
                                  href={feed.ics_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 text-xs font-semibold text-apple-gray-500 transition hover:text-black"
                                >
                                  <ExternalLink className="h-3.5 w-3.5" />
                                  Ouvrir
                                </a>
                              </div>
                            </div>
                            <p className="mt-2 break-all text-xs text-apple-gray-500">
                              {feed.ics_url}
                            </p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
