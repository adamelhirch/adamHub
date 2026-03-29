import {
  CheckCircle2,
  Circle,
  Clock,
  AlignLeft,
  CheckSquare,
  X,
  Plus,
  Trash2,
  Calendar as CalendarIcon,
  Search,
  Filter,
} from "lucide-react";
import { useState, useEffect } from "react";
import { format } from "date-fns";
import { useTaskStore } from "../store/taskStore";
import type { TaskItem } from "../store/taskStore";

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
      const newTag = inputValue.trim().replace(/^,+|,+$/g, ""); // Remove trailing/leading commas
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
            onClick={() => removeTag(tag)}
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

export default function TasksPage() {
  const {
    tasks,
    addTask: storeAddTask,
    updateTask,
    deleteTask: storeDeleteTask,
    fetchTasks,
    toggleTask: storeToggleTask,
  } = useTaskStore();

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  const [showComposer, setShowComposer] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskDuration, setNewTaskDuration] = useState("30");
  const [newTaskTags, setNewTaskTags] = useState<string[]>(["Personal"]);
  const [selectedTask, setSelectedTask] = useState<TaskItem | null>(null);
  const [overlapError, setOverlapError] = useState<string | null>(null);

  // Filter States
  const [filterTitle, setFilterTitle] = useState("");
  const [filterTags, setFilterTags] = useState<string[]>([]);
  const [filterDate, setFilterDate] = useState("");
  const [filterDuration, setFilterDuration] = useState("");

  const filteredTasks = tasks.filter((task) => {
    if (
      filterTitle &&
      !task.title.toLowerCase().includes(filterTitle.toLowerCase())
    )
      return false;
    if (
      filterTags.length > 0 &&
      !filterTags.some((tag) =>
        task.tags?.some((t) => t.toLowerCase() === tag.toLowerCase()),
      )
    )
      return false;
    if (filterDate && !task.slotId?.startsWith(filterDate)) return false;
    if (filterDuration && task.duration !== parseInt(filterDuration))
      return false;
    return true;
  });

  // State for adding a subtask inside the modal
  const [newSubtaskTitle, setNewSubtaskTitle] = useState("");

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
      )
        return false;
      const oStart = timeToMinutes(t.slotId.substring(11, 16));
      const oEnd = oStart + t.duration;
      return Math.max(tStart, oStart) < Math.min(tEnd, oEnd);
    });
  };

  const toggleTask = (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    storeToggleTask(id);
  };

  const addTask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim()) return;

    storeAddTask({
      title: newTaskTitle,
      tags: newTaskTags.length > 0 ? newTaskTags : ["Personal"],
      duration: parseInt(newTaskDuration) || 30,
    });
    setNewTaskTitle("");
    setNewTaskTags(["Personal"]);
  };

  const updateSelectedTask = (updates: Partial<TaskItem>) => {
    if (!selectedTask) return;

    const newSlotId =
      updates.slotId !== undefined ? updates.slotId : selectedTask.slotId;
    const newDuration =
      updates.duration !== undefined ? updates.duration : selectedTask.duration;

    if (newSlotId) {
      if (checkOverlap(newSlotId, newDuration, selectedTask.id)) {
        setOverlapError("This time slot overlaps with another scheduled task.");
        setTimeout(() => setOverlapError(null), 3000);
        return;
      }
    }

    const updatedTask = { ...selectedTask, ...updates };
    setSelectedTask(updatedTask);
    updateTask(selectedTask.id, updates);
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
      subtasks: selectedTask.subtasks.map((s) =>
        s.id === subId ? { ...s, completed: !s.completed } : s,
      ),
    });
  };

  const deleteSubtask = (subId: string) => {
    if (!selectedTask || !selectedTask.subtasks) return;
    updateSelectedTask({
      subtasks: selectedTask.subtasks.filter((s) => s.id !== subId),
    });
  };

  const deleteTask = (taskId: string) => {
    storeDeleteTask(taskId);
    if (selectedTask?.id === taskId) setSelectedTask(null);
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-transparent overflow-hidden">
      {/* Header */}
      <div className="sticky top-0 z-10 border-b border-white/60 bg-white/75 px-4 py-4 shadow-[0_8px_30px_rgba(15,23,42,0.06)] backdrop-blur-xl md:px-8 md:py-5">
        <div className="max-w-5xl mx-auto flex items-end justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-apple-gray-500">
              Organisation
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-black md:text-3xl">
              Tasks
            </h1>
            <p className="mt-1 text-sm text-apple-gray-500">
              Garde les tâches visibles, rapides à éditer et simples à déplacer
              sur mobile.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowComposer((current) => !current)}
            className="inline-flex items-center gap-2 rounded-2xl bg-apple-blue px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-600"
          >
            <Plus className="w-4 h-4" />
            {showComposer ? "Fermer" : "Nouveau"}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 pb-[calc(env(safe-area-inset-bottom)+5.75rem)] md:px-8 md:py-6 flex flex-col items-center">
        <div className="w-full max-w-5xl space-y-6">
          {/* Add Task Form */}
          {showComposer && (
            <form
              onSubmit={addTask}
              className="relative grid gap-3 rounded-[28px] border border-white/60 bg-white/80 p-4 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl md:grid-cols-[minmax(0,1fr)_320px_112px_auto] md:items-center md:p-5"
            >
              <div className="relative min-w-0">
                <input
                  type="text"
                  value={newTaskTitle}
                  onChange={(e) => setNewTaskTitle(e.target.value)}
                  placeholder="Add a new task to your inbox..."
                  className="w-full rounded-2xl border border-apple-gray-200 bg-white/90 px-4 py-4 text-base transition-all focus:outline-none focus:ring-2 focus:ring-apple-blue/40 md:text-lg"
                />
              </div>
              <div className="relative min-w-0">
                <TagInput
                  tags={newTaskTags}
                  setTags={setNewTaskTags}
                  placeholder="Add tags..."
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
                className="rounded-2xl bg-apple-blue px-6 py-4 font-semibold text-white transition-colors hover:bg-blue-600 whitespace-nowrap"
              >
                Add Task
              </button>
            </form>
          )}

          {/* Filters */}
          <div className="rounded-[28px] border border-white/60 bg-white/75 p-4 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl flex flex-col gap-4 md:p-5">
            <div className="flex items-center gap-2 text-apple-gray-500 font-medium text-sm px-1">
              <Filter className="w-4 h-4" />
              <span>Filter Tasks</span>
            </div>
            <div className="flex flex-wrap gap-3">
              <div className="relative flex-1 min-w-[150px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-apple-gray-400" />
                <input
                  type="text"
                  placeholder="Filter by title..."
                  value={filterTitle}
                  onChange={(e) => setFilterTitle(e.target.value)}
                  className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-apple-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                />
              </div>
              <div className="w-[200px] relative shrink-0">
                <TagInput
                  tags={filterTags}
                  setTags={setFilterTags}
                  placeholder="Filter by tags..."
                  className="py-1.5"
                />
              </div>
              <div className="w-[140px] relative shrink-0">
                <input
                  type="date"
                  value={filterDate}
                  onChange={(e) => setFilterDate(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50 bg-white"
                />
              </div>
              <div className="w-[100px] relative shrink-0">
                <input
                  type="number"
                  placeholder="Duration"
                  value={filterDuration}
                  onChange={(e) => setFilterDuration(e.target.value)}
                  className="w-full pl-3 pr-7 py-2.5 rounded-xl border border-apple-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50"
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-apple-gray-400 text-xs pointer-events-none">
                  m
                </span>
              </div>
              {(filterTitle ||
                filterTags.length > 0 ||
                filterDate ||
                filterDuration) && (
                <button
                  onClick={() => {
                    setFilterTitle("");
                    setFilterTags([]);
                    setFilterDate("");
                    setFilterDuration("");
                  }}
                  className="px-3 py-2.5 text-sm font-medium text-apple-gray-500 hover:text-black hover:bg-apple-gray-100 rounded-xl transition-colors"
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          {/* Task List */}
          <div className="overflow-hidden rounded-[28px] border border-white/60 bg-white/75 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl flex flex-col divide-y divide-apple-gray-100">
            {filteredTasks.length === 0 ? (
              <div className="py-12 text-center text-apple-gray-500">
                No tasks found matching your filters.
              </div>
            ) : (
              filteredTasks.map((task) => (
                <div
                  key={task.id}
                  className={`flex items-center px-6 py-4 transition-colors hover:bg-apple-gray-50 cursor-pointer ${task.completed ? "opacity-60" : ""}`}
                  onClick={() => setSelectedTask(task)} // Open modal on row click
                >
                  <div
                    className="mr-4 text-apple-gray-400 hover:text-apple-blue transition-colors cursor-pointer"
                    onClick={(e) => toggleTask(task.id, e)}
                  >
                    {task.completed ? (
                      <CheckCircle2 className="w-6 h-6 text-apple-blue" />
                    ) : (
                      <Circle className="w-6 h-6" />
                    )}
                  </div>
                  <div className="flex-1 flex flex-col">
                    <span
                      className={`text-lg font-medium transition-all ${task.completed ? "line-through text-apple-gray-400" : "text-black"}`}
                    >
                      {task.title}
                    </span>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      {task.tags &&
                        task.tags.map((tag) => (
                          <span
                            key={tag}
                            className="text-xs font-semibold text-apple-blue uppercase tracking-wider bg-apple-blue/10 px-2 py-0.5 rounded-md"
                          >
                            {tag}
                          </span>
                        ))}
                      {task.slotId && (
                        <span className="text-xs font-semibold text-apple-gray-600 bg-apple-gray-100 px-2 py-0.5 rounded-md flex items-center">
                          <CalendarIcon className="w-3.5 h-3.5 mr-1" />
                          {task.slotId.substring(11, 16)}
                        </span>
                      )}
                      <div className="flex items-center text-xs text-apple-gray-500 font-medium">
                        <Clock className="w-3.5 h-3.5 mr-1" />
                        {task.duration}m
                      </div>
                      {task.description && (
                        <div
                          className="flex items-center text-xs text-apple-gray-400"
                          title="Has description"
                        >
                          <AlignLeft className="w-3.5 h-3.5" />
                        </div>
                      )}
                      {task.subtasks && task.subtasks.length > 0 && (
                        <div
                          className="flex items-center text-xs text-apple-gray-400"
                          title={`${task.subtasks.filter((s) => s.completed).length}/${task.subtasks.length} subtasks completed`}
                        >
                          <CheckSquare className="w-3.5 h-3.5 mr-1" />
                          {task.subtasks.filter((s) => s.completed).length}/
                          {task.subtasks.length}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Task Details Modal */}
      {selectedTask && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-[60] flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl w-full max-w-lg overflow-hidden shadow-2xl animate-in fade-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">
            <div className="px-6 py-4 border-b border-apple-gray-200 flex justify-between items-center bg-apple-gray-50 shrink-0">
              <h2 className="text-xl font-bold">Edit Task</h2>
              <button
                onClick={() => {
                  setSelectedTask(null);
                  setOverlapError(null);
                }}
                className="p-2 text-apple-gray-500 hover:text-black rounded-full hover:bg-apple-gray-200 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 pb-[calc(env(safe-area-inset-bottom)+6.5rem)] md:pb-6 overflow-y-auto w-full hide-scrollbar">
              <div className="space-y-6">
                {overlapError && (
                  <div className="bg-red-50 text-red-600 text-sm p-3 rounded-xl border border-red-100 flex items-center">
                    <span className="font-medium">{overlapError}</span>
                  </div>
                )}

                {/* Title & Category & Duration */}
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-apple-gray-500 uppercase tracking-wider mb-2">
                      Title
                    </label>
                    <input
                      type="text"
                      value={selectedTask.title}
                      onChange={(e) =>
                        updateSelectedTask({ title: e.target.value })
                      }
                      className="w-full px-4 py-3 rounded-xl border border-apple-gray-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50 text-lg font-medium"
                    />
                  </div>
                  <div className="flex gap-4">
                    <div className="flex-1">
                      <label className="block text-xs font-semibold text-apple-gray-500 uppercase tracking-wider mb-2">
                        Tags
                      </label>
                      <TagInput
                        tags={selectedTask.tags || []}
                        setTags={(newTags) =>
                          updateSelectedTask({ tags: newTags })
                        }
                        placeholder="Add tags..."
                      />
                    </div>
                    <div className="w-32">
                      <label className="block text-xs font-semibold text-apple-gray-500 uppercase tracking-wider mb-2">
                        Duration
                      </label>
                      <div className="relative">
                        <input
                          type="number"
                          value={selectedTask.duration}
                          onChange={(e) =>
                            updateSelectedTask({
                              duration: parseInt(e.target.value) || 0,
                            })
                          }
                          className="w-full pl-4 pr-8 py-3 rounded-xl border border-apple-gray-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50 text-base"
                        />
                        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-apple-gray-400">
                          m
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Scheduling (Date & Time) */}
                  <div className="flex gap-4 p-4 bg-apple-gray-50 rounded-xl border border-apple-gray-100">
                    <div className="flex-1">
                      <label className="block text-xs font-semibold text-apple-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1">
                        <CalendarIcon className="w-3.5 h-3.5" /> Date
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
                          const date = e.target.value;
                          if (!date) {
                            updateSelectedTask({ slotId: null });
                            return;
                          }
                          // Keep existing hour or default to 09, and ensure :00 suffix
                          const hourStr = selectedTask.slotId
                            ? selectedTask.slotId.substring(11, 16)
                            : "09:00";
                          updateSelectedTask({ slotId: `${date}-${hourStr}` });
                        }}
                        className="w-full px-4 py-2.5 rounded-lg border border-apple-gray-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50 text-sm bg-white"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="block text-xs font-semibold text-apple-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" /> Time
                      </label>
                      <input
                        type="time"
                        value={
                          selectedTask.slotId
                            ? selectedTask.slotId.substring(11, 16)
                            : ""
                        }
                        onChange={(e) => {
                          const time = e.target.value;
                          if (!time) {
                            updateSelectedTask({ slotId: null });
                            return;
                          }
                          // Keep existing date or default to today
                          const date = selectedTask.slotId
                            ? selectedTask.slotId.substring(0, 10)
                            : format(new Date(), "yyyy-MM-dd");
                          updateSelectedTask({ slotId: `${date}-${time}` });
                        }}
                        className="w-full px-4 py-2.5 rounded-lg border border-apple-gray-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50 text-sm bg-white"
                      />
                    </div>
                  </div>
                </div>

                {/* Description */}
                <div>
                  <label className="block text-xs font-semibold text-apple-gray-500 uppercase tracking-wider mb-2">
                    Description
                  </label>
                  <textarea
                    value={selectedTask.description || ""}
                    onChange={(e) =>
                      updateSelectedTask({ description: e.target.value })
                    }
                    placeholder="Add notes or details..."
                    rows={3}
                    className="w-full px-4 py-3 rounded-xl border border-apple-gray-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50 text-base resize-none"
                  />
                </div>

                {/* Subtasks */}
                <div>
                  <label className="block text-xs font-semibold text-apple-gray-500 uppercase tracking-wider mb-2">
                    Checklist
                  </label>
                  <div className="space-y-3">
                    {selectedTask.subtasks &&
                      selectedTask.subtasks.map((sub) => (
                        <div
                          key={sub.id}
                          className="flex items-center gap-3 group"
                        >
                          <button
                            onClick={() => toggleSubtask(sub.id)}
                            className="text-apple-gray-400 hover:text-apple-blue transition-colors"
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
                            onClick={() => deleteSubtask(sub.id)}
                            className="opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-600 transition-opacity p-1"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      ))}

                    {/* Add Subtask Form */}
                    <form onSubmit={addSubtask} className="flex gap-2">
                      <input
                        type="text"
                        value={newSubtaskTitle}
                        onChange={(e) => setNewSubtaskTitle(e.target.value)}
                        placeholder="Add subtask..."
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

            <div className="p-6 border-t border-apple-gray-200 bg-apple-gray-50 shrink-0 flex justify-between">
              <button
                onClick={() => deleteTask(selectedTask.id)}
                className="text-red-500 hover:text-red-600 font-semibold px-4 py-2 hover:bg-red-50 rounded-lg transition-colors"
              >
                Delete Task
              </button>
              <button
                onClick={() => setSelectedTask(null)}
                className="bg-apple-blue text-white font-semibold px-6 py-2 rounded-xl hover:bg-blue-600 transition-colors shadow-sm"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
