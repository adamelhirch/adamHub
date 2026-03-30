import {
  Check,
  CheckCircle2,
  CheckSquare,
  Circle,
  Clock,
  AlignLeft,
  X,
  Plus,
  Trash2,
  Calendar as CalendarIcon,
  Search,
  Filter,
  Repeat2,
  Flame,
  PauseCircle,
  PlayCircle,
  History,
  Pencil,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import { useTaskStore } from "../store/taskStore";
import type { TaskItem, TaskScheduleMode } from "../store/taskStore";
import {
  useHabitStore,
  type HabitFrequency,
  type HabitItem,
} from "../store/habitStore";

const PAGE_TABS = ["Tâches", "Routine"] as const;
type PageTab = (typeof PAGE_TABS)[number];

const FREQUENCY_LABELS: Record<HabitFrequency, string> = {
  daily: "Chaque jour",
  weekly: "Chaque semaine",
};

const TASK_SCHEDULE_LABELS: Record<TaskScheduleMode, string> = {
  none: "Non planifiée",
  once: "Une fois",
  daily: "Tous les jours",
  weekly: "Un jour de semaine",
};

const WEEKDAY_OPTIONS = [
  { value: 0, label: "Lundi" },
  { value: 1, label: "Mardi" },
  { value: 2, label: "Mercredi" },
  { value: 3, label: "Jeudi" },
  { value: 4, label: "Vendredi" },
  { value: 5, label: "Samedi" },
  { value: 6, label: "Dimanche" },
];

function buildTaskScheduleUpdate(
  scheduleMode: TaskScheduleMode,
  dateValue: string,
  timeValue: string,
  weekdayValue: number | null,
): Pick<
  TaskItem,
  "scheduleMode" | "slotId" | "scheduleTime" | "scheduleWeekday"
> {
  if (scheduleMode === "none") {
    return {
      scheduleMode,
      slotId: null,
      scheduleTime: null,
      scheduleWeekday: null,
    };
  }

  if (scheduleMode === "once") {
    return {
      scheduleMode,
      slotId: dateValue && timeValue ? `${dateValue}-${timeValue}` : null,
      scheduleTime: null,
      scheduleWeekday: null,
    };
  }

  return {
    scheduleMode,
    slotId: null,
    scheduleTime: timeValue || null,
    scheduleWeekday: scheduleMode === "weekly" ? weekdayValue : null,
  };
}

function formatTaskSchedule(task: TaskItem) {
  if (task.scheduleMode === "once" && task.slotId) {
    return `Le ${task.slotId.substring(0, 10)} à ${task.slotId.substring(11, 16)}`;
  }
  if (task.scheduleMode === "daily" && task.scheduleTime) {
    return `Tous les jours à ${task.scheduleTime}`;
  }
  if (
    task.scheduleMode === "weekly" &&
    task.scheduleTime &&
    task.scheduleWeekday !== null &&
    task.scheduleWeekday !== undefined
  ) {
    const dayLabel =
      WEEKDAY_OPTIONS.find((option) => option.value === task.scheduleWeekday)
        ?.label ?? "Jour inconnu";
    return `${dayLabel} à ${task.scheduleTime}`;
  }
  return "Inbox";
}

function formatHabitSchedule(habit: HabitItem) {
  const scheduleTimes =
    habit.scheduleTimes.length > 0
      ? habit.scheduleTimes
      : habit.scheduleTime
        ? [habit.scheduleTime]
        : [];
  if (scheduleTimes.length === 0) return "Hors calendrier";
  const scheduleLabel = scheduleTimes.join(", ");
  const scheduleDays =
    habit.scheduleWeekdays.length > 0
      ? habit.scheduleWeekdays
      : habit.scheduleWeekday !== null && habit.scheduleWeekday !== undefined
        ? [habit.scheduleWeekday]
        : [];
  if (habit.frequency === "weekly" && scheduleDays.length > 0) {
    const dayLabel = scheduleDays
      .map(
        (weekday) =>
          WEEKDAY_OPTIONS.find((option) => option.value === weekday)?.label ??
          "Jour inconnu",
      )
      .join(", ");
    return `${dayLabel} · ${scheduleLabel} · ${habit.durationMinutes} min`;
  }
  return `${scheduleLabel} · ${habit.durationMinutes} min`;
}

function TimeListInput({
  times,
  onChange,
}: {
  times: string[];
  onChange: (times: string[]) => void;
}) {
  const [value, setValue] = useState("08:00");

  const addTime = () => {
    if (!value) return;
    const next = Array.from(new Set([...times, value])).sort();
    onChange(next);
  };

  const removeTime = (timeToRemove: string) => {
    onChange(times.filter((time) => time !== timeToRemove));
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input
          type="time"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="w-full rounded-2xl border border-apple-gray-200 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
        />
        <button
          type="button"
          onClick={addTime}
          className="inline-flex items-center justify-center rounded-2xl bg-apple-blue px-4 py-3 text-white transition-colors hover:bg-blue-600"
          title="Ajouter un horaire"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {times.length === 0 ? (
          <span className="rounded-full bg-apple-gray-100 px-3 py-1 text-xs font-medium text-apple-gray-500">
            Aucun horaire
          </span>
        ) : (
          times.map((time) => (
            <span
              key={time}
              className="inline-flex items-center gap-2 rounded-full bg-apple-blue/10 px-3 py-1.5 text-xs font-semibold text-apple-blue"
            >
              {time}
              <button
                type="button"
                onClick={() => removeTime(time)}
                className="rounded-full p-0.5 transition-colors hover:bg-apple-blue/10"
                title="Retirer"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </span>
          ))
        )}
      </div>
    </div>
  );
}

function WeekdayListInput({
  days,
  onChange,
}: {
  days: number[];
  onChange: (days: number[]) => void;
}) {
  const toggleDay = (weekday: number) => {
    onChange(
      days.includes(weekday)
        ? days.filter((value) => value !== weekday)
        : [...days, weekday].sort((a, b) => a - b),
    );
  };

  return (
    <div className="flex flex-wrap gap-2">
      {WEEKDAY_OPTIONS.map((option) => {
        const active = days.includes(option.value);
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => toggleDay(option.value)}
            className={`rounded-full px-3 py-2 text-xs font-semibold transition-colors ${
              active
                ? "bg-apple-blue text-white"
                : "bg-apple-gray-100 text-apple-gray-600 hover:bg-apple-gray-200"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function TagInput({
  tags,
  setTags,
  placeholder,
  className,
}: {
  tags: string[];
  setTags: (tags: string[]) => void;
  placeholder?: string;
  className?: string;
}) {
  const [inputValue, setInputValue] = useState("");

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const newTag = inputValue.trim().replace(/^,+|,+$/g, "");
      if (newTag && !tags.includes(newTag)) {
        setTags([...tags, newTag]);
      }
      setInputValue("");
    } else if (e.key === "Backspace" && !inputValue && tags.length > 0) {
      setTags(tags.slice(0, -1));
    }
  };

  const removeTag = (tagToRemove: string) => {
    setTags(tags.filter((t) => t !== tagToRemove));
  };

  return (
    <div
      className={`flex flex-wrap items-center gap-1.5 w-full rounded-xl border border-apple-gray-200 bg-white px-3 py-2 shadow-sm transition-all focus-within:ring-2 focus-within:ring-apple-blue/50 ${className || ""}`}
    >
      {tags.map((tag) => (
        <span
          key={tag}
          className="flex items-center gap-1 rounded-md bg-apple-blue/10 pl-2 pr-1 py-1 text-[10px] font-semibold uppercase tracking-wider text-apple-blue"
        >
          {tag}
          <button
            type="button"
            onClick={() => removeTag(tag)}
            className="flex items-center justify-center rounded-sm p-0.5 transition-colors hover:bg-blue-200/50 hover:text-blue-800"
            title="Retirer le tag"
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      <input
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={tags.length === 0 ? placeholder : ""}
        className="min-w-[80px] flex-1 bg-transparent p-1 text-sm focus:outline-none"
      />
    </div>
  );
}

function StatCard({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string | number;
  tone?: "default" | "blue" | "amber" | "green";
}) {
  const toneClass =
    tone === "blue"
      ? "text-apple-blue"
      : tone === "amber"
        ? "text-amber-600"
        : tone === "green"
          ? "text-emerald-600"
          : "text-black";

  return (
    <div className="rounded-[24px] border border-white/70 bg-white/80 p-4 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl">
      <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
        {label}
      </p>
      <p className={`mt-2 text-2xl font-semibold ${toneClass}`}>{value}</p>
    </div>
  );
}

function HabitHistory({
  logs,
  loading,
}: {
  logs: Array<{ id: number; loggedAt: string; value: number; note?: string | null }>;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="rounded-2xl border border-apple-gray-100 bg-apple-gray-50 px-4 py-3 text-sm text-apple-gray-500">
        Chargement de l’historique…
      </div>
    );
  }

  if (logs.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-apple-gray-200 bg-apple-gray-50/70 px-4 py-3 text-sm text-apple-gray-500">
        Aucun passage enregistré pour cette routine.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {logs.map((log) => (
        <div
          key={log.id}
          className="flex items-start justify-between gap-3 rounded-2xl border border-apple-gray-100 bg-apple-gray-50/70 px-4 py-3"
        >
          <div>
            <p className="text-sm font-medium text-black">
              {format(new Date(log.loggedAt), "dd/MM/yyyy • HH:mm")}
            </p>
            {log.note ? (
              <p className="mt-1 text-sm text-apple-gray-500">{log.note}</p>
            ) : null}
          </div>
          <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-apple-gray-600">
            +{log.value}
          </span>
        </div>
      ))}
    </div>
  );
}

function HabitEditorModal({
  habit,
  onClose,
  onSave,
}: {
  habit: HabitItem | null;
  onClose: () => void;
  onSave: (habitId: number, payload: {
    name: string;
    description?: string | null;
    frequency: HabitFrequency;
    targetPerPeriod: number;
    scheduleTime: string | null;
    scheduleTimes: string[];
    scheduleWeekday: number | null;
    scheduleWeekdays: number[];
    durationMinutes: number;
  }) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [frequency, setFrequency] = useState<HabitFrequency>("daily");
  const [targetPerPeriod, setTargetPerPeriod] = useState("1");
  const [scheduleTimes, setScheduleTimes] = useState<string[]>([]);
  const [scheduleWeekdays, setScheduleWeekdays] = useState<number[]>([]);
  const [durationMinutes, setDurationMinutes] = useState("30");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!habit) return;
    setName(habit.name);
    setDescription(habit.description ?? "");
    setFrequency(habit.frequency);
    setTargetPerPeriod(String(habit.targetPerPeriod));
    setScheduleTimes(
      habit.scheduleTimes.length > 0
        ? habit.scheduleTimes
        : habit.scheduleTime
          ? [habit.scheduleTime]
          : [],
    );
    setScheduleWeekdays(
      habit.scheduleWeekdays.length > 0
        ? habit.scheduleWeekdays
        : habit.scheduleWeekday !== null && habit.scheduleWeekday !== undefined
          ? [habit.scheduleWeekday]
          : [],
    );
    setDurationMinutes(String(habit.durationMinutes));
  }, [habit]);

  if (!habit) return null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setIsSaving(true);
    try {
      await onSave(habit.id, {
        name: name.trim(),
        description: description.trim() || null,
        frequency,
        targetPerPeriod: parseInt(targetPerPeriod, 10) || 1,
        scheduleTime: scheduleTimes[0] ?? null,
        scheduleTimes,
        scheduleWeekday: frequency === "weekly" && scheduleTimes.length > 0
          ? scheduleWeekdays[0] ?? null
          : null,
        scheduleWeekdays: frequency === "weekly" ? scheduleWeekdays : [],
        durationMinutes: parseInt(durationMinutes, 10) || 30,
      });
      onClose();
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center bg-black/40 p-0 backdrop-blur-sm md:items-center md:p-4">
      <form
        onSubmit={submit}
        className="flex max-h-[92vh] w-full max-w-xl flex-col overflow-hidden rounded-t-3xl bg-white shadow-2xl md:rounded-3xl"
      >
        <div className="flex items-center justify-between border-b border-apple-gray-200 bg-apple-gray-50 px-4 py-4 md:px-6">
          <h2 className="text-lg font-bold md:text-xl">Modifier la routine</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-2 text-apple-gray-500 transition-colors hover:bg-apple-gray-200 hover:text-black"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="hide-scrollbar overflow-y-auto p-4 pb-[calc(env(safe-area-inset-bottom)+5.5rem)] md:p-6">
          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                Nom
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-2xl border border-apple-gray-200 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                  Fréquence
                </label>
                <select
                  value={frequency}
                  onChange={(e) => setFrequency(e.target.value as HabitFrequency)}
                  className="w-full rounded-2xl border border-apple-gray-200 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
                >
                  <option value="daily">Chaque jour</option>
                  <option value="weekly">Chaque semaine</option>
                </select>
              </div>
              <div>
                <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                  Objectif par période
                </label>
                <input
                  type="number"
                  min="1"
                  max="365"
                  value={targetPerPeriod}
                  onChange={(e) => setTargetPerPeriod(e.target.value)}
                  className="w-full rounded-2xl border border-apple-gray-200 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
                />
              </div>
            </div>

            <div>
              <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                Horaires calendrier
              </label>
              <TimeListInput times={scheduleTimes} onChange={setScheduleTimes} />
            </div>

            {frequency === "weekly" ? (
              <div>
                <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                  Jours
                </label>
                <WeekdayListInput
                  days={scheduleWeekdays}
                  onChange={setScheduleWeekdays}
                />
              </div>
            ) : null}

            <div>
              <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                Durée
              </label>
              <div className="relative">
                <input
                  type="number"
                  min="1"
                  value={durationMinutes}
                  onChange={(e) => setDurationMinutes(e.target.value)}
                  className="w-full rounded-2xl border border-apple-gray-200 bg-white px-4 py-3 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
                />
                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-apple-gray-400">
                  min
                </span>
              </div>
            </div>

            <div>
              <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                className="w-full resize-none rounded-2xl border border-apple-gray-200 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
              />
            </div>
          </div>
        </div>

        <div className="flex justify-between gap-3 border-t border-apple-gray-200 bg-apple-gray-50 p-4 md:p-6">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl px-4 py-2 font-semibold text-apple-gray-600 transition-colors hover:bg-apple-gray-100"
          >
            Annuler
          </button>
          <button
            type="submit"
            disabled={isSaving}
            className="rounded-xl bg-apple-blue px-6 py-2 font-semibold text-white transition-colors hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSaving ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>
      </form>
    </div>
  );
}

export default function TasksPage() {
  const {
    tasks,
    addTask: storeAddTask,
    updateTask,
    deleteTask: storeDeleteTask,
    fetchTasks,
    toggleTask: storeToggleTask,
  } = useTaskStore();
  const {
    habits,
    logsByHabitId,
    isLoading: habitsLoading,
    fetchHabits,
    createHabit,
    updateHabit,
    logHabit,
    fetchHabitLogs,
  } = useHabitStore();

  useEffect(() => {
    fetchTasks();
    fetchHabits(false);
  }, [fetchTasks, fetchHabits]);

  const [activeTab, setActiveTab] = useState<PageTab>("Tâches");
  const [showTaskComposer, setShowTaskComposer] = useState(false);
  const [showRoutineComposer, setShowRoutineComposer] = useState(false);

  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskDuration, setNewTaskDuration] = useState("30");
  const [newTaskTags, setNewTaskTags] = useState<string[]>(["Personal"]);
  const [newTaskScheduleMode, setNewTaskScheduleMode] =
    useState<TaskScheduleMode>("none");
  const [newTaskScheduleDate, setNewTaskScheduleDate] = useState(
    format(new Date(), "yyyy-MM-dd"),
  );
  const [newTaskScheduleTime, setNewTaskScheduleTime] = useState("09:00");
  const [newTaskScheduleWeekday, setNewTaskScheduleWeekday] = useState(0);
  const [selectedTask, setSelectedTask] = useState<TaskItem | null>(null);
  const [overlapError, setOverlapError] = useState<string | null>(null);
  const [newSubtaskTitle, setNewSubtaskTitle] = useState("");

  const [filterTitle, setFilterTitle] = useState("");
  const [filterTags, setFilterTags] = useState<string[]>([]);
  const [filterDate, setFilterDate] = useState("");
  const [filterDuration, setFilterDuration] = useState("");

  const [newHabitName, setNewHabitName] = useState("");
  const [newHabitDescription, setNewHabitDescription] = useState("");
  const [newHabitFrequency, setNewHabitFrequency] =
    useState<HabitFrequency>("daily");
  const [newHabitTarget, setNewHabitTarget] = useState("1");
  const [newHabitScheduleTimes, setNewHabitScheduleTimes] = useState<string[]>(
    [],
  );
  const [newHabitScheduleWeekdays, setNewHabitScheduleWeekdays] = useState<
    number[]
  >([]);
  const [newHabitDuration, setNewHabitDuration] = useState("30");
  const [editingHabit, setEditingHabit] = useState<HabitItem | null>(null);
  const [expandedHabitId, setExpandedHabitId] = useState<number | null>(null);
  const [logsLoadingHabitId, setLogsLoadingHabitId] = useState<number | null>(
    null,
  );

  const filteredTasks = tasks.filter((task) => {
    if (
      filterTitle &&
      !task.title.toLowerCase().includes(filterTitle.toLowerCase())
    ) {
      return false;
    }

    if (
      filterTags.length > 0 &&
      !filterTags.some((tag) =>
        task.tags?.some((t) => t.toLowerCase() === tag.toLowerCase()),
      )
    ) {
      return false;
    }

    if (
      filterDate &&
      !(task.scheduleMode === "once" && task.slotId?.startsWith(filterDate))
    ) {
      return false;
    }
    if (filterDuration && task.duration !== parseInt(filterDuration, 10)) {
      return false;
    }

    return true;
  });

  const taskStats = useMemo(
    () => ({
      total: tasks.length,
      open: tasks.filter((task) => !task.completed).length,
      scheduled: tasks.filter((task) => task.scheduleMode !== "none").length,
    }),
    [tasks],
  );

  const routineStats = useMemo(
    () => ({
      total: habits.length,
      active: habits.filter((habit) => habit.active).length,
      paused: habits.filter((habit) => !habit.active).length,
      longestStreak: habits.reduce(
        (max, habit) => Math.max(max, habit.streak),
        0,
      ),
    }),
    [habits],
  );

  const sortedHabits = useMemo(() => {
    return [...habits].sort((a, b) => {
      if (a.active !== b.active) return a.active ? -1 : 1;
      return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
    });
  }, [habits]);

  const timeToMinutes = (timeStr: string) => {
    if (!timeStr) return 0;
    const [h, m] = timeStr.split(":").map(Number);
    return (h || 0) * 60 + (m || 0);
  };

  const checkOverlap = (
    slotId: string | null,
    duration: number,
    excludeId?: string,
  ) => {
    if (!slotId) return false;
    const tStart = timeToMinutes(slotId.substring(11, 16));
    const tEnd = tStart + duration;
    const dateStr = slotId.substring(0, 10);

    return tasks.some((t) => {
      if (
        (excludeId && t.id === excludeId) ||
        !t.slotId ||
        !t.slotId.startsWith(dateStr)
      ) {
        return false;
      }
      const oStart = timeToMinutes(t.slotId.substring(11, 16));
      const oEnd = oStart + t.duration;
      return Math.max(tStart, oStart) < Math.min(tEnd, oEnd);
    });
  };

  const toggleTask = (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    void storeToggleTask(id);
  };

  const addTask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim()) return;

    void storeAddTask({
      title: newTaskTitle,
      tags: newTaskTags.length > 0 ? newTaskTags : ["Personal"],
      duration: parseInt(newTaskDuration, 10) || 30,
      ...buildTaskScheduleUpdate(
        newTaskScheduleMode,
        newTaskScheduleDate,
        newTaskScheduleTime,
        newTaskScheduleWeekday,
      ),
    });

    setNewTaskTitle("");
    setNewTaskTags(["Personal"]);
    setNewTaskDuration("30");
    setNewTaskScheduleMode("none");
    setNewTaskScheduleDate(format(new Date(), "yyyy-MM-dd"));
    setNewTaskScheduleTime("09:00");
    setNewTaskScheduleWeekday(0);
    setShowTaskComposer(false);
  };

  const updateSelectedTask = (updates: Partial<TaskItem>) => {
    if (!selectedTask) return;

    const newSlotId =
      updates.slotId !== undefined ? updates.slotId : selectedTask.slotId;
    const newDuration =
      updates.duration !== undefined ? updates.duration : selectedTask.duration;
    const nextScheduleMode =
      updates.scheduleMode !== undefined
        ? updates.scheduleMode
        : selectedTask.scheduleMode;

    if (
      nextScheduleMode === "once" &&
      newSlotId &&
      checkOverlap(newSlotId, newDuration, selectedTask.id)
    ) {
      setOverlapError("Ce créneau chevauche déjà une autre tâche.");
      setTimeout(() => setOverlapError(null), 3000);
      return;
    }

    const updatedTask = { ...selectedTask, ...updates };
    setSelectedTask(updatedTask);
    void updateTask(selectedTask.id, updates);
  };

  const addSubtask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTask || !newSubtaskTitle.trim()) return;
    const subtasks = selectedTask.subtasks || [];
    updateSelectedTask({
      subtasks: [
        ...subtasks,
        { id: Date.now().toString(), title: newSubtaskTitle, completed: false },
      ],
    });
    setNewSubtaskTitle("");
  };

  const toggleSubtask = (subId: string) => {
    if (!selectedTask || !selectedTask.subtasks) return;
    updateSelectedTask({
      subtasks: selectedTask.subtasks.map((subtask) =>
        subtask.id === subId
          ? { ...subtask, completed: !subtask.completed }
          : subtask,
      ),
    });
  };

  const deleteSubtask = (subId: string) => {
    if (!selectedTask || !selectedTask.subtasks) return;
    updateSelectedTask({
      subtasks: selectedTask.subtasks.filter((subtask) => subtask.id !== subId),
    });
  };

  const deleteTask = (taskId: string) => {
    void storeDeleteTask(taskId);
    if (selectedTask?.id === taskId) setSelectedTask(null);
  };

  const handleCreateHabit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newHabitName.trim()) return;

    await createHabit({
      name: newHabitName.trim(),
      description: newHabitDescription.trim() || undefined,
      frequency: newHabitFrequency,
      targetPerPeriod: parseInt(newHabitTarget, 10) || 1,
      scheduleTime: newHabitScheduleTimes[0] ?? null,
      scheduleTimes: newHabitScheduleTimes,
      scheduleWeekday:
        newHabitFrequency === "weekly" && newHabitScheduleTimes.length > 0
          ? newHabitScheduleWeekdays[0] ?? null
          : null,
      scheduleWeekdays:
        newHabitFrequency === "weekly" ? newHabitScheduleWeekdays : [],
      durationMinutes: parseInt(newHabitDuration, 10) || 30,
    });

    setNewHabitName("");
    setNewHabitDescription("");
    setNewHabitFrequency("daily");
    setNewHabitTarget("1");
    setNewHabitScheduleTimes([]);
    setNewHabitScheduleWeekdays([]);
    setNewHabitDuration("30");
    setShowRoutineComposer(false);
  };

  const handleToggleHabit = async (habit: HabitItem) => {
    await updateHabit(habit.id, { active: !habit.active });
  };

  const handleSaveHabit = async (
    habitId: number,
    payload: {
      name: string;
      description?: string | null;
      frequency: HabitFrequency;
      targetPerPeriod: number;
      scheduleTime: string | null;
      scheduleTimes: string[];
      scheduleWeekday: number | null;
      scheduleWeekdays: number[];
      durationMinutes: number;
    },
  ) => {
    await updateHabit(habitId, payload);
  };

  const handleLogHabit = async (habit: HabitItem) => {
    await logHabit(habit.id, 1);
  };

  const handleToggleHistory = async (habitId: number) => {
    if (expandedHabitId === habitId) {
      setExpandedHabitId(null);
      return;
    }

    setExpandedHabitId(habitId);
    if (logsByHabitId[habitId]) return;

    try {
      setLogsLoadingHabitId(habitId);
      await fetchHabitLogs(habitId, 12);
    } finally {
      setLogsLoadingHabitId(null);
    }
  };

  return (
    <div className="flex h-full flex-1 flex-col overflow-hidden bg-transparent">
      <div className="sticky top-0 z-10 border-b border-white/60 bg-white/75 px-4 py-4 shadow-[0_8px_30px_rgba(15,23,42,0.06)] backdrop-blur-xl md:px-8 md:py-5">
        <div className="mx-auto flex max-w-5xl items-end justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-apple-gray-500">
              Organisation
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-black md:text-3xl">
              Tâches et routine
            </h1>
            <p className="mt-1 text-sm text-apple-gray-500">
              Sépare les actions ponctuelles de ta routine pour garder une vue
              plus claire.
            </p>
          </div>
          <button
            type="button"
            onClick={() =>
              activeTab === "Tâches"
                ? setShowTaskComposer((current) => !current)
                : setShowRoutineComposer((current) => !current)
            }
            className="inline-flex items-center gap-2 rounded-2xl bg-apple-blue px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-600"
          >
            <Plus className="h-4 w-4" />
            {activeTab === "Tâches"
              ? showTaskComposer
                ? "Fermer"
                : "Nouvelle tâche"
              : showRoutineComposer
                ? "Fermer"
                : "Nouvelle routine"}
          </button>
        </div>
      </div>

      <div className="border-b border-white/60 bg-white/60 px-4 backdrop-blur-xl md:px-8">
        <div className="mx-auto flex max-w-5xl gap-1 overflow-x-auto py-2">
          {PAGE_TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`rounded-full px-4 py-2.5 text-sm font-semibold transition-all ${
                activeTab === tab
                  ? "bg-white text-black shadow-[0_8px_24px_rgba(15,23,42,0.06)] ring-1 ring-black/5"
                  : "text-apple-gray-500 hover:bg-white/70 hover:text-black"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-1 flex-col items-center overflow-y-auto px-4 py-4 pb-[calc(env(safe-area-inset-bottom)+5.75rem)] md:px-8 md:py-6">
        <div className="w-full max-w-5xl space-y-6">
          {activeTab === "Tâches" ? (
            <>
              <div className="grid gap-4 md:grid-cols-3">
                <StatCard label="Total" value={taskStats.total} />
                <StatCard label="Ouvertes" value={taskStats.open} tone="blue" />
                <StatCard
                  label="Planifiées"
                  value={taskStats.scheduled}
                  tone="green"
                />
              </div>

              {showTaskComposer ? (
                <form
                  onSubmit={addTask}
                  className="relative grid gap-3 rounded-[28px] border border-white/60 bg-white/80 p-4 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl md:p-5"
                >
                  <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_320px_112px_auto] md:items-center">
                    <div className="relative min-w-0">
                      <input
                        type="text"
                        value={newTaskTitle}
                        onChange={(e) => setNewTaskTitle(e.target.value)}
                        placeholder="Ajouter une tâche dans l’inbox…"
                        className="w-full rounded-2xl border border-apple-gray-200 bg-white/90 px-4 py-4 text-base transition-all focus:outline-none focus:ring-2 focus:ring-apple-blue/40 md:text-lg"
                      />
                    </div>
                    <div className="relative min-w-0">
                      <TagInput
                        tags={newTaskTags}
                        setTags={setNewTaskTags}
                        placeholder="Ajouter des tags…"
                        className="py-2.5"
                      />
                    </div>
                    <div className="relative min-w-0">
                      <input
                        type="number"
                        value={newTaskDuration}
                        onChange={(e) => setNewTaskDuration(e.target.value)}
                        placeholder="Min"
                        className="w-full rounded-2xl border border-apple-gray-200 bg-white/90 px-4 py-4 text-lg transition-all focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
                      />
                      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm text-apple-gray-400">
                        m
                      </span>
                    </div>
                    <button
                      type="submit"
                      className="whitespace-nowrap rounded-2xl bg-apple-blue px-6 py-4 font-semibold text-white transition-colors hover:bg-blue-600"
                    >
                      Ajouter
                    </button>
                  </div>

                  <div className="grid gap-3 rounded-2xl border border-apple-gray-100 bg-apple-gray-50 p-4 md:grid-cols-4">
                    <div>
                      <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                        Planning
                      </label>
                      <select
                        value={newTaskScheduleMode}
                        onChange={(e) =>
                          setNewTaskScheduleMode(e.target.value as TaskScheduleMode)
                        }
                        className="w-full rounded-xl border border-apple-gray-200 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
                      >
                        {Object.entries(TASK_SCHEDULE_LABELS).map(([value, label]) => (
                          <option key={value} value={value}>
                            {label}
                          </option>
                        ))}
                      </select>
                    </div>

                    {newTaskScheduleMode === "once" ? (
                      <>
                        <div>
                          <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                            Date
                          </label>
                          <input
                            type="date"
                            value={newTaskScheduleDate}
                            onChange={(e) => setNewTaskScheduleDate(e.target.value)}
                            className="w-full rounded-xl border border-apple-gray-200 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
                          />
                        </div>
                        <div>
                          <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                            Heure
                          </label>
                          <input
                            type="time"
                            value={newTaskScheduleTime}
                            onChange={(e) => setNewTaskScheduleTime(e.target.value)}
                            className="w-full rounded-xl border border-apple-gray-200 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
                          />
                        </div>
                      </>
                    ) : null}

                    {newTaskScheduleMode === "daily" ? (
                      <div>
                        <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                          Heure
                        </label>
                        <input
                          type="time"
                          value={newTaskScheduleTime}
                          onChange={(e) => setNewTaskScheduleTime(e.target.value)}
                          className="w-full rounded-xl border border-apple-gray-200 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
                        />
                      </div>
                    ) : null}

                    {newTaskScheduleMode === "weekly" ? (
                      <>
                        <div>
                          <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                            Jour
                          </label>
                          <select
                            value={newTaskScheduleWeekday}
                            onChange={(e) =>
                              setNewTaskScheduleWeekday(parseInt(e.target.value, 10))
                            }
                            className="w-full rounded-xl border border-apple-gray-200 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
                          >
                            {WEEKDAY_OPTIONS.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                            Heure
                          </label>
                          <input
                            type="time"
                            value={newTaskScheduleTime}
                            onChange={(e) => setNewTaskScheduleTime(e.target.value)}
                            className="w-full rounded-xl border border-apple-gray-200 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
                          />
                        </div>
                      </>
                    ) : null}
                  </div>
                </form>
              ) : null}

              <div className="flex flex-col gap-4 rounded-[28px] border border-white/60 bg-white/75 p-4 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl md:p-5">
                <div className="flex items-center gap-2 px-1 text-sm font-medium text-apple-gray-500">
                  <Filter className="h-4 w-4" />
                  <span>Filtrer les tâches</span>
                </div>
                <div className="flex flex-wrap gap-3">
                  <div className="relative min-w-[150px] flex-1">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-apple-gray-400" />
                    <input
                      type="text"
                      placeholder="Titre…"
                      value={filterTitle}
                      onChange={(e) => setFilterTitle(e.target.value)}
                      className="w-full rounded-xl border border-apple-gray-200 py-2.5 pl-9 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                    />
                  </div>
                  <div className="relative w-[200px] shrink-0">
                    <TagInput
                      tags={filterTags}
                      setTags={setFilterTags}
                      placeholder="Tags…"
                      className="py-1.5"
                    />
                  </div>
                  <div className="relative w-[140px] shrink-0">
                    <input
                      type="date"
                      value={filterDate}
                      onChange={(e) => setFilterDate(e.target.value)}
                      className="w-full rounded-xl border border-apple-gray-200 bg-white px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                    />
                  </div>
                  <div className="relative w-[100px] shrink-0">
                    <input
                      type="number"
                      placeholder="Durée"
                      value={filterDuration}
                      onChange={(e) => setFilterDuration(e.target.value)}
                      className="w-full rounded-xl border border-apple-gray-200 py-2.5 pl-3 pr-7 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                    />
                    <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-apple-gray-400">
                      m
                    </span>
                  </div>
                  {filterTitle ||
                  filterTags.length > 0 ||
                  filterDate ||
                  filterDuration ? (
                    <button
                      type="button"
                      onClick={() => {
                        setFilterTitle("");
                        setFilterTags([]);
                        setFilterDate("");
                        setFilterDuration("");
                      }}
                      className="rounded-xl px-3 py-2.5 text-sm font-medium text-apple-gray-500 transition-colors hover:bg-apple-gray-100 hover:text-black"
                    >
                      Réinitialiser
                    </button>
                  ) : null}
                </div>
              </div>

              <div className="flex flex-col divide-y divide-apple-gray-100 overflow-hidden rounded-[28px] border border-white/60 bg-white/75 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl">
                {filteredTasks.length === 0 ? (
                  <div className="py-12 text-center text-apple-gray-500">
                    Aucune tâche ne correspond aux filtres.
                  </div>
                ) : (
                  filteredTasks.map((task) => (
                    <div
                      key={task.id}
                      className={`flex cursor-pointer items-center px-6 py-4 transition-colors hover:bg-apple-gray-50 ${task.completed ? "opacity-60" : ""}`}
                      onClick={() => setSelectedTask(task)}
                    >
                      <div
                        className="mr-4 cursor-pointer text-apple-gray-400 transition-colors hover:text-apple-blue"
                        onClick={(e) => toggleTask(task.id, e)}
                      >
                        {task.completed ? (
                          <CheckCircle2 className="h-6 w-6 text-apple-blue" />
                        ) : (
                          <Circle className="h-6 w-6" />
                        )}
                      </div>
                      <div className="flex flex-1 flex-col">
                        <span
                          className={`text-lg font-medium transition-all ${task.completed ? "text-apple-gray-400 line-through" : "text-black"}`}
                        >
                          {task.title}
                        </span>
                        <div className="mt-1 flex flex-wrap items-center gap-2">
                          {task.tags?.map((tag) => (
                            <span
                              key={tag}
                              className="rounded-md bg-apple-blue/10 px-2 py-0.5 text-xs font-semibold uppercase tracking-wider text-apple-blue"
                            >
                              {tag}
                            </span>
                          ))}
                          {task.scheduleMode !== "none" ? (
                            <span className="flex items-center rounded-md bg-apple-gray-100 px-2 py-0.5 text-xs font-semibold text-apple-gray-600">
                              <CalendarIcon className="mr-1 h-3.5 w-3.5" />
                              {formatTaskSchedule(task)}
                            </span>
                          ) : null}
                          <div className="flex items-center text-xs font-medium text-apple-gray-500">
                            <Clock className="mr-1 h-3.5 w-3.5" />
                            {task.duration}m
                          </div>
                          {task.description ? (
                            <div
                              className="flex items-center text-xs text-apple-gray-400"
                              title="Description présente"
                            >
                              <AlignLeft className="h-3.5 w-3.5" />
                            </div>
                          ) : null}
                          {task.subtasks && task.subtasks.length > 0 ? (
                            <div
                              className="flex items-center text-xs text-apple-gray-400"
                              title={`${task.subtasks.filter((subtask) => subtask.completed).length}/${task.subtasks.length} étapes cochées`}
                            >
                              <CheckSquare className="mr-1 h-3.5 w-3.5" />
                              {
                                task.subtasks.filter((subtask) => subtask.completed)
                                  .length
                              }
                              /{task.subtasks.length}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </>
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-4">
                <StatCard label="Routines" value={routineStats.total} />
                <StatCard
                  label="Actives"
                  value={routineStats.active}
                  tone="green"
                />
                <StatCard
                  label="En pause"
                  value={routineStats.paused}
                  tone="amber"
                />
                <StatCard
                  label="Meilleure série"
                  value={routineStats.longestStreak}
                  tone="blue"
                />
              </div>

              {showRoutineComposer ? (
                <form
                  onSubmit={handleCreateHabit}
                  className="grid gap-3 rounded-[28px] border border-white/60 bg-white/80 p-4 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl md:grid-cols-2 md:p-5"
                >
                  <div className="md:col-span-2">
                    <input
                      type="text"
                      value={newHabitName}
                      onChange={(e) => setNewHabitName(e.target.value)}
                      placeholder="Nom de la routine…"
                      className="w-full rounded-2xl border border-apple-gray-200 bg-white/90 px-4 py-4 text-base transition-all focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                      Fréquence
                    </label>
                    <select
                      value={newHabitFrequency}
                      onChange={(e) =>
                        setNewHabitFrequency(e.target.value as HabitFrequency)
                      }
                      className="w-full rounded-2xl border border-apple-gray-200 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
                    >
                      <option value="daily">Chaque jour</option>
                      <option value="weekly">Chaque semaine</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                      Objectif par période
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="365"
                      value={newHabitTarget}
                      onChange={(e) => setNewHabitTarget(e.target.value)}
                      className="w-full rounded-2xl border border-apple-gray-200 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                      Horaires calendrier
                    </label>
                    <TimeListInput
                      times={newHabitScheduleTimes}
                      onChange={setNewHabitScheduleTimes}
                    />
                  </div>
                  {newHabitFrequency === "weekly" ? (
                    <div>
                      <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                        Jours
                      </label>
                      <WeekdayListInput
                        days={newHabitScheduleWeekdays}
                        onChange={setNewHabitScheduleWeekdays}
                      />
                    </div>
                  ) : null}
                  <div>
                    <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-apple-gray-500">
                      Durée
                    </label>
                    <div className="relative">
                      <input
                        type="number"
                        min="1"
                        value={newHabitDuration}
                        onChange={(e) => setNewHabitDuration(e.target.value)}
                        className="w-full rounded-2xl border border-apple-gray-200 bg-white px-4 py-3 pr-9 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
                      />
                      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-apple-gray-400">
                        min
                      </span>
                    </div>
                  </div>
                  <div className="md:col-span-2">
                    <textarea
                      value={newHabitDescription}
                      onChange={(e) => setNewHabitDescription(e.target.value)}
                      placeholder="Petit rappel ou contexte…"
                      rows={3}
                      className="w-full resize-none rounded-2xl border border-apple-gray-200 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
                    />
                  </div>
                  <div className="md:col-span-2 flex justify-end">
                    <button
                      type="submit"
                      className="rounded-2xl bg-apple-blue px-6 py-3 font-semibold text-white transition-colors hover:bg-blue-600"
                    >
                      Créer la routine
                    </button>
                  </div>
                </form>
              ) : null}

              <div className="rounded-[28px] border border-white/60 bg-white/75 p-4 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl md:p-5">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-apple-gray-500">
                      Routine
                    </p>
                    <h2 className="mt-2 text-xl font-semibold text-black">
                      Habitudes récurrentes
                    </h2>
                  </div>
                  <div className="rounded-full bg-apple-gray-100 px-3 py-1 text-xs font-semibold text-apple-gray-500">
                    {routineStats.active} actives
                  </div>
                </div>

                <div className="space-y-4">
                  {habitsLoading && habits.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-apple-gray-200 px-4 py-8 text-center text-sm text-apple-gray-500">
                      Chargement des routines…
                    </div>
                  ) : sortedHabits.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-apple-gray-200 px-4 py-8 text-center text-sm text-apple-gray-500">
                      Aucune routine pour le moment. Ajoute la première pour
                      suivre tes habitudes séparément des tâches.
                    </div>
                  ) : (
                    sortedHabits.map((habit) => {
                      const isExpanded = expandedHabitId === habit.id;
                      const habitLogs = logsByHabitId[habit.id] ?? [];

                      return (
                        <div
                          key={habit.id}
                          className={`rounded-[26px] border p-4 shadow-[0_16px_42px_rgba(15,23,42,0.06)] transition-all ${
                            habit.active
                              ? "border-white/70 bg-white"
                              : "border-amber-100 bg-amber-50/70"
                          }`}
                        >
                          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <h3 className="text-lg font-semibold text-black">
                                  {habit.name}
                                </h3>
                                <span
                                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${
                                    habit.active
                                      ? "bg-emerald-50 text-emerald-600"
                                      : "bg-amber-100 text-amber-700"
                                  }`}
                                >
                                  {habit.active ? "Active" : "En pause"}
                                </span>
                              </div>

                              {habit.description ? (
                                <p className="mt-2 text-sm leading-6 text-apple-gray-500">
                                  {habit.description}
                                </p>
                              ) : null}

                              <div className="mt-4 flex flex-wrap items-center gap-2">
                                <span className="inline-flex items-center rounded-full bg-apple-blue/10 px-3 py-1 text-xs font-semibold text-apple-blue">
                                  <Repeat2 className="mr-1.5 h-3.5 w-3.5" />
                                  {FREQUENCY_LABELS[habit.frequency]}
                                </span>
                                <span className="inline-flex items-center rounded-full bg-orange-50 px-3 py-1 text-xs font-semibold text-orange-600">
                                  <Flame className="mr-1.5 h-3.5 w-3.5" />
                                  Série {habit.streak}
                                </span>
                                <span className="rounded-full bg-apple-gray-100 px-3 py-1 text-xs font-semibold text-apple-gray-600">
                                  Objectif {habit.targetPerPeriod}
                                </span>
                                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                                  {formatHabitSchedule(habit)}
                                </span>
                              </div>
                            </div>

                            <div className="flex flex-wrap gap-2 lg:justify-end">
                              <button
                                type="button"
                                onClick={() => void handleLogHabit(habit)}
                                className="inline-flex items-center gap-2 rounded-2xl bg-apple-blue px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-600"
                              >
                                <Check className="h-4 w-4" />
                                Marquer fait
                              </button>
                              <button
                                type="button"
                                onClick={() => void handleToggleHistory(habit.id)}
                                className="inline-flex items-center gap-2 rounded-2xl border border-apple-gray-200 bg-white px-4 py-2.5 text-sm font-semibold text-apple-gray-600 transition-colors hover:border-apple-blue/30 hover:text-black"
                              >
                                <History className="h-4 w-4" />
                                Historique
                              </button>
                              <button
                                type="button"
                                onClick={() => setEditingHabit(habit)}
                                className="inline-flex items-center gap-2 rounded-2xl border border-apple-gray-200 bg-white px-4 py-2.5 text-sm font-semibold text-apple-gray-600 transition-colors hover:border-apple-blue/30 hover:text-black"
                              >
                                <Pencil className="h-4 w-4" />
                                Modifier
                              </button>
                              <button
                                type="button"
                                onClick={() => void handleToggleHabit(habit)}
                                className={`inline-flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-semibold transition-colors ${
                                  habit.active
                                    ? "border border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100"
                                    : "border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                                }`}
                              >
                                {habit.active ? (
                                  <PauseCircle className="h-4 w-4" />
                                ) : (
                                  <PlayCircle className="h-4 w-4" />
                                )}
                                {habit.active ? "Mettre en pause" : "Réactiver"}
                              </button>
                            </div>
                          </div>

                          {isExpanded ? (
                            <div className="mt-4 border-t border-apple-gray-100 pt-4">
                              <HabitHistory
                                logs={habitLogs}
                                loading={logsLoadingHabitId === habit.id}
                              />
                            </div>
                          ) : null}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {selectedTask ? (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-3xl bg-white shadow-2xl animate-in fade-in zoom-in-95 duration-200">
            <div className="flex shrink-0 items-center justify-between border-b border-apple-gray-200 bg-apple-gray-50 px-6 py-4">
              <h2 className="text-xl font-bold">Modifier la tâche</h2>
              <button
                onClick={() => {
                  setSelectedTask(null);
                  setOverlapError(null);
                }}
                className="rounded-full p-2 text-apple-gray-500 transition-colors hover:bg-apple-gray-200 hover:text-black"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="hide-scrollbar w-full overflow-y-auto p-6 pb-[calc(env(safe-area-inset-bottom)+6.5rem)] md:pb-6">
              <div className="space-y-6">
                {overlapError ? (
                  <div className="flex items-center rounded-xl border border-red-100 bg-red-50 p-3 text-sm text-red-600">
                    <span className="font-medium">{overlapError}</span>
                  </div>
                ) : null}

                <div className="space-y-4">
                  <div>
                    <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-apple-gray-500">
                      Titre
                    </label>
                    <input
                      type="text"
                      value={selectedTask.title}
                      onChange={(e) =>
                        updateSelectedTask({ title: e.target.value })
                      }
                      className="w-full rounded-xl border border-apple-gray-200 px-4 py-3 text-lg font-medium shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                    />
                  </div>

                  <div className="flex flex-col gap-4 sm:flex-row">
                    <div className="flex-1">
                      <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-apple-gray-500">
                        Tags
                      </label>
                      <TagInput
                        tags={selectedTask.tags || []}
                        setTags={(newTags) =>
                          updateSelectedTask({ tags: newTags })
                        }
                        placeholder="Ajouter des tags…"
                      />
                    </div>
                    <div className="w-full sm:w-32">
                      <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-apple-gray-500">
                        Durée
                      </label>
                      <div className="relative">
                        <input
                          type="number"
                          value={selectedTask.duration}
                          onChange={(e) =>
                            updateSelectedTask({
                              duration: parseInt(e.target.value, 10) || 0,
                            })
                          }
                          className="w-full rounded-xl border border-apple-gray-200 py-3 pl-4 pr-8 text-base shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                        />
                        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-apple-gray-400">
                          m
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-4 rounded-xl border border-apple-gray-100 bg-apple-gray-50 p-4 sm:grid-cols-3">
                    <div>
                      <label className="mb-2 flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-apple-gray-500">
                        <CalendarIcon className="h-3.5 w-3.5" /> Planning
                      </label>
                      <select
                        value={selectedTask.scheduleMode}
                        onChange={(e) => {
                          const nextMode = e.target.value as TaskScheduleMode;
                          const currentDate =
                            selectedTask.slotId?.substring(0, 10) ??
                            format(new Date(), "yyyy-MM-dd");
                          const currentTime =
                            selectedTask.slotId?.substring(11, 16) ??
                            selectedTask.scheduleTime ??
                            "09:00";
                          updateSelectedTask(
                            buildTaskScheduleUpdate(
                              nextMode,
                              currentDate,
                              currentTime,
                              selectedTask.scheduleWeekday ?? 0,
                            ),
                          );
                        }}
                        className="w-full rounded-lg border border-apple-gray-200 bg-white px-4 py-2.5 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                      >
                        {Object.entries(TASK_SCHEDULE_LABELS).map(([value, label]) => (
                          <option key={value} value={value}>
                            {label}
                          </option>
                        ))}
                      </select>
                    </div>

                    {selectedTask.scheduleMode === "once" ? (
                      <>
                        <div>
                          <label className="mb-2 flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-apple-gray-500">
                            <CalendarIcon className="h-3.5 w-3.5" /> Date
                          </label>
                          <input
                            type="date"
                            min={format(new Date(), "yyyy-MM-dd")}
                            value={
                              selectedTask.slotId
                                ? selectedTask.slotId.substring(0, 10)
                                : format(new Date(), "yyyy-MM-dd")
                            }
                            onChange={(e) => {
                              updateSelectedTask(
                                buildTaskScheduleUpdate(
                                  "once",
                                  e.target.value,
                                  selectedTask.slotId?.substring(11, 16) ?? "09:00",
                                  null,
                                ),
                              );
                            }}
                            className="w-full rounded-lg border border-apple-gray-200 bg-white px-4 py-2.5 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                          />
                        </div>
                        <div>
                          <label className="mb-2 flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-apple-gray-500">
                            <Clock className="h-3.5 w-3.5" /> Heure
                          </label>
                          <input
                            type="time"
                            value={selectedTask.slotId?.substring(11, 16) ?? "09:00"}
                            onChange={(e) => {
                              updateSelectedTask(
                                buildTaskScheduleUpdate(
                                  "once",
                                  selectedTask.slotId?.substring(0, 10) ??
                                    format(new Date(), "yyyy-MM-dd"),
                                  e.target.value,
                                  null,
                                ),
                              );
                            }}
                            className="w-full rounded-lg border border-apple-gray-200 bg-white px-4 py-2.5 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                          />
                        </div>
                      </>
                    ) : null}

                    {selectedTask.scheduleMode === "daily" ? (
                      <div>
                        <label className="mb-2 flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-apple-gray-500">
                          <Clock className="h-3.5 w-3.5" /> Heure
                        </label>
                        <input
                          type="time"
                          value={selectedTask.scheduleTime ?? "09:00"}
                          onChange={(e) =>
                            updateSelectedTask(
                              buildTaskScheduleUpdate(
                                "daily",
                                "",
                                e.target.value,
                                null,
                              ),
                            )
                          }
                          className="w-full rounded-lg border border-apple-gray-200 bg-white px-4 py-2.5 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                        />
                      </div>
                    ) : null}

                    {selectedTask.scheduleMode === "weekly" ? (
                      <>
                        <div>
                          <label className="mb-2 flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-apple-gray-500">
                            <Repeat2 className="h-3.5 w-3.5" /> Jour
                          </label>
                          <select
                            value={selectedTask.scheduleWeekday ?? 0}
                            onChange={(e) =>
                              updateSelectedTask(
                                buildTaskScheduleUpdate(
                                  "weekly",
                                  "",
                                  selectedTask.scheduleTime ?? "09:00",
                                  parseInt(e.target.value, 10),
                                ),
                              )
                            }
                            className="w-full rounded-lg border border-apple-gray-200 bg-white px-4 py-2.5 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                          >
                            {WEEKDAY_OPTIONS.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="mb-2 flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-apple-gray-500">
                            <Clock className="h-3.5 w-3.5" /> Heure
                          </label>
                          <input
                            type="time"
                            value={selectedTask.scheduleTime ?? "09:00"}
                            onChange={(e) =>
                              updateSelectedTask(
                                buildTaskScheduleUpdate(
                                  "weekly",
                                  "",
                                  e.target.value,
                                  selectedTask.scheduleWeekday ?? 0,
                                ),
                              )
                            }
                            className="w-full rounded-lg border border-apple-gray-200 bg-white px-4 py-2.5 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                          />
                        </div>
                      </>
                    ) : null}
                  </div>
                </div>

                <div>
                  <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-apple-gray-500">
                    Description
                  </label>
                  <textarea
                    value={selectedTask.description || ""}
                    onChange={(e) =>
                      updateSelectedTask({ description: e.target.value })
                    }
                    placeholder="Ajouter des notes…"
                    rows={3}
                    className="w-full resize-none rounded-xl border border-apple-gray-200 px-4 py-3 text-base shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-apple-gray-500">
                    Checklist
                  </label>
                  <div className="space-y-3">
                    {selectedTask.subtasks?.map((subtask) => (
                      <div
                        key={subtask.id}
                        className="group flex items-center gap-3"
                      >
                        <button
                          onClick={() => toggleSubtask(subtask.id)}
                          className="text-apple-gray-400 transition-colors hover:text-apple-blue"
                        >
                          {subtask.completed ? (
                            <CheckSquare className="h-5 w-5 text-apple-blue" />
                          ) : (
                            <div className="h-5 w-5 rounded border-2 border-apple-gray-300" />
                          )}
                        </button>
                        <span
                          className={`flex-1 text-base ${subtask.completed ? "text-apple-gray-400 line-through" : "text-black"}`}
                        >
                          {subtask.title}
                        </span>
                        <button
                          onClick={() => deleteSubtask(subtask.id)}
                          className="p-1 text-red-500 opacity-0 transition-opacity hover:text-red-600 group-hover:opacity-100"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    ))}

                    <form onSubmit={addSubtask} className="flex gap-2">
                      <input
                        type="text"
                        value={newSubtaskTitle}
                        onChange={(e) => setNewSubtaskTitle(e.target.value)}
                        placeholder="Ajouter une étape…"
                        className="flex-1 rounded-lg border border-apple-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                      />
                      <button
                        type="submit"
                        className="rounded-lg bg-apple-gray-100 p-2 text-apple-gray-600 transition-colors hover:bg-apple-gray-200"
                      >
                        <Plus className="h-5 w-5" />
                      </button>
                    </form>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex shrink-0 justify-between border-t border-apple-gray-200 bg-apple-gray-50 p-6">
              <button
                onClick={() => deleteTask(selectedTask.id)}
                className="rounded-lg px-4 py-2 font-semibold text-red-500 transition-colors hover:bg-red-50 hover:text-red-600"
              >
                Supprimer
              </button>
              <button
                onClick={() => setSelectedTask(null)}
                className="rounded-xl bg-apple-blue px-6 py-2 font-semibold text-white shadow-sm transition-colors hover:bg-blue-600"
              >
                Fermer
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <HabitEditorModal
        habit={editingHabit}
        onClose={() => setEditingHabit(null)}
        onSave={handleSaveHabit}
      />
    </div>
  );
}
