import { useState, useEffect, useRef, useCallback } from "react";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import type {
  DragStartEvent,
  DragEndEvent,
  DragMoveEvent,
} from "@dnd-kit/core";
import {
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  Circle,
  Clock,
  CheckSquare,
  X,
  Plus,
  Trash2,
  Calendar as CalendarIcon,
} from "lucide-react";
import {
  format,
  addDays,
  subDays,
  startOfWeek,
  endOfWeek,
  isSameDay,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  isSameMonth,
} from "date-fns";
import api from "../lib/api";
import DraggableTask from "../components/DraggableTask";
import DroppableSlot from "../components/DroppableSlot";
import DraggableCalendarItem, {
  type CalendarTimelineItem,
} from "../components/DraggableCalendarItem";
import { useTaskStore } from "../store/taskStore";
import type { TaskItem as Task } from "../store/taskStore";

export type { Task };

type CalendarItem = CalendarTimelineItem;

const HOURS = Array.from({ length: 24 }, (_, i) => i);
const SNAP_INTERVAL_MIN = 5; // Base snap every 15 minutes
const GRID_SNAP_THRESHOLD = 5; // Snap to grid if within 5 mins
const TASK_SNAP_THRESHOLD = 8; // Snap to task boundary if within 8 mins

const timeToMinutes = (timeStr: string) => {
  const [h, m] = timeStr.split(":").map(Number);
  return h * 60 + m;
};

const minutesToTimeStr = (totalMinutes: number) => {
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
};

function getCalendarItemDurationMinutes(item: CalendarItem) {
  const start = new Date(item.start_at).getTime();
  const end = new Date(item.end_at).getTime();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start)
    return 30;
  return Math.max(15, Math.round((end - start) / 60000));
}

function getCalendarItemSourceLabel(item: CalendarItem) {
  switch (item.source) {
    case "manual":
      return "Manuel";
    case "meal_plan":
      return "Repas";
    case "fitness_session":
      return "Fitness";
    case "task":
      return "Tâche";
    case "event":
      return "Événement";
    case "subscription":
      return "Abonnement";
    default:
      return "Calendrier";
  }
}

function getCalendarItemStartMinutes(item: CalendarItem) {
  // Parse directly from ISO to prevent timezone shifts
  const parts = item.start_at.split(/[-T:Z.]/);
  if (parts.length >= 5) {
    const [, , , h, m] = parts;
    return parseInt(h, 10) * 60 + parseInt(m, 10);
  }
  return 0;
}

function getCalendarItemEndMinutes(item: CalendarItem) {
  const start = new Date(item.start_at).getTime();
  const end = new Date(item.end_at).getTime();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
    return getCalendarItemStartMinutes(item) + 30;
  }
  const startMinutes = getCalendarItemStartMinutes(item);
  const durationMinutes = Math.max(15, Math.round((end - start) / 60000));
  return startMinutes + durationMinutes;
}

function parseLocalDateTime(dateString: string, timeString: string) {
  // Enforce UTC parsing to avoid local browser timezone shifts
  return new Date(`${dateString}T${timeString}:00Z`);
}

function getScheduleKeyFromTask(task: Task) {
  return `task:${task.id}`;
}

function getScheduleKeyFromCalendarItem(item: CalendarItem) {
  return item.source === "manual"
    ? `manual:${item.id}`
    : `${item.source}:${item.source_ref_id ?? item.id}`;
}

function computeSnappedMinutes(
  rawMinutes: number,
  otherTasks: Task[],
  datePrefix: string,
  otherCalendarItems: CalendarItem[] = [],
): number {
  const roundedRaw = Math.round(rawMinutes);
  let best = roundedRaw;
  let bestDist = Infinity;

  // 1. Grid-snap check
  const gridSnapped =
    Math.round(rawMinutes / SNAP_INTERVAL_MIN) * SNAP_INTERVAL_MIN;
  const gridDist = Math.abs(rawMinutes - gridSnapped);
  if (gridDist <= GRID_SNAP_THRESHOLD) {
    best = gridSnapped;
    bestDist = gridDist;
  }

  // 2. Check if any existing task boundary on the same day is closer
  for (const t of otherTasks) {
    if (!t.slotId?.startsWith(datePrefix)) continue;
    const tStart = timeToMinutes(t.slotId.substring(11));
    const tEnd = tStart + t.duration;

    // Distance to task start
    const dStart = Math.abs(rawMinutes - tStart);
    if (dStart <= TASK_SNAP_THRESHOLD && dStart < bestDist) {
      best = tStart;
      bestDist = dStart;
    }

    // Distance to task end
    const dEnd = Math.abs(rawMinutes - tEnd);
    if (dEnd <= TASK_SNAP_THRESHOLD && dEnd < bestDist) {
      best = tEnd;
      bestDist = dEnd;
    }
  }

  for (const item of otherCalendarItems) {
    const itemDate = item.start_at.substring(0, 10);
    if (itemDate !== datePrefix) continue;
    const itemStart = getCalendarItemStartMinutes(item);
    const itemEnd = getCalendarItemEndMinutes(item);

    const itemStartDist = Math.abs(rawMinutes - itemStart);
    if (itemStartDist <= TASK_SNAP_THRESHOLD && itemStartDist < bestDist) {
      best = itemStart;
      bestDist = itemStartDist;
    }

    const itemEndDist = Math.abs(rawMinutes - itemEnd);
    if (itemEndDist <= TASK_SNAP_THRESHOLD && itemEndDist < bestDist) {
      best = itemEnd;
      bestDist = itemEndDist;
    }
  }

  return Math.max(0, Math.min(23 * 60 + 59, best)); // clamp 00:00–23:59
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
      if (newTag && !tags.includes(newTag)) setTags([...tags, newTag]);
      setInputValue("");
    } else if (e.key === "Backspace" && !inputValue && tags.length > 0) {
      setTags(tags.slice(0, -1));
    }
  };

  return (
    <div
      className={`flex flex-wrap gap-1.5 items-center w-full px-3 py-2 rounded-xl border border-apple-gray-200 shadow-sm bg-white focus-within:ring-2 focus-within:ring-apple-blue/50 text-base transition-all ${className || ""}`}
    >
      {tags.map((tag) => (
        <span
          key={tag}
          className="flex items-center gap-1 text-[10px] font-semibold text-apple-blue uppercase tracking-wider bg-apple-blue/10 pl-2 pr-1 py-1 rounded-md"
        >
          {tag}
          <button
            type="button"
            onClick={() => setTags(tags.filter((t) => t !== tag))}
            className="hover:text-blue-800 focus:outline-none flex items-center justify-center p-0.5 rounded-sm hover:bg-blue-200/50 transition-colors"
            title="Remove tag"
          >
            <X className="w-3 h-3" />
          </button>
        </span>
      ))}
      <input
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={tags.length === 0 ? placeholder : ""}
        className="flex-1 bg-transparent min-w-[80px] focus:outline-none text-sm p-1"
      />
    </div>
  );
}

function TaskEditorModal({
  task,
  overlapError,
  onClose,
  onUpdate,
  onDelete,
  onToggleComplete,
}: {
  task: Task | null;
  overlapError: string | null;
  onClose: () => void;
  onUpdate: (updates: Partial<Task>) => void;
  onDelete: (taskId: string) => void;
  onToggleComplete: (taskId: string, completed: boolean) => void;
}) {
  const [newSubtaskTitle, setNewSubtaskTitle] = useState("");

  if (!task) return null;

  const subtasks = task.subtasks || [];

  const addSubtask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSubtaskTitle.trim()) return;
    onUpdate({
      subtasks: [
        ...subtasks,
        {
          id: Date.now().toString(),
          title: newSubtaskTitle.trim(),
          completed: false,
        },
      ],
    });
    setNewSubtaskTitle("");
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-[60] flex items-end md:items-center justify-center p-0 md:p-4">
      <div className="bg-white rounded-t-3xl md:rounded-3xl w-full md:max-w-lg overflow-hidden shadow-2xl animate-in fade-in zoom-in-95 duration-200 flex flex-col max-h-[92vh]">
        <div className="px-4 md:px-6 py-4 border-b border-apple-gray-200 flex justify-between items-center bg-apple-gray-50 shrink-0">
          <h2 className="text-lg md:text-xl font-bold">Modifier la tâche</h2>
          <button
            onClick={onClose}
            className="p-2 text-apple-gray-500 hover:text-black rounded-full hover:bg-apple-gray-200 transition-colors"
            type="button"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 pb-[calc(env(safe-area-inset-bottom)+5.75rem)] md:p-6 overflow-y-auto w-full hide-scrollbar">
          <div className="space-y-5">
            {overlapError && (
              <div className="bg-red-50 text-red-600 text-sm p-3 rounded-xl border border-red-100 flex items-center">
                <span className="font-medium">{overlapError}</span>
              </div>
            )}

            <div className="flex items-center justify-between gap-3 rounded-2xl border border-apple-gray-200 bg-apple-gray-50 px-4 py-3">
              <div className="flex items-center gap-3 min-w-0">
                <button
                  type="button"
                  onClick={() => onToggleComplete(task.id, !task.completed)}
                  className="text-apple-gray-500 hover:text-apple-blue transition-colors shrink-0"
                >
                  {task.completed ? (
                    <CheckCircle2 className="w-7 h-7 text-apple-blue" />
                  ) : (
                    <Circle className="w-7 h-7" />
                  )}
                </button>
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-wider text-apple-gray-500">
                    Statut
                  </p>
                  <p
                    className={`text-sm font-medium ${task.completed ? "text-apple-gray-400 line-through" : "text-black"}`}
                  >
                    {task.completed ? "Terminée" : "À faire"}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => onDelete(task.id)}
                className="text-red-500 hover:text-red-600 font-semibold px-3 py-2 rounded-lg hover:bg-red-50 transition-colors"
              >
                Supprimer
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-apple-gray-500 uppercase tracking-wider mb-2">
                  Titre
                </label>
                <input
                  type="text"
                  value={task.title}
                  onChange={(e) => onUpdate({ title: e.target.value })}
                  className="w-full px-4 py-3 rounded-xl border border-apple-gray-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50 text-lg font-medium"
                />
              </div>
              <div className="flex flex-col md:flex-row gap-4">
                <div className="flex-1">
                  <label className="block text-xs font-semibold text-apple-gray-500 uppercase tracking-wider mb-2">
                    Tags
                  </label>
                  <TagInput
                    tags={task.tags || []}
                    setTags={(tags) => onUpdate({ tags })}
                    placeholder="Ajouter des tags..."
                  />
                </div>
                <div className="w-full md:w-32">
                  <label className="block text-xs font-semibold text-apple-gray-500 uppercase tracking-wider mb-2">
                    Durée
                  </label>
                  <div className="relative">
                    <input
                      type="number"
                      value={task.duration}
                      onChange={(e) =>
                        onUpdate({ duration: parseInt(e.target.value) || 0 })
                      }
                      className="w-full pl-4 pr-8 py-3 rounded-xl border border-apple-gray-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50 text-base"
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-apple-gray-400">
                      m
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex flex-col md:flex-row gap-4 p-4 bg-apple-gray-50 rounded-xl border border-apple-gray-100">
                <div className="flex-1">
                  <label className="block text-xs font-semibold text-apple-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1">
                    <CalendarIcon className="w-3.5 h-3.5" /> Date
                  </label>
                  <input
                    type="date"
                    min={format(new Date(), "yyyy-MM-dd")}
                    value={
                      task.slotId
                        ? task.slotId.substring(0, 10)
                        : format(new Date(), "yyyy-MM-dd")
                    }
                    onChange={(e) => {
                      const date = e.target.value;
                      if (!date) {
                        onUpdate({ slotId: null });
                        return;
                      }
                      const hourStr = task.slotId
                        ? task.slotId.substring(11, 16)
                        : "09:00";
                      onUpdate({ slotId: `${date}-${hourStr}` });
                    }}
                    className="w-full px-4 py-2.5 rounded-lg border border-apple-gray-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50 text-sm bg-white"
                  />
                </div>
                <div className="flex-1">
                  <label className="block text-xs font-semibold text-apple-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" /> Heure
                  </label>
                  <input
                    type="time"
                    value={task.slotId ? task.slotId.substring(11, 16) : ""}
                    onChange={(e) => {
                      const time = e.target.value;
                      if (!time) {
                        onUpdate({ slotId: null });
                        return;
                      }
                      const date = task.slotId
                        ? task.slotId.substring(0, 10)
                        : format(new Date(), "yyyy-MM-dd");
                      onUpdate({ slotId: `${date}-${time}` });
                    }}
                    className="w-full px-4 py-2.5 rounded-lg border border-apple-gray-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50 text-sm bg-white"
                  />
                </div>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-apple-gray-500 uppercase tracking-wider mb-2">
                Description
              </label>
              <textarea
                value={task.description || ""}
                onChange={(e) => onUpdate({ description: e.target.value })}
                placeholder="Ajouter une note..."
                rows={3}
                className="w-full px-4 py-3 rounded-xl border border-apple-gray-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50 text-base resize-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-apple-gray-500 uppercase tracking-wider mb-2">
                Checklist
              </label>
              <div className="space-y-3">
                {subtasks.map((sub) => (
                  <div key={sub.id} className="flex items-center gap-3 group">
                    <button
                      type="button"
                      onClick={() =>
                        onUpdate({
                          subtasks: subtasks.map((s) =>
                            s.id === sub.id
                              ? { ...s, completed: !s.completed }
                              : s,
                          ),
                        })
                      }
                      className="text-apple-gray-400 hover:text-apple-blue transition-colors shrink-0"
                    >
                      {sub.completed ? (
                        <CheckSquare className="w-5 h-5 text-apple-blue" />
                      ) : (
                        <div className="w-5 h-5 rounded border-2 border-apple-gray-300" />
                      )}
                    </button>
                    <span
                      className={`flex-1 text-base ${sub.completed ? "line-through text-apple-gray-400" : "text-black"}`}
                    >
                      {sub.title}
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        onUpdate({
                          subtasks: subtasks.filter((s) => s.id !== sub.id),
                        })
                      }
                      className="text-red-500 hover:text-red-600 transition-colors p-1"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}

                <form onSubmit={addSubtask} className="flex gap-2">
                  <input
                    type="text"
                    value={newSubtaskTitle}
                    onChange={(e) => setNewSubtaskTitle(e.target.value)}
                    placeholder="Ajouter une étape..."
                    className="flex-1 px-3 py-2 rounded-lg border border-apple-gray-200 focus:outline-none focus:ring-2 focus:ring-apple-blue/50 text-sm"
                  />
                  <button
                    type="submit"
                    className="p-2 bg-apple-gray-100 text-apple-gray-600 rounded-lg hover:bg-apple-gray-200 transition-colors"
                  >
                    <Plus className="w-5 h-5" />
                  </button>
                </form>
              </div>
            </div>
          </div>
        </div>

        <div className="px-4 pt-4 pb-[calc(env(safe-area-inset-bottom)+6.5rem)] md:pb-6 md:p-6 border-t border-apple-gray-200 bg-apple-gray-50 shrink-0 flex justify-between gap-3">
          <button
            type="button"
            onClick={onClose}
            className="text-apple-gray-600 font-semibold px-4 py-2 hover:bg-apple-gray-100 rounded-lg transition-colors"
          >
            Fermer
          </button>
          <button
            type="button"
            onClick={onClose}
            className="bg-apple-blue text-white font-semibold px-6 py-2 rounded-xl hover:bg-blue-600 transition-colors shadow-sm"
          >
            Terminé
          </button>
        </div>
      </div>
    </div>
  );
}

export default function CalendarPage() {
  const { tasks, fetchTasks, updateTask, deleteTask, toggleTask } =
    useTaskStore();
  const [calendarItems, setCalendarItems] = useState<CalendarItem[]>([]);
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [activeCalendarItem, setActiveCalendarItem] =
    useState<CalendarItem | null>(null);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [editingCalendarItem, setEditingCalendarItem] =
    useState<CalendarItem | null>(null);
  const [overlapError, setOverlapError] = useState<string | null>(null);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [view, setView] = useState<"day" | "week" | "month">("week");
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768);

  // Ghost indicator during drag (snapped time per column)
  const [dragGhost, setDragGhost] = useState<{
    dateString: string;
    minutes: number;
  } | null>(null);
  const [dragOrigin, setDragOrigin] = useState<{
    x: number;
    y: number;
    offsetY: number;
  } | null>(null);
  const swipeTouchRef = useRef<{
    id: string;
    x: number;
    y: number;
    time: number;
  } | null>(null);
  const swipeBlockRef = useRef<{ id: string; until: number } | null>(null);

  // Refs to map each date column's DOM element for pixel→time computation
  const columnRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const timelineScrollRef = useRef<HTMLDivElement | null>(null);

  const loadCalendarItems = useCallback(async () => {
    try {
      const response = await api.get("/calendar/items", {
        params: {
          include_completed: true,
          limit: 1000,
        },
      });
      setCalendarItems(response.data);
    } catch (error) {
      console.error("Failed to load calendar items", error);
      setCalendarItems([]);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  useEffect(() => {
    void loadCalendarItems();
  }, [loadCalendarItems]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void loadCalendarItems();
    }, 60000);
    return () => window.clearInterval(interval);
  }, [loadCalendarItems]);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 767px)");
    const syncViewport = (matches: boolean) => {
      setIsMobile(matches);
    };
    syncViewport(media.matches);
    const handler = (event: MediaQueryListEvent) => syncViewport(event.matches);
    media.addEventListener("change", handler);
    return () => media.removeEventListener("change", handler);
  }, []);

  useEffect(() => {
    if (isMobile && view === "week") {
      setView("month");
    }
  }, [isMobile, view]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: 220, tolerance: 8 },
    }),
    useSensor(KeyboardSensor),
  );

  const getActiveDurationMinutes = (
    task: Task | null,
    item: CalendarItem | null,
  ) => {
    if (task) return task.duration || 30;
    if (item) return getCalendarItemDurationMinutes(item);
    return 30;
  };

  const getActiveDragKind = (event: DragStartEvent) => {
    const data = event.active.data.current as
      | { kind?: "task"; task?: Task }
      | { kind?: "calendar-item"; item?: CalendarItem }
      | undefined;

    if (data?.kind === "task" && data.task)
      return { kind: "task" as const, task: data.task };
    if (data?.kind === "calendar-item" && data.item)
      return { kind: "calendar-item" as const, item: data.item };

    const task = tasks.find((entry) => entry.id === String(event.active.id));
    if (task) return { kind: "task" as const, task };

    const calendarItem = calendarItems.find(
      (entry) => `calendar-${entry.id}` === String(event.active.id),
    );
    if (calendarItem)
      return { kind: "calendar-item" as const, item: calendarItem };

    return null;
  };

  const buildIgnoreKeys = (
    activeTaskId: string | null,
    activeCalendarItem: CalendarItem | null,
  ) => {
    const ignore = new Set<string>();
    if (activeTaskId) {
      ignore.add(getScheduleKeyFromTask({ id: activeTaskId } as Task));
    }
    if (activeCalendarItem) {
      ignore.add(getScheduleKeyFromCalendarItem(activeCalendarItem));
    }
    return ignore;
  };

  const hasScheduleOverlap = useCallback(
    (
      dateString: string,
      minutes: number,
      duration: number,
      ignoreKeys: Set<string>,
    ) => {
      const endMinutes = minutes + duration;
      const taskConflict = tasks.some((task) => {
        if (!task.slotId || !task.slotId.startsWith(dateString)) return false;
        if (ignoreKeys.has(getScheduleKeyFromTask(task))) return false;
        const startMinutes = timeToMinutes(task.slotId.substring(11, 16));
        const taskEndMinutes = startMinutes + task.duration;
        return (
          Math.max(minutes, startMinutes) < Math.min(endMinutes, taskEndMinutes)
        );
      });
      if (taskConflict) return true;

      return calendarItems.some((item) => {
        const itemDate = item.start_at.substring(0, 10);
        if (itemDate !== dateString) return false;
        if (ignoreKeys.has(getScheduleKeyFromCalendarItem(item))) return false;
        const startMinutes = getCalendarItemStartMinutes(item);
        const itemEndMinutes = getCalendarItemEndMinutes(item);
        return (
          Math.max(minutes, startMinutes) < Math.min(endMinutes, itemEndMinutes)
        );
      });
    },
    [calendarItems, tasks],
  );

  const handleDragStart = (event: DragStartEvent) => {
    const activeDrag = getActiveDragKind(event);
    setActiveTask(activeDrag?.kind === "task" ? activeDrag.task : null);
    setActiveCalendarItem(
      activeDrag?.kind === "calendar-item" ? activeDrag.item : null,
    );

    const activator = event.activatorEvent as
      | MouseEvent
      | PointerEvent
      | TouchEvent
      | undefined;
    if (activator instanceof TouchEvent) {
      const touch = activator.touches[0] ?? activator.changedTouches[0];
      setDragOrigin(
        touch
          ? {
              x: touch.clientX,
              y: touch.clientY,
              offsetY:
                event.active.rect.current.initial?.top != null &&
                touch.clientY >= event.active.rect.current.initial.top
                  ? touch.clientY - event.active.rect.current.initial.top
                  : 10,
            }
          : null,
      );
    } else if (activator && "clientX" in activator && "clientY" in activator) {
      setDragOrigin({
        x: activator.clientX,
        y: activator.clientY,
        offsetY:
          event.active.rect.current.initial?.top != null &&
          activator.clientY >= event.active.rect.current.initial.top
            ? activator.clientY - event.active.rect.current.initial.top
            : 10,
      });
    } else {
      setDragOrigin(null);
    }
  };

  const handleDragMove = useCallback(
    (event: DragMoveEvent) => {
      const currentItem = activeTask ?? activeCalendarItem;
      if (!currentItem || !dragOrigin) return;

      const { delta } = event;
      const currentX = dragOrigin.x + delta.x;
      const currentY = dragOrigin.y + delta.y - dragOrigin.offsetY;
      const duration = getActiveDurationMinutes(activeTask, activeCalendarItem);

      for (const [dateString, el] of columnRefs.current.entries()) {
        const rect = el.getBoundingClientRect();
        if (currentX >= rect.left && currentX <= rect.right) {
          const ratio = Math.max(
            0,
            Math.min(1, (currentY - rect.top) / rect.height),
          );
          const rawMinutes = ratio * 24 * 60;
          const ignoreKeys = buildIgnoreKeys(
            activeTask?.id ?? null,
            activeCalendarItem,
          );
          const otherTasks = tasks.filter(
            (task) => !ignoreKeys.has(getScheduleKeyFromTask(task)),
          );
          const otherCalendarItems = calendarItems.filter((item) => {
            const itemDate = item.start_at.substring(0, 10);
            return (
              itemDate === dateString &&
              !ignoreKeys.has(getScheduleKeyFromCalendarItem(item))
            );
          });
          let snapped = computeSnappedMinutes(
            rawMinutes,
            otherTasks,
            dateString,
            otherCalendarItems,
          );
          // If the smart snap puts us in an overlap, fallback to pure grid snap
          if (hasScheduleOverlap(dateString, snapped, duration, ignoreKeys)) {
            snapped =
              Math.round(rawMinutes / SNAP_INTERVAL_MIN) * SNAP_INTERVAL_MIN;
          }
          if (snapped + duration <= 24 * 60) {
            setDragGhost({ dateString, minutes: snapped });
          } else {
            setDragGhost(null);
          }
          return;
        }
      }
      setDragGhost(null);
    },
    [activeCalendarItem, activeTask, dragOrigin, tasks],
  );

  const moveDraggedItem = useCallback(
    async (dateString: string, minutes: number) => {
      const task = activeTask;
      const item = activeCalendarItem;
      const duration = getActiveDurationMinutes(task, item);
      const ignoreKeys = buildIgnoreKeys(task?.id ?? null, item);

      if (minutes + duration > 24 * 60) return;
      if (hasScheduleOverlap(dateString, minutes, duration, ignoreKeys)) {
        setOverlapError("This time slot overlaps with another scheduled item.");
        window.setTimeout(() => setOverlapError(null), 3000);
        return;
      }

      const timeString = minutesToTimeStr(minutes);
      const startAt = parseLocalDateTime(dateString, timeString);
      const endAt = new Date(startAt.getTime() + duration * 60000);
      const taskSlotId = `${dateString}-${timeString}`;

      try {
        if (task) {
          await updateTask(task.id, { slotId: taskSlotId });
        } else if (item) {
          switch (item.source) {
            case "task":
              if (item.source_ref_id !== null) {
                await updateTask(String(item.source_ref_id), {
                  slotId: taskSlotId,
                });
              }
              break;
            case "manual":
              await api.patch(`/calendar/items/${item.id}`, {
                start_at: startAt.toISOString(), // Assuming parseLocalDateTime adds 'Z' making it UTC
                end_at: endAt.toISOString(),
              });
              break;
            case "meal_plan":
              if (item.source_ref_id !== null) {
                await api.patch(`/meal-plans/${item.source_ref_id}`, {
                  planned_at: startAt.toISOString(),
                });
              }
              break;
            case "fitness_session":
              if (item.source_ref_id !== null) {
                await api.patch(`/fitness/sessions/${item.source_ref_id}`, {
                  planned_at: startAt.toISOString(),
                  duration_minutes: duration,
                });
              }
              break;
            case "event":
              if (item.source_ref_id !== null) {
                await api.patch(`/events/${item.source_ref_id}`, {
                  start_at: startAt.toISOString(),
                  end_at: endAt.toISOString(),
                });
              }
              break;
            case "subscription":
              if (item.source_ref_id !== null) {
                await api.patch(`/subscriptions/${item.source_ref_id}`, {
                  next_due_date: dateString,
                });
              }
              break;
            default:
              break;
          }
        }
        await fetchTasks();
        await loadCalendarItems();
      } catch (error) {
        console.error("Failed to move scheduled item", error);
        setOverlapError(
          "Unable to move this item. The server rejected the new slot.",
        );
        window.setTimeout(() => setOverlapError(null), 3000);
      }
    },
    [
      activeCalendarItem,
      activeTask,
      fetchTasks,
      hasScheduleOverlap,
      loadCalendarItems,
      updateTask,
    ],
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { over } = event;
    const currentGhost = dragGhost;
    const movedTask = activeTask;
    const movedCalendarItem = activeCalendarItem;
    setActiveTask(null);
    setActiveCalendarItem(null);
    setDragGhost(null);
    setDragOrigin(null);

    if (currentGhost) {
      void moveDraggedItem(currentGhost.dateString, currentGhost.minutes);
      return;
    }

    if (movedTask && over?.id === "inbox") {
      void updateTask(movedTask.id, { slotId: null }).then(() => {
        void loadCalendarItems();
      });
      return;
    }

    if (
      movedCalendarItem &&
      over?.id === "inbox" &&
      movedCalendarItem.source === "task" &&
      movedCalendarItem.source_ref_id !== null
    ) {
      void updateTask(String(movedCalendarItem.source_ref_id), {
        slotId: null,
      }).then(() => {
        void loadCalendarItems();
      });
    }
  };

  const openTaskEditor = (task: Task) => {
    setEditingTask(task);
    setOverlapError(null);
  };

  const closeTaskEditor = () => {
    setEditingTask(null);
    setOverlapError(null);
  };

  const checkOverlap = (
    slotId: string | null,
    duration: number,
    excludeId?: string,
  ) => {
    if (!slotId) return false;
    const tStart = timeToMinutes(slotId.substring(11, 16));
    const dateStr = slotId.substring(0, 10);

    const ignoreKeys = new Set<string>();
    if (excludeId) {
      ignoreKeys.add(getScheduleKeyFromTask({ id: excludeId } as Task));
    }

    return hasScheduleOverlap(dateStr, tStart, duration, ignoreKeys);
  };

  const updateEditingTask = (updates: Partial<Task>) => {
    if (!editingTask) return;

    const nextSlotId =
      updates.slotId !== undefined ? updates.slotId : editingTask.slotId;
    const nextDuration =
      updates.duration !== undefined ? updates.duration : editingTask.duration;

    if (nextSlotId && checkOverlap(nextSlotId, nextDuration, editingTask.id)) {
      setOverlapError("This time slot overlaps with another scheduled item.");
      setTimeout(() => setOverlapError(null), 3000);
      return;
    }

    const nextTask = { ...editingTask, ...updates };
    setEditingTask(nextTask);
    void updateTask(editingTask.id, updates).then(() => {
      void loadCalendarItems();
    });
  };

  const deleteEditingTask = (taskId: string) => {
    void deleteTask(taskId).then(() => {
      void loadCalendarItems();
    });
    if (editingTask?.id === taskId) closeTaskEditor();
  };

  const shouldSuppressTaskClick = (taskId: string) => {
    const block = swipeBlockRef.current;
    return Boolean(block && block.id === taskId && block.until > Date.now());
  };

  const handleTaskTouchStart = (
    taskId: string,
    e: React.TouchEvent<HTMLElement>,
  ) => {
    const touch = e.touches[0];
    if (!touch) return;
    swipeTouchRef.current = {
      id: taskId,
      x: touch.clientX,
      y: touch.clientY,
      time: Date.now(),
    };
  };

  const handleTaskTouchEnd = (task: Task, e: React.TouchEvent<HTMLElement>) => {
    const touch = swipeTouchRef.current;
    if (!touch || touch.id !== task.id) return;

    const ended = e.changedTouches[0];
    swipeTouchRef.current = null;
    if (!ended) return;

    const dx = ended.clientX - touch.x;
    const dy = ended.clientY - touch.y;
    const dt = Date.now() - touch.time;
    const isSwipe =
      isMobile && dt < 900 && Math.abs(dx) > 70 && Math.abs(dy) < 28 && dx > 0;

    if (isSwipe && !task.completed) {
      swipeBlockRef.current = { id: task.id, until: Date.now() + 700 };
      toggleTask(task.id);
    }
  };

  const handleCalendarItemClick = (item: CalendarItem) => {
    setEditingCalendarItem(item);
    setOverlapError(null);
  };

  const closeCalendarItemEditor = () => {
    setEditingCalendarItem(null);
    setOverlapError(null);
  };

  const deleteCalendarItem = async (itemId: number) => {
    try {
      await api.delete(`/calendar/items/${itemId}`);
      await loadCalendarItems();
      closeCalendarItemEditor();
    } catch (err) {
      console.error("Failed to delete item", err);
    }
  };

  const handleTaskClick = (task: Task) => {
    if (shouldSuppressTaskClick(task.id)) return;
    openTaskEditor(task);
  };

  const visibleTasks = tasks.filter((t) => !t.completed);
  const visibleCalendarItems = calendarItems.filter(
    (item) => item.source !== "task",
  );
  const inboxTasks = visibleTasks.filter((t) => !t.slotId);

  const startDate = startOfWeek(currentDate, { weekStartsOn: 1 });
  const weekDays = Array.from({ length: 7 }, (_, i) => addDays(startDate, i));

  const monthDays = eachDayOfInterval({
    start: startOfWeek(startOfMonth(currentDate), { weekStartsOn: 1 }),
    end: endOfWeek(endOfMonth(currentDate), { weekStartsOn: 1 }),
  });

  const calendarItemsForDay = (dateString: string) =>
    visibleCalendarItems
      .filter((item) => {
        const itemDate = item.start_at.substring(0, 10);
        return itemDate === dateString;
      })
      .sort(
        (a, b) =>
          new Date(a.start_at).getTime() - new Date(b.start_at).getTime(),
      );

  const columnsToShow = view === "day" ? [currentDate] : weekDays;
  const availableViews: Array<"day" | "week" | "month"> = isMobile
    ? ["day", "month"]
    : ["day", "week", "month"];

  const [currentTime, setCurrentTime] = useState(new Date());
  useEffect(() => {
    const interval = setInterval(() => setCurrentTime(new Date()), 60000);
    return () => clearInterval(interval);
  }, []);
  const currentHour = currentTime.getHours() + currentTime.getMinutes() / 60;
  const mobileTaskMinHeight = 40;
  const mobileHourHeight = 72;

  useEffect(() => {
    const scroller = timelineScrollRef.current;
    if (!scroller) return;

    requestAnimationFrame(() => {
      if (view === "month") {
        scroller.scrollTop = 0;
        scroller.scrollLeft = 0;
        return;
      }

      if (isMobile && view === "day") {
        const target = Math.max(
          currentHour * mobileHourHeight - mobileHourHeight * 2,
          0,
        );
        scroller.scrollTop = target;
        scroller.scrollLeft = 0;
        return;
      }

      const totalHeight = scroller.scrollHeight;
      const viewportHeight = scroller.clientHeight;
      const desiredMinutes = Math.max(currentHour * 60 - 120, 0);
      const maxScroll = Math.max(totalHeight - viewportHeight, 0);
      const nextScrollTop = Math.min(
        (desiredMinutes / (24 * 60)) * totalHeight,
        maxScroll,
      );
      scroller.scrollTop = nextScrollTop;
      scroller.scrollLeft = 0;
    });
  }, [currentDate, isMobile, view]);

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragMove={handleDragMove}
      onDragEnd={handleDragEnd}
    >
      <div className="flex h-full w-full bg-transparent  text-black font-sans overflow-hidden md:pb-0">
        {/* INBOX PANEL (Left Sidebar) */}
        <div className="hidden h-full w-48 shrink-0 border-r border-apple-gray-200 bg-apple-gray-100 md:flex lg:w-64">
          <div className="flex h-full w-full flex-col">
            <div className="px-4 py-4 border-b border-apple-gray-200 flex justify-between items-center h-16 bg-white/50 backdrop-blur-sm">
              <h2 className="text-xs font-semibold text-apple-gray-500 uppercase tracking-widest">
                Inbox
              </h2>
            </div>
            <DroppableSlot
              id="inbox"
              className="flex-1 overflow-y-auto p-3 flex flex-col gap-2 hide-scrollbar"
            >
              {inboxTasks.map((task) => (
                <div
                  key={task.id}
                  className="relative group"
                  onClick={() => handleTaskClick(task)}
                  onTouchStart={(e) => handleTaskTouchStart(task.id, e)}
                  onTouchEnd={(e) => handleTaskTouchEnd(task, e)}
                >
                  <DraggableTask task={task} />
                </div>
              ))}
              {inboxTasks.length === 0 && (
                <div className="flex items-center justify-center p-4 text-xs text-apple-gray-400 w-full h-full text-center">
                  All tasks scheduled!
                </div>
              )}
            </DroppableSlot>
          </div>
        </div>

        {/* TIMELINE PANEL */}
        <div className="flex-1 flex flex-col bg-transparent relative overflow-hidden h-full">
          {/* Header row with Navigation & Days */}
          <div className="flex flex-col border-b border-apple-gray-200 shrink-0 relative bg-white z-20">
            {/* Top Navigation Bar */}
            <div className="flex flex-col gap-3 border-b border-white/60 bg-white/75 px-3 py-3 backdrop-blur-xl md:flex-row md:items-center md:justify-between md:px-4 md:py-2">
              <div className="flex flex-wrap items-center gap-3 md:gap-4">
                <div className="flex items-center gap-1">
                  <button
                    onClick={() =>
                      setCurrentDate(
                        view === "day"
                          ? subDays(currentDate, 1)
                          : subDays(currentDate, 7),
                      )
                    }
                    className="p-1.5 rounded-full hover:bg-apple-gray-100 text-apple-gray-600 transition-colors"
                  >
                    <ChevronLeft className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => setCurrentDate(new Date())}
                    className="px-3 py-1.5 rounded-md hover:bg-apple-gray-100 text-sm font-medium text-apple-gray-600 transition-colors"
                  >
                    Today
                  </button>
                  <button
                    onClick={() =>
                      setCurrentDate(
                        view === "day"
                          ? addDays(currentDate, 1)
                          : addDays(currentDate, 7),
                      )
                    }
                    className="p-1.5 rounded-full hover:bg-apple-gray-100 text-apple-gray-600 transition-colors"
                  >
                    <ChevronRight className="w-5 h-5" />
                  </button>
                </div>
                <h1 className="text-base font-bold tracking-tight text-black md:text-lg">
                  {view === "day"
                    ? format(currentDate, "MMMM d, yyyy")
                    : format(currentDate, "MMMM yyyy")}
                </h1>
              </div>

              {/* View Switcher */}
              <div className="flex items-center self-start rounded-2xl border border-white/60 bg-white/80 p-0.5 shadow-sm md:self-auto">
                {availableViews.map((v) => (
                  <button
                    key={v}
                    onClick={() => setView(v)}
                    className={`rounded-md px-3 py-1.5 text-xs font-semibold capitalize transition-all md:px-4 ${
                      view === v
                        ? "bg-white text-black shadow-sm ring-1 ring-black/5"
                        : "text-apple-gray-500 hover:text-black"
                    }`}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>

            {/* Days row - only show if view is not month */}
            {view !== "month" && (
              <div className="flex h-12 items-end">
                <div className="flex h-full w-12 shrink-0 items-center justify-center md:w-16">
                  <span className="text-[10px] text-apple-gray-400 font-medium mb-1">
                    GMT+01
                  </span>
                </div>
                <div className="flex-1 flex h-full">
                  {columnsToShow.map((date) => {
                    const isToday = isSameDay(date, new Date());
                    return (
                      <div
                        key={date.toString()}
                        className="flex-1 flex flex-col items-center justify-center border-l border-apple-gray-100 relative h-full pt-1"
                      >
                        <span
                          className={`text-[10px] uppercase tracking-widest font-medium mb-0.5 ${isToday ? "text-apple-blue" : "text-apple-gray-400"}`}
                        >
                          {format(date, "eee")}
                        </span>
                        <div
                          className={`w-7 h-7 flex items-center justify-center rounded-full text-sm font-bold ${isToday ? "bg-apple-blue text-white" : "text-black"}`}
                        >
                          {format(date, "d")}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Grid Area - FULL HEIGHT flex */}
          <div className="flex-1 flex w-full h-full overflow-hidden bg-white">
            {view === "month" ? (
              // Enhanced Premium Month View implementation
              <div
                className={`flex-1 flex flex-col bg-white border-t border-apple-gray-200 pt-px ${
                  isMobile
                    ? "overflow-y-auto overscroll-contain touch-pan-y"
                    : "overflow-hidden"
                }`}
                style={
                  isMobile
                    ? {
                        WebkitOverflowScrolling: "touch",
                        scrollPaddingBottom:
                          "calc(env(safe-area-inset-bottom) + 6.25rem)",
                        paddingBottom:
                          "calc(env(safe-area-inset-bottom) + 6.25rem)",
                      }
                    : undefined
                }
              >
                <div className="flex min-h-full flex-col">
                  {/* Month Headers bg-apple-gray-50 */}
                  <div className="grid grid-cols-7 bg-white shrink-0 border-b border-apple-gray-200">
                    {(isMobile
                      ? ["M", "T", "W", "T", "F", "S", "S"]
                      : ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                    ).map((day, index) => (
                      <div
                        key={`${day}-${index}`}
                        className="text-[10px] font-bold uppercase text-apple-gray-400 text-center py-2 mb-0.5"
                      >
                        {day}
                      </div>
                    ))}
                  </div>
                  {/* Month Grid */}
                  <div
                    className="flex-1 grid grid-cols-7 gap-px bg-apple-gray-200"
                    style={{ gridAutoRows: "minmax(0, 1fr)" }}
                  >
                    {monthDays.map((date) => {
                      const isToday = isSameDay(date, new Date());
                      const isCurrentMonth = isSameMonth(date, currentDate);
                      const dateString = format(date, "yyyy-MM-dd");
                      const dayTasks = visibleTasks.filter((t) =>
                        t.slotId?.startsWith(dateString),
                      );
                      const dayCalendarItems = calendarItemsForDay(dateString);

                      return (
                        <div
                          key={date.toString()}
                          className={`bg-white p-1 xl:p-2 flex flex-col transition-colors hover:bg-apple-gray-50 cursor-pointer overflow-hidden ${isCurrentMonth ? "" : "bg-apple-gray-50/50"}`}
                          onClick={() => {
                            setCurrentDate(date);
                            setView("day");
                          }}
                        >
                          <div className="flex justify-end mb-1 shrink-0">
                            <span
                              className={`text-xs font-semibold w-6 h-6 flex items-center justify-center rounded-full ${isToday ? "bg-apple-blue text-white shadow-sm" : isCurrentMonth ? "text-black" : "text-apple-gray-300"}`}
                            >
                              {format(date, "d")}
                            </span>
                          </div>
                          {/* Task Indicators */}
                          <div className="flex-1 flex flex-col gap-1 overflow-y-auto hide-scrollbar">
                            {dayTasks.map((task) => {
                              const colorMatch =
                                task.color.match(/text-([a-z]+)-(\d+)/);
                              const dotColorClass = colorMatch
                                ? `bg-${colorMatch[1]}-500`
                                : "bg-apple-gray-400";

                              return (
                                <div
                                  key={task.id}
                                  className="flex items-center gap-1.5 px-0.5 group"
                                >
                                  <div
                                    className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotColorClass}`}
                                  />
                                  <span className="text-[9px] sm:text-[10px] font-medium text-apple-gray-500 truncate group-hover:text-black transition-colors">
                                    {task.title}
                                  </span>
                                </div>
                              );
                            })}
                            {dayCalendarItems.map((item) => (
                              <div
                                key={`calendar-${item.id}`}
                                className="flex items-center gap-1.5 px-0.5 group"
                              >
                                <div
                                  className={`w-1.5 h-1.5 rounded-full shrink-0 ${item.source === "fitness_session" ? "bg-emerald-500" : item.source === "meal_plan" ? "bg-orange-500" : "bg-apple-gray-400"}`}
                                />
                                <span
                                  className={`text-[9px] sm:text-[10px] font-medium truncate group-hover:text-black transition-colors ${item.completed ? "text-apple-gray-400 line-through" : "text-apple-gray-500"}`}
                                >
                                  {getCalendarItemSourceLabel(item)} ·{" "}
                                  {item.title}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            ) : (
              // Day / Week Timeline View — Freeform drag, magnetic snap
              <div
                ref={timelineScrollRef}
                className={`flex-1 flex relative w-full h-full bg-apple-gray-50/30 ${
                  isMobile
                    ? view === "day"
                      ? "overflow-y-auto overflow-x-hidden overscroll-contain touch-pan-y"
                      : "overflow-y-auto overflow-x-hidden overscroll-contain touch-pan-y"
                    : "overflow-hidden"
                }`}
                id="timeline-scroll"
                style={
                  isMobile
                    ? {
                        WebkitOverflowScrolling: "touch",
                        scrollPaddingBottom: "7rem",
                        paddingBottom:
                          "calc(env(safe-area-inset-bottom) + 7rem)",
                      }
                    : undefined
                }
              >
                {/* Time Labels Column */}
                <div
                  className="sticky left-0 z-10 flex w-12 shrink-0 flex-col border-r border-apple-gray-100 bg-white md:w-16"
                  style={{
                    height:
                      isMobile && view === "day"
                        ? `${HOURS.length * mobileHourHeight}px`
                        : "100%",
                    minHeight:
                      isMobile && view === "day"
                        ? `${HOURS.length * mobileHourHeight}px`
                        : undefined,
                  }}
                >
                  {HOURS.map((hour) => (
                    <div
                      key={hour}
                      className="w-full relative shrink-0"
                      style={{
                        height:
                          isMobile && view === "day"
                            ? `${mobileHourHeight}px`
                            : `${100 / 24}%`,
                      }}
                    >
                      <span className="absolute -top-2.5 right-2 text-[10px] font-medium text-apple-gray-400">
                        {hour === 0
                          ? ""
                          : hour < 12
                            ? `${hour} AM`
                            : hour === 12
                              ? "12 PM"
                              : `${hour - 12} PM`}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Matrix of day columns */}
                <div
                  className="relative flex h-full flex-1 min-w-0 max-w-full"
                  style={{
                    minHeight:
                      isMobile && view === "day"
                        ? `${HOURS.length * mobileHourHeight}px`
                        : isMobile && view !== "day"
                          ? "960px"
                          : undefined,
                    height:
                      isMobile && view === "day"
                        ? `${HOURS.length * mobileHourHeight}px`
                        : "100%",
                    minWidth: isMobile && view === "day" ? "0" : undefined,
                  }}
                >
                  {/* Horizontal hour grid lines */}
                  <div className="absolute inset-0 flex flex-col pointer-events-none">
                    {HOURS.map((hour) => (
                      <div
                        key={hour}
                        className="flex-1 border-t border-apple-gray-100/60 w-full"
                      />
                    ))}
                  </div>

                  {/* Current Time Indicator */}
                  <div
                    className="absolute left-0 w-full z-10 pointer-events-none flex items-center"
                    style={{
                      top: `${(currentHour / 24) * 100}%`,
                      transform: "translateY(-50%)",
                    }}
                  >
                    <div className="w-full h-[1px] bg-red-500 relative">
                      {columnsToShow.map((date, index) => {
                        if (isSameDay(date, new Date())) {
                          const leftPercent =
                            (index / columnsToShow.length) * 100;
                          return (
                            <div
                              key="dot"
                              className="absolute w-2 h-2 rounded-full bg-red-500 -top-[3px]"
                              style={{ left: `calc(${leftPercent}% - 3px)` }}
                            />
                          );
                        }
                        return null;
                      })}
                    </div>
                  </div>

                  {/* Day columns */}
                  {columnsToShow.map((date) => {
                    const dateString = format(date, "yyyy-MM-dd");
                    const colTasks = visibleTasks
                      .filter((t) => t.slotId?.startsWith(dateString))
                      .slice()
                      .sort(
                        (a, b) =>
                          timeToMinutes(a.slotId!.substring(11)) -
                          timeToMinutes(b.slotId!.substring(11)),
                      );
                    const colCalendarItems = calendarItemsForDay(dateString);
                    const isGhostCol = dragGhost?.dateString === dateString;

                    return (
                      <div
                        key={dateString}
                        ref={(el) => {
                          if (el) columnRefs.current.set(dateString, el);
                          else columnRefs.current.delete(dateString);
                        }}
                        className="flex-1 min-w-0 border-l border-apple-gray-100/60 relative h-full overflow-hidden"
                      >
                        {/* Droppable zone for inbox (dragging back, or no ghost) */}
                        <DroppableSlot
                          id={`col-${dateString}`}
                          className="absolute inset-0 z-0"
                        />

                        {/* Ghost snap indicator */}
                        {isGhostCol && activeTask && (
                          <div
                            className="absolute left-0.5 right-0.5 z-30 pointer-events-none rounded-md border-2 border-apple-blue/60 bg-apple-blue/10 transition-none"
                            style={{
                              top: `${(dragGhost.minutes / (24 * 60)) * 100}%`,
                              height: isMobile
                                ? `max(${(activeTask.duration / (24 * 60)) * 100}%, ${mobileTaskMinHeight}px)`
                                : `${(activeTask.duration / (24 * 60)) * 100}%`,
                            }}
                          >
                            <span className="absolute top-0.5 left-1 text-[9px] font-bold text-apple-blue opacity-80">
                              {minutesToTimeStr(dragGhost.minutes)}
                            </span>
                          </div>
                        )}

                        {colCalendarItems.map((item) => {
                          const startMin = getCalendarItemStartMinutes(item);
                          const durationMinutes =
                            getCalendarItemDurationMinutes(item);
                          const topPct = (startMin / (24 * 60)) * 100;
                          const heightPct = (durationMinutes / (24 * 60)) * 100;

                          return (
                            <div
                              key={`calendar-${item.id}`}
                              className="absolute left-1 right-1 z-10 pointer-events-auto group"
                              style={{
                                top: `${topPct}%`,
                                minHeight: isMobile ? "40px" : undefined,
                                height: `${Math.max(heightPct, 2)}%`,
                              }}
                            >
                              <div
                                onClick={() => handleCalendarItemClick(item)}
                                className="w-full h-full cursor-pointer touch-none pointer-events-auto"
                              >
                                <DraggableCalendarItem
                                  item={item}
                                  compactMobile={isMobile}
                                />
                              </div>
                            </div>
                          );
                        })}

                        {/* Render tasks absolutely positioned */}
                        {colTasks.map((task, index) => {
                          if (!task.slotId) return null;
                          const startMin = timeToMinutes(
                            task.slotId.substring(11),
                          );
                          const topPct = (startMin / (24 * 60)) * 100;
                          const heightPct = (task.duration / (24 * 60)) * 100;
                          const actualHeightPx =
                            (task.duration / 1440) *
                            (HOURS.length * mobileHourHeight);
                          const nextTask = colTasks[index + 1];
                          const nextStartMin = nextTask?.slotId
                            ? timeToMinutes(nextTask.slotId.substring(11))
                            : null;
                          const availableHeightPx =
                            nextStartMin !== null
                              ? Math.max(
                                  ((nextStartMin - startMin) / (24 * 60)) *
                                    (HOURS.length * mobileHourHeight) -
                                    4,
                                  24,
                                )
                              : null;
                          const isBeingDragged = activeTask?.id === task.id;
                          const taskHeight = isMobile
                            ? `${Math.min(
                                Math.max(actualHeightPx, mobileTaskMinHeight),
                                availableHeightPx ?? Infinity,
                              )}px`
                            : `${heightPct}%`;

                          return (
                            <div
                              key={task.id}
                              className="absolute left-0.5 right-0.5 z-20 pointer-events-auto group"
                              onClick={() => handleTaskClick(task)}
                              onTouchStart={(e) =>
                                handleTaskTouchStart(task.id, e)
                              }
                              onTouchEnd={(e) => handleTaskTouchEnd(task, e)}
                              style={{
                                top: `${topPct}%`,
                                height: isMobile ? taskHeight : `${heightPct}%`,
                                opacity: isBeingDragged ? 0.3 : 1,
                              }}
                            >
                              <DraggableTask
                                task={task}
                                isScheduled
                                compactMobile={isMobile}
                              />
                            </div>
                          );
                        })}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <DragOverlay>
        {activeTask ? <DraggableTask task={activeTask} isOverlay /> : null}
        {!activeTask && activeCalendarItem ? (
          <DraggableCalendarItem item={activeCalendarItem} isOverlay />
        ) : null}
      </DragOverlay>

      {overlapError && (
        <div
          role="alert"
          className="fixed bottom-[calc(env(safe-area-inset-bottom)+6.5rem)] left-1/2 z-50 w-[min(92vw,28rem)] -translate-x-1/2 rounded-2xl border border-red-200 bg-red-50/95 px-4 py-3 text-sm font-medium text-red-700 shadow-xl backdrop-blur-md"
        >
          {overlapError}
        </div>
      )}

      {editingTask && (
        <TaskEditorModal
          task={editingTask}
          overlapError={overlapError}
          onClose={closeTaskEditor}
          onUpdate={updateEditingTask}
          onDelete={deleteEditingTask}
          onToggleComplete={(taskId, completed) => {
            toggleTask(taskId);
            if (completed) {
              closeTaskEditor();
            }
          }}
        />
      )}

      {editingCalendarItem && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-[60] flex items-end md:items-center justify-center p-0 md:p-4">
          <div className="bg-white rounded-t-3xl md:rounded-3xl w-full md:max-w-lg overflow-hidden shadow-2xl animate-in fade-in zoom-in-95 duration-200 flex flex-col max-h-[92vh]">
            <div className="px-4 md:px-6 py-4 border-b border-apple-gray-200 flex justify-between items-center bg-apple-gray-50 shrink-0">
              <h2 className="text-lg md:text-xl font-bold">
                Modifier l'élément
              </h2>
              <button
                onClick={closeCalendarItemEditor}
                className="p-2 text-apple-gray-500 hover:text-black rounded-full hover:bg-apple-gray-200 transition-colors"
                type="button"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 pb-[calc(env(safe-area-inset-bottom)+5.75rem)] md:p-6 overflow-y-auto w-full hide-scrollbar">
              <div className="space-y-5">
                <div className="flex items-center justify-between gap-3 rounded-2xl border border-apple-gray-200 bg-apple-gray-50 px-4 py-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold uppercase tracking-wider text-apple-gray-500">
                        Source
                      </p>
                      <p className="text-sm font-medium text-black capitalize">
                        {editingCalendarItem.source}
                      </p>
                    </div>
                  </div>
                  {editingCalendarItem.source === "manual" && (
                    <button
                      type="button"
                      onClick={() => deleteCalendarItem(editingCalendarItem.id)}
                      className="text-red-500 hover:text-red-600 font-semibold px-3 py-2 rounded-lg hover:bg-red-50 transition-colors"
                    >
                      Supprimer
                    </button>
                  )}
                </div>

                <div>
                  <label className="block text-xs font-semibold text-apple-gray-500 uppercase tracking-wider mb-2">
                    Titre
                  </label>
                  <input
                    type="text"
                    disabled
                    value={editingCalendarItem.title}
                    className="w-full px-4 py-3 rounded-xl border border-apple-gray-200 shadow-sm bg-apple-gray-50 text-apple-gray-500 text-lg font-medium"
                  />
                  {editingCalendarItem.source !== "manual" && (
                    <p className="text-xs text-apple-gray-400 mt-2">
                      Cet élément provient d'une autre application (ex: Repas,
                      Fitness) et doit être édité depuis là-bas.
                    </p>
                  )}
                </div>
              </div>
            </div>

            <div className="px-4 pt-4 pb-[calc(env(safe-area-inset-bottom)+6.5rem)] md:pb-6 md:p-6 border-t border-apple-gray-200 bg-apple-gray-50 shrink-0 flex justify-end gap-3">
              <button
                type="button"
                onClick={closeCalendarItemEditor}
                className="bg-apple-blue text-white font-semibold px-6 py-2 rounded-xl hover:bg-blue-600 transition-colors shadow-sm"
              >
                Terminé
              </button>
            </div>
          </div>
        </div>
      )}
    </DndContext>
  );
}
