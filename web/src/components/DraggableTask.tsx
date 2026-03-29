import { useDraggable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import type { Task } from '../pages/CalendarPage';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface Props {
  task: Task;
  isOverlay?: boolean;
  isScheduled?: boolean;
}

export default function DraggableTask({ task, isOverlay, isScheduled }: Props) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: task.id,
    data: task,
  });

  const style = {
    transform: CSS.Translate.toString(transform),
  };

  const baseClasses = "flex flex-col rounded-lg border shadow-xs cursor-grab active:cursor-grabbing transition-all ring-1 ring-black/5 hover:shadow-md group relative overflow-hidden backdrop-blur-md";
  const draggingClasses = isDragging ? "opacity-40 scale-95" : "opacity-100";
  const overlayClasses = isOverlay ? "rotate-2 shadow-2xl cursor-grabbing z-50 opacity-95 scale-105" : "";
  const scheduledClasses = isScheduled ? "h-full w-full absolute" : "w-full mb-2";

  // Parse slotId to get the start time (e.g. "2024-03-11-09:15" -> "09:15")
  const startTimeMatch = task.slotId?.match(/-(\d{2}:\d{2})$/);
  const startTime = startTimeMatch ? startTimeMatch[1] : null;

  // Responsive styling based on duration
  const isTiny = isScheduled && task.duration <= 15;
  const isSmall = isScheduled && task.duration > 15 && task.duration <= 30;

  // Dynamic padding and text sizing
  const paddingClass = isTiny ? "p-0.5 px-1 sm:p-1" : isSmall ? "p-1.5" : "p-2";
  const titleTextClass = isTiny ? "text-[9px] leading-none" : isSmall ? "text-[10px] leading-tight" : "text-xs leading-tight";

  const showDurationInline = isScheduled && task.duration <= 45;

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className={twMerge(clsx(baseClasses, paddingClass, task.color, draggingClasses, overlayClasses, scheduledClasses))}
    >
      <div className="flex flex-col w-full h-full relative z-10 overflow-hidden">
        <div className="flex items-start justify-between gap-1 w-full flex-wrap sm:flex-nowrap">
          <span className={twMerge("font-semibold tracking-tight truncate", titleTextClass)} title={task.title}>
            {task.title}
          </span>
          {showDurationInline && (
            <span className="font-normal opacity-75 shrink-0 text-[8px] sm:text-[9px] leading-none mt-0.5">
              {task.duration}m
            </span>
          )}
        </div>
        
        {/* Show duration and time if enough height, else hide */}
        {(!isScheduled || task.duration > 45) && (
          <div className="mt-0.5 flex items-center text-[9px] sm:text-[10px] font-semibold opacity-75 truncate shrink-0">
            {startTime && <span className="truncate">{startTime} &nbsp;</span>}
            <span className="shrink-0">{task.duration}m</span>
          </div>
        )}
      </div>

      {/* Glossy gradient reflection */}
      <div className="absolute inset-0 bg-gradient-to-b from-white/20 to-transparent opacity-50 z-0 pointer-events-none" />
    </div>
  );
}
