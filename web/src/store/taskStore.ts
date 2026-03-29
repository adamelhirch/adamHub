import { create } from 'zustand';
import api from '../lib/api';
import { format, parseISO } from 'date-fns';

export type SubTask = { id: string; title: string; completed: boolean };

export type TaskItem = { 
  id: string; 
  title: string; 
  completed: boolean; 
  tags: string[];
  duration: number; // in minutes
  description?: string;
  subtasks?: SubTask[];
  slotId?: string | null; // Used for Calendar positioning (yyyy-MM-dd-HH:mm)
  color: string; // Used for UI
};

interface TaskStore {
  tasks: TaskItem[];
  isLoading: boolean;
  error: string | null;
  fetchTasks: () => Promise<void>;
  addTask: (task: Omit<TaskItem, 'id' | 'color' | 'completed'>) => Promise<void>;
  updateTask: (id: string, updates: Partial<TaskItem>) => Promise<void>;
  deleteTask: (id: string) => Promise<void>;
  toggleTask: (id: string) => Promise<void>;
}

const getRandomColor = () => {
  const colors = [
    'bg-red-50 text-red-700 border-red-200',
    'bg-blue-50 text-blue-700 border-blue-200',
    'bg-green-50 text-green-700 border-green-200',
    'bg-purple-50 text-purple-700 border-purple-200',
    'bg-orange-50 text-orange-700 border-orange-200',
    'bg-pink-50 text-pink-700 border-pink-200',
  ];
  return colors[Math.floor(Math.random() * colors.length)];
};

// Helper: Frontend to Backend
function mapToBackendTask(t: Partial<TaskItem>) {
  const payload: any = {};
  if (t.title !== undefined) payload.title = t.title;
  if (t.duration !== undefined) payload.estimated_minutes = t.duration;
  if (t.tags !== undefined) payload.tags = t.tags;
  
  // Mapping slotId (yyyy-MM-dd-HH:mm) to due_at
  if (t.slotId !== undefined) {
    if (t.slotId) {
       // Using a naive parse, assuming local timezone for now
       try {
         const [year, month, day, hm] = t.slotId.split('-');
         payload.due_at = new Date(`${year}-${month}-${day}T${hm}:00`).toISOString();
       } catch (e) {
         console.warn("Invalid slotId format", t.slotId);
       }
    } else {
      payload.due_at = null;
    }
  }

  // description + subtasks are stored as a JSON string in description to keep it simple
  if (t.description !== undefined || t.subtasks !== undefined) {
      payload.description = JSON.stringify({
          text: t.description || "",
          subtasks: t.subtasks || []
      });
  }

  // Status mapping
  if (t.completed !== undefined) {
    payload.status = t.completed ? "done" : "todo";
  }

  return payload;
}

// Helper: Backend to Frontend
function mapToFrontendTask(b: any): TaskItem {
   let descriptionText = "";
   let subtasks: SubTask[] = [];

   if (b.description) {
      try {
        const parsed = JSON.parse(b.description);
        descriptionText = parsed.text || "";
        subtasks = parsed.subtasks || [];
      } catch (e) {
        descriptionText = b.description;
      }
   }

   let slotId = null;
   if (b.due_at) {
      // Format to yyyy-MM-dd-HH:mm
      try {
        const d = parseISO(b.due_at);
        slotId = format(d, 'yyyy-MM-dd-HH:mm');
      } catch (e) {}
   }

   return {
     id: String(b.id),
     title: b.title,
     completed: b.status === "done",
     tags: b.tags || [],
     duration: b.estimated_minutes || 30,
     description: descriptionText,
     subtasks: subtasks,
     slotId: slotId,
     color: getRandomColor(), // Assign random color on load for now
   };
}

export const useTaskStore = create<TaskStore>((set, get) => ({
  tasks: [],
  isLoading: false,
  error: null,

  fetchTasks: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.get('/tasks');
      const frontendTasks = response.data.map(mapToFrontendTask);
      set({ tasks: frontendTasks, isLoading: false });
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
      console.error("Failed to fetch tasks", error);
    }
  },

  addTask: async (task) => {
    try {
      const payload = mapToBackendTask(task);
      const response = await api.post('/tasks', payload);
      const newTask = mapToFrontendTask(response.data);
      
      set((state) => ({
        tasks: [...state.tasks, newTask]
      }));
    } catch (error) {
      console.error("Failed to add task", error);
    }
  },

  updateTask: async (id, updates) => {
    // Optimistic UI Update
    set((state) => ({
      tasks: state.tasks.map(t => t.id === id ? { ...t, ...updates } : t)
    }));

    try {
      const payload = mapToBackendTask(updates);
      await api.patch(`/tasks/${id}`, payload);
    } catch (error) {
      console.error("Failed to update task", error);
      // Revert optimistic update (could add logic here if needed)
      get().fetchTasks(); 
    }
  },

  toggleTask: async (id) => {
     const task = get().tasks.find(t => t.id === id);
     if (!task) return;

     const newStatus = !task.completed;
     
     // Optimistic
     set((state) => ({
        tasks: state.tasks.map(t => t.id === id ? { ...t, completed: newStatus } : t)
     }));

     try {
       if (newStatus) {
         await api.post(`/tasks/${id}/complete`);
       } else {
         await api.patch(`/tasks/${id}`, { status: "todo" });
       }
     } catch (error) {
       console.error("Failed to toggle task", error);
       get().fetchTasks(); 
     }
  },

  deleteTask: async (id) => {
    // Optimistic Delete
    set((state) => ({
      tasks: state.tasks.filter(t => t.id !== id)
    }));

    try {
      await api.delete(`/tasks/${id}`);
    } catch (error) {
      console.error("Failed to delete task", error);
      get().fetchTasks(); 
    }
  }
}));
